"""Same-origin React delivery and transparent proxy to the existing GPU API.

No model loading, no API-key injection, no changes to visual decisions.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.getenv("FORTE_FRONTEND_DIST", str(ROOT / "frontend" / "dist"))).resolve()
UPSTREAM = os.getenv("FORTE_API_UPSTREAM", "http://127.0.0.1:8000").rstrip("/")


from .regulatory import enrich as with_rule_sources


@asynccontextmanager
async def lifespan(app):
    # Never route local inference through system HTTP proxies.
    async with httpx.AsyncClient(base_url=UPSTREAM, timeout=310, trust_env=False) as client:
        app.state.client = client
        yield


app = FastAPI(title="Video analysis web gateway", docs_url=None,
              redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.api_route("/api/{path:path}", methods=["GET", "POST"])
@app.get("/health")
@app.get("/docs")
@app.get("/openapi.json")
async def proxy(request: Request, path: str = ""):
    target = "/api/v1/health" if request.url.path == "/health" else request.url.path
    # Deliberate allowlist: do not expose the old unauthenticated /ui routes.
    headers = {k: v for k, v in request.headers.items()
               if k.lower() in {"x-api-key", "content-type", "accept"}}
    if request.headers.get("content-length"):
        if int(request.headers["content-length"]) > 201 * 1024 * 1024:
            return JSONResponse({"detail": "File exceeds 200 MiB limit"}, status_code=413)
        headers["content-length"] = request.headers["content-length"]
    try:
        response = await request.app.state.client.request(
            request.method, target, params=request.query_params, headers=headers,
            content=request.stream() if request.method == "POST" else None)
    except httpx.RequestError:
        return JSONResponse({"detail": "Analysis service unavailable"}, status_code=503)
    if response.status_code == 200 and target.startswith("/api/v1/jobs/"):
        return JSONResponse(with_rule_sources(response.json()), headers={"Cache-Control": "no-store"})
    return Response(response.content, status_code=response.status_code,
                    headers={"Content-Type": response.headers.get("content-type", "application/json"),
                             "Cache-Control": "no-store"})


# check_dir=False permits backend-only test/installation before npm build.
app.mount("/assets", StaticFiles(directory=DIST / "assets", check_dir=False), name="assets")


@app.get("/{path:path}")
async def frontend(path: str):
    if path.startswith(("api/", "ui/", ".")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (DIST / path).resolve()
    if candidate.is_relative_to(DIST) and candidate.is_file():
        return FileResponse(candidate)
    if Path(path).suffix:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if not (DIST / "index.html").is_file():
        return JSONResponse({"detail": "Build frontend first: npm ci && npm run build"}, status_code=503)
    return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
