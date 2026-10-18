"""Same-origin React delivery and transparent proxy to the existing GPU API.

No model loading, no API-key injection, no changes to visual decisions.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from .api_docs import TITLE, DESCRIPTION, present_schema
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


app = FastAPI(title=TITLE, docs_url=None,
              redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.get("/docs", include_in_schema=False)
async def swagger_docs():
    page = get_swagger_ui_html(openapi_url="/openapi.json", title=TITLE + " — документация",
        swagger_js_url="/docs-assets/swagger-ui-bundle.js",
        swagger_css_url="/docs-assets/swagger-ui.css",
        swagger_favicon_url="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%238e174b'/%3E%3Ctext x='10' y='25' font-family='Arial' font-size='27' fill='white'%3Ef%3C/text%3E%3C/svg%3E",
        swagger_ui_parameters={"persistAuthorization": False, "defaultModelsExpandDepth": -1,
                               "displayRequestDuration": True, "docExpansion": "list"})
    static = Path(__file__).parent / "static"
    body = page.body.decode().replace('<html>', '<html lang="ru">')
    body = body.replace('</head>', '<style>' + (static / 'forte_docs.css').read_text() + '</style></head>')
    body = body.replace('<body>', '<body>' + (static / 'forte_docs_shell.html').read_text())
    body = body.replace('</body>', '<footer class="docs-footer">Forte · OpenAPI / Swagger UI</footer></main></div><script>' +
                        (static / 'forte_docs_auth.js').read_text() + '</script></body>')
    # Expose only the already-created UI instance to our key form.
    body = body.replace('const ui = SwaggerUIBundle(', 'const ui = window.ui = SwaggerUIBundle(')
    return Response(body, media_type="text/html", headers={"Cache-Control": "no-store"})



@app.api_route("/api/{path:path}", methods=["GET", "POST"])
@app.get("/health")
@app.get("/openapi.json")
async def proxy(request: Request, path: str = ""):
    target = "/api/v1/health" if request.url.path == "/health" else request.url.path
    if target.startswith("/api/v1/jobs/") and target.endswith("/review"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
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
    if response.status_code == 200 and target == "/openapi.json":
        schema = response.json()
        schema = present_schema(schema)
        return JSONResponse(schema, headers={"Cache-Control": "no-store"})
    if response.status_code == 200 and target.startswith("/api/v1/jobs/"):
        return JSONResponse(with_rule_sources(response.json()), headers={"Cache-Control": "no-store"})
    return Response(response.content, status_code=response.status_code,
                    headers={"Content-Type": response.headers.get("content-type", "application/json"),
                             "Cache-Control": "no-store"})


# check_dir=False permits backend-only test/installation before npm build.
app.mount("/docs-assets", StaticFiles(directory=Path(__file__).parent / "static" / "swagger"), name="docs-assets")
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
