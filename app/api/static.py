from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

router = APIRouter()


@router.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


def mount_static(app) -> None:
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
