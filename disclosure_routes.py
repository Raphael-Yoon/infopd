"""
infopd - 공시 작업 라우팅 (4+5단계)
"""
import uuid
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, send_from_directory, abort)
from db_config import get_db

bp_disclosure = Blueprint('disclosure', __name__, url_prefix='/disclosure')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'disclosure')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                      'jpg', 'jpeg', 'png', 'gif', 'zip', 'txt', 'hwp', 'hwpx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

CATEGORY_NAMES = {1: '정보보호 투자', 2: '정보보호 인력', 3: '정보보호 인증', 4: '정보보호 활동'}
YES_VALUES = ('YES', 'Y', 'TRUE', '1', '예', '네')


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
                if q['id'] in answers and answers[q['id']] not in (None, '', 'N/A'):
                    categories[cat_id]['completed'] += 1
            elif _is_question_skipped(q, questions_dict, answers):
                categories[cat_id]['completed'] += 1

        cat_list = []
        total_q, total_done = 0, 0
        for cat_id in sorted(categories):
            c = categories[cat_id]
            c['rate'] = round((c['completed'] / c['total']) * 100) if c['total'] > 0 else 0
            cat_list.append(c)
            total_q += c['total']
            total_done += c['completed']

        overall = round((total_done / total_q) * 100) if total_q > 0 else 0

        session_row = conn.execute(
            'SELECT * FROM ipd_sessions WHERE company_id=? AND year=?', (company_id, year)
        ).fetchone()
        session = dict(session_row) if session_row else None

    return render_template('disclosure/dashboard.html',
                           company=dict(company), year=year,
                           categories=cat_list, overall=overall, session=session)


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

        categories = [dict(r) for r in conn.execute(
            'SELECT DISTINCT category_id, category FROM ipd_questions ORDER BY category_id'
        ).fetchall()]

    return render_template('disclosure/work.html',
                           company=dict(company), year=year,
                           questions=questions, answers=answers, answer_ids=answer_ids,
                           evidence_map=evidence_map, categories=categories,
                           current_category=category_id)


# ============================================================
# API — 답변 저장
# ============================================================

@bp_disclosure.route('/api/answer', methods=['POST'])
def save_answer():
    """답변 저장 (JSON API)"""
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
            # 숫자 필드 음수 방지
            q_info = conn.execute(
                'SELECT type FROM ipd_questions WHERE id=?', (question_id,)
            ).fetchone()
            if q_info and q_info['type'] == 'number' and value is not None:
                try:
                    num_val = float(str(value).replace(',', ''))
                    if num_val < 0:
                        return jsonify({'success': False, 'message': '음수는 입력할 수 없습니다.'}), 400
                except ValueError:
                    pass

            # 투자액 검증: 정보보호 투자액(B) <= 정보기술 투자액(A)
            inv_b_ids = ['Q4', 'Q5', 'Q6']
            if question_id in inv_b_ids or question_id == 'Q2':
                b_rows = conn.execute(
                    'SELECT question_id, value FROM ipd_answers WHERE question_id IN (?,?,?) AND company_id=? AND year=? AND deleted_at IS NULL',
                    ('Q4', 'Q5', 'Q6', company_id, year)
                ).fetchall()
                b_vals = {r['question_id']: r['value'] for r in b_rows}
                if question_id in inv_b_ids:
                    b_vals[question_id] = value
                q2_row = conn.execute(
                    'SELECT value FROM ipd_answers WHERE question_id=? AND company_id=? AND year=? AND deleted_at IS NULL',
                    ('Q2', company_id, year)
                ).fetchone()
                try:
                    val_a = float(str(value).replace(',', '')) if question_id == 'Q2' \
                        else (float(str(q2_row['value']).replace(',', '')) if q2_row and q2_row['value'] else 0)
                    if val_a > 0:
                        val_b = sum(float(str(b_vals.get(qid, 0) or 0).replace(',', '')) for qid in inv_b_ids)
                        if val_b > val_a:
                            return jsonify({'success': False,
                                            'message': f'정보보호 투자액(B) {int(val_b):,}원이 정보기술 투자액(A) {int(val_a):,}원을 초과합니다.'}), 400
                except ValueError:
                    pass

            # 인력 계층 검증
            per_ids = ['Q10', 'Q28', 'Q11', 'Q12']
            if question_id in per_ids:
                per_rows = conn.execute(
                    'SELECT question_id, value FROM ipd_answers WHERE question_id IN (?,?,?,?) AND company_id=? AND year=? AND deleted_at IS NULL',
                    (*per_ids, company_id, year)
                ).fetchall()
                per_vals = {r['question_id']: r['value'] for r in per_rows}
                per_vals[question_id] = value
                try:
                    total_emp = float(str(per_vals.get('Q10', 0) or 0).replace(',', ''))
                    it_emp = float(str(per_vals.get('Q28', 0) or 0).replace(',', ''))
                    internal = float(str(per_vals.get('Q11', 0) or 0).replace(',', ''))
                    external = float(str(per_vals.get('Q12', 0) or 0).replace(',', ''))
                    sec_total = internal + external
                    if total_emp > 0 and it_emp > total_emp:
                        return jsonify({'success': False,
                                        'message': f'IT 인력({int(it_emp)}명)은 총 임직원({int(total_emp)}명)을 초과할 수 없습니다.'}), 400
                    if it_emp > 0 and sec_total > it_emp:
                        return jsonify({'success': False,
                                        'message': f'정보보호 전담인력({int(sec_total)}명)은 IT 인력({int(it_emp)}명)을 초과할 수 없습니다.'}), 400
                except ValueError:
                    pass

            # 답변 저장 (UPSERT)
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

            # YES/NO 연동 처리
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

    return render_template('disclosure/review.html',
                           company=dict(company), year=year,
                           categories=sorted(categories.values(), key=lambda x: x['id']),
                           answers=answers, evidence_map=evidence_map,
                           session=session, ratios=ratios)


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
            flash('이미 제출된 공시입니다.', 'info')
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
