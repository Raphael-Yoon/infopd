"""
infopd - 정보보호공시 관리 시스템
메인 Flask 애플리케이션
"""
import json
from flask import Flask, render_template, jsonify
from pathlib import Path
import os

_APP_DIR = Path(__file__).parent.resolve()
os.chdir(_APP_DIR)

from company_routes import bp_company
from disclosure_routes import bp_disclosure

app = Flask(__name__)
app.secret_key = os.getenv('INFOPD_SECRET_KEY', 'infopd-dev-secret-key-change-in-production')

app.config.update(
    TEMPLATES_AUTO_RELOAD=True,
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
)
app.jinja_env.auto_reload = True


# ─── Jinja2 커스텀 필터 ───────────────────────────
@app.template_filter('from_json_or_default')
def from_json_or_default(value, default=None):
    """JSON 문자열을 파싱. 실패 시 default 반환."""
    if default is None:
        default = []
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


# Blueprint 등록
app.register_blueprint(bp_company)
app.register_blueprint(bp_disclosure)


@app.route('/health')
def health():
    """서버 상태 확인"""
    return jsonify({'status': 'ok', 'service': 'infopd'})


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message='페이지를 찾을 수 없습니다.'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500, message='서버 오류가 발생했습니다.'), 500


if __name__ == '__main__':
    port = int(os.getenv('INFOPD_PORT', 5001))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    print(f"\n infopd 서버 시작 — http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
