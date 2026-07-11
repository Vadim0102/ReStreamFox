FROM jrottenberg/ffmpeg:4.4-ubuntu

# Переключаемся на root, обновляем пакеты и устанавливаем актуальные сертификаты безопасности (необходимо для RTMPS)
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY entrypoint.sh /app/entrypoint.sh
COPY transcode.sh /app/transcode.sh
COPY backup.sh /app/backup.sh
COPY config.env /app/config.env

RUN chmod +x /app/entrypoint.sh /app/transcode.sh /app/backup.sh

ENTRYPOINT ["/app/entrypoint.sh"]
