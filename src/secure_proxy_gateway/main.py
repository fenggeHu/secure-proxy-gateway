from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from secure_proxy_gateway.core.config_mgr import get_config, load_config
from secure_proxy_gateway.core.logging import configure_logging
from secure_proxy_gateway.proxy.client import close_http_client, init_http_client
from secure_proxy_gateway.proxy.engine import error_response, forward_request, match_route
from secure_proxy_gateway.web.routers import router as web_router

APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    configure_logging()
    await init_http_client(config)
    yield
    await close_http_client()


app = FastAPI(title="Secure Proxy Gateway", version=APP_VERSION, lifespan=lifespan)
app.include_router(web_router)


@app.get("/healthz")
async def health_check():
    return {"status": "ok", "version": APP_VERSION}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_entry(request: Request):
    config = get_config()
    route = match_route(str(request.url.path), request.method, config.routes)
    if not route:
        return error_response(404, "Route Not Found", request)
    if route.method != "*" and route.method != request.method.upper():
        return error_response(405, "Method Not Allowed", request)
    return await forward_request(request, route)
