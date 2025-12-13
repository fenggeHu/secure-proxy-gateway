from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from secure_proxy_gateway.core.config_mgr import read_raw_config, resolve_config_path, load_config
from secure_proxy_gateway.core.logging import configure_logging
from secure_proxy_gateway.core.runtime import init_runtime_state, maybe_reload_app_config
from secure_proxy_gateway.proxy.client import create_http_client
from secure_proxy_gateway.proxy.engine import error_response, forward_request, match_route
from secure_proxy_gateway.web.routers import router as web_router

APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    config_path = resolve_config_path()
    config = load_config(config_path)
    _, fmt = read_raw_config(config_path)
    http_client = create_http_client(config)

    init_runtime_state(app, config_path, config, fmt, http_client)

    yield
    await http_client.aclose()


app = FastAPI(title="Secure Proxy Gateway", version=APP_VERSION, lifespan=lifespan)
_STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(web_router)


@app.get("/healthz")
async def health_check():
    return {"status": "ok", "version": APP_VERSION}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_entry(request: Request):
    await maybe_reload_app_config(request.app)
    config = request.app.state.config
    route, has_path_match = match_route(str(request.url.path), request.method, config.routes)
    if not has_path_match:
        return error_response(404, "Route Not Found", request)
    if route is None:
        return error_response(405, "Method Not Allowed", request)
    return await forward_request(request, route)
