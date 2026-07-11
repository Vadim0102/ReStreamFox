#!/bin/bash
set -e

# Парсинг кодека вещания напрямую из config.yml для синхронизации форматов заставки
INGEST_CODEC="h264"
if [ -f /app/config.yml ]; then
  if grep -qi "ingest_codec:.*h265" /app/config.yml; then
    INGEST_CODEC="h265"
  fi
fi

# 1. Генерация и оптимизация резервного файла на старте под формат OBS
# Мы генерируем файл заново при каждом запуске, чтобы он всегда соответствовал вашим настройкам кодека
IMG_FILE=""
for ext in png jpg jpeg webp; do
  if [ -f "/data/offline.${ext}" ]; then
    IMG_FILE="/data/offline.${ext}"
    break
  fi
done

if [ -n "$IMG_FILE" ]; then
  if [ "$INGEST_CODEC" = "h265" ]; then
    echo "Ingest codec is H.265. Generating H.265 (HEVC) fallback MP4 from static image..."
    ffmpeg -y -loop 1 -framerate 30 -i "$IMG_FILE" \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx265 -pix_fmt yuv420p -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  else
    echo "Ingest codec is H.264. Generating H.264 (AVC) fallback MP4 from static image..."
    ffmpeg -y -loop 1 -framerate 30 -i "$IMG_FILE" \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.0 -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  fi
else
  if [ "$INGEST_CODEC" = "h265" ]; then
    echo "No image found. Generating H.265 (HEVC) black screen fallback..."
    ffmpeg -y -f lavfi -i color=size=1280x720:rate=30:color=black \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx265 -pix_fmt yuv420p -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  else
    echo "No image found. Generating H.264 (AVC) black screen fallback..."
    ffmpeg -y -f lavfi -i color=size=1280x720:rate=30:color=black \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.0 -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  fi
fi

# 2. Функция определения формата для пушеров
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
    echo "flv"
  fi
}

# 3. Запуск вечно работающего мастер-транскодера в фоне
echo "Starting Master 24/7 Encoder..."
(
  while true; do
    echo "[Encoder] Launching transcode..."
    /app/transcode.sh > /data/ffmpeg.log 2>&1 || true
    echo "[Encoder] Process exited. Restarting in 2 seconds..."
    sleep 2
  done
) &

# Даем транскодеру 3 секунды на инициализацию потока /transcoded
sleep 3

# 4. Запуск изолированных фоновых пушеров на каждую платформу
echo "Starting isolated distribution pushers..."
while IFS= read -r line || [ -n "$line" ]; do
  line=$(echo "$line" | xargs)
  [ -z "$line" ] && continue
  [[ "$line" == \#* ]] && continue
  name=${line%%=*}
  url=${line#*=}
  
  if [[ ! "$url" =~ ^[a-zA-Z0-9]+:// ]]; then
    url="rtmp://$url"
  fi
  
  fmt=$(get_muxer_format "$url")
  
  (
    while true; do
      echo "[Pusher:$name] Streaming to $url..."
      ffmpeg -fflags nobuffer -rtsp_transport tcp -i "rtsp://mediamtx:8554/transcoded" \
        -c copy -f "$fmt" "$url" > "/data/ffmpeg_${name}.log" 2>&1 || true
      echo "[Pusher:$name] Disconnected. Reconnecting in 5 seconds..."
      sleep 5
    done
  ) &
done < /outputs/outputs.txt

# Ожидание фоновых процессов, чтобы контейнер не завершал работу
wait
