#!/bash/sh
#!/bin/bash
set -euo pipefail

source /app/config.env || true
if [ -f /data/ffmpeg.env ]; then
  source /data/ffmpeg.env
fi

INPUT_URL="rtsp://mediamtx:8554/live"

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

# Build outputs tee string from /outputs/outputs.txt
TEE_PARTS=()
while IFS= read -r line || [ -n "$line" ]; do
  line=$(echo "$line" | xargs)
  [ -z "$line" ] && continue
  [[ "$line" == \#* ]] && continue
  name=${line%%=*}
  url=${line#*=}
  
  # Если протокол не указан явно, подставляем rtmp:// по умолчанию
  if [[ ! "$url" =~ ^[a-zA-Z0-9]+:// ]]; then
    url="rtmp://$url"
  fi
  
  fmt=$(get_muxer_format "$url")
  TEE_PARTS+=("[f=$fmt]$url")
done < /outputs/outputs.txt

if [ ${#TEE_PARTS[@]} -eq 0 ]; then
  echo "No valid output stream destinations found in /outputs/outputs.txt. Exiting." >&2
  exit 1
fi

TEE_JOINED=$(IFS='|'; echo "${TEE_PARTS[*]}")

echo "Starting main transcode from $INPUT_URL -> $TEE_JOINED"

exec ffmpeg -fflags nobuffer -flags low_delay -i "$INPUT_URL" \
  -c:v ${VIDEO_CODEC:-libx264} \
  -preset ${PRESET:-veryfast} -tune ${TUNE:-zerolatency} \
  -pix_fmt ${PIX_FMT:-yuv420p} -profile:v ${PROFILE:-high} -level ${LEVEL:-4.2} \
  -g ${GOP:-120} -keyint_min ${KEYINT_MIN:-120} \
  -b:v ${BITRATE:-6000k} -maxrate ${MAXRATE:-6000k} -bufsize ${BUFSIZE:-3000k} \
  -c:a ${AUDIO_CODEC:-aac} -b:a ${AUDIO_BITRATE:-192k} -ar ${AUDIO_RATE:-48000} \
  -f tee "${TEE_JOINED}"
