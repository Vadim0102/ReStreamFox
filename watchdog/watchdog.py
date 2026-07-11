import time
import requests
import yaml
import os

CONFIG_PATH = '/app/config.yml'
CONTROL_FILE = '/data/control'
FF_MODE_FILE = '/data/ffmpeg.mode'
FF_ENV_FILE = '/data/ffmpeg.env'

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
            # validate
            validate_config(cfg)
            return cfg
    return {}


def validate_config(cfg):
    # Strict schema for important fields. If invalid, exit to avoid misbehavior.
    schema = {
        "type": "object",
        "required": ["mediamtx_api", "path_name", "check_interval"],
        "properties": {
            "mediamtx_api": {"type": "string"},
            "path_name": {"type": "string"},
            "check_interval": {"type": "number"},
            "backup": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "file": {"type": "string"}
                },
                "required": ["enabled"]
            },
            "ffmpeg": {
                "type": "object",
                "properties": {
                    "video": {
                        "type": "object",
                        "properties": {
                            "codec": {"type": "string"},
                            "bitrate": {"type": "string"},
                            "preset": {"type": "string"}
                        }
                    },
                    "audio": {
                        "type": "object",
                        "properties": {
                            "codec": {"type": "string"},
                            "bitrate": {"type": "string"}
                        }
                    }
                }
            },
            "ui_admin_token": {"type": "string"}
        }
    }
    try:
        from jsonschema import validate, ValidationError
        validate(instance=cfg, schema=schema)
    except Exception as e:
        print(f"Config validation error: {e}")
        print("Configuration invalid — watchdog exiting to avoid unsafe behavior.")
        import sys
        sys.exit(1)

def mediamtx_paths(url):
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return r.json().get('items', [])
    except Exception:
        return []

def write_control(mode):
    if mode is None:
        if os.path.exists(CONTROL_FILE):
            os.remove(CONTROL_FILE)
        return
    with open(CONTROL_FILE, 'w', encoding='utf-8') as f:
        f.write(mode)

def generate_ffmpeg_env(cfg):
    ff = cfg.get('ffmpeg', {}) or {}
    lines = []
    # map common video/audio keys
    v = ff.get('video', {}) or {}
    a = ff.get('audio', {}) or {}
    if 'codec' in v:
        lines.append(f"VIDEO_CODEC={v.get('codec')}")
    if 'bitrate' in v:
        lines.append(f"BITRATE={v.get('bitrate')}")
    if 'preset' in v:
        lines.append(f"PRESET={v.get('preset')}")
    if 'tune' in v:
        lines.append(f"TUNE={v.get('tune')}")
    if 'pix_fmt' in v:
        lines.append(f"PIX_FMT={v.get('pix_fmt')}")
    if 'gop' in v:
        lines.append(f"GOP={v.get('gop')}")

    if 'codec' in a:
        lines.append(f"AUDIO_CODEC={a.get('codec')}")
    if 'bitrate' in a:
        lines.append(f"AUDIO_BITRATE={a.get('bitrate')}")

    # backup file
    backup = cfg.get('backup', {}) or {}
    if 'file' in backup:
        lines.append(f"OFFLINE_FILE={backup.get('file')}")

    if lines:
        with open(FF_ENV_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    else:
        if os.path.exists(FF_ENV_FILE):
            os.remove(FF_ENV_FILE)

def validate_outputs_file(path='/outputs/outputs.txt'):
    # Ensure outputs file exists and lines look like name=rtmp://...
    if not os.path.exists(path):
        print(f"Outputs file {path} not found — exiting.")
        import sys
        sys.exit(1)
    bad = []
    with open(path, 'r', encoding='utf-8') as f:
        for idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                bad.append((idx, line))
            else:
                name, url = line.split('=',1)
                url = url.strip()
                if not (url.startswith('rtmp://') or url.startswith('rtmps://')):
                    bad.append((idx, line))
    if bad:
        print('Invalid outputs in outputs/outputs.txt:')
        for i,l in bad:
            print(f"  line {i}: {l}")
        print('Please fix outputs/outputs.txt — exiting.')
        import sys
        sys.exit(1)

def read_current_mode():
    if os.path.exists(FF_MODE_FILE):
        return open(FF_MODE_FILE,'r',encoding='utf-8').read().strip()
    return None


def read_manual_override():
    # manual override file contains 'main'|'backup'|'stop' or 'auto' to clear
    manual = '/data/manual_mode'
    if os.path.exists(manual):
        try:
            return open(manual,'r',encoding='utf-8').read().strip()
        except Exception:
            return None
    return None

def main():
    cfg = load_config()
    # validate outputs file exists and has valid entries
    validate_outputs_file('/outputs/outputs.txt')
    api = cfg.get('mediamtx_api', 'http://mediamtx:9997/v3/paths/list')
    path_name = cfg.get('path_name', 'live')
    check_interval = cfg.get('check_interval', 1)

    last_mode = None
    while True:
        items = mediamtx_paths(api)
        ready = False
        for it in items:
            if it.get('name') == path_name:
                ready = bool(it.get('ready'))
                break

        if ready:
            # stream present
            desired = 'main'
        else:
            # stream absent
            desired = 'backup' if cfg.get('backup', {}).get('enabled', True) else None

        # generate ffmpeg env overrides from config
        generate_ffmpeg_env(cfg)

        # respect manual override if present
        manual = read_manual_override()
        if manual:
            if manual == 'auto':
                # clear manual override and continue automatic behavior
                try:
                    os.remove('/data/manual_mode')
                except Exception:
                    pass
            else:
                # honor manual instruction
                write_control(manual)
                time.sleep(check_interval)
                continue

        current = read_current_mode()
        if desired != current:
            if desired is None:
                write_control('stop')
            else:
                write_control(desired)
            last_mode = desired

        time.sleep(check_interval)

if __name__ == '__main__':
    main()
