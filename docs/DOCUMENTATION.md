# ReStreamFox — Technical Documentation

## Architecture Overview

ReStreamFox is a microservices-based streaming system orchestrated via Docker Compose. The stack consists of four primary components:

```
                  ┌──────────────┐
                  │ OBS / Source │
                  └──────┬───────┘
                         │ (RTMP/SRT with Auth)
                         ▼
                  ┌──────────────┐
                  │   MediaMTX   │◄──────────────┐
                  └──────┬───────┘               │
                         │ (RTSP)                │ (API Poll)
                         ▼                       │
   ┌──────────┐   ┌──────────────┐   ┌───────────┴──┐
   │ Outputs  ├──►│    FFmpeg    │◄──┤   Watchdog   │
   │  (.txt)  │   │  Transcoder  │   │  (Control)   │
   └──────────┘   └──────────────┘   └──────────────┘
                         │ (tee muxer)
                         ▼
             [ YouTube / Twitch / Kick ]
```

1. **MediaMTX**: Serves as the ingest server, accepting incoming streams via RTMP, RTMPS, SRT, RTSP, or WebRTC.
2. **Watchdog**: A lightweight Python daemon that monitors the MediaMTX API (`/v3/paths/list`). When the stream goes online, it instructs FFmpeg to transcode the feed. When it goes offline, it automatically switches FFmpeg to fallback loop mode.
3. **FFmpeg**: The transcoding engine. It runs in a controller-loop (`entrypoint.sh`), initiating `transcode.sh` or `backup.sh` based on signals from the watchdog. It uses the `tee` muxer to stream to multiple destinations concurrently.
4. **UI**: A web interface developed in Flask and Socket.IO. Provides public status monitoring, API configurations, and an authenticated administrative panel (`/admin`) with real-time log streaming.

---

## Configuration Reference (`config.yml`)

The root configuration schema is evaluated by the watchdog during container startup.

| Section | Key | Type | Description |
| :--- | :--- | :--- | :--- |
| - | `mediamtx_api` | String | The HTTP endpoint of your MediaMTX API (e.g. `http://mediamtx:9997`). |
| - | `path_name` | String | Ingest path name to monitor (default is `live`). |
| - | `check_interval` | Integer | Interval in seconds between watchdog checks. |
| `backup` | `enabled` | Boolean | Activates the fallback mode if the main ingest is offline. |
| `backup` | `file` | String | Path to backup video (`.mp4`) or image (`.png`/`.jpg`). |
| `ffmpeg.video` | `codec` | String | FFmpeg video codec parameter (e.g., `libx264`). |
| `ffmpeg.video` | `bitrate` | String | Video encoding bitrate (e.g., `4500k`). |
| `ffmpeg.video` | `gop` | Integer | Group of Pictures size (GOP) for stream alignment. |
| `ffmpeg.audio` | `codec` | String | FFmpeg audio codec parameter (e.g., `aac`). |
| `ffmpeg.audio` | `bitrate` | String | Audio encoding bitrate (e.g., `128k`). |
| `ui` | `admin_password` | String | Plaintext password used to access `/admin`. |
| `ui` | `admin_token` | String | Secure token header required for API actions. |
| `ui` | `secret` | String | Secret key for secure Flask session cookies. |

---

## Protocol Multi-plexing

The stack utilizes FFmpeg's `tee` muxer which enables concurrent streaming using a single encoder pass. Destination protocols are parsed automatically inside bash scripts:

* **RTMP / RTMPS**: Automatically routed using the `flv` format wrapper. Perfect for standard RTMP ingest platforms and secure endpoints like Kick (`rtmps://`).
* **SRT / UDP**: Routed using the `mpegts` format wrapper, which provides low-latency delivery over unstable network connections.

---

## Ingest Security (Auth)

To protect your server from unauthorized broadcasters, the `live` path requires publication credentials.

This is configured in `mediamtx/mediamtx.yml`:
```yaml
paths:
  live:
    publishUser: "streamer"
    publishPass: "secure_ingest_key_here"
```

Because `publishUser` and `publishPass` only secure the `publish` action, the internal FFmpeg transcoder can pull RTSP without credentials locally.

To stream from OBS Studio, use:
* **SRT**: `srt://<IP>:8890?streamid=publish:live:streamer:secure_ingest_key_here`
* **RTMP**: `rtmp://<IP>:1935/live?user=streamer&pass=secure_ingest_key_here`

---

## Backup Fallback Engine

When the source stream disconnects, the watchdog triggers backup mode:
- **Video Fallback**: Loops the video file continuously.
- **Image Fallback**: Takes the static image, loops it, and integrates a synchronized virtual stereo silent audio channel (`anullsrc`), maintaining continuous sync on ingest endpoints.
