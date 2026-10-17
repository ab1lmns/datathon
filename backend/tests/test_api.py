import asyncio
import base64
import subprocess
import time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.analyzer import MODEL_NOT_CONFIGURED
from app.main import create_app
from app.schemas import AnalysisResult
from app.worker import run_one

pytestmark = pytest.mark.anyio


async def test_authentication_precedes_upload_parsing(client, headers):
    for key in ({}, {"X-API-Key": "wrong"}):
        assert (
            await client.post("/api/v1/analyze", content=b"bad", headers=key)
        ).status_code == 401
        assert (await client.get(f"/api/v1/jobs/{uuid4().hex}", headers=key)).status_code == 401
    assert (await client.get("/health")).json()["analysis_available"] is False


async def test_openapi_has_upload_and_security(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/v1/analyze"]["post"]
    assert operation["security"] == [{"APIKeyHeader": []}]
    form = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert form["required"] == ["file"]
    assert form["properties"]["file"]["format"] == "binary"


async def test_real_worker_reports_missing_model(settings, headers, video):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post(
                "/api/v1/analyze",
                headers=headers,
                files={"file": ("../../test.MOV", video, "video/quicktime")},
            )
            assert created.status_code == 202
            job_id = created.json()["job_id"]
            async with asyncio.timeout(15):
                while True:
                    result = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
                    if result.json()["status"] != "processing":
                        break
                    await asyncio.sleep(0.05)
            assert result.json() == {
                "job_id": job_id,
                "status": "failed",
                "error": MODEL_NOT_CONFIGURED,
            }
    assert not list(settings.upload_dir.iterdir())


async def test_processing_is_persistent_and_queue_is_bounded(client, settings, headers, video):
    settings.max_pending_jobs = 1
    created = await client.post(
        "/api/v1/analyze", headers=headers, files={"file": ("a.mov", video)}
    )
    job_id = created.json()["job_id"]
    assert (await client.get(f"/api/v1/jobs/{job_id}", headers=headers)).json() == {
        "job_id": job_id,
        "status": "processing",
    }
    from app.storage import Store

    assert Store(settings.database).get(job_id)["state"] == "queued"
    rejected = await client.post(
        "/api/v1/analyze", headers=headers, files={"file": ("b.mov", video)}
    )
    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "5"
    assert len(list(settings.upload_dir.iterdir())) == 1


@pytest.mark.parametrize(
    "name,data,expected",
    [
        ("a.mp4", b"x", 415),
        ("a.mov", b"", 422),
        ("a.mov", b"x" * (1024 * 1024 + 1), 413),
    ],
)
async def test_invalid_uploads_leave_no_files(client, headers, settings, name, data, expected):
    result = await client.post("/api/v1/analyze", headers=headers, files={"file": (name, data)})
    assert result.status_code == expected
    assert not list(settings.upload_dir.iterdir())


async def test_missing_file_and_unknown_job(client, headers):
    assert (await client.post("/api/v1/analyze", headers=headers, json={})).status_code == 422
    response = await client.post(
        "/api/v1/analyze", headers=headers, files={"wrong": ("a.mov", b"x")}
    )
    assert response.status_code == 422
    for job_id in [uuid4().hex, "not-a-uuid"]:
        assert (await client.get(f"/api/v1/jobs/{job_id}", headers=headers)).status_code == 404


async def test_streaming_body_limit(client, headers):
    async def chunks():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a.mov"\r\n\r\n'
        yield b"x" * (2 * 1024 * 1024 + 1)
        yield b"\r\n--boundary--\r\n"

    result = await client.post(
        "/api/v1/analyze",
        content=chunks(),
        headers={**headers, "Content-Type": "multipart/form-data; boundary=boundary"},
    )
    assert result.status_code == 413


async def test_cors_preflight_and_unauthorized_response(client):
    result = await client.options(
        "/api/v1/analyze",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key,content-type",
        },
    )
    assert result.status_code == 200
    result = await client.get(
        f"/api/v1/jobs/{uuid4().hex}", headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert result.status_code == 401
    assert result.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


async def test_corrupt_mov_fails_in_worker(client, settings, headers):
    response = await client.post(
        "/api/v1/analyze", headers=headers, files={"file": ("bad.mov", b"not a video")}
    )
    job_id = response.json()["job_id"]
    store = client.app.state.store
    await run_one(settings, store, store.claim())
    result = (await client.get(f"/api/v1/jobs/{job_id}", headers=headers)).json()
    assert result["status"] == "failed"
    assert "повреждён" in result["error"]


async def test_done_results_match_frontend_contract(client, headers):
    # Synthetic test fixtures only: the running service has no fake analyzer mode.
    jpeg = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=32x32",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-c:v",
            "mjpeg",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
        timeout=20,
    ).stdout
    event = {
        "type": "Тестовое событие",
        "timecode_sec": 0.1,
        "description": "Тест схемы",
        "evidence_frames": [
            {"timestamp_sec": 0.1, "image_base64": base64.b64encode(jpeg).decode()}
        ],
        "rule": {"document": "Тестовый источник", "url": "https://example.org/rule"},
    }
    store = client.app.state.store
    for verdict, events in [("no_violation", []), ("violation", [event, event])]:
        job_id = uuid4().hex
        store.enqueue(job_id, time.time(), time.time() + 60, 4)
        store.claim()
        store.complete(job_id, AnalysisResult(verdict=verdict, violations=events))
        result = (await client.get(f"/api/v1/jobs/{job_id}", headers=headers)).json()
        assert result["status"] == "done"
        assert result["verdict"] == verdict
        assert len(result["violations"]) == len(events)
