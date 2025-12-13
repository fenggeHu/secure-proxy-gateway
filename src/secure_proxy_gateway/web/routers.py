from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
import ipaddress

from ..core.runtime import apply_config, maybe_reload_app_config
from ..core.config_mgr import (
    detect_config_format,
    read_raw_config,
    save_config,
    save_config_raw,
    validate_config_raw,
)
from ..core.models import SystemConfig

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _ensure_admin_access(request: Request) -> None:
    client_host = request.client.host if request.client else None
    admin_host = request.app.state.config.server.admin_host
    if not client_host:
        raise HTTPException(status_code=403, detail="Admin interface restricted")
    if client_host == admin_host:
        return
    if _is_loopback(client_host) and _is_loopback(admin_host):
        return
    if client_host != admin_host:
        raise HTTPException(status_code=403, detail="Admin interface restricted")


@router.get("/ui", response_class=HTMLResponse)
async def ui(request: Request):
    _ensure_admin_access(request)
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/config")
async def get_current_config(request: Request):
    _ensure_admin_access(request)
    await maybe_reload_app_config(request.app)
    config_path = request.app.state.config_path
    raw_content, fmt = await run_in_threadpool(read_raw_config, config_path)
    return {
        "config": request.app.state.config.model_dump(),
        "raw": raw_content,
        "format": fmt,
        "path": str(config_path),
    }


@router.post("/api/config")
async def update_config(payload: dict, request: Request):
    _ensure_admin_access(request)
    config_path = request.app.state.config_path
    minimal = (request.headers.get("X-Config-Minimal") or "").strip() in {"1", "true", "yes", "on"}
    # New path: accept raw content with format hint to avoid format conversion
    if "content" in payload:
        content = payload.get("content") or ""
        try:
            fmt = (payload.get("format") or "").strip().lower() or detect_config_format(content)
            new_config = await run_in_threadpool(save_config_raw, content, fmt, config_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await apply_config(request.app, new_config, fmt)
        return {"ok": True, "format": fmt}

    # Backward compatibility: accept structured JSON config
    try:
        new_config = SystemConfig.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    fmt = getattr(request.app.state, "config_format", "yaml")
    try:
        await run_in_threadpool(save_config, new_config, config_path, fmt, minimal)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await apply_config(request.app, new_config, fmt)
    return {"ok": True}


@router.post("/api/config/validate")
async def validate_config(payload: dict, request: Request):
    _ensure_admin_access(request)
    if "content" in payload:
        content = payload.get("content") or ""
        fmt = (payload.get("format") or "").strip().lower() or detect_config_format(content)
        try:
            cfg = await run_in_threadpool(validate_config_raw, content, fmt)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "config": cfg.model_dump()}

    try:
        cfg = SystemConfig.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "config": cfg.model_dump()}
