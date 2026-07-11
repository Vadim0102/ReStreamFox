#!/bin/bash
set -e

# control file: /data/control
CONTROL_FILE=/data/control
FF_PID_FILE=/data/ffmpeg.pid

# Load generated overrides if present
if [ -f /data/ffmpeg.env ]; then
  echo "Loading overrides from /data/ffmpeg.env"
  # shellcheck disable=SC1090
  source /data/ffmpeg.env
fi

function stop_ffmpeg() {
  if [ -f "$FF_PID_FILE" ]; then
    PID=$(cat "$FF_PID_FILE" | tr -d '\r')
    if kill -0 "$PID" 2>/dev/null; then
      echo "Stopping ffmpeg (pid $PID)"
      kill $PID
      wait $PID 2>/dev/null || true
    fi
    rm -f "$FF_PID_FILE"
  fi
}

trap stop_ffmpeg EXIT

echo "FFmpeg controller started, watching $CONTROL_FILE"

while true; do
  MODE=""
  if [ -f "$CONTROL_FILE" ]; then
    MODE=$(cat "$CONTROL_FILE" | tr -d '\r' | tr -d '\n')
  fi

  if [ -z "$MODE" ]; then
    # nothing to do
    stop_ffmpeg
    sleep 1
    continue
  fi

  if [ -f "$FF_PID_FILE" ]; then
    # already running, check if mode changed
    CURRENT_PID=$(cat "$FF_PID_FILE" | tr -d '\r')
    if kill -0 "$CURRENT_PID" 2>/dev/null; then
      CURRENT_MODE="$(cat /data/ffmpeg.mode 2>/dev/null || true)"
      if [ "$CURRENT_MODE" = "$MODE" ]; then
        sleep 1
        continue
      else
        stop_ffmpeg
      fi
    else
      rm -f "$FF_PID_FILE"
    fi
  fi

  echo "Requested mode: $MODE"
  if [ "$MODE" = "main" ]; then
    ( /app/transcode.sh ) > /data/ffmpeg.log 2>&1 &
    echo $! > "$FF_PID_FILE"
    echo "$MODE" > /data/ffmpeg.mode
  elif [ "$MODE" = "backup" ]; then
    ( /app/backup.sh ) > /data/ffmpeg.log 2>&1 &
    echo $! > "$FF_PID_FILE"
    echo "$MODE" > /data/ffmpeg.mode
  elif [ "$MODE" = "stop" ]; then
    stop_ffmpeg
    rm -f "$CONTROL_FILE"
  else
    echo "Unknown mode: $MODE" >&2
  fi

  sleep 1
done
