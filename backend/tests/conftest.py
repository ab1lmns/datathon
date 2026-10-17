import shutil
import subprocess

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app

TEST_KEY = "test-only-api-key-with-at-least-24-characters"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, api_key=TEST_KEY, data_dir=tmp_path, max_upload_mb=1)


@pytest.fixture
def headers():
    return {"X-API-Key": TEST_KEY}


@pytest.fixture
async def client(settings):
    app = create_app(settings, start_worker=False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.app = app
            yield client


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.fail("FFmpeg and FFprobe are required for the integration tests")
    path = tmp_path_factory.mktemp("media") / "synthetic.mov"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:r=10",
            "-t",
            "0.5",
            "-c:v",
            "mpeg4",
            str(path),
        ],
        check=True,
        timeout=20,
    )
    return path.read_bytes()
