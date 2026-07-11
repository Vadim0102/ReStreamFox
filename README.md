## Admin Page and Security

This project includes a Web UI with an admin page (`/admin`) that requires login. The admin page uses WebSocket (Socket.IO) to stream `ffmpeg` logs live and to send control commands (force mode, restart transcoder). Administrative actions require an admin password set in `config.yml` under `ui_admin_password` and the Flask `secret` under `ui_secret`.

Security notes

- Do not embed admin secrets in public repos. Use environment variables or a secrets manager in production.
- Mounting the Docker socket into UI (`/var/run/docker.sock`) grants powerful permissions to the UI container; prefer the fallback `manual_mode` approach or a controlled socket-proxy with hardened access.

See full documentation in `docs/DOCUMENTATION.md` for architecture, config reference, security guidance, and development notes.

Beginner guide

If you're new to Docker or streaming, read `docs/BEGINNER_GUIDE.md` — it explains step-by-step how to set up, configure `outputs/outputs.txt`, set admin secrets, and common troubleshooting steps (including the CI `Dockerfile not found` error and how we fixed it).

Configuration and runtime files

- Template: a build-time template lives at `watchdog/config.example.yml`. Copy it to `watchdog/config.yml` and edit before running, or keep a runtime `config.yml` outside the repository and mount it into containers.
- Do not commit secrets: `config.yml`, `outputs/outputs.txt` and `data/` are ignored by `.gitignore`.
- Recommended local override: create `docker-compose.override.yml` with mounts for `./runtime/config.yml:/app/config.yml:ro` and `./data:/data` for testing.

Quick start

1. Copy the example config and edit secrets:

```bash
cp watchdog/config.example.yml watchdog/config.yml
# edit watchdog/config.yml (set ui.admin_password, ui.secret, outputs path, etc.)
```

2. (Optional) Place an `offline.mp4` into `data/` for backup streaming.

3. Start the stack:

```bash
docker compose up -d --build
```

CI note

The GitHub Actions workflow was updated to build each service image from its own folder (`./ffmpeg`, `./watchdog`, `./ui`) so buildx finds each `Dockerfile` correctly.
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

Restarting transcoder (optional):

 - The UI can restart the `ffmpeg` container directly if you mount the Docker socket into the UI container. To enable this, uncomment the following line in `docker-compose.yml` under the `ui` service:

```yaml
		volumes:
			- /var/run/docker.sock:/var/run/docker.sock
```

 - If the Docker socket is not available, the UI uses a safe fallback: it writes `/data/manual_mode` with `stop` then `main` to force a restart cycle.

Security: admin token

 - To prevent unauthorized restarts, set `ui_admin_token` in `config.yml` to a strong secret. The UI will require the `X-Admin-Token` header to be present and matching the token when calling the `/api/restart` endpoint.

UI additions

 - The UI exposes `/api/outputs` (reads `outputs/outputs.txt`) and `/api/logs` (tails `/data/ffmpeg.log`). Use the buttons on the page to inspect outputs and logs.

Manual override:

 - Creating `/data/manual_mode` with value `main`/`backup`/`stop` forces that mode until you write `auto` or remove the file. The UI provides buttons for this.
