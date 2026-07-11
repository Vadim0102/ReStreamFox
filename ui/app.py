from flask import Flask, render_template, jsonify, request
import requests
import yaml
import os

app = Flask(__name__)
CONFIG_PATH = '/app/config.yml'
MANUAL_PATH = '/data/manual_mode'
CONTROL_PATH = '/data/control'

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
