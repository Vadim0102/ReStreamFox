#!/bin/bash
set -euo pipefail

source /app/config.env || true

INPUT_URL="rtsp://mediamtx:8554/live"

# Build outputs tee string from /outputs/outputs.txt
TEE_PARTS=()
while IFS= read -r line || [ -n "$line" ]; do
  line=$(echo "$line" | xargs)
  [ -z "$line" ] && continue
  name=${line%%=*}
  url=${line#*=}
  TEE_PARTS+=("[f=flv]$url")
done < /outputs/outputs.txt

TEE_JOINED=$(IFS='|'; echo "${TEE_PARTS[*]}")

echo "Starting main transcode from $INPUT_URL -> $TEE_JOINED"

ffmpeg -fflags nobuffer -flags low_delay -i "$INPUT_URL" \
  -c:v ${VIDEO_CODEC:-libx264} \
  -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
  -pix_fmt ${PIX_FMT:-yuv420p} -profile:v ${PROFILE:-high} -level ${LEVEL:-4.2} \
  -g ${GOP:-120} -keyint_min ${KEYINT_MIN:-120} \
  -b:v ${BITRATE:-6000k} -maxrate ${MAXRATE:-6000k} -bufsize ${BUFSIZE:-3000k} \
  -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
  -f tee "${TEE_JOINED}"
