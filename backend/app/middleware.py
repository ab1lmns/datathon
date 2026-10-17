import asyncio
import secrets
import time

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from .config import Settings


class APIAccessMiddleware:
    """Authenticate before multipart parsing; bound even chunked request bodies."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        supplied = headers.get("x-api-key", "")
        expected = self.settings.api_key.get_secret_value()
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            return await JSONResponse(
                {"detail": "Неверный или отсутствующий API-ключ."}, status_code=401
            )(scope, receive, send)
        started = time.time()
        scope.setdefault("state", {})["request_started"] = started
        limit = self.settings.max_upload_bytes + 1024 * 1024
        length = headers.get("content-length")
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError
            except ValueError:
                return await JSONResponse(
                    {"detail": "Некорректный Content-Length."}, status_code=400
                )(scope, receive, send)
            if declared > limit:
                return await JSONResponse(
                    {"detail": "Превышен лимит размера загрузки."}, status_code=413
                )(scope, receive, send)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            remaining = self.settings.job_timeout_seconds - (time.time() - started)
            try:
                message = await asyncio.wait_for(receive(), timeout=max(0, remaining))
            except TimeoutError as exc:
                raise HTTPException(408, "Превышено время загрузки.") from exc
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise HTTPException(413, "Превышен лимит размера загрузки.")
            return message

        await self.app(scope, limited_receive, send)
