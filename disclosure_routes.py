"""
infosd - 공시 작업 라우팅 (4+5단계)
"""
import uuid
import json
import os
import io
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, send_from_directory, abort, session, send_file)
from db_config import get_db

bp_disclosure = Blueprint('disclosure', __name__, url_prefix='/disclosure')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'disclosure')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                      'jpg', 'jpeg', 'png', 'gif', 'zip', 'txt', 'hwp', 'hwpx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

CATEGORY_NAMES = {1: '정보보호 투자', 2: '정보보호 인력', 3: '정보보호 인증', 4: '정보보호 활동'}
YES_VALUES = ('YES', 'Y', 'TRUE', '1', '예', '네')

# ============================================================================
# Snowball Link11 - QID 상수 및 검증 로직 이식 (v0.10)
# ============================================================================
class QID:
    """정보보호공시 질문 ID 상수 (Snowball 100% 동기화)"""
    # 카테고리 1: 정보보호 투자
    INV_HAS_INVESTMENT = "Q1"      # 정보보호 투자 발생 여부
    INV_IT_AMOUNT = "Q2"           # 정보기술부문 투자액 A
    INV_SEC_GROUP = "Q3"           # 정보보호부문 투자액 B Group
    INV_SEC_DEPRECIATION = "Q4"    # 감가상각비
    INV_SEC_SERVICE = "Q5"         # 서비스비용
    INV_SEC_LABOR = "Q6"           # 인건비
    INV_HAS_PLAN = "Q7"            # 향후 투자 계획 여부
    INV_PLAN_AMOUNT = "Q8"         # 예정 투자액
    INV_MAIN_ITEMS = "Q27"         # 주요 투자 항목 (신규)

    # 카테고리 2: 정보보호 인력
    PER_HAS_TEAM = "Q9"            # 전담 부서/인력 여부
    PER_TOTAL_EMPLOYEES = "Q10"    # 총 임직원 수
    PER_INTERNAL = "Q11"           # 내부 전담인력 수
    PER_EXTERNAL = "Q12"           # 외주 전담인력 수
    PER_HAS_CISO = "Q13"           # CISO/CPO 지정 여부
    PER_CISO_DETAIL = "Q14"        # CISO/CPO 상세 현황
    PER_IT_EMPLOYEES = "Q28"       # 정보기술인력(C) (신규)
    PER_CISO_ACTIVITY = "Q29"      # CISO 활동내역 (신규)

    # 카테고리 3: 정보보호 인증
    CERT_HAS_CERT = "Q15"          # 인증 보유 여부
    CERT_DETAIL = "Q16"            # 인증 보유 현황

    # 카테고리 4: 정보보호 활동
    ACT_HAS_ACTIVITY = "Q17"       # 이용자 보호 활동 여부
    ACT_IT_ASSET = "Q18"           # IT 자산 관리
    ACT_TRAINING = "Q19"           # 교육/훈련 실적
    ACT_PROCEDURE = "Q20"          # 지침/절차서
    ACT_VULN_ASSESS = "Q21"        # 취약점 분석
    ACT_ZERO_TRUST = "Q22"         # 제로트러스트
    ACT_SBOM = "Q23"               # SBOM
    ACT_CTAS = "Q24"               # C-TAS
    ACT_DRILL = "Q25"              # 모의훈련
    ACT_INSURANCE = "Q26"          # 배상책임보험


def _generate_uuid():
    return str(uuid.uuid4())


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _is_yes(value):
    return str(value).strip().upper() in YES_VALUES


def _is_question_active(q, questions_dict, answers):
    """질문이 현재 답변 상태에 따라 활성화되어야 하는지 확인 (재귀적)"""
    if q['level'] == 1:
        return True
    parent_id = q.get('parent_question_id')
    if not parent_id:
        return True
    parent_q = questions_dict.get(parent_id)
    if not parent_q:
        return False
    if not _is_question_active(parent_q, questions_dict, answers):
        return False
    parent_answer = answers.get(parent_id)
    if parent_answer is None:
        return False
    if parent_q['type'] == 'group':
        return True
    if parent_q['type'] == 'yes_no':
        return _is_yes(parent_answer)
    return False


def _is_question_skipped(q, questions_dict, answers):
    """부모가 NO로 명시 답변된 경우 True (자동 완료 처리)"""
    if q['level'] == 1:
        return False
    parent_id = q.get('parent_question_id')
    if not parent_id:
        return False
    parent_q = questions_dict.get(parent_id)
    if not parent_q:
        return False
    parent_answer = answers.get(parent_id)
    if parent_q['type'] == 'group':
        return _is_question_skipped(parent_q, questions_dict, answers)
    if parent_q['type'] == 'yes_no':
        if parent_answer is None:
            return False
        if not _is_yes(str(parent_answer)):
            return True
        return _is_question_skipped(parent_q, questions_dict, answers)
    return False


def _get_all_dependent_ids(conn, question_ids):
    """재귀적으로 모든 하위 질문 ID 수집"""
    all_ids = list(question_ids)
    for q_id in question_ids:
        row = conn.execute(
            'SELECT dependent_question_ids FROM ipd_questions WHERE id = ?', (q_id,)
        ).fetchone()
        if row and row['dependent_question_ids']:
            try:
                child_ids = json.loads(row['dependent_question_ids'])
                if child_ids:
                    all_ids.extend(_get_all_dependent_ids(conn, child_ids))
            except (json.JSONDecodeError, TypeError):
                pass
    return all_ids


def _update_session_progress(conn, company_id, year):
    """세션 진행률 자동 업데이트"""
    try:
        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM ipd_questions ORDER BY category_id, sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        total, answered = 0, 0
        for q in all_questions:
            if q['type'] == 'group':
                continue
            total += 1
            if _is_question_active(q, questions_dict, answers):
                if q['id'] in answers and answers[q['id']] not in (None, ''):
                    answered += 1
            elif _is_question_skipped(q, questions_dict, answers):
                answered += 1

        rate = round((answered / total) * 100) if total > 0 else 0
        status = 'submitted' if rate == 100 else ('in_progress' if answered > 0 else 'draft')

        existing = conn.execute(
            'SELECT id FROM ipd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()

        if existing:
            conn.execute('''
                UPDATE ipd_sessions
                SET total_questions=?, answered_questions=?, completion_rate=?,
                    status=CASE WHEN status='submitted' THEN 'submitted' ELSE ? END,
                    updated_at=CURRENT_TIMESTAMP
                WHERE company_id=? AND year=?
            ''', (total, answered, rate, status, company_id, year))
        else:
            conn.execute('''
                INSERT INTO ipd_sessions
                (id, company_id, year, status, total_questions, answered_questions, completion_rate)
                VALUES (?,?,?,?,?,?,?)
            ''', (_generate_uuid(), company_id, year, status, total, answered, rate))
        conn.commit()
    except Exception as e:
        print(f"진행률 업데이트 오류: {e}")


def _mark_dependents_na(conn, question_id, company_id, year):
    """상위 질문 NO 시 하위 질문을 N/A로 표시"""
    row = conn.execute(
        'SELECT dependent_question_ids FROM ipd_questions WHERE id=?', (question_id,)
    ).fetchone()
    if not row or not row['dependent_question_ids']:
        return
    try:
        dep_ids = json.loads(row['dependent_question_ids'])
    except (json.JSONDecodeError, TypeError):
        return
    all_dep = _get_all_dependent_ids(conn, dep_ids)
    for dep_id in all_dep:
        existing = conn.execute(
            'SELECT id FROM ipd_answers WHERE question_id=? AND company_id=? AND year=?',
            (dep_id, company_id, year)
        ).fetchone()
        if existing:
            conn.execute('''
                UPDATE ipd_answers SET value='N/A', status='skipped',
                updated_at=CURRENT_TIMESTAMP, deleted_at=NULL WHERE id=?
            ''', (existing['id'],))
        else:
            conn.execute('''
                INSERT INTO ipd_answers (id, question_id, company_id, year, value, status)
                VALUES (?,?,?,?,'N/A','skipped')
            ''', (_generate_uuid(), dep_id, company_id, year))


def _clear_na_from_dependents(conn, question_id, company_id, year):
    """상위 질문 YES 복귀 시 N/A 답변 삭제"""
    row = conn.execute(
        'SELECT dependent_question_ids FROM ipd_questions WHERE id=?', (question_id,)
    ).fetchone()
    if not row or not row['dependent_question_ids']:
        return
    try:
        dep_ids = json.loads(row['dependent_question_ids'])
    except (json.JSONDecodeError, TypeError):
        return
    all_dep = _get_all_dependent_ids(conn, dep_ids)
    for dep_id in all_dep:
        conn.execute('''
            DELETE FROM ipd_answers
            WHERE question_id=? AND company_id=? AND year=? AND value='N/A' AND status='skipped'
        ''', (dep_id, company_id, year))


def _get_company_or_404(conn, company_id):
    company = conn.execute(
        'SELECT * FROM ipd_companies WHERE id=?', (company_id,)
    ).fetchone()
    if not company:
        abort(404)
    return company


def _get_target_or_404(conn, company_id, year):
    target = conn.execute(
        'SELECT * FROM ipd_targets WHERE company_id=? AND year=?', (company_id, year)
    ).fetchone()
    if not target:
        abort(404)
    return target


# ============================================================
# 공시 대시보드
# ============================================================

@bp_disclosure.route('/<company_id>/<int:year>')
def dashboard(company_id, year):
    """공시 작업 대시보드 — 카테고리별 진행률"""
    with get_db() as conn:
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM ipd_questions ORDER BY category_id, sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        categories = {}
        for q in all_questions:
            cat_id = q['category_id']
            cat_name = q['category']
            if cat_id not in categories:
                categories[cat_id] = {'id': cat_id, 'name': cat_name, 'total': 0, 'completed': 0}
            if q['type'] == 'group':
                continue
            categories[cat_id]['total'] += 1
            if _is_question_active(q, questions_dict, answers):
                if q['id'] in answers and answers[q['id']] not in (None, ''):
                    categories[cat_id]['completed'] += 1
            elif _is_question_skipped(q, questions_dict, answers):
                categories[cat_id]['completed'] += 1

        cat_list = []
        total_q, total_done = 0, 0
        for cat_id in sorted(categories):
            c = categories[cat_id]
            c['rate'] = int((c['completed'] / c['total']) * 100) if c['total'] > 0 else 0
            cat_list.append(c)
            total_q += c['total']
            total_done += c['completed']

        overall = int((total_done / total_q) * 100) if total_q > 0 else 0

        # 투자 및 인력 비율 계산
        ratios = _calculate_ratios(conn, company_id, year, answers)
        
        # 보유 인증 건수 계산 (Category 3 질문 중 YES인 항목 수 또는 증빙 수)
        # 여기서는 단순하게 Q16이 YES이거나 관련 항목에 답변이 있는 경우 등으로 계산할 수 있으나,
        # 일단 Category 3 (ID: 3)에 해당하는 질문들 중 답변이 있는 항목 수를 건수로 표시
        cert_count = 0
        cat3_questions = [q['id'] for q in all_questions if q['category_id'] == 3 and q['type'] != 'group']
        for qid in cat3_questions:
            if qid in answers and answers[qid] not in (None, '', 'NO', 'N/A'):
                cert_count += 1

    return render_template('disclosure/dashboard.html',
                           company=dict(company), year=year,
                           categories=cat_list, overall=overall, session=session,
                           ratios=ratios, cert_count=cert_count)


# ============================================================
# 공시 작업 화면
# ============================================================

@bp_disclosure.route('/<company_id>/<int:year>/work')
def work(company_id, year):
    """질문-답변 입력 화면"""
    category_id = request.args.get('category', type=int, default=1)
    with get_db() as conn:
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        questions = [dict(r) for r in conn.execute(
            'SELECT * FROM ipd_questions WHERE category_id=? ORDER BY sort_order',
            (category_id,)
        ).fetchall()]

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM ipd_questions ORDER BY sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers_rows = conn.execute(
            'SELECT question_id, value, id as answer_id FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()
        answers = {r['question_id']: r['value'] for r in answers_rows}
        answer_ids = {r['question_id']: r['answer_id'] for r in answers_rows}

        evidence_rows = conn.execute(
            'SELECT * FROM ipd_evidence WHERE company_id=? AND year=? ORDER BY uploaded_at DESC',
            (company_id, year)
        ).fetchall()
        evidence_map = {}
        for e in evidence_rows:
            qid = e['question_id']
            if qid not in evidence_map:
                evidence_map[qid] = []
            evidence_map[qid].append(dict(e))

        # options JSON 파싱
        for q in questions:
            if q.get('options'):
                try:
                    q['options_list'] = json.loads(q['options'])
                except (json.JSONDecodeError, TypeError):
                    q['options_list'] = []
            else:
                q['options_list'] = []
            q['is_active'] = _is_question_active(q, questions_dict, answers)
            q['is_skipped'] = _is_question_skipped(q, questions_dict, answers)

        # 카테고리별 진행률 계산 (사이드바용) — active/skip 로직 반영
        sidebar_categories = []
        cat_ids = sorted({q['category_id'] for q in all_questions})
        for cat_id in cat_ids:
            cat_qs = [q for q in all_questions if q['category_id'] == cat_id and q['type'] != 'group']
            cat_name = next((q['category'] for q in all_questions if q['category_id'] == cat_id), '')
            total = len(cat_qs)
            done = 0
            for q in cat_qs:
                if _is_question_active(q, questions_dict, answers):
                    if q['id'] in answers and answers[q['id']] not in (None, ''):
                        done += 1
                elif _is_question_skipped(q, questions_dict, answers):
                    done += 1
            sidebar_categories.append({
                'id': cat_id,
                'name': cat_name,
                'total': total,
                'done': done,
                'rate': int((done / total) * 100) if total > 0 else 0
            })

        current_category_name = next((c['name'] for c in sidebar_categories if c['id'] == category_id), "Unknown")
        
        # 전체 진행률 가져오기
        ipd_session = conn.execute(
            'SELECT completion_rate FROM ipd_sessions WHERE company_id=? AND year=?',
            (company_id, year)
        ).fetchone()
        overall_progress = ipd_session['completion_rate'] if ipd_session else 0
        
        current_cat_stat = next((c for c in sidebar_categories if c['id'] == category_id), None)
        current_progress = current_cat_stat['rate'] if current_cat_stat else 0

        if request.args.get('api'):
            return jsonify({
                'questions': questions,
                'answers': answers,
                'evidence': evidence_map,
                'sidebar_categories': sidebar_categories,
                'overall_progress': overall_progress
            })

    return render_template('disclosure/work.html',
                           company=dict(company), year=year,
                           questions=questions, answers=answers, answer_ids=answer_ids,
                           evidence=evidence_map, 
                           sidebar_categories=sidebar_categories,
                           current_category_id=category_id, 
                           current_category_name=current_category_name,
                           current_progress=current_progress,
                           overall_progress=overall_progress)


# ============================================================
# API — 답변 저장
# ============================================================

@bp_disclosure.route('/api/answer', methods=['POST'])
def save_answer():
    """답변 저장 (Snowball 검증 엔진 이식)"""
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        value = data.get('value')
        company_id = data.get('company_id')
        year = data.get('year')

        if not all([question_id, company_id, year]):
            return jsonify({'success': False, 'message': '필수 파라미터 누락'}), 400

        # 리스트 값 직렬화
        if isinstance(value, list):
            value = json.dumps(value, ensure_ascii=False)

        with get_db() as conn:
            # 0. 숫자 필드 음수 방지 및 콤마 제거
            numeric_fields = [
                QID.INV_IT_AMOUNT, QID.INV_SEC_GROUP, QID.INV_SEC_DEPRECIATION,
                QID.INV_SEC_SERVICE, QID.INV_SEC_LABOR, QID.INV_PLAN_AMOUNT,
                QID.PER_TOTAL_EMPLOYEES, QID.PER_IT_EMPLOYEES, QID.PER_INTERNAL, QID.PER_EXTERNAL
            ]
            if question_id in numeric_fields and value is not None:
                try:
                    num_val = float(str(value).replace(',', ''))
                    if num_val < 0:
                        return jsonify({'success': False, 'message': '음수는 입력할 수 없습니다.'}), 400
                except ValueError:
                    pass

            # 1. 인력 수 계층 검증 (총 임직원 >= IT 인력 >= 보안 인력)
            personnel_ids = [QID.PER_TOTAL_EMPLOYEES, QID.PER_IT_EMPLOYEES, QID.PER_INTERNAL, QID.PER_EXTERNAL]
            if question_id in personnel_ids:
                cursor = conn.execute('''
                    SELECT question_id, value FROM ipd_answers
                    WHERE question_id IN (?, ?, ?, ?) AND company_id = ? AND year = ? AND deleted_at IS NULL
                ''', (*personnel_ids, company_id, year))
                per_vals = {row['question_id']: row['value'] for row in cursor.fetchall()}
                per_vals[question_id] = value

                try:
                    total_emp = float(str(per_vals.get(QID.PER_TOTAL_EMPLOYEES, 0) or 0).replace(',', ''))
                    it_emp = float(str(per_vals.get(QID.PER_IT_EMPLOYEES, 0) or 0).replace(',', ''))
                    internal = float(str(per_vals.get(QID.PER_INTERNAL, 0) or 0).replace(',', ''))
                    external = float(str(per_vals.get(QID.PER_EXTERNAL, 0) or 0).replace(',', ''))
                    security_total = internal + external

                    if total_emp > 0 and it_emp > total_emp:
                        return jsonify({'success': False, 'message': f'정보기술부문 인력({int(it_emp)}명)은 총 임직원 수({int(total_emp)}명)를 초과할 수 없습니다.'}), 400
                    if it_emp > 0 and security_total > it_emp:
                        return jsonify({'success': False, 'message': f'정보보호 전담인력({int(security_total)}명)은 정보기술부문 인력({int(it_emp)}명)을 초과할 수 없습니다.'}), 400
                except ValueError:
                    pass

            # 2. 정보보호 투자액 검증 (B <= A)
            inv_b_ids = [QID.INV_SEC_DEPRECIATION, QID.INV_SEC_SERVICE, QID.INV_SEC_LABOR]
            if question_id in inv_b_ids or question_id == QID.INV_IT_AMOUNT:
                cursor = conn.execute('''
                    SELECT question_id, value FROM ipd_answers
                    WHERE question_id IN (?, ?, ?) AND company_id = ? AND year = ? AND deleted_at IS NULL
                ''', (*inv_b_ids, company_id, year))
                b_vals = {row['question_id']: row['value'] for row in cursor.fetchall()}
                b_vals[question_id] = value

                cursor = conn.execute(
                    'SELECT value FROM ipd_answers WHERE question_id=? AND company_id=? AND year=? AND deleted_at IS NULL',
                    (QID.INV_IT_AMOUNT, company_id, year)
                )
                q_a = cursor.fetchone()
                try:
                    val_a = float(str(value).replace(',', '')) if question_id == QID.INV_IT_AMOUNT \
                        else (float(str(q_a['value']).replace(',', '')) if q_a and q_a['value'] else 0)
                    if val_a > 0:
                        val_b = sum(float(str(b_vals.get(qid, 0) or 0).replace(',', '')) for qid in inv_b_ids)
                        if val_b > val_a:
                            return jsonify({'success': False, 'message': f'정보보호 투자액(B) {int(val_b):,}원이 정보기술 투자액(A) {int(val_a):,}원을 초과합니다.'}), 400
                except ValueError:
                    pass

            # 3. 답변 저장 (UPSERT)
            existing = conn.execute(
                'SELECT id FROM ipd_answers WHERE question_id=? AND company_id=? AND year=?',
                (question_id, company_id, year)
            ).fetchone()
            
            if existing:
                conn.execute('''
                    UPDATE ipd_answers SET value=?, status='completed',
                    updated_at=CURRENT_TIMESTAMP, deleted_at=NULL WHERE id=?
                ''', (value, existing['id']))
                answer_id = existing['id']
            else:
                answer_id = _generate_uuid()
                conn.execute('''
                    INSERT INTO ipd_answers (id, question_id, company_id, year, value, status)
                    VALUES (?,?,?,?,?,'completed')
                ''', (answer_id, question_id, company_id, year, value))

            # 4. YES/NO 연동 처리 (Dependent questions cleansing)
            q_info = conn.execute('SELECT type FROM ipd_questions WHERE id=?', (question_id,)).fetchone()
            if q_info and q_info['type'] == 'yes_no':
                if _is_yes(str(value)):
                    _clear_na_from_dependents(conn, question_id, company_id, year)
                else:
                    _mark_dependents_na(conn, question_id, company_id, year)

            conn.commit()
            _update_session_progress(conn, company_id, year)

        return jsonify({'success': True, 'answer_id': answer_id})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# API — 증빙 자료
# ============================================================

@bp_disclosure.route('/api/evidence', methods=['POST'])
def upload_evidence():
    """증빙 자료 업로드"""
    try:
        company_id = request.form.get('company_id')
        year = request.form.get('year', type=int)
        question_id = request.form.get('question_id')

        if not all([company_id, year, question_id]):
            return jsonify({'success': False, 'message': '필수 파라미터 누락'}), 400

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '파일이 없습니다.'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'message': '파일명이 없습니다.'}), 400

        if not _allowed_file(file.filename):
            return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'}), 400

        # 저장 경로 생성
        save_dir = os.path.join(UPLOAD_FOLDER, company_id, str(year))
        os.makedirs(save_dir, exist_ok=True)

        evidence_id = _generate_uuid()
        ext = file.filename.rsplit('.', 1)[1].lower()
        save_name = f"{evidence_id}.{ext}"
        save_path = os.path.join(save_dir, save_name)
        file.save(save_path)
        file_size = os.path.getsize(save_path)

        file_url = f"/disclosure/evidence/file/{company_id}/{year}/{save_name}"

        with get_db() as conn:
            conn.execute('''
                INSERT INTO ipd_evidence
                (id, question_id, company_id, year, file_name, file_url, file_size, file_type)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (evidence_id, question_id, company_id, year,
                  secure_filename(file.filename), file_url, file_size, ext))
            conn.commit()

        return jsonify({
            'success': True,
            'evidence_id': evidence_id,
            'file_name': file.filename,
            'file_url': file_url,
            'file_size': file_size
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp_disclosure.route('/api/evidence/<evidence_id>', methods=['DELETE'])
def delete_evidence(evidence_id):
    """증빙 자료 삭제"""
    try:
        with get_db() as conn:
            ev = conn.execute(
                'SELECT * FROM ipd_evidence WHERE id=?', (evidence_id,)
            ).fetchone()
            if not ev:
                return jsonify({'success': False, 'message': '존재하지 않는 파일'}), 404

            # 실제 파일 삭제
            file_path = os.path.join(UPLOAD_FOLDER, ev['company_id'],
                                     str(ev['year']),
                                     os.path.basename(ev['file_url']))
            if os.path.exists(file_path):
                os.remove(file_path)

            conn.execute('DELETE FROM ipd_evidence WHERE id=?', (evidence_id,))
            conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp_disclosure.route('/evidence/file/<company_id>/<int:year>/<filename>')
def serve_evidence(company_id, year, filename):
    """증빙 파일 서빙"""
    directory = os.path.join(UPLOAD_FOLDER, company_id, str(year))
    return send_from_directory(directory, filename)


# ============================================================
# 공시 자료 검토 (5단계)
# ============================================================

@bp_disclosure.route('/<company_id>/<int:year>/review')
def review(company_id, year):
    """공시 자료 전체 검토 화면"""
    with get_db() as conn:
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM ipd_questions ORDER BY sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        evidence_rows = conn.execute(
            'SELECT * FROM ipd_evidence WHERE company_id=? AND year=?', (company_id, year)
        ).fetchall()
        evidence_map = {}
        for e in evidence_rows:
            qid = e['question_id']
            if qid not in evidence_map:
                evidence_map[qid] = []
            evidence_map[qid].append(dict(e))

        # options 파싱
        for q in all_questions:
            if q.get('options'):
                try:
                    q['options_list'] = json.loads(q['options'])
                except (json.JSONDecodeError, TypeError):
                    q['options_list'] = []
            else:
                q['options_list'] = []
            q['is_active'] = _is_question_active(q, questions_dict, answers)
            q['is_skipped'] = _is_question_skipped(q, questions_dict, answers)

        # 카테고리별 그룹핑
        categories = {}
        for q in all_questions:
            cat_id = q['category_id']
            if cat_id not in categories:
                categories[cat_id] = {'id': cat_id, 'name': q['category'], 'questions': []}
            categories[cat_id]['questions'].append(q)

        session_row = conn.execute(
            'SELECT * FROM ipd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()
        session = dict(session_row) if session_row else {'completion_rate': 0, 'status': 'draft'}

        # 투자 비율 계산
        ratios = _calculate_ratios(conn, company_id, year, answers)

        # 답변이 없는 가상 세션 객체 보완
        if not session:
            session = {'completion_rate': 0, 'status': 'draft', 'id': None}
            
        # 전체 진행률 계산
        total_q = sum(1 for q in all_questions if q['type'] != 'group')
        done_q = 0
        for q in all_questions:
            if q['type'] == 'group': continue
            if _is_question_active(q, questions_dict, answers):
                if q['id'] in answers and answers[q['id']] not in (None, '', 'N/A'):
                    done_q += 1
            elif _is_question_skipped(q, questions_dict, answers):
                done_q += 1
        overall = round((done_q / total_q) * 100) if total_q > 0 else 0

    return render_template('disclosure/review.html',
                           company=dict(company), year=year,
                           questions=questions_dict,
                           answers=answers, evidence=evidence_map,
                           session=session, ratios=ratios, overall=overall)


def _calculate_ratios(conn, company_id, year, answers=None):
    """투자 및 인력 비율 계산"""
    if answers is None:
        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

    ratios = {'investment_ratio': 0.0, 'personnel_ratio': 0.0}

    # 투자 비율 (B/A * 100)
    if _is_yes(answers.get('Q1', '')):
        try:
            val_a = float(str(answers.get('Q2', 0) or 0).replace(',', ''))
            b1 = float(str(answers.get('Q4', 0) or 0).replace(',', ''))
            b2 = float(str(answers.get('Q5', 0) or 0).replace(',', ''))
            b3 = float(str(answers.get('Q6', 0) or 0).replace(',', ''))
            val_b = b1 + b2 + b3
            if val_a > 0:
                ratios['investment_ratio'] = round((val_b / val_a) * 100, 2)
        except ValueError:
            pass

    # 인력 비율 (D/C * 100, D = 내부+외주, C = IT 전체)
    if _is_yes(answers.get('Q9', '')):
        try:
            it_emp = float(str(answers.get('Q28', 0) or 0).replace(',', ''))
            internal = float(str(answers.get('Q11', 0) or 0).replace(',', ''))
            external = float(str(answers.get('Q12', 0) or 0).replace(',', ''))
            d_sum = internal + external
            if it_emp > 0:
                ratios['personnel_ratio'] = round((d_sum / it_emp) * 100, 2)
        except ValueError:
            pass

    return ratios


# ============================================================
# 공시 제출
# ============================================================

@bp_disclosure.route('/<company_id>/<int:year>/submit', methods=['POST'])
def submit(company_id, year):
    """공시 제출 처리"""
    with get_db() as conn:
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        session_row = conn.execute(
            'SELECT * FROM ipd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()

        if not session_row:
            flash('공시 세션이 없습니다. 먼저 답변을 입력하세요.', 'error')
            return redirect(url_for('disclosure.dashboard', company_id=company_id, year=year))

        if session_row['completion_rate'] < 100:
            flash(f'미완료 항목이 있습니다. (현재 진행률: {session_row["completion_rate"]}%)', 'warning')
            return redirect(url_for('disclosure.review', company_id=company_id, year=year))

        # 이미 제출된 경우
        if session_row['status'] == 'submitted':
            flash('성공적으로 제출되었습니다.', 'success')
            return redirect(url_for('disclosure.review', company_id=company_id, year=year))

        # 제출 처리
        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        submission_id = _generate_uuid()
        confirmation = f"IPD-{year}-{submission_id[:8].upper()}"

        conn.execute('''
            INSERT INTO ipd_submissions
            (id, session_id, company_id, year, submission_data, submitted_at, confirmation_number, status)
            VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,?,'submitted')
        ''', (submission_id, session_row['id'], company_id, year,
              json.dumps(answers, ensure_ascii=False), confirmation))

        conn.execute('''
            UPDATE ipd_sessions SET status='submitted', submitted_at=CURRENT_TIMESTAMP
            WHERE company_id=? AND year=?
        ''', (company_id, year))

        conn.execute(
            'UPDATE ipd_targets SET status="submitted" WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.commit()

    flash(f'공시 제출 완료. 확인번호: {confirmation}', 'success')
    return redirect(url_for('disclosure.review', company_id=company_id, year=year))


# ============================================================
# API — 전년도 참고 데이터 (Reference View)
# ============================================================

@bp_disclosure.route('/api/years/<company_id>')
def get_available_years(company_id):
    """특정 회사의 데이터가 존재하는 연도 목록 조회"""
    try:
        with get_db() as conn:
            # ipd_targets 또는 ipd_answers에서 연도 추출
            rows = conn.execute('''
                SELECT DISTINCT year FROM ipd_targets 
                WHERE company_id = ? 
                UNION 
                SELECT DISTINCT year FROM ipd_answers 
                WHERE company_id = ? AND deleted_at IS NULL
                ORDER BY year DESC
            ''', (company_id, company_id)).fetchall()
            
            years = [row['year'] for row in rows]
            return jsonify({'success': True, 'years': years})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp_disclosure.route('/<company_id>/<int:year>/download/excel')
def download_excel(company_id, year):
    """공시 자료 Excel 다운로드"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        with get_db() as conn:
            company = _get_company_or_404(conn, company_id)
            _get_target_or_404(conn, company_id, year)

            all_questions = [dict(r) for r in conn.execute(
                'SELECT * FROM ipd_questions ORDER BY category_id, sort_order'
            ).fetchall()]
            questions_dict = {q['id']: q for q in all_questions}

            answers = {r['question_id']: r['value'] for r in conn.execute(
                'SELECT question_id, value FROM ipd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
                (company_id, year)
            ).fetchall()}

        wb = Workbook()
        ws = wb.active
        ws.title = f"{year}년 공시"

        # 스타일 정의
        header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
        cat_fill = PatternFill(start_color="3b82f6", end_color="3b82f6", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        normal_font = Font(size=10)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

        # 제목 행
        ws.merge_cells('A1:D1')
        ws['A1'] = f"정보보호공시 — {company['name']} ({year}년)"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].alignment = center_align

        # 헤더 행
        headers = ['질문 번호', '질문 항목', '답변', '구분']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        ws.column_dimensions['A'].width = 14
        ws.column_dimensions['B'].width = 55
        ws.column_dimensions['C'].width = 35
        ws.column_dimensions['D'].width = 16
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 22

        row = 3
        current_cat = None
        for q in all_questions:
            if q['type'] == 'group':
                continue
            # 카테고리 구분 행
            if q['category_id'] != current_cat:
                current_cat = q['category_id']
                ws.merge_cells(f'A{row}:D{row}')
                cat_cell = ws.cell(row=row, column=1, value=f"▶ {q['category']}")
                cat_cell.font = Font(bold=True, color="FFFFFF", size=10)
                cat_cell.fill = cat_fill
                cat_cell.alignment = left_align
                cat_cell.border = thin_border
                ws.row_dimensions[row].height = 18
                row += 1

            # 답변 값 처리
            raw_val = answers.get(q['id'], '')
            if raw_val and raw_val not in ('N/A', ''):
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        if isinstance(parsed[0], dict):
                            # table 타입: 헤더|값 형식으로 표현
                            raw_val = '\n'.join(
                                ' | '.join(f"{k}: {v}" for k, v in r.items())
                                for r in parsed
                            )
                        else:
                            raw_val = ', '.join(str(v) for v in parsed)
                except (json.JSONDecodeError, TypeError):
                    pass

            status = '미작성'
            if raw_val == 'N/A':
                status = '해당없음'
            elif raw_val:
                status = '완료'

            cells = [
                ws.cell(row=row, column=1, value=q.get('display_number') or q['id']),
                ws.cell(row=row, column=2, value=q['text']),
                ws.cell(row=row, column=3, value=raw_val),
                ws.cell(row=row, column=4, value=status),
            ]
            for cell in cells:
                cell.font = normal_font
                cell.alignment = left_align
                cell.border = thin_border
            cells[0].alignment = center_align

            # 미작성 행 연한 빨강
            if status == '미작성':
                for cell in cells:
                    cell.fill = PatternFill(start_color="FFF3F3", end_color="FFF3F3", fill_type="solid")

            ws.row_dimensions[row].height = 18
            row += 1

        # 메모리 버퍼로 저장
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"정보보호공시_{company['name']}_{year}.xlsx"
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except ImportError:
        flash('Excel 다운로드 기능을 사용하려면 openpyxl을 설치하세요. (pip install openpyxl)', 'warning')
        return redirect(url_for('disclosure.review', company_id=company_id, year=year))
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Excel 생성 중 오류: {str(e)}', 'error')
        return redirect(url_for('disclosure.review', company_id=company_id, year=year))


@bp_disclosure.route('/api/answers/<company_id>/<int:year>')
def get_year_answers(company_id, year):
    """특정 연도의 모든 질문 상세 정보와 답변 데이터 조회 (카테고리 필터 지원)"""
    category_id = request.args.get('category_id', type=int)
    
    try:
        with get_db() as conn:
            # 질문 상세 정보와 답변을 JOIN하여 조회
            query = '''
                SELECT q.id as question_id, q.text as question_text, q.type as question_type,
                       q.display_number, q.category_id, q.category, a.value
                FROM ipd_questions q
                LEFT JOIN ipd_answers a ON q.id = a.question_id 
                    AND a.company_id = ? AND a.year = ? AND a.deleted_at IS NULL
                WHERE q.type != 'group'
            '''
            params = [company_id, year]
            
            if category_id:
                query += ' AND q.category_id = ? '
                params.append(category_id)
                
            query += ' ORDER BY q.category_id, q.sort_order '
            
            cursor = conn.execute(query, params)
            
            data = []
            for row in cursor.fetchall():
                item = dict(row)
                # JSON 필드 파싱 시도 (단순 값은 그대로 유지)
                if item.get('value'):
                    try:
                        item['value'] = json.loads(item['value'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                data.append(item)
                
            return jsonify({
                'success': True,
                'company_id': company_id,
                'year': year,
                'answers': data
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
