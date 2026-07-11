# ReStreamFox — Documentation (English)

## Overview
ReStreamFox is a small open-source stack to receive a live stream and restream it to multiple destinations using a single FFmpeg encoder instance. The stack uses MediaMTX as the ingest point, a dedicated FFmpeg container for transcode and distribution, and a Watchdog service that monitors MediaMTX and controls FFmpeg.

Architecture
- MediaMTX: receives streams via SRT/RTMP/RTSP/WebRTC. Minimal configuration.
- Watchdog: polls MediaMTX API and controls FFmpeg via control files in `/data`.
- FFmpeg: runs main transcode (reads from MediaMTX RTSP) or backup loop (offline video) and sends to outputs using `tee`.
- UI: Flask + Socket.IO admin UI to view status, logs and control the stack.

## Quick Start
1. Edit `outputs/outputs.txt` with your destination RTMP URLs in the format `name=rtmp://...`.
2. Set secrets in `config.yml`:
   - `ui_admin_password`: a strong password for admins.
   - `ui_secret`: Flask secret key for sessions.
3. (Optional) Mount the Docker socket into the UI container if you want direct container restarts (security risk):

```yaml
services:
  ui:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

4. Build and run:

```bash
docker compose up -d --build
```

Open UI: `http://localhost:8080` for public UI; visit `/admin` to login and access admin controls.

## Files and configuration
- `docker-compose.yml` — orchestrates `mediamtx`, `ffmpeg`, `watchdog`, `ui`.
- `mediamtx/mediamtx.yml` — minimal configuration for MediaMTX.
- `ffmpeg/` — Dockerfile and scripts. `entrypoint.sh` reads `/data/control` and `/data/ffmpeg.env` to decide mode.
- `watchdog/` — Python app that polls MediaMTX and writes control files. Validates `config.yml` and `outputs/outputs.txt` on startup.
- `outputs/outputs.txt` — list of destinations (one per line): `name=rtmp://...`.
- `config.yml` — main YAML config. Important keys:
  - `mediamtx_api` — URL to MediaMTX API.
  - `path_name` — path to check (default `live`).
  - `check_interval` — seconds between checks.
  - `backup.enabled` and `backup.file` — backup loop settings.
  - `ffmpeg.video`, `ffmpeg.audio` — overrides used to generate `/data/ffmpeg.env`.
  - `ui_admin_password` — admin login password (plaintext in file by default; use secrets manager in prod).
  - `ui_secret` — Flask secret for sessions.

## Security
- Do not commit `config.yml` with production secrets. Replace with environment variables or mount secrets at runtime.
- Mounting the Docker socket is powerful and risky. Use a socket-proxy with strict rules if exposing it to a web UI.

## Development
- Python services use `requirements.txt` files per service.
- To run `watchdog` locally outside Docker:
  - Create a virtualenv, install `watchdog/requirements.txt`, and run `python watchdog/watchdog.py`.

## CI
- GitHub Actions workflow builds Docker images (disabled push) and runs simple Python syntax checks.

## Troubleshooting
- `docker logs mediamtx` to check ingest.
- `docker logs ffmpeg` shows encoder output (or check `/data/ffmpeg.log`).
- `docker logs watchdog` for watchdog behavior.

*** End Patch