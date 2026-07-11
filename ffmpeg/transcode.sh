#!/bin/bash
set -euo pipefail

source /app/config.env || true
if [ -f /data/ffmpeg.env ]; then
  source /data/ffmpeg.env
fi

# Указываем имя контейнера "mediamtx" вместо сбоящего "localhost"
INPUT_URL="rtsp://mediamtx:8554/live"
OUTPUT_URL="rtsp://mediamtx:8554/transcoded"

# Конфигурация
FRAMERATE=${FRAMERATE:-60}
GOP=${GOP:-$((FRAMERATE * 2))}
KEYINT_MIN=${KEYINT_MIN:-$GOP}
RESOLUTION=${RESOLUTION:-1920x1080}

SCALE_FILTER="scale=${RESOLUTION//x/:},setsar=1:1,setdar=16/9"

echo "Master Encoder: Transcoding $INPUT_URL -> $OUTPUT_URL (Resolution: $RESOLUTION, FPS: $FRAMERATE, GOP: $GOP)"

# -rtsp_transport tcp принудительно заставляет FFmpeg работать по надежному протоколу TCP вместо сбойного в Docker UDP
exec ffmpeg -fflags nobuffer -rtsp_transport tcp -flags +low_delay+global_header -i "$INPUT_URL" \
  -map 0:v -map 0:a \
  -vsync cfr -r "$FRAMERATE" \
  -vf "$SCALE_FILTER" \
  -c:v ${VIDEO_CODEC:-libx264} \
  -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
  -pix_fmt ${PIX_FMT:-yuv420p} -profile:v ${PROFILE:-high} -level ${LEVEL:-4.2} \
  -g "$GOP" -keyint_min "$KEYINT_MIN" -sc_threshold 0 \
  -b:v ${BITRATE:-6000k} -maxrate ${MAXRATE:-6000k} -bufsize ${BUFSIZE:-3000k} \
  -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
  -rtsp_transport tcp -f rtsp "$OUTPUT_URL"
