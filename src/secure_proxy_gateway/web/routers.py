import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

# Ensure src directory is on sys.path for absolute imports
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ..core.config_mgr import (
    get_config,
    read_raw_config,
    save_config,
    save_config_raw,
    set_config,
)
from ..core.models import SystemConfig

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _ensure_admin_access(request: Request) -> None:
    client_host = request.client.host if request.client else None
    admin_host = get_config().server.admin_host
    if client_host and client_host != admin_host:
        raise HTTPException(status_code=403, detail="Admin interface restricted")


def _detect_format_from_content(content: str) -> str:
    """Detect config format based on first meaningful char."""
    first = ""
    for ch in content.lstrip():
        if not ch.isspace():
            first = ch
            break
    return "json" if first in ("{", "[") else "yaml"


@router.get("/ui", response_class=HTMLResponse)
async def ui(request: Request):
    _ensure_admin_access(request)
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/config")
async def get_current_config(request: Request):
    _ensure_admin_access(request)
    raw_content, fmt = read_raw_config()
    return {
        "config": get_config().model_dump(),
        "raw": raw_content,
        "format": fmt,
    }


@router.post("/api/config")
async def update_config(payload: dict, request: Request):
    _ensure_admin_access(request)
    # New path: accept raw content with format hint to avoid format conversion
    if "content" in payload:
        content = payload.get("content") or ""
        fmt = (payload.get("format") or "").strip().lower() or _detect_format_from_content(content)
        try:
            await save_config_raw(content, fmt)
        except Exception as exc:  # capture validation/parse errors
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "format": fmt}

    # Backward compatibility: accept structured JSON config
    try:
        new_config = SystemConfig.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    set_config(new_config)
    await save_config(new_config)
    return {"ok": True}
