# Beginner Guide — ReStreamFox

This guide walks a newcomer through getting ReStreamFox running locally with Docker.

Prerequisites

- A system with Docker and Docker Compose installed.
  - For Linux: follow https://docs.docker.com/engine/install/ and https://docs.docker.com/compose/install/
  - For Windows: install Docker Desktop.
- Basic terminal/shell skills (copy/paste commands).

Quick checklist

1. Clone the repository:

```bash
git clone https://github.com/Vadim0102/ReStreamFox.git
cd ReStreamFox
```

2. Edit `outputs/outputs.txt` and replace example RTMP targets with your real streaming keys and URLs.
   - Each line: `name=rtmp://server/app/STREAM_KEY`

3. (Optional) Put a test offline file `offline.mp4` into `data/` so the backup stream has content.

4. Set admin secrets in `config.yml` before running in production:
   - `ui_admin_password`: set a strong password for the admin UI.
   - `ui_secret`: a random secret for Flask sessions.

5. Start the stack with Docker Compose:

```bash
docker compose up -d --build
```

6. Open the public UI at `http://localhost:8080`. To access admin page, go to `http://localhost:8080/admin` and login with the `ui_admin_password` you set.

How it works (simple)

- Send your encoder (OBS) to MediaMTX (e.g., via SRT or RTMP) using address `srt://localhost:8890` or `rtmp://localhost:1935/live` depending on your setup.
- Watchdog checks MediaMTX API and switches `ffmpeg` to `main` mode when input is present, otherwise `backup` mode streams `offline.mp4` in a loop.
- `ffmpeg` reads destinations from `outputs/outputs.txt` and uses `tee` to send the one encoded output to multiple platforms.

Common commands

- View logs:

```bash
docker logs -f watchdog
docker logs -f ffmpeg
docker logs -f mediamtx
```

- Check MediaMTX API (see paths):

```bash
curl http://localhost:9997/v3/paths/list
```

- Manually force backup/main (admin UI) or create `/data/manual_mode` with content `backup` or `main`.

Troubleshooting

- If CI/build fails with `open Dockerfile: no such file or directory`, it's because each service Dockerfile is in its subfolder — the project CI has been updated to build per-service directories.
- If UI cannot restart ffmpeg automatically, ensure you've mounted Docker socket in `docker-compose.yml` (only for trusted hosts):

```yaml
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

Security notes

- Do not commit `config.yml` with real secrets to public repos. Use environment variables or Docker secrets in production.
- Mounting Docker socket into a web-facing container gives it root-equivalent control over the host — avoid or secure with a proxy.

If you want, I can create a small `docker-compose.override.yml` with example mounts and environment variables to make getting started even easier.

*** End Patch