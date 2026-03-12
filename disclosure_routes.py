"""
infosd - 공시 작업 라우팅 (4+5단계)
"""
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, send_from_directory, abort, session)
from db_config import get_db, generate_uuid

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
    # group 타입은 별도 답변이 없어도 하위 항목을 항상 활성화
    if parent_q['type'] == 'group':
        return True
    parent_answer = answers.get(parent_id)
    if parent_answer is None:
        return False
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
            'SELECT dependent_question_ids FROM isd_questions WHERE id = ?', (q_id,)
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
            'SELECT * FROM isd_questions ORDER BY category_id, sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
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
        
        # 현재 세션의 상태 확인 (이미 확정된 경우 유지)
        existing_status = None
        existing_row = conn.execute(
            'SELECT status FROM isd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()
        if existing_row:
            existing_status = existing_row['status']

        if existing_status == 'confirmed':
            status = 'confirmed'
        else:
            status = 'completed' if rate == 100 else ('in_progress' if answered > 0 else 'draft')

        existing = conn.execute(
            'SELECT id FROM isd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()

        if existing:
            conn.execute('''
                UPDATE isd_sessions
                SET total_questions=?, answered_questions=?, completion_rate=?,
                    status=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE company_id=? AND year=?
            ''', (total, answered, rate, status, company_id, year))
        else:
            conn.execute('''
                INSERT INTO isd_sessions
                (id, company_id, year, status, total_questions, answered_questions, completion_rate)
                VALUES (?,?,?,?,?,?,?)
            ''', (generate_uuid(), company_id, year, status, total, answered, rate))
        conn.commit()
    except Exception as e:
        print(f"진행률 업데이트 오류: {e}")


def _mark_dependents_na(conn, question_id, company_id, year):
    """상위 질문 NO 시 하위 질문을 N/A로 표시"""
    row = conn.execute(
        'SELECT dependent_question_ids FROM isd_questions WHERE id=?', (question_id,)
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
            'SELECT id FROM isd_answers WHERE question_id=? AND company_id=? AND year=?',
            (dep_id, company_id, year)
        ).fetchone()
        if existing:
            conn.execute('''
                UPDATE isd_answers SET value='N/A', status='skipped',
                updated_at=CURRENT_TIMESTAMP, deleted_at=NULL WHERE id=?
            ''', (existing['id'],))
        else:
            conn.execute('''
                INSERT INTO isd_answers (id, question_id, company_id, year, value, status)
                VALUES (?,?,?,?,'N/A','skipped')
            ''', (generate_uuid(), dep_id, company_id, year))


def _clear_na_from_dependents(conn, question_id, company_id, year):
    """상위 질문 YES 복귀 시 N/A 답변 삭제"""
    row = conn.execute(
        'SELECT dependent_question_ids FROM isd_questions WHERE id=?', (question_id,)
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
            DELETE FROM isd_answers
            WHERE question_id=? AND company_id=? AND year=? AND value='N/A' AND status='skipped'
        ''', (dep_id, company_id, year))


def _get_company_or_404(conn, company_id):
    company = conn.execute(
        'SELECT * FROM isd_companies WHERE id=?', (company_id,)
    ).fetchone()
    if not company:
        abort(404)
    return company


def _get_target_or_404(conn, company_id, year):
    target = conn.execute(
        'SELECT * FROM isd_targets WHERE company_id=? AND year=?', (company_id, year)
    ).fetchone()
    if not target:
        abort(404)
    return target


def _build_evidence_map(conn, company_id, year):
    """증빙 자료를 질문 ID 기준으로 그룹화하여 반환"""
    rows = conn.execute(
        'SELECT * FROM isd_evidence WHERE company_id=? AND year=? ORDER BY uploaded_at DESC',
        (company_id, year)
    ).fetchall()
    evidence_map = {}
    for e in rows:
        qid = e['question_id']
        if qid not in evidence_map:
            evidence_map[qid] = []
        evidence_map[qid].append(dict(e))
    return evidence_map


def _parse_options(questions):
    """questions 리스트의 options 필드를 JSON 파싱하여 options_list 주입"""
    for q in questions:
        if q.get('options'):
            try:
                q['options_list'] = json.loads(q['options'])
            except (json.JSONDecodeError, TypeError):
                q['options_list'] = []
        else:
            q['options_list'] = []


def _calc_cat_progress(all_questions, questions_dict, answers):
    """카테고리별 진행률 계산. [{'id', 'name', 'total', 'done', 'rate'}] 반환"""
    cat_map = {}
    for q in all_questions:
        if q['type'] == 'group':
            continue
        cat_id = q['category_id']
        if cat_id not in cat_map:
            cat_map[cat_id] = {'id': cat_id, 'name': q['category'], 'total': 0, 'done': 0}
        cat_map[cat_id]['total'] += 1
        if _is_question_active(q, questions_dict, answers):
            if q['id'] in answers and answers[q['id']] not in (None, ''):
                cat_map[cat_id]['done'] += 1
        elif _is_question_skipped(q, questions_dict, answers):
            cat_map[cat_id]['done'] += 1
    result = []
    for cat_id in sorted(cat_map):
        c = cat_map[cat_id]
        c['rate'] = int((c['done'] / c['total']) * 100) if c['total'] > 0 else 0
        result.append(c)
    return result


# ============================================================
# 공시 대시보드 및 세션 관리
# ============================================================

@bp_disclosure.route('/select/<company_id>/<int:year>')
@bp_disclosure.route('/<company_id>/<int:year>')
def select_session(company_id, year):
    """공시 작업 세션 설정 후 대시보드로 리다이렉트 (주소창 ID 숨김 및 하위 호환성)"""
    session['current_company_id'] = company_id
    session['current_year'] = year
    return redirect(url_for('disclosure.dashboard'))


@bp_disclosure.route('/')
def dashboard():
    """공시 작업 대시보드 — 카테고리별 진행률 (세션 기반)"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')
    
    if not company_id or not year:
        return redirect(url_for('company.index'))

    with get_db() as conn:
        _update_session_progress(conn, company_id, year)
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM isd_questions ORDER BY category_id, sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        cat_list = _calc_cat_progress(all_questions, questions_dict, answers)
        total_q = sum(c['total'] for c in cat_list)
        total_done = sum(c['done'] for c in cat_list)
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
        # 세션 정보 조회
        session_info = conn.execute(
            'SELECT * FROM isd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone() or {'status': 'draft'}

    return render_template('disclosure/dashboard.html',
                           company=dict(company), year=year,
                           categories=cat_list, overall=overall,
                           session=session_info,
                           ratios=ratios, cert_count=cert_count)


# ============================================================
# 공시 작업 화면
# ============================================================

@bp_disclosure.route('/work')
def work():
    """질문-답변 입력 화면 (세션 기반)"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')
    
    if not company_id or not year:
        return redirect(url_for('company.index'))
    category_id = request.args.get('category', type=int, default=1)
    with get_db() as conn:
        _update_session_progress(conn, company_id, year)
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        questions = [dict(r) for r in conn.execute(
            'SELECT * FROM isd_questions WHERE category_id=? ORDER BY sort_order',
            (category_id,)
        ).fetchall()]

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM isd_questions ORDER BY sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers_rows = conn.execute(
            'SELECT question_id, value, id as answer_id FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()
        answers = {r['question_id']: r['value'] for r in answers_rows}
        answer_ids = {r['question_id']: r['answer_id'] for r in answers_rows}

        evidence_map = _build_evidence_map(conn, company_id, year)

        # options JSON 파싱 + 단위(unit) 주입
        PERSON_UNIT_IDS = {
            QID.PER_TOTAL_EMPLOYEES,  # Q10 총 임직원 수
            QID.PER_IT_EMPLOYEES,     # Q28 정보기술부문 인력(C)
            QID.PER_INTERNAL,         # Q11 내부 전담인력(D1)
            QID.PER_EXTERNAL,         # Q12 외주 전담인력(D2)
        }
        _parse_options(questions)
        for q in questions:
            q['is_active'] = _is_question_active(q, questions_dict, answers)
            q['is_skipped'] = _is_question_skipped(q, questions_dict, answers)
            q['unit'] = ('명' if q['id'] in PERSON_UNIT_IDS else '원') if q['type'] == 'number' else ''

        sidebar_categories = _calc_cat_progress(all_questions, questions_dict, answers)

        current_category_name = next((c['name'] for c in sidebar_categories if c['id'] == category_id), "Unknown")
        
        # 전체 진행률 가져오기
        isd_session = conn.execute(
            'SELECT completion_rate FROM isd_sessions WHERE company_id=? AND year=?',
            (company_id, year)
        ).fetchone()
        overall_progress = isd_session['completion_rate'] if isd_session else 0
        
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
        company_id = data.get('company_id') or session.get('current_company_id')
        year = data.get('year') or session.get('current_year')

        if not all([question_id, company_id, year]):
            return jsonify({'success': False, 'message': '필수 파라미터 누락'}), 400

        # 리스트 값 직렬화
        if isinstance(value, list):
            value = json.dumps(value, ensure_ascii=False)

        with get_db() as conn:
            # 0-0. 확정 상태 수정 차단
            session_row = conn.execute(
                'SELECT status FROM isd_sessions WHERE company_id=? AND year=?',
                (company_id, year)
            ).fetchone()
            if session_row and session_row['status'] == 'confirmed':
                return jsonify({'success': False, 'message': '확정된 공시는 수정할 수 없습니다.'}), 403

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
                    SELECT question_id, value FROM isd_answers
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
                    SELECT question_id, value FROM isd_answers
                    WHERE question_id IN (?, ?, ?) AND company_id = ? AND year = ? AND deleted_at IS NULL
                ''', (*inv_b_ids, company_id, year))
                b_vals = {row['question_id']: row['value'] for row in cursor.fetchall()}
                b_vals[question_id] = value

                cursor = conn.execute(
                    'SELECT value FROM isd_answers WHERE question_id=? AND company_id=? AND year=? AND deleted_at IS NULL',
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
                'SELECT id, value FROM isd_answers WHERE question_id=? AND company_id=? AND year=?',
                (question_id, company_id, year)
            ).fetchone()

            old_value = existing['value'] if existing else None

            if existing:
                conn.execute('''
                    UPDATE isd_answers SET value=?, status='completed',
                    updated_at=CURRENT_TIMESTAMP, deleted_at=NULL WHERE id=?
                ''', (value, existing['id']))
                answer_id = existing['id']
            else:
                answer_id = generate_uuid()
                conn.execute('''
                    INSERT INTO isd_answers (id, question_id, company_id, year, value, status)
                    VALUES (?,?,?,?,?,'completed')
                ''', (answer_id, question_id, company_id, year, value))

            # 3-1. Audit Trail: 답변 변경 이력 기록
            conn.execute(
                '''INSERT INTO isd_answer_history
                   (company_id, year, question_id, old_value, new_value)
                   VALUES (?, ?, ?, ?, ?)''',
                (company_id, year, question_id, old_value, value)
            )

            # 4. YES/NO 연동 처리 (Dependent questions cleansing)
            q_info = conn.execute('SELECT type FROM isd_questions WHERE id=?', (question_id,)).fetchone()
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
        company_id = request.form.get('company_id') or session.get('current_company_id')
        year = request.form.get('year', session.get('current_year'), type=int)
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

        evidence_id = generate_uuid()
        ext = file.filename.rsplit('.', 1)[1].lower()
        save_name = f"{evidence_id}.{ext}"
        save_path = os.path.join(save_dir, save_name)
        file.save(save_path)
        file_size = os.path.getsize(save_path)

        file_url = f"/disclosure/evidence/file/{company_id}/{year}/{save_name}"

        with get_db() as conn:
            conn.execute('''
                INSERT INTO isd_evidence
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
                'SELECT * FROM isd_evidence WHERE id=?', (evidence_id,)
            ).fetchone()
            if not ev:
                return jsonify({'success': False, 'message': '존재하지 않는 파일입니다.'}), 404

            # 실제 파일 삭제
            file_path = os.path.join(UPLOAD_FOLDER, ev['company_id'],
                                     str(ev['year']),
                                     os.path.basename(ev['file_url']))
            if os.path.exists(file_path):
                os.remove(file_path)

            conn.execute('DELETE FROM isd_evidence WHERE id=?', (evidence_id,))
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

@bp_disclosure.route('/review')
def review():
    """공시 자료 전체 검토 화면 (세션 기반)"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')
    
    if not company_id or not year:
        return redirect(url_for('company.index'))
    with get_db() as conn:
        company = _get_company_or_404(conn, company_id)
        _get_target_or_404(conn, company_id, year)

        all_questions = [dict(r) for r in conn.execute(
            'SELECT * FROM isd_questions ORDER BY sort_order'
        ).fetchall()]
        questions_dict = {q['id']: q for q in all_questions}

        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

        evidence_map = _build_evidence_map(conn, company_id, year)

        # options 파싱 + 활성화 상태 주입
        _parse_options(all_questions)
        for q in all_questions:
            q['is_active'] = _is_question_active(q, questions_dict, answers)
            q['is_skipped'] = _is_question_skipped(q, questions_dict, answers)

        # 카테고리별 그룹핑
        categories = {}
        for q in all_questions:
            cat_id = q['category_id']
            if cat_id not in categories:
                categories[cat_id] = {'id': cat_id, 'name': q['category'], 'questions': []}
            categories[cat_id]['questions'].append(q)

        # Q3 (정보보호부문 투자액) 자동 계산 (Q4+Q5+Q6)
        if 'Q4' in answers or 'Q5' in answers or 'Q6' in answers:
            try:
                b1 = float(str(answers.get('Q4', 0) or 0).replace(',', ''))
                b2 = float(str(answers.get('Q5', 0) or 0).replace(',', ''))
                b3 = float(str(answers.get('Q6', 0) or 0).replace(',', ''))
                answers['Q3'] = b1 + b2 + b3
            except ValueError:
                pass

        session_row = conn.execute(
            'SELECT * FROM isd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()
        session_info = dict(session_row) if session_row else {'completion_rate': 0, 'status': 'draft'}

        # 투자 비율 계산
        ratios = _calculate_ratios(conn, company_id, year, answers)

        # 전체 진행률 계산
        cat_progress = _calc_cat_progress(all_questions, questions_dict, answers)
        total_q = sum(c['total'] for c in cat_progress)
        total_done = sum(c['done'] for c in cat_progress)
        overall = round((total_done / total_q) * 100) if total_q > 0 else 0

    return render_template('disclosure/review.html',
                           company=dict(company), year=year,
                           questions=questions_dict,
                           answers=answers, evidence=evidence_map,
                           session=session_info, ratios=ratios, overall=overall)


def _calculate_ratios(conn, company_id, year, answers=None):
    """투자 및 인력 비율 계산"""
    if answers is None:
        answers = {r['question_id']: r['value'] for r in conn.execute(
            'SELECT question_id, value FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
            (company_id, year)
        ).fetchall()}

    ratios = {'investment_ratio': 0.0, 'personnel_ratio': 0.0}

    # 투자 비율 (B/A * 100)
    if _is_yes(answers.get(QID.INV_HAS_INVESTMENT, '')):
        try:
            val_a = float(str(answers.get(QID.INV_IT_AMOUNT, 0) or 0).replace(',', ''))
            b1 = float(str(answers.get(QID.INV_SEC_DEPRECIATION, 0) or 0).replace(',', ''))
            b2 = float(str(answers.get(QID.INV_SEC_SERVICE, 0) or 0).replace(',', ''))
            b3 = float(str(answers.get(QID.INV_SEC_LABOR, 0) or 0).replace(',', ''))
            val_b = b1 + b2 + b3
            if val_a > 0:
                ratios['investment_ratio'] = round((val_b / val_a) * 100, 2)
        except ValueError:
            pass

    # 인력 비율 (D/C * 100, D = 내부+외주, C = IT 전체)
    if _is_yes(answers.get(QID.PER_HAS_TEAM, '')):
        try:
            it_emp = float(str(answers.get(QID.PER_IT_EMPLOYEES, 0) or 0).replace(',', ''))
            internal = float(str(answers.get(QID.PER_INTERNAL, 0) or 0).replace(',', ''))
            external = float(str(answers.get(QID.PER_EXTERNAL, 0) or 0).replace(',', ''))
            d_sum = internal + external
            if it_emp > 0:
                ratios['personnel_ratio'] = round((d_sum / it_emp) * 100, 2)
        except ValueError:
            pass

    return ratios


# ============================================================
# 공시 확정 및 상태 관리
# ============================================================

@bp_disclosure.route('/submit', methods=['POST'])
def submit_disclosure():
    """공시 자료 검토 요청 (SoD: 작성자 → 검토자 단계 분리)"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')

    if not company_id or not year:
        return redirect(url_for('company.index'))

    with get_db() as conn:
        session_row = conn.execute(
            'SELECT completion_rate, status FROM isd_sessions WHERE company_id=? AND year=?',
            (company_id, year)
        ).fetchone()

        if not session_row or session_row['completion_rate'] < 100:
            flash('모든 항목을 작성해야 검토 요청이 가능합니다.', 'warning')
            return redirect(url_for('disclosure.review'))

        if session_row['status'] in ('submitted', 'confirmed'):
            flash('이미 검토 요청되었거나 확정된 공시입니다.', 'info')
            return redirect(url_for('disclosure.review'))

        conn.execute(
            'UPDATE isd_sessions SET status="submitted", updated_at=CURRENT_TIMESTAMP WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.execute(
            'UPDATE isd_targets SET status="submitted" WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.commit()

    flash('검토 요청이 완료되었습니다. 담당자가 최종 확정하면 공시가 완료됩니다.', 'success')
    return redirect(url_for('disclosure.review'))


@bp_disclosure.route('/confirm', methods=['POST'])
def confirm_disclosure():
    """공시 자료 확정 처리"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')
    
    if not company_id or not year:
        return redirect(url_for('company.index'))
        
    with get_db() as conn:
        session_row = conn.execute(
            'SELECT completion_rate, status FROM isd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()

        if not session_row or session_row['status'] != 'submitted':
            flash('검토 요청 완료 후 확정할 수 있습니다.', 'warning')
            return redirect(url_for('disclosure.review'))

        if session_row['completion_rate'] < 100:
            flash('모든 항목을 작성해야 확정이 가능합니다.', 'warning')
            return redirect(url_for('disclosure.review'))

        # 필수 증빙 검증: 답변 완료 항목 중 증빙 미업로드 항목 차단
        # (number 타입 항목은 금액이 0인 경우 증빙 불필요)
        req_questions = conn.execute(
            'SELECT id, display_number, type FROM isd_questions WHERE evidence_list IS NOT NULL'
        ).fetchall()
        if req_questions:
            answered_ids = {r['question_id'] for r in conn.execute(
                "SELECT question_id FROM isd_answers WHERE company_id=? AND year=? AND status='completed'",
                (company_id, year)
            ).fetchall()}
            all_answers = {r['question_id']: r['value'] for r in conn.execute(
                'SELECT question_id, value FROM isd_answers WHERE company_id=? AND year=? AND deleted_at IS NULL',
                (company_id, year)
            ).fetchall()}
            uploaded_ids = {r['question_id'] for r in conn.execute(
                'SELECT DISTINCT question_id FROM isd_evidence WHERE company_id=? AND year=?',
                (company_id, year)
            ).fetchall()}
            missing_ev = []
            for q in req_questions:
                if q['id'] not in answered_ids:
                    continue
                if q['type'] == 'number':
                    try:
                        val = float(str(all_answers.get(q['id'], '0') or '0').replace(',', ''))
                        if val == 0:
                            continue
                    except ValueError:
                        pass
                if q['id'] not in uploaded_ids:
                    missing_ev.append(q['display_number'])
            if missing_ev:
                flash(f'다음 항목의 증빙 자료를 업로드해 주세요: {", ".join(missing_ev)}', 'warning')
                return redirect(url_for('disclosure.review'))

        conn.execute(
            'UPDATE isd_sessions SET status="confirmed", updated_at=CURRENT_TIMESTAMP WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.execute(
            'UPDATE isd_targets SET status="confirmed" WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.commit()
        
    flash('공시 자료가 확정되었습니다. 이제 자료를 생성할 수 있습니다.', 'success')
    return redirect(url_for('disclosure.review'))

@bp_disclosure.route('/unconfirm', methods=['POST'])
def unconfirm_disclosure():
    """공시 자료 확정 취소 (작성 가능 상태로 복구)"""
    company_id = session.get('current_company_id')
    year = session.get('current_year')
    
    if not company_id or not year:
        return redirect(url_for('company.index'))
        
    with get_db() as conn:
        conn.execute(
            'UPDATE isd_sessions SET status="completed", updated_at=CURRENT_TIMESTAMP WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.execute(
            'UPDATE isd_targets SET status="completed" WHERE company_id=? AND year=?',
            (company_id, year)
        )
        conn.commit()
        
    flash('확정이 취소되었습니다. 다시 수정할 수 있습니다.', 'info')
    return redirect(url_for('disclosure.review'))


# ============================================================
# API — 전년도 참고 데이터 (Reference View)
# ============================================================

@bp_disclosure.route('/api/years/<company_id>')
def get_available_years(company_id):
    """특정 회사의 데이터가 존재하는 연도 목록 조회"""
    try:
        with get_db() as conn:
            # isd_targets와 isd_sessions를 JOIN하여 연도와 상태 추출
            rows = conn.execute('''
                SELECT t.year, COALESCE(s.status, 'draft') as status
                FROM isd_targets t
                LEFT JOIN isd_sessions s ON t.company_id = s.company_id AND t.year = s.year
                WHERE t.company_id = ?
                ORDER BY t.year DESC
            ''', (company_id,)).fetchall()
            
            years_data = [{'year': row['year'], 'status': row['status']} for row in rows]
            return jsonify({'success': True, 'years': years_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


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
                FROM isd_questions q
                LEFT JOIN isd_answers a ON q.id = a.question_id 
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
                
            # 해당 연도의 세션 상태 조회
            session_row = conn.execute(
                'SELECT status FROM isd_sessions WHERE company_id=? AND year=?',
                (company_id, year)
            ).fetchone()
            year_status = session_row['status'] if session_row else 'draft'
            
            return jsonify({
                'success': True,
                'company_id': company_id,
                'year': year,
                'status': year_status,
                'answers': data
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
