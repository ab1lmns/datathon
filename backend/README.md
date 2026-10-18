# Backend: воспроизводимый серверный снимок

Экспорт действующего `/workspace/cashguard_live_20261017` от 18.10.2026. `cashguard/`, исходный `service/` и два joblib совпадают с SHA-256 экспортированного production. Дополнительно создан `service/gateway.py`; он не загружает модели и не меняет решения.

Обновление оформления кадров: русские подписи без tracker ID и confidence, читаемые тёмные плашки. Изменён только рендер в `pipeline.py`, добавлен `evidence_labels.py` и шрифт DejaVu с лицензией. Контрольные суммы этого обновления — `deploy/presentation-sha256.json`; исходный серверный манифест сохранён. Проверены реальные Х-25 (без нарушения) и Х-46 (событие и 2 JPEG).

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

- GPU API: `forte_api`, localhost:17070, исходники `/workspace/cashguard_live_20261017`.
- Новый UI/gateway: `forte_ui`, localhost:7860, `/workspace/forte_web_release_20261018`.
- GPU API, checkpoint, SQLite и настройки распознавания при интеграции не изменены.
- Откат UI: вернуть `/workspace/forte_web_release_20261018/forte-ui.before.sh` в `/opt/supervisor-scripts/forte-ui.sh`, затем `supervisorctl restart forte_ui`.
- `service/static` — сохранённый старый интерфейс внутри исходного backend; наружу новый gateway отдаёт только React.

`requirements-service.txt` содержит версии прямых зависимостей рабочего Linux-окружения; `deploy/environment-freeze.txt` — полный справочный снимок, включая пакеты экспериментов. Устанавливать весь freeze не требуется. Установка на совершенно новой машине отдельно не проверялась.
