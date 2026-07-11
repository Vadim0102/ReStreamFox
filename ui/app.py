from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import requests
import yaml
import os
import time
import hashlib
from functools import wraps

# docker SDK optional
try:
    import docker
    _docker_available = True
except Exception:
    _docker_available = False

app = Flask(__name__)
CONFIG_PATH = '/app/config.yml'
MANUAL_PATH = '/data/manual_mode'
CONTROL_PATH = '/data/control'

# load config for secret
cfg0 = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH,'r',encoding='utf-8') as f:
        cfg0 = yaml.safe_load(f) or {}

app.secret_key = cfg0.get('ui_secret','change_this_secret')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


def read_outputs(path='/outputs/outputs.txt'):
    outs = []
    if not os.path.exists(path):
        return outs
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                name, url = line.split('=',1)
                outs.append({'name': name.strip(), 'url': url.strip()})
    return outs

@app.route('/')
def index():
    cfg = load_config()
    # try mediaMTX API
    api = cfg.get('mediamtx_api', 'http://mediamtx:9997/v3/paths/list')
    items = []
    try:
        r = requests.get(api, timeout=2)
        items = r.json().get('items', [])
    except Exception:
        items = []

    current_mode = None
    try:
        if os.path.exists(CONTROL_PATH):
            current_mode = open(CONTROL_PATH,'r').read().strip()
    except Exception:
        current_mode = None

    manual = None
    if os.path.exists(MANUAL_PATH):
        try:
            manual = open(MANUAL_PATH,'r').read().strip()
        except Exception:
            manual = None

    return render_template('index.html', items=items, current_mode=current_mode, manual=manual)


def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if session.get('admin'):
            return f(*a, **kw)
        return redirect(url_for('login'))
    return wrapped


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.form
    pwd = data.get('password','')
    cfg = load_config()
    admin_pwd = cfg.get('ui_admin_password')
    if not admin_pwd:
        return 'Admin password not set', 500
    # compare hashes to avoid plaintext issues
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
    data = request.json or {}
    mode = data.get('mode')
    if mode not in ('main','backup','stop','auto'):
        return jsonify({'ok': False, 'error': 'invalid mode'}), 400
    try:
        with open(MANUAL_PATH, 'w', encoding='utf-8') as f:
            f.write(mode)
        # if mode is 'auto', watchdog will clear it and resume auto
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/status')
def api_status():
    cfg = load_config()
    api = cfg.get('mediamtx_api', 'http://mediamtx:9997/v3/paths/list')
    try:
        r = requests.get(api, timeout=2)
        items = r.json().get('items', [])
    except Exception:
        items = []
    current_mode = None
    if os.path.exists(CONTROL_PATH):
        try:
            current_mode = open(CONTROL_PATH,'r').read().strip()
        except Exception:
            current_mode = None
    manual = None
    if os.path.exists(MANUAL_PATH):
        try:
            manual = open(MANUAL_PATH,'r').read().strip()
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
    # tail last n lines
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-n:]
    return jsonify({'ok': True, 'lines': lines})


@app.route('/api/restart', methods=['POST'])
def api_restart():
    # Try to restart ffmpeg container via Docker socket if available
    # require admin token if configured in config.yml
    cfg = load_config()
    token = cfg.get('ui_admin_token')
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
                # try by name prefix
                for c in client.containers.list(all=True):
                    if c.name == 'ffmpeg' or c.name.endswith('_ffmpeg'):
                        ctr = c
                        break
            if not ctr:
                return jsonify({'ok': False, 'error': 'ffmpeg container not found via Docker'}), 404
            ctr.restart(timeout=10)
            return jsonify({'ok': True})
        except Exception as e:
            # fall through to fallback
            print(f"Docker restart failed: {e}")

    # Fallback: write manual_mode stop then main sequence
    try:
        with open('/data/manual_mode', 'w', encoding='utf-8') as f:
            f.write('stop')
        # after a short pause, request main
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
    with open(path,'r',encoding='utf-8',errors='ignore') as f:
        lines = f.readlines()[-200:]
    emit('logs', {'lines': lines})


@socketio.on('restart')
def ws_restart(payload):
    # require admin session
    if not session.get('admin'):
        emit('restart_response', {'ok': False, 'error': 'not authorized'})
        return
    # try docker
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
    # fallback
    try:
        with open('/data/manual_mode','w',encoding='utf-8') as f:
            f.write('stop')
        time.sleep(1)
        with open('/data/manual_mode','w',encoding='utf-8') as f:
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
        with open('/data/manual_mode','w',encoding='utf-8') as f:
            f.write(mode)
        emit('force_response', {'ok': True})
    except Exception as e:
        emit('force_response', {'ok': False, 'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
