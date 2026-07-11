# restream-stack — быстрое ретранслирование (русский)

Проект организует простую, надёжную систему ретрансляции на основе трёх компонентов:

- MediaMTX — принимает входной поток (SRT/RTMP/RTSP/WebRTC). Не кодирует.
- FFmpeg — кодирует поток один раз и рассылает на несколько платформ (`tee`).
- Watchdog — мониторит MediaMTX API и переключает `ffmpeg` на основной или резервный режим.

Структура репозитория

 - `docker-compose.yml` — запустит 3 контейнера: `mediamtx`, `ffmpeg`, `watchdog`.
 - `mediamtx/mediamtx.yml` — минимальная конфигурация MediaMTX.
 - `ffmpeg/` — Dockerfile и скрипты: `entrypoint.sh`, `transcode.sh`, `backup.sh`, `config.env`.
 - `watchdog/` — контейнер с `watchdog.py`, опрашивает API MediaMTX.
 - `outputs/outputs.txt` — список целей в формате `name=rtmp://...`.
 - `config.yml` — основной конфигурационный файл (YAML). Watchdog читает его и генерирует настройки для FFmpeg.

Концепция

 - Поток поступает в MediaMTX (например, из OBS через SRT).
 - Watchdog опрашивает `http://mediamtx:9997/v3/paths/list` и смотрит, готов ли путь `live`.
 - Если поток есть, watchdog пишет `main` в `/data/control` — контейнер `ffmpeg` запускает `transcode.sh`.
 - Если потока нет, watchdog пишет `backup` — `ffmpeg` запускает `backup.sh` (loop offline).
 - Параметры кодирования можно задать в `config.yml`; watchdog создаёт `/data/ffmpeg.env` и `ffmpeg` его подхватывает.

Настройка

1) Отредактируйте `outputs/outputs.txt` — добавьте все конечные RTMP-адреса, по одному в строке: `youtube=rtmp://...`.
2) Положите резервное видео в `data/offline.mp4` (если хотите кастомный плейлист).
3) Настройте `config.yml` (пояснения ниже).

Пример `config.yml`

```yaml
mediamtx_api: http://mediamtx:9997/v3/paths/list
path_name: live
check_interval: 1

backup:
  enabled: true
  file: /data/offline.mp4

ffmpeg:
  video:
    codec: libx264
    bitrate: 6000k
    preset: veryfast
    tune: zerolatency
  audio:
    codec: aac
    bitrate: 192k
```

Что ещё можно менять

- `outputs/outputs.txt` позволяет добавлять сколько угодно платформ. Watchdog/FFmpeg собирают `tee` автоматически.
- Параметры кодека из `config.yml` будут записаны в `/data/ffmpeg.env` и подхвачены контейнером `ffmpeg`.

Запуск

```bash
docker compose up -d --build
```

Диагностика

- Логи `watchdog`: `docker logs -f watchdog` — смотрите опрос MediaMTX и смену режимов.
- Логи `ffmpeg`: `docker logs -f ffmpeg` — вывод ffmpeg, PID, ошибки.
- API MediaMTX: `http://localhost:9997/v3/paths/list`

Web UI

 - Запустите и откройте `http://localhost:8080` — простая панель состояния и кнопки управления (Force main / Force backup / Stop / Resume auto).

Перезапуск транскодера (опционально):

 - UI может перезапускать контейнер `ffmpeg` напрямую, если в `ui` сервис смонтировать Docker socket. Для этого в `docker-compose.yml` под сервисом `ui` раскомментируйте:

```yaml
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

 - Если Docker socket не смонтирован, UI делает "безопасный" fallback: записывает `/data/manual_mode` со значением `stop`, затем `main`, что вызывает перезапуск через логику watchdog.

Безопасность: токен администратора

 - Чтобы ограничить доступ к перезапуску, установите `ui_admin_token` в `config.yml` — сильную секретную строку. UI будет требовать заголовок `X-Admin-Token` с этим значением для вызова `/api/restart`.

Дополнения UI

 - UI предоставляет `/api/outputs` (читает `outputs/outputs.txt`) и `/api/logs` (последние строки `/data/ffmpeg.log`). Кнопки на странице открывают вывод и логи.

Админ-страница и безопасность

 - Проект включает админ-страницу `/admin` (требуется логин). Админ-страница использует WebSocket (Socket.IO) для потоковой выдачи логов `ffmpeg` и отправки команд (force/restart). Админские действия защищены паролем `ui_admin_password` в `config.yml` и секретом Flask `ui_secret`.

Примечания по безопасности

 - Не храните секреты в публичных репозиториях. Для продакшена используйте менеджер секретов или переменные окружения.
 - Монтирование Docker socket (`/var/run/docker.sock`) в контейнер UI даёт ему широкие права — по возможности используйте fallback с `manual_mode` или настройте прокси с ограниченными правами.

Полную документацию (архитектура, конфигурация, руководство по развёртыванию и безопасности) смотрите в `docs/DOCUMENTATION_RU.md`.

Гайд для новичков

Если вы не уверены в Docker или стриминге, откройте `docs/BEGINNER_GUIDE.md` — в нём пошагово описано: как настроить `outputs/outputs.txt`, задать секреты, запустить стек, и решения частых проблем (включая ошибку CI `Dockerfile not found` и её исправление).

Ручное управление

 - Создайте файл `/data/manual_mode` со значением `main`/`backup`/`stop`, чтобы заставить `ffmpeg` работать в нужном режиме. Чтобы вернуть автоматическое поведение, запишите `auto` или удалите файл. UI предоставляет эти действия.

Лицензия

MIT — см. `LICENSE`.

Дальше я могу:

- Добавить веб-интерфейс для статуса и управления (force backup / restart transcoder). 
- Добавить CI, шаблоны PR, CONTRIBUTING.md и примеры конфигураций для популярных платформ.

Хотите, чтобы я сразу добавил веб-интерфейс (простое Flask-приложение) или сначала улучшу конфиг/валидацию? 
