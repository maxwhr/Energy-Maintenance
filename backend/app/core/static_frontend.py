from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BACKEND_DIR / "static" / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
ASSETS_DIR = FRONTEND_DIR / "assets"

PROTECTED_PREFIXES = {
    "api",
    "docs",
    "redoc",
    "assets",
}
PROTECTED_PATHS = {
    "openapi.json",
}


def _is_within_frontend(path: Path) -> bool:
    try:
        path.resolve().relative_to(FRONTEND_DIR.resolve())
    except ValueError:
        return False
    return True


def _frontend_file(path: str) -> Path | None:
    candidate = FRONTEND_DIR / path
    if not _is_within_frontend(candidate):
        return None
    if candidate.is_file():
        return candidate
    return None


def register_static_frontend(app: FastAPI) -> None:
    if not INDEX_FILE.is_file():
        logger.info("Static frontend not installed; missing %s", INDEX_FILE)
        return

    if ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def frontend_root() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        first_segment = full_path.split("/", 1)[0]
        if first_segment in PROTECTED_PREFIXES or full_path in PROTECTED_PATHS:
            raise HTTPException(status_code=404, detail="Not found")

        static_file = _frontend_file(full_path)
        if static_file:
            return FileResponse(static_file)

        return FileResponse(INDEX_FILE)

    logger.info("Static frontend registered from %s", FRONTEND_DIR)
