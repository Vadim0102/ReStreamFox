#!/bin/bash
set -e

# Папка для отслеживания PID-процессов запущенных платформ
PID_DIR="/tmp/pushers"
mkdir -p "$PID_DIR"
rm -f "$PID_DIR"/*

# Парсинг входящего кодека из config.yml
INGEST_CODEC="h264"
if [ -f /app/config.yml ]; then
  if grep -qi "ingest_codec:.*h265" /app/config.yml; then
    INGEST_CODEC="h265"
  fi
fi

# 1. Генерация резервного файла под формат OBS
IMG_FILE=""
for ext in png jpg jpeg webp; do
  if [ -f "/data/offline.${ext}" ]; then
    IMG_FILE="/data/offline.${ext}"
    break
  fi
done

if [ -n "$IMG_FILE" ]; then
  if [ "$INGEST_CODEC" = "h265" ]; then
    echo "Generating H.265 fallback MP4..."
    ffmpeg -y -loop 1 -framerate 30 -i "$IMG_FILE" \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
      -t 5 -c:v libx265 -pix_fmt yuv420p -r 30 -g 60 -sc_threshold 0 \
      -c:a aac -ar 48000 -ac 2 -b:a 128k -movflags +faststart /data/offline.mp4
  else
    echo "Generating H.264 fallback MP4..."
    ffmpeg -y -loop 1 -framerate 30 -i "$IMG_FILE" \
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

# 3. Запуск вечно работающего мастер-транскодера в бесконечном цикле
echo "Starting Master 24/7 Encoder..."
(
  while true; do
    echo "[Encoder] Launching transcode..."
    /app/transcode.sh > /data/ffmpeg.log 2>&1 &
    ENCODER_PID=$!
    # Записываем PID транскодера, чтобы Watchdog мог его перезапустить при обновлении конфига
    echo $ENCODER_PID > /data/ffmpeg_encoder.pid
    wait $ENCODER_PID || true
    echo "[Encoder] Process exited. Restarting in 2 seconds..."
    sleep 2
  done
) &

sleep 3

# 4. Фоновый интерактивный диспетчер (Супервизор) пушеров
(
  echo "Supervisor: Dynamic outputs watcher started."
  while true; do
    # Читаем текущий список целевых платформ из outputs.txt
    declare -A active_targets
    while IFS= read -r line || [ -n "$line" ]; do
      line=$(echo "$line" | xargs)
      [ -z "$line" ] && continue
      [[ "$line" == \#* ]] && continue
      name=${line%%=*}
      url=${line#*=}
      
      if [[ ! "$url" =~ ^[a-zA-Z0-9]+:// ]]; then
        url="rtmp://$url"
      fi
      active_targets["$name"]="$url"
    done < /outputs/outputs.txt

    # Шаг А: Удаляем пушеры, которые были убраны из файла outputs.txt
    for pid_file in "$PID_DIR"/*; do
      [ -e "$pid_file" ] || continue
      name=$(basename "$pid_file")
      if [ -z "${active_targets[$name]+exact_match}" ]; then
        echo "[Supervisor] Destination '$name' removed. Stopping stream..."
        pid=$(cat "$pid_file")
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$pid_file"
      fi
    done

    # Шаг Б: Запускаем новые платформы или поднимаем упавшие
    for name in "${!active_targets[@]}"; do
      url="${active_targets[$name]}"
      pid_file="$PID_DIR/$name"
      
      running=false
      if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
          running=true
        else
          rm -f "$pid_file"
        fi
      fi

      if [ "$running" = false ]; then
        echo "[Supervisor] Launching new isolated pusher for '$name'..."
        fmt=$(get_muxer_format "$url")
        
        # Запускаем фоновую сессию пушера с перехватом системных сигналов
        sh -c "
          echo \$\$ > '$pid_file'
          cleanup() {
            echo '[Pusher:$name] Terminating stream...'
            kill \$child_pid 2>/dev/null || true
            exit 0
          }
          trap cleanup TERM INT
          while true; do
            echo '[Pusher:$name] Connecting to $url...'
            ffmpeg -fflags nobuffer -rtsp_transport tcp -i 'rtsp://mediamtx:8554/transcoded' \
              -c copy -f '$fmt' '$url' > '/data/ffmpeg_${name}.log' 2>&1 &
            child_pid=\$!
            wait \$child_pid || true
            echo '[Pusher:$name] Connection lost. Reconnecting in 5 seconds...'
            sleep 5
          done
        " &
      fi
    done

    sleep 5
  done
) &

# Удержание главного процесса контейнера
wait
