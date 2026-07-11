# restream-stack

Lightweight restreaming stack using MediaMTX, FFmpeg and a Watchdog.

Structure:

 - `docker-compose.yml` - services: mediamtx, ffmpeg, watchdog
 - `mediamtx/mediamtx.yml` - minimal MediaMTX configuration
 - `ffmpeg/` - Dockerfile and scripts to run main/backup ffmpeg
 - `watchdog/` - Dockerfile and `watchdog.py` that polls MediaMTX and switches modes
 - `outputs/outputs.txt` - list of destination RTMP endpoints (name=url)

Usage:

1. Edit `outputs/outputs.txt` with your RTMP destinations.
2. Place an offline video at `ffmpeg/offline.mp4` if you want a custom backup.
3. Run:

```bash
docker compose up -d --build
```

Watchdog will poll MediaMTX API and write `/data/control` to instruct the `ffmpeg` container to run `main` or `backup`.

Web UI:

 - A lightweight web UI is available at `http://localhost:8080` (service `ui`). It shows MediaMTX status and allows forcing `main`/`backup`/`stop` or resuming automatic mode.

Manual override:

 - Creating `/data/manual_mode` with value `main`/`backup`/`stop` forces that mode until you write `auto` or remove the file. The UI provides buttons for this.
