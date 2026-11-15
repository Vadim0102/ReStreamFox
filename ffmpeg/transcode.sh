#!/bin/bash
set -euo pipefail

source /app/config.env || true
if [ -f /data/ffmpeg.env ]; then
  source /data/ffmpeg.env
fi

INPUT_URL="rtsp://mediamtx:8554/live"
OUTPUT_URL="rtsp://mediamtx:8554/transcoded"

# Конфигурация
FRAMERATE=${FRAMERATE:-60}
GOP=${GOP:-$((FRAMERATE * 2))}
KEYINT_MIN=${KEYINT_MIN:-$GOP}
RESOLUTION=${RESOLUTION:-1920x1080}
BITRATE=${BITRATE:-6000k}

SCALE_FILTER="scale=${RESOLUTION//x/:},setsar=1:1,setdar=16/9"

# Обработка параметра tune (если пустой в config.yml — параметр не передается)
TUNE_ARG=""
if [ -n "${TUNE:-}" ]; then
  TUNE_ARG="-tune $TUNE"
fi

X264_PARAMS_ARG=()
if [ "${VIDEO_CODEC:-libx264}" = "libx264" ]; then
  X264_PARAMS_ARG=(-x264-params 'nal-hrd=cbr:force-cfr=1:open-gop=0')
fi

echo "Master Encoder: Transcoding $INPUT_URL -> $OUTPUT_URL (Resolution: $RESOLUTION, FPS: $FRAMERATE, GOP: $GOP)"

exec ffmpeg -fflags nobuffer -rtsp_transport tcp -flags +low_delay+global_header -i "$INPUT_URL" \
  -map 0:v -map 0:a \
  -vsync cfr -r "$FRAMERATE" \
  -vf "$SCALE_FILTER" \
  -c:v "${VIDEO_CODEC:-libx264}" \
  -preset ${PRESET:-superfast} $TUNE_ARG \
  -pix_fmt ${PIX_FMT:-yuv420p} -profile:v ${PROFILE:-high} -level ${LEVEL:-4.2} \
  -g "$GOP" -keyint_min "$KEYINT_MIN" -sc_threshold 0 \
  -b:v "$BITRATE" -maxrate "$BITRATE" -bufsize "$BITRATE" \
  "${X264_PARAMS_ARG[@]}" \
  -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
  -rtsp_transport tcp -f rtsp "$OUTPUT_URL"
