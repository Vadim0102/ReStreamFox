#!/bin/bash
set -e

# 1. Генерация и оптимизация резервного файла на старте
# Если в /data нет готового offline.mp4, мы создаем его из картинки (png, jpg) или генерируем черный экран
if [ ! -f "/data/offline.mp4" ]; then
  IMG_FILE=""
  for ext in png jpg jpeg webp; do
    if [ -f "/data/offline.${ext}" ]; then
      IMG_FILE="/data/offline.${ext}"
      break
    fi
  done

  if [ -n "$IMG_FILE" ]; then
    echo "Found static image at $IMG_FILE. Compiling optimized fallback MP4..."
    ffmpeg -y -loop 1 -framerate 30 -i "$IMG_FILE" \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.0 -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  else
    echo "No offline media found. Generating a black screen fallback..."
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
  
  # Запуск изолированного подпроцесса в бесконечном цикле авторестарта
  (
    while true; do
      echo "[Pusher:$name] Streaming to $url..."
      # -c copy потребляет 0% процессора, просто пересылая готовый поток транскодера
      ffmpeg -fflags nobuffer -rtsp_transport tcp -i "rtsp://localhost:8554/transcoded" \
        -c copy -f "$fmt" "$url" > "/data/ffmpeg_${name}.log" 2>&1 || true
      echo "[Pusher:$name] Disconnected. Reconnecting in 5 seconds..."
      sleep 5
    done
  ) &
done < /outputs/outputs.txt

# Ожидание фоновых процессов, чтобы контейнер не завершал работу
wait
