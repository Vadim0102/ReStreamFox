FROM jrottenberg/ffmpeg:4.4-ubuntu

WORKDIR /app

COPY entrypoint.sh /app/entrypoint.sh
COPY transcode.sh /app/transcode.sh
COPY backup.sh /app/backup.sh
COPY config.env /app/config.env

RUN chmod +x /app/entrypoint.sh /app/transcode.sh /app/backup.sh

ENTRYPOINT ["/app/entrypoint.sh"]
