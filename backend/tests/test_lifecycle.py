import asyncio
import sys
import time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import AnalysisResult, EvidenceFrame
from app.storage import Store
from app.worker import run_one


def test_schema_rejects_contradictory_verdict_and_invalid_evidence():
    with pytest.raises(ValidationError):
        AnalysisResult(verdict="violation", violations=[])
    for timestamp, image in [(-1, "a"), (float("nan"), "a"), (0, "not-jpeg")]:
        with pytest.raises(ValidationError):
            EvidenceFrame(timestamp_sec=timestamp, image_base64=image)


def test_recovery_expiration_and_retention(settings):
    store = Store(settings.database)
    store.initialize()
    settings.upload_dir.mkdir()
    interrupted, expired = uuid4().hex, uuid4().hex
    store.enqueue(interrupted, time.time(), time.time() + 60, 4)
    store.claim()
    store.enqueue(expired, time.time(), time.time() - 1, 4)
    store.recover()
    store.expire()
    assert "перезапуском" in store.get(interrupted)["error"]
    assert "время" in store.get(expired)["error"]
    (settings.upload_dir / f"{expired}.mov").write_bytes(b"test")
    with store.connect() as db:
        db.execute("UPDATE jobs SET updated_at=?", (time.time() - 25 * 3600,))
    store.cleanup(settings.upload_dir, 24)
    assert store.get(expired) is None
    assert not list(settings.upload_dir.iterdir())


@pytest.mark.anyio
async def test_deadline_stops_actual_child_process(settings, monkeypatch):
    store = Store(settings.database)
    store.initialize()
    settings.upload_dir.mkdir()
    job_id = uuid4().hex
    store.enqueue(job_id, time.time(), time.time() + 0.15, 4)
    real_spawn = asyncio.create_subprocess_exec
    children = []

    async def spawn_slow_analyzer(*args, **kwargs):
        process = await real_spawn(
            sys.executable, "-c", "import time; time.sleep(60)", start_new_session=True
        )
        children.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_slow_analyzer)
    await run_one(settings, store, store.claim())
    assert children[0].returncode is not None
    assert store.get(job_id)["state"] == "failed"
    assert "время" in store.get(job_id)["error"]
