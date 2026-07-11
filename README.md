# ReStreamFox 🦊

A lightweight, robust, self-hosted multi-streaming stack powered by **MediaMTX**, **FFmpeg**, and a Python-based **Watchdog**. It allows you to ingest a single live stream from OBS/vMix (via RTMP, SRT, RTSP, or WebRTC) and distribute it to multiple platforms simultaneously (e.g., YouTube, Twitch, Kick) with automatic failover to a looping offline video or a static backup image.

---

## Features

- **Single Transcoding Instance**: Encodes the source stream once using FFmpeg and multiplexes it to multiple target platforms using the efficient `tee` muxer.
- **Protocol Versatility**: Supports both standard RTMP and secure RTMPS (required for Kick, Facebook Live) as well as SRT and UDP.
- **Failover Mode**: Automatically switches to an offline fallback loop if the primary source stream goes offline.
- **Static Image Support**: Accepts static image files (`.png`, `.jpg`, `.jpeg`, `.webp`) as a backup screen, complete with synthesized silent audio to satisfy platform ingest requirements.
- **Web Administration Panel**: Built-in Flask + Socket.IO dashboard to monitor live status, view real-time FFmpeg logs, force manual streaming modes, and perform safe restarts.

---

## Quick Start

### 1. Configure Destinations
Open `outputs/outputs.txt` and define your target stream endpoints in `name=url` format (one per line):
```text
youtube=rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY
kick=rtmps://fa6bc2412803.global-contribute.live-video.net:443/app/YOUR_STREAM_KEY
twitch=rtmp://live.twitch.tv/app/YOUR_STREAM_KEY
```

### 2. Configure Settings
Copy the example configuration file:
```bash
cp watchdog/config.example.yml config.yml
```
Edit `config.yml` to define your credentials, bitrates, and paths.

### 3. Provide Backup Media (Optional)
If you wish to use a custom fallback stream, place an `offline.mp4` video or `offline.png` image inside the `data/` directory and ensure the configuration points to it:
```yaml
backup:
  enabled: true
  file: "/data/offline.png"
```

### 4. Build and Start
```bash
docker compose up -d --build
```
Access the public dashboard at `http://localhost:8080`. To access administrative commands, go to `http://localhost:8080/admin` and log in with your configured admin password.

---

## Security Guidelines

- **Protect Secrets**: Never commit `config.yml` or `outputs.txt` containing raw streaming keys to a public repository. They are added to `.gitignore` by default.
- **Docker Socket Permissions**: Mounting the Docker socket (`/var/run/docker.sock`) inside the UI container allows restarting containers but exposes root-equivalent access to the host. If security is a priority, do not mount the socket; the UI will seamlessly switch to a secure fallback mechanism (using internal control files via watchdog).

Refer to [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for full architecture details and configuration reference.
