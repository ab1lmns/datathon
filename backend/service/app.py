"""Асинхронный API для жюри (X-API-Key) и веб-интерфейс.

    FORTE_API_KEY=... uvicorn service.app:app --host 0.0.0.0 --port 8000

Запускать одним процессом uvicorn (без --workers и --reload): задачи обрабатывает
один воркер-процесс, которым управляет этот процесс.
"""
import os
import secrets
import shutil
import sqlite3
import time
import uuid
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Security, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from .jobs import Dispatcher, JobStore
from .logs import setup_logging

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
DATA = Path(os.environ.get("FORTE_DATA_DIR", ROOT / "data" / "service"))
API_KEY = os.environ.get("FORTE_API_KEY", "")
TIMEOUT_SEC = float(os.environ.get("FORTE_JOB_TIMEOUT", "300"))
MAX_UPLOAD = int(float(os.environ.get("FORTE_MAX_UPLOAD_MB", "200")) * 1024 * 1024)
KEEP_API_VIDEOS = os.environ.get("FORTE_KEEP_API_VIDEOS", "0") == "1"
LEGACY_DB = os.environ.get("FORTE_LEGACY_DB", "")

UPLOADS = DATA / "uploads"
LOG_FILE = DATA / "service.log"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        raise RuntimeError("Задайте ключ API: FORTE_API_KEY=<ключ> uvicorn service.app:app ...")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    setup_logging(str(LOG_FILE), "server")
    store = JobStore(DATA)
    disp = Dispatcher(store, str(LOG_FILE), TIMEOUT_SEC, KEEP_API_VIDEOS)
    disp.start()
    app.state.store, app.state.disp = store, disp
    yield
    disp.stop()


app = FastAPI(title="Анализ кассовых видео API", version="1.0",
              description="Поиск признаков нарушений кассовой дисциплины на видео. Все модели локальные.",
              lifespan=lifespan)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Ключ доступа к API (выдаётся жюри)")


def key_ok(key: str | None) -> bool:
    return bool(key) and secrets.compare_digest(key.encode(), API_KEY.encode())


@app.middleware("http")
async def check_api_key(request: Request, call_next):
    """Ключ проверяется до чтения тела запроса: без ключа видео даже не загружается."""
    path = request.url.path
    if path.startswith("/api/") and path != "/api/v1/health" and not key_ok(request.headers.get("X-API-Key")):
        return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401,
                            headers={"WWW-Authenticate": "X-API-Key"})
    return await call_next(request)


def require_key(key: str | None = Security(api_key_header)):
    # дублирует middleware; нужно, чтобы /docs показывал авторизацию по X-API-Key
    if not key_ok(key):
        raise HTTPException(401, "Invalid or missing API key")


def save_upload(request: Request, file: UploadFile, source: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    name = Path(file.filename or "video.mov").name
    ext = Path(name).suffix.lower() or ".mov"
    if source == "api" and ext != ".mov":
        raise HTTPException(400, "Only .mov files are accepted")
    dst = UPLOADS / f"{job_id}{ext}"
    size = 0
    with open(dst, "wb") as out:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close()
                dst.unlink(missing_ok=True)
                raise HTTPException(413, f"Файл больше {MAX_UPLOAD // (1024 * 1024)} МБ")
            out.write(chunk)
    if size == 0:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, "Пустой файл: передайте видео в поле file")
    request.app.state.store.add(job_id, source, name, dst, size)
    request.app.state.disp.submit(job_id)
    return job_id


def api_view(j: dict) -> dict:
    """Ответ по схеме ТЗ (раздел 10)."""
    status = "processing" if j["status"] in ("queued", "processing") else j["status"]
    out = {"job_id": j["job_id"], "status": status, "verdict": None, "violations": []}
    if status == "done":
        out["verdict"] = j["result"]["verdict"]
        out["violations"] = j["result"]["violations"]
    elif status == "failed":
        out["error"] = j["error"]
    return out


def legacy_view(job_id: str) -> tuple[dict, list] | None:
    """Read already completed ForteBank jobs without modifying the old SQLite DB."""
    if not LEGACY_DB:
        return None
    try:
        uuid.UUID(job_id)
    except ValueError:
        return None
    path = Path(LEGACY_DB)
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as db:
            row = db.execute(
                "SELECT status,result_json,error,review_json FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    status, result_json, error, review_json = row
    out = {"job_id": job_id, "status": status, "verdict": None, "violations": []}
    if status == "done" and result_json:
        result = json.loads(result_json)
        out["verdict"] = result.get("verdict")
        out["violations"] = result.get("violations", [])
    elif status == "failed":
        out["error"] = error
    return out, json.loads(review_json) if review_json else []


# ---------------- API для жюри ----------------

@app.post("/api/v1/analyze", dependencies=[Security(require_key)], tags=["api"],
          summary="Загрузить видео (.mov, поле file); в ответ job_id")
def analyze(request: Request, file: UploadFile = File(..., description="Видео .mov")):
    return {"job_id": save_upload(request, file, "api")}


@app.get("/api/v1/jobs/{job_id}", dependencies=[Security(require_key)], tags=["api"],
         summary="Статус (processing, done, failed) и результат")
def job_status(request: Request, job_id: str):
    j = request.app.state.store.get(job_id)
    if j is None:
        old = legacy_view(job_id)
        if old is None:
            raise HTTPException(404, "Задача не найдена")
        return old[0]
    return api_view(j)


@app.get("/api/v1/jobs/{job_id}/review", dependencies=[Security(require_key)], tags=["api"])
def old_job_review(job_id: str):
    old = legacy_view(job_id)
    if old is None:
        raise HTTPException(404, "Задача не найдена")
    return {"status": old[0]["status"], "events": old[1]}


@app.get("/api/v1/health", tags=["api"], summary="Состояние сервиса (без ключа)")
def health(request: Request):
    return {"status": "ok", **request.app.state.disp.health()}


# ---------------- веб-интерфейс (без авторизации) ----------------
# Видны только задачи, загруженные через интерфейс: результаты и видео жюри сюда не попадают.

def ui_job(request: Request, job_id: str) -> dict:
    j = request.app.state.store.get(job_id)
    if j is None or j["source"] != "ui":
        raise HTTPException(404, "Задача не найдена")
    return j


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.post("/ui/api/analyze", include_in_schema=False)
def ui_analyze(request: Request, file: UploadFile = File(...)):
    return {"job_id": save_upload(request, file, "ui")}


@app.get("/ui/api/jobs/{job_id}", include_in_schema=False)
def ui_status(request: Request, job_id: str):
    j = ui_job(request, job_id)
    out = api_view(j)
    now = time.time()
    res = j["result"] or {}
    out.update({
        "state": j["status"],
        "filename": j["filename"],
        "created_at": j["created_at"],
        "queue_position": request.app.state.disp.position(job_id),
        "elapsed_sec": round((j["finished_at"] or now) - j["started_at"], 1) if j["started_at"] else 0.0,
        "total_sec": round((j["finished_at"] or now) - j["created_at"], 1),
        "explain": res.get("explain", []),
        "meta": res.get("meta", {}),
        "timeline": res.get("timeline"),
        "video_url": f"/ui/video/{job_id}" if Path(j["video"]).exists() else None,
    })
    return out


@app.get("/ui/video/{job_id}", include_in_schema=False)
def ui_video(request: Request, job_id: str):
    j = ui_job(request, job_id)
    p = Path(j["video"])
    if not p.exists():
        raise HTTPException(404, "Видео удалено")
    # H.264 в .mov браузеры воспроизводят, если отдать его как video/mp4
    media = "video/mp4" if p.suffix in (".mov", ".mp4", ".m4v") else None
    return FileResponse(p, media_type=media)
