"""FastAPI app: CORS, health, API routers, and SPA static-file serving."""

import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import directories as directories_routes
from app.api.routes import files as files_routes
from app.api.routes import scan as scan_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

app = FastAPI(title="ebook-meta-helper API", version="0.1.0")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("--> %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("<-- %s %s %s", request.method, request.url.path, response.status_code)
    return response


app.include_router(directories_routes.router)
app.include_router(files_routes.router)
app.include_router(scan_routes.router)


@app.get("/api/health")
def health():
    logger.info("Health check OK")
    return {"status": "ok"}


# SPA fallback — must come after every /api/* route so API paths are not shadowed.
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(FRONTEND_DIR / "index.html")
