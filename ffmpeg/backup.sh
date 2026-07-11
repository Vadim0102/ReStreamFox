#!/bin/bash
set -euo pipefail

source /app/config.env || true

OFFLINE_FILE=${OFFLINE_FILE:-/app/offline.mp4}
if [ ! -f "$OFFLINE_FILE" ]; then
  echo "No offline file found at $OFFLINE_FILE" >&2
  # create a simple placeholder stream using color source if ffmpeg supports it
  ffmpeg -f lavfi -i color=size=1280x720:rate=25:color=black -t 10 -c:v libx264 /tmp/placeholder.mp4
  OFFLINE_FILE=/tmp/placeholder.mp4
fi

TEE_PARTS=()
while IFS= read -r line || [ -n "$line" ]; do
  line=$(echo "$line" | xargs)
  [ -z "$line" ] && continue
  name=${line%%=*}
  url=${line#*=}
  TEE_PARTS+=("[f=flv]$url")
done < /outputs/outputs.txt

TEE_JOINED=$(IFS='|'; echo "${TEE_PARTS[*]}")

echo "Starting backup loop from $OFFLINE_FILE -> $TEE_JOINED"

ffmpeg -stream_loop -1 -re -i "$OFFLINE_FILE" \
  -c:v ${VIDEO_CODEC:-libx264} -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
  -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
  -f tee "${TEE_JOINED}"
