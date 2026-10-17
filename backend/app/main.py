import asyncio
import fcntl
import logging
import shutil
import time
from contextlib import asynccontextmanager, suppress
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from starlette.datastructures import UploadFile

from .config import Settings
from .middleware import APIAccessMiddleware
from .schemas import CreatedJob, JobResponse
from .storage import QueueFull, Store
from .worker import run_worker

logger = logging.getLogger(__name__)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
Key = Annotated[str | None, Security(api_key_header)]


def create_app(settings: Settings | None = None, *, start_worker: bool = True) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings.database)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        # This starter uses one API process and one supervised analysis at a time.
        # Fail explicitly instead of allowing a second process to recover live jobs.
        with (settings.data_dir / "server.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Use one API worker per FORTE_DATA_DIR") from exc
            store.initialize()
            store.recover()
            store.expire()
            worker = asyncio.create_task(run_worker(settings, store)) if start_worker else None
            logger.info("API ready; local analysis model is not configured")
            try:
                yield
            finally:
                if worker:
                    worker.cancel()
                    with suppress(asyncio.CancelledError):
                        await worker

    app = FastAPI(
        title="Forte Video Control API",
        version="0.1.0",
        description="Datathon 26 API. Local AI model is not configured yet.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.settings = settings
    app.add_middleware(APIAccessMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    @app.get("/health", tags=["service"])
    def health():
        return {
            "status": "ok",
            "analysis_available": False,
            "analyzer": "not_configured",
            "ffprobe_available": shutil.which(settings.ffprobe) is not None,
        }

    @app.post(
        "/api/v1/analyze",
        response_model=CreatedJob,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["analysis"],
        responses={
            401: {"description": "Invalid API key"},
            413: {"description": "Upload too large"},
            415: {"description": "MOV required"},
            422: {"description": "Missing or empty file"},
            429: {"description": "Queue full"},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {"file": {"type": "string", "format": "binary"}},
                        }
                    }
                },
            }
        },
    )
    async def analyze(request: Request, key: Key):
        if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
            raise HTTPException(422, "Ожидается multipart/form-data с полем file.")
        async with request.form(max_files=1, max_fields=0, max_part_size=1024) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile):
                raise HTTPException(422, "Отсутствует файл в поле file.")
            if not (file.filename or "").lower().endswith(".mov"):
                raise HTTPException(415, "Принимаются только файлы .MOV.")
            if not file.size:
                raise HTTPException(422, "Файл пустой.")
            if file.size > settings.max_upload_bytes:
                raise HTTPException(413, "Превышен лимит размера видео.")
            job_id = uuid4().hex
            path = settings.upload_dir / f"{job_id}.mov"
            created = request.state.request_started
            deadline = created + settings.job_timeout_seconds

            def save():
                with path.open("xb") as target:
                    shutil.copyfileobj(file.file, target, length=1024 * 1024)

            try:
                await asyncio.to_thread(save)
                if time.time() >= deadline:
                    raise HTTPException(408, "Превышено время загрузки.")
                store.expire()
                store.enqueue(job_id, created, deadline, settings.max_pending_jobs)
            except QueueFull as exc:
                path.unlink(missing_ok=True)
                raise HTTPException(
                    429,
                    "Очередь обработки заполнена. Повторите позже.",
                    headers={"Retry-After": "5"},
                ) from exc
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        return CreatedJob(job_id=job_id)

    @app.get(
        "/api/v1/jobs/{job_id}",
        response_model=JobResponse,
        response_model_exclude_none=True,
        tags=["analysis"],
        responses={
            401: {"description": "Invalid API key"},
            404: {"description": "Job not found or expired"},
        },
    )
    def get_job(job_id: str, key: Key):
        try:
            normalized = UUID(job_id).hex
        except ValueError as exc:
            raise HTTPException(404, "Проверка не найдена.") from exc
        store.expire()
        row = store.get(normalized)
        if row is None:
            raise HTTPException(404, "Проверка не найдена или срок хранения истёк.")
        return store.response(row)

    return app
