import asyncio
import logging
import os
import signal
import sys
import time

from .config import BACKEND_DIR, Settings
from .storage import Store

logger = logging.getLogger(__name__)


async def stop_process(process: asyncio.subprocess.Process) -> None:
    # The process group also includes FFprobe or a future model subprocess.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await process.wait()


async def run_one(settings: Settings, store: Store, job: dict) -> None:
    job_id = job["job_id"]
    process = None
    try:
        remaining = job["deadline"] - time.time()
        if remaining <= 0:
            store.fail(job_id, "Превышено время ожидания обработки.")
            return
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.process_job",
            job_id,
            "--database",
            str(settings.database),
            "--upload-dir",
            str(settings.upload_dir),
            "--ffprobe",
            settings.ffprobe,
            cwd=BACKEND_DIR,
            start_new_session=True,
        )
        await asyncio.wait_for(process.wait(), timeout=remaining)
        # Includes crashes, termination and a model that failed to produce a result.
        store.fail(job_id, "Обработчик завершился без результата. Повторите загрузку.")
    except TimeoutError:
        store.fail(job_id, "Превышено время ожидания обработки.")
    except asyncio.CancelledError:
        store.fail(job_id, "Сервер остановлен во время обработки. Загрузите видео повторно.")
        raise
    except Exception:
        logger.exception("Worker failed for job %s", job_id)
        store.fail(job_id, "Не удалось запустить обработку видео.")
    finally:
        if process is not None:
            await stop_process(process)
        (settings.upload_dir / f"{job_id}.mov").unlink(missing_ok=True)


async def run_worker(settings: Settings, store: Store) -> None:
    next_cleanup = 0.0
    while True:
        try:
            store.expire()
            if time.time() >= next_cleanup:
                store.cleanup(settings.upload_dir, settings.retention_hours)
                # Recover files left by an interrupted upload or expired queued job.
                for path in settings.upload_dir.iterdir():
                    job = store.get(path.name.split(".")[0])
                    stale = time.time() - path.stat().st_mtime > settings.job_timeout_seconds
                    if (job and job["state"] in ("done", "failed")) or (not job and stale):
                        path.unlink(missing_ok=True)
                next_cleanup = time.time() + 60
            job = store.claim()
            if job:
                await run_one(settings, store, job)
            else:
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker loop failed; retrying")
            await asyncio.sleep(1)
