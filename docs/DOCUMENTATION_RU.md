# ReStreamFox — Документация (Русская)

## Обзор
ReStreamFox — это набор контейнеров для приёма стрима и его ретрансляции на множество платформ с одним экземпляром кодировщика FFmpeg. Компоненты:

- MediaMTX — принимает поток (SRT/RTMP/RTSP/WebRTC).
- Watchdog — опрашивает API MediaMTX и управляет режимами FFmpeg.
- FFmpeg — основной транскодер/распространитель и резервный плейбек.
- UI — админ-панель на Flask + Socket.IO для управления и просмотра логов.

## Быстрый старт
1. Отредактируйте `outputs/outputs.txt`, добавив RTMP-адреса в формате `name=rtmp://...`.
2. Установите секреты в `config.yml`:
   - `ui_admin_password` — пароль админа.
   - `ui_secret` — секрет Flask для сессий.
3. (Опционально) Если нужен прямой рестарт контейнера из UI, смонтируйте Docker socket в `ui`.
4. Соберите и запустите:

```bash
docker compose up -d --build
```

Откройте UI: `http://localhost:8080`. Для доступа к админке перейдите на `/admin`.

## Конфиги и файлы
- `docker-compose.yml` — описание сервисов.
- `mediamtx/mediamtx.yml` — конфигурация MediaMTX.
- `ffmpeg/` — скрипты и Dockerfile для ffmpeg.
- `watchdog/` — python-скрипт; валидирует `config.yml` и `outputs/outputs.txt`.
- `outputs/outputs.txt` — список целей для `tee`.
- `config.yml` — основной YAML-конфиг. Основные поля описаны в `docs/DOCUMENTATION.md`.

## Безопасность
- Не храните секреты в публичных репозиториях.
- Монтирование Docker socket несёт риски; по возможности используйте fallback с `manual_mode`.

## Разработка
- Каждый python-сервис имеет свой `requirements.txt`.
- Для локального запуска watchdog: создайте venv, установите зависимости и выполните `python watchdog/watchdog.py`.

## CI
- GitHub Actions выполняет синтакс-проверку и сборку образов (без push).

## Устранение неполадок
- `docker logs mediamtx`
- `docker logs ffmpeg` или содержимое `/data/ffmpeg.log`
- `docker logs watchdog`

*** End Patch