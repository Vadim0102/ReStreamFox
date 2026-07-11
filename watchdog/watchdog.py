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
    # Basic schema for important fields. Extend as needed.
    schema = {
        "type": "object",
        "properties": {
            "mediamtx_api": {"type": "string"},
            "path_name": {"type": "string"},
            "check_interval": {"type": "number"},
            "backup": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "file": {"type": "string"}
                }
            },
            "ffmpeg": {"type": "object"}
        }
    }
    try:
        from jsonschema import validate, ValidationError
        validate(instance=cfg, schema=schema)
    except Exception as e:
        print(f"Config validation error: {e}")
        # if validation fails, continue with defaults but warn
        # to be strict, you may sys.exit(1)

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
