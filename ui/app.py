try:
    import eventlet
    eventlet.monkey_patch()
except ImportError:
    pass

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import requests
import yaml
import os
import time
import hashlib
from functools import wraps

try:
    import docker
    _docker_available = True
except Exception:
    _docker_available = False

app = Flask(__name__)
CONFIG_PATH = '/app/config.yml'
MANUAL_PATH = '/data/manual_mode'
CONTROL_PATH = '/data/control'

def read_file_robust(path):
    """Отказоустойчивое чтение файлов с поддержкой кодировок UTF-8 и Windows-1251 (CP1251)"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='cp1251') as f:
                return f.read()
        except Exception:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

def load_config():
    if os.path.exists(CONFIG_PATH):
        content = read_file_robust(CONFIG_PATH)
        return yaml.safe_load(content) or {}
    return {}

def get_ui_value(cfg, key, default=None):
    ui_cfg = cfg.get('ui', {}) or {}
    if key in ui_cfg:
        return ui_cfg[key]
    
    # Legacy flat key fallback
    flat_key = f"ui_{key}"
    if flat_key in cfg:
        return cfg[flat_key]
    if key == 'secret' and 'ui_secret' in cfg:
        return cfg['ui_secret']
    return default

cfg0 = load_config()
app.secret_key = get_ui_value(cfg0, 'secret', 'change_this_secret')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

def get_mediamtx_api_url(cfg):
    api = cfg.get('mediamtx_api', 'http://mediamtx:9997/v3/paths/list')
    if not api.endswith('/v3/paths/list') and not api.endswith('/v3/paths/list/'):
        api = api.rstrip('/') + '/v3/paths/list'
    return api

def read_outputs(path='/outputs/outputs.txt'):
    outs = []
    if not os.path.exists(path):
        return outs
    content = read_file_robust(path)
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            name, url = line.split('=', 1)
            url = url.strip()
            # Автоматическая корректировка отображения при отсутствии схемы
            if '://' not in url:
                url = 'rtmp://' + url
            outs.append({'name': name.strip(), 'url': url})
    return outs

def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if session.get('admin'):
            return f(*a, **kw)
        return redirect(url_for('login'))
    return wrapped

@app.route('/')
def index():
    cfg = load_config()
    api = get_mediamtx_api_url(cfg)
    items = []
    try:
        r = requests.get(api, timeout=2)
        items = r.json().get('items', [])
    except Exception:
        items = []

    current_mode = None
    try:
        if os.path.exists(CONTROL_PATH):
            current_mode = open(CONTROL_PATH, 'r').read().strip()
    except Exception:
        current_mode = None

    manual = None
    if os.path.exists(MANUAL_PATH):
        try:
            manual = open(MANUAL_PATH, 'r').read().strip()
        except Exception:
            manual = None

    admin_pwd_set = bool(get_ui_value(cfg, 'admin_password'))
    return render_template('index.html', items=items, current_mode=current_mode, manual=manual, admin_pwd_set=admin_pwd_set)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.form
    pwd = data.get('password', '')
    cfg = load_config()
    admin_pwd = get_ui_value(cfg, 'admin_password')
    if not admin_pwd:
        return 'Admin password not set', 500
    if hashlib.sha256(pwd.encode()).hexdigest() == hashlib.sha256(admin_pwd.encode()).hexdigest():
        session['admin'] = True
        return redirect(url_for('admin'))
    return 'Invalid', 403

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/api/force', methods=['POST'])
def api_force():
    cfg = load_config()
    admin_pwd = get_ui_value(cfg, 'admin_password')
    if admin_pwd and not session.get('admin'):
        return jsonify({'ok': False, 'error': 'Unauthorized. Admin login required.'}), 403

    data = request.json or {}
    mode = data.get('mode')
    if mode not in ('main', 'backup', 'stop', 'auto'):
        return jsonify({'ok': False, 'error': 'invalid mode'}), 400
    try:
        with open(MANUAL_PATH, 'w', encoding='utf-8') as f:
            f.write(mode)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/status')
def api_status():
    cfg = load_config()
    api = get_mediamtx_api_url(cfg)
    try:
        r = requests.get(api, timeout=2)
        items = r.json().get('items', [])
    except Exception:
        items = []
    current_mode = None
    if os.path.exists(CONTROL_PATH):
        try:
            current_mode = open(CONTROL_PATH, 'r').read().strip()
        except Exception:
            current_mode = None
    manual = None
    if os.path.exists(MANUAL_PATH):
        try:
            manual = open(MANUAL_PATH, 'r').read().strip()
        except Exception:
            manual = None
    return jsonify({'items': items, 'current_mode': current_mode, 'manual': manual})

@app.route('/api/outputs')
def api_outputs():
    outs = read_outputs('/outputs/outputs.txt')
    return jsonify({'outputs': outs})

@app.route('/api/logs')
def api_logs():
    path = '/data/ffmpeg.log'
    if not os.path.exists(path):
        return jsonify({'ok': False, 'error': 'log not found'}), 404
    try:
        n = int(request.args.get('n', '200'))
    except Exception:
        n = 200
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-n:]
    return jsonify({'ok': True, 'lines': lines})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    cfg = load_config()
    token = get_ui_value(cfg, 'admin_token')
    
    if not session.get('admin'):
        if token:
            header = request.headers.get('X-Admin-Token')
            if header != token:
                return jsonify({'ok': False, 'error': 'missing or invalid admin token'}), 403

    if _docker_available:
        try:
            client = docker.from_env()
            ctr = None
            try:
                ctr = client.containers.get('ffmpeg')
            except Exception:
                for c in client.containers.list(all=True):
                    if c.name == 'ffmpeg' or c.name.endswith('_ffmpeg'):
                        ctr = c
                        break
            if not ctr:
                return jsonify({'ok': False, 'error': 'ffmpeg container not found via Docker'}), 404
            ctr.restart(timeout=10)
            return jsonify({'ok': True})
        except Exception as e:
            print(f"Docker restart failed: {e}")

    try:
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write('stop')
        time.sleep(1)
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write('main')
        return jsonify({'ok': True, 'fallback': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@socketio.on('get_outputs')
def ws_get_outputs():
    outs = read_outputs('/outputs/outputs.txt')
    emit('outputs', {'outputs': outs})

@socketio.on('tail_logs')
def ws_tail_logs():
    path = '/data/ffmpeg.log'
    if not os.path.exists(path):
        emit('logs', {'lines': ['log not found\n']})
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-200:]
    emit('logs', {'lines': lines})

@socketio.on('restart')
def ws_restart(payload):
    if not session.get('admin'):
        emit('restart_response', {'ok': False, 'error': 'not authorized'})
        return
    if _docker_available:
        try:
            client = docker.from_env()
            ctr = None
            try:
                ctr = client.containers.get('ffmpeg')
            except Exception:
                for c in client.containers.list(all=True):
                    if c.name == 'ffmpeg' or c.name.endswith('_ffmpeg'):
                        ctr = c
                        break
            if ctr:
                ctr.restart(timeout=10)
                emit('restart_response', {'ok': True})
                return
        except Exception as e:
            print('docker restart failed', e)
    try:
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write('stop')
        time.sleep(1)
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write('main')
        emit('restart_response', {'ok': True, 'fallback': True})
    except Exception as e:
        emit('restart_response', {'ok': False, 'error': str(e)})

@socketio.on('force')
def ws_force(data):
    mode = data.get('mode')
    if not session.get('admin'):
        emit('force_response', {'ok': False, 'error': 'not authorized'})
        return
    try:
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write(mode)
        emit('force_response', {'ok': True})
    except Exception as e:
        emit('force_response', {'ok': False, 'error': str(e)})

# Eventlet-compatible background worker to push live logs
def tail_logs_bg():
    path = '/data/ffmpeg.log'
    last_pos = 0
    if os.path.exists(path):
        last_pos = os.path.getsize(path)
    while True:
        socketio.sleep(0.5)
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                if size < last_pos:
                    last_pos = 0
                if size > last_pos:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_pos)
                        new_lines = f.readlines()
                        last_pos = f.tell()
                        if new_lines:
                            socketio.emit('log_lines', {'lines': new_lines})
            except Exception:
                pass

if __name__ == '__main__':
    socketio.start_background_task(tail_logs_bg)
    socketio.run(app, host='0.0.0.0', port=8080)
