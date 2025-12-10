from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from core.config_mgr import get_config, save_config, set_config
from core.models import SystemConfig

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _ensure_admin_access(request: Request) -> None:
    client_host = request.client.host if request.client else None
    admin_host = get_config().server.admin_host
    if client_host and client_host != admin_host:
        raise HTTPException(status_code=403, detail="Admin interface restricted")


@router.get("/ui", response_class=HTMLResponse)
async def ui(request: Request):
    _ensure_admin_access(request)
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/config")
async def get_current_config(request: Request):
    _ensure_admin_access(request)
    return get_config().model_dump()


@router.post("/api/config")
async def update_config(payload: dict, request: Request):
    _ensure_admin_access(request)
    try:
        new_config = SystemConfig.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    set_config(new_config)
    await save_config(new_config)
    return {"ok": True}
