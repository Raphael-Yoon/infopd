"""
infopd - 회사/연도 관리 라우팅
"""
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from db_config import get_db

bp_company = Blueprint('company', __name__)


def _generate_uuid():
    return str(uuid.uuid4())


def _get_progress(conn, company_id, year):
    """회사+연도의 완료율 반환"""
    row = conn.execute(
        'SELECT completion_rate, status FROM ipd_sessions WHERE company_id = ? AND year = ?',
        (company_id, year)
    ).fetchone()
    if row:
        return row['completion_rate'], row['status']
    return 0, 'draft'


def _delete_target_data(conn, company_id, year):
    """특정 연도의 공시 데이터 전체 삭제"""
    conn.execute('DELETE FROM ipd_evidence WHERE company_id = ? AND year = ?', (company_id, year))
    conn.execute('DELETE FROM ipd_answers WHERE company_id = ? AND year = ?', (company_id, year))
    conn.execute('DELETE FROM ipd_submissions WHERE company_id = ? AND year = ?', (company_id, year))
    conn.execute('DELETE FROM ipd_sessions WHERE company_id = ? AND year = ?', (company_id, year))


# ============================================================
# 메인 — 회사 목록
# ============================================================

@bp_company.route('/')
def index():
    """메인 페이지 — 회사+연도 목록 및 진행률"""
    with get_db() as conn:
        companies = conn.execute(
            'SELECT * FROM ipd_companies ORDER BY name'
        ).fetchall()

        result = []
        for c in companies:
            targets = conn.execute(
                'SELECT * FROM ipd_targets WHERE company_id = ? ORDER BY year DESC',
                (c['id'],)
            ).fetchall()

            target_list = []
            for t in targets:
                rate, status = _get_progress(conn, c['id'], t['year'])
                target_list.append({
                    'id': t['id'],
                    'year': t['year'],
                    'status': status,
                    'completion_rate': rate
                })

            result.append({
                'id': c['id'],
                'name': c['name'],
                'targets': target_list
            })

    current_year = datetime.now().year
    return render_template('index.html', companies=result, current_year=current_year)


# ============================================================
# 회사 관리
# ============================================================

@bp_company.route('/company/add', methods=['POST'])
def add_company():
    """회사 등록"""
    name = request.form.get('name', '').strip()
    if not name:
        flash('회사명을 입력하세요.', 'warning')
        return redirect(url_for('company.index'))

    with get_db() as conn:
        existing = conn.execute(
            'SELECT id FROM ipd_companies WHERE name = ?', (name,)
        ).fetchone()
        if existing:
            flash(f'"{name}" 은(는) 이미 등록된 회사입니다.', 'warning')
            return redirect(url_for('company.index'))

        company_id = _generate_uuid()
        conn.execute(
            'INSERT INTO ipd_companies (id, name) VALUES (?, ?)',
            (company_id, name)
        )
        conn.commit()

    flash(f'"{name}" 등록 완료.', 'success')
    return redirect(url_for('company.index'))


@bp_company.route('/company/<company_id>/delete', methods=['POST'])
def delete_company(company_id):
    """회사 삭제 (연관 데이터 전체 포함)"""
    with get_db() as conn:
        company = conn.execute(
            'SELECT name FROM ipd_companies WHERE id = ?', (company_id,)
        ).fetchone()
        if not company:
            flash('존재하지 않는 회사입니다.', 'error')
            return redirect(url_for('company.index'))

        name = company['name']
        conn.execute('PRAGMA foreign_keys = OFF')
        targets = conn.execute(
            'SELECT year FROM ipd_targets WHERE company_id = ?', (company_id,)
        ).fetchall()
        for t in targets:
            _delete_target_data(conn, company_id, t['year'])
        conn.execute('DELETE FROM ipd_targets WHERE company_id = ?', (company_id,))
        conn.execute('DELETE FROM ipd_companies WHERE id = ?', (company_id,))
        conn.execute('PRAGMA foreign_keys = ON')
        conn.commit()

    flash(f'"{name}" 및 관련 데이터 삭제 완료.', 'success')
    return redirect(url_for('company.index'))


# ============================================================
# 연도 관리
# ============================================================

@bp_company.route('/company/<company_id>/year/add', methods=['POST'])
def add_year(company_id):
    """공시 연도 추가"""
    year_str = request.form.get('year', '').strip()
    try:
        year = int(year_str)
        if year < 2000 or year > 2100:
            raise ValueError
    except (ValueError, TypeError):
        flash('올바른 연도(2000~2100)를 입력하세요.', 'warning')
        return redirect(url_for('company.index'))

    with get_db() as conn:
        company = conn.execute(
            'SELECT name FROM ipd_companies WHERE id = ?', (company_id,)
        ).fetchone()
        if not company:
            flash('존재하지 않는 회사입니다.', 'error')
            return redirect(url_for('company.index'))

        existing = conn.execute(
            'SELECT id FROM ipd_targets WHERE company_id = ? AND year = ?',
            (company_id, year)
        ).fetchone()
        if existing:
            flash(f'{year}년도는 이미 등록되어 있습니다.', 'warning')
            return redirect(url_for('company.index'))

        conn.execute(
            'INSERT INTO ipd_targets (id, company_id, year) VALUES (?, ?, ?)',
            (_generate_uuid(), company_id, year)
        )
        conn.commit()

    flash(f'{year}년도 공시 대상 추가 완료.', 'success')
    return redirect(url_for('company.index'))


@bp_company.route('/company/<company_id>/year/<int:year>/delete', methods=['POST'])
def delete_year(company_id, year):
    """연도 삭제 (해당 연도 공시 데이터 포함)"""
    with get_db() as conn:
        target = conn.execute(
            'SELECT id FROM ipd_targets WHERE company_id = ? AND year = ?',
            (company_id, year)
        ).fetchone()
        if not target:
            flash('존재하지 않는 공시 대상입니다.', 'error')
            return redirect(url_for('company.index'))

        conn.execute('PRAGMA foreign_keys = OFF')
        _delete_target_data(conn, company_id, year)
        conn.execute(
            'DELETE FROM ipd_targets WHERE company_id = ? AND year = ?',
            (company_id, year)
        )
        conn.execute('PRAGMA foreign_keys = ON')
        conn.commit()

    flash(f'{year}년도 공시 데이터 삭제 완료.', 'success')
    return redirect(url_for('company.index'))
