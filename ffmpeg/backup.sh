#!/bin/bash
set -euo pipefail

source /app/config.env || true
if [ -f /data/ffmpeg.env ]; then
  source /data/ffmpeg.env
fi

OFFLINE_FILE=${OFFLINE_FILE:-/app/offline.mp4}

if [ ! -f "$OFFLINE_FILE" ]; then
  echo "No offline file found at $OFFLINE_FILE. Generating fallback placeholder..." >&2
  # Generate video with black screen AND silent audio to prevent AAC encoding crash
  ffmpeg -f lavfi -i color=size=1280x720:rate=25:color=black \
         -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
         -t 10 -c:v libx264 -c:a aac -shortest /tmp/placeholder.mp4
  OFFLINE_FILE=/tmp/placeholder.mp4
fi

# Helper function to detect correct format for ffmpeg tee muxer
get_muxer_format() {
  local url="$1"
  if [[ "$url" =~ ^rtmps?:// ]]; then
    echo "flv"
  elif [[ "$url" =~ ^srts?:// ]]; then
    echo "mpegts"
  elif [[ "$url" =~ ^udps?:// ]]; then
    echo "mpegts"
  elif [[ "$url" =~ ^rtsp:// ]]; then
    echo "rtsp"
  else
    echo "flv" # default fallback
  fi
}

TEE_PARTS=()
while IFS= read -r line || [ -n "$line" ]; do
  line=$(echo "$line" | xargs)
  [ -z "$line" ] && continue
  [[ "$line" == \#* ]] && continue
  name=${line%%=*}
  url=${line#*=}
  fmt=$(get_muxer_format "$url")
  TEE_PARTS+=("[f=$fmt]$url")
done < /outputs/outputs.txt

if [ ${#TEE_PARTS[@]} -eq 0 ]; then
  echo "No valid output stream destinations found in /outputs/outputs.txt. Exiting." >&2
  exit 1
fi

TEE_JOINED=$(IFS='|'; echo "${TEE_PARTS[*]}")

# Check if OFFLINE_FILE is a static image
if [[ "$OFFLINE_FILE" =~ \.(png|jpg|jpeg|webp)$ ]]; then
  echo "Starting backup loop from static image $OFFLINE_FILE -> $TEE_JOINED"
  # Используем -map 0:v (видео из картинки) и -map 1:a (аудио из anullsrc)
  exec ffmpeg -re -loop 1 -framerate 25 -i "$OFFLINE_FILE" \
    -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
    -map 0:v -map 1:a \
    -c:v ${VIDEO_CODEC:-libx264} -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
    -pix_fmt ${PIX_FMT:-yuv420p} \
    -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
    -f tee "${TEE_JOINED}"
else
  echo "Starting backup loop from video file $OFFLINE_FILE -> $TEE_JOINED"
  # Используем явный маппинг -map 0:v -map 0:a для видеофайла
  exec ffmpeg -stream_loop -1 -re -i "$OFFLINE_FILE" \
    -map 0:v -map 0:a \
    -c:v ${VIDEO_CODEC:-libx264} -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
    -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
    -f tee "${TEE_JOINED}"
fi
