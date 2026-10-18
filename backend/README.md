# Backend: воспроизводимый серверный снимок

Действующий backend: `/workspace/forte_live_20261018`. Пакет переименован в `forte`, переменные окружения — в `FORTE_*`. Контрольные суммы текущего релиза находятся в `deploy/`; исходный снимок сохранён в истории Git. Дополнительно создан `service/gateway.py`; он не загружает модели и не меняет решения.

Предыдущее обновление оформления кадров: русские подписи без tracker ID и confidence, читаемые тёмные плашки. Изменён только рендер в `pipeline.py`, добавлен `evidence_labels.py` и шрифт DejaVu с лицензией. Контрольные суммы этого обновления — `deploy/presentation-sha256.json`; исходный серверный манифест сохранён. Проверены реальные Х-25 (без нарушения) и Х-46 (событие и 2 JPEG).

## Новый Linux GPU-сервер

Установите FFmpeg/FFprobe системным пакетным менеджером. Python 3.12 и совместимый NVIDIA-драйвер должны быть доступны.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-service.txt
cp .env.example .env
# В .env установите свой ключ, существующий HF_HOME и каталог данных.
set -a
source .env
set +a
```

`.env.example` — пример, `.env` не читается Python автоматически. Используйте переменные окружения или supervisor wrapper. Не устанавливайте зависимости поверх работающего окружения сервера.

Если нужные веса уже лежат в HF_HOME, используйте их. Для новой машины **отдельно** выполните однократное скачивание фиксированных ревизий (большая загрузка):

```bash
HF_HUB_OFFLINE=0 python scripts/download_models.py
```

Для offline-запуска:

```bash
export HF_HUB_OFFLINE=1
python scripts/verify_source.py
python -m uvicorn service.app:app --host 127.0.0.1 --port 8000 --workers 1
```

**Не используйте `--reload` или несколько workers для GPU API.** Дождитесь `worker: ready` в `/api/v1/health`.

В другом терминале соберите UI из корня репозитория:

```bash
npm ci --prefix frontend
npm run build --prefix frontend
```

И запустите gateway из `backend` тем же Python:

```bash
FORTE_API_UPSTREAM=http://127.0.0.1:8000 \
  python -m uvicorn service.gateway:app --host 127.0.0.1 --port 8080
```

Откройте localhost:8080. Для внешнего доступа используйте TLS reverse proxy. Не выставляйте внутренний GPU API напрямую: он сохраняет старые `/ui` маршруты для совместимости. Gateway их не публикует.

## Действующий сервер

- GPU API: `forte_api`, localhost:17070, исходники `/workspace/forte_live_20261018`.
- Новый UI/gateway: `forte_ui`, localhost:7860, `/workspace/forte_web_release_20261018`.
- GPU API, checkpoint, SQLite и настройки распознавания при интеграции не изменены.
- Откат UI: вернуть `/workspace/forte_web_release_20261018/forte-ui.before.sh` в `/opt/supervisor-scripts/forte-ui.sh`, затем `supervisorctl restart forte_ui`.
- `service/static` — сохранённый старый интерфейс внутри исходного backend; наружу новый gateway отдаёт только React.

`requirements-service.txt` содержит версии прямых зависимостей рабочего Linux-окружения; `deploy/environment-freeze.txt` — полный справочный снимок, включая пакеты экспериментов. Устанавливать весь freeze не требуется. Установка на совершенно новой машине отдельно не проверялась.

Выбор JPEG дополнен контекстом: до трёх разных моментов в границах видео, без дублирования. Состав событий и основной таймкод не меняются. План следующего пилота и видеоклипов: `../docs/NEXT_STEPS.md`.

## Состав актуальной развёрнутой версии

GPU API и публичный gateway — разные процессы. Модели, pipeline и классификаторы находятся в `forte_live_20261018`; интерфейс, публичный Swagger и нормативное обогащение — в `forte_web_release_20261018`. Сравнивать файлы следует по роли процесса, а не требовать одинакового содержимого всех серверных папок. Внутренний GPU API сохраняет прежнее название документации; публичный `/docs` показывает Forte.

Основной публичный адрес: https://forte.makquiz.site:14901 — HTTPS через `forte_direct_tls` на gateway. Tailscale не является основным адресом сдачи. Резервный процесс `forte_web_tunnel`; состояние и сертификаты вне репозитория. Ключи и state-файлы не копировать в Git. Источники нормативных актов лежат локально; при обработке видео загрузка их из интернета не нужна.

Swagger UI 5.33.3 поставляется локально вместе с лицензией, CDN-запросы не нужны. Полный перенос на новую машину без сети ещё не проверен.

### Подготовка пакетов для установки без сети

На подключённой Linux x86_64 машине с Python 3.12:

```bash
python -m pip download --only-binary=:all: -r requirements-service.txt -d /path/to/wheels
```

Перенесите wheelhouse, проект и HF_HOME с четырьмя snapshot на целевую машину. Затем:

```bash
scripts/install_offline.sh /path/to/wheels /path/to/new-venv
```

Не используйте эту команду для перезаписи рабочего окружения. `--no-index` запрещает установщику обращаться к индексам; полная изоляция системы требует отдельной сетевой проверки. Статус фактической проверки: `docs/READINESS_FIXES_20261018.md` в корне проекта.

## Дополнительные наблюдения

Сборка содержит обученную голову папки `models/folder_patch_heads.joblib` и визуальную проверку ошибочно подавленных треков людей. Они работают внутри `forte.pipeline.Analyzer`, без вызова другого API и без зависимости от `research/`. Уже загруженные Qwen и совместимый DINOv2 переиспользуются. Настройка `FORTE_OBSERVATIONS=0` отключает оба дополнения; по умолчанию они включены. Отсутствующий checkpoint или Qwen при включённых дополнениях приводит к ошибке запуска, а ошибка новой ветки — к `failed`, а не к ложному ответу «нарушений нет».

Перед запуском выполните `python scripts/verify_source.py`. Контрольные суммы и ограничения моделей: [DEPLOYED_MODELS.md](DEPLOYED_MODELS.md). Исследовательские данные, исходные видео, секреты и большие веса в Git не добавляются.
