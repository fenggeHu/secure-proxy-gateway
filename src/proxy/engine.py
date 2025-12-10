import logging
import time
import uuid
from typing import Iterable, Mapping

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from core.config_mgr import get_config
from core.models import RequestRules, RouteConfig, SystemConfig
from proxy.client import get_http_client
from proxy.masking import MASKABLE_CONTENT_TYPES, mask_content

logger = logging.getLogger(__name__)


def match_route(path: str, method: str, routes: Iterable[RouteConfig]) -> RouteConfig | None:
    """Match route by longest prefix and method."""
    sorted_routes = sorted(routes, key=lambda r: len(r.path), reverse=True)
    method_upper = method.upper()
    for route in sorted_routes:
        if path.startswith(route.path):
            if route.method == "*" or route.method.upper() == method_upper:
                return route
    return None


def merge_params(query_params: Mapping[str, str], rules: RequestRules) -> dict:
    """Merge incoming query params with configured add/del rules."""
    merged = dict(query_params)
    merged.update(rules.add_params)
    for key in rules.del_params:
        merged.pop(key, None)
    return merged


def clean_headers(
    headers: Mapping[str, str], strip_list: Iterable[str], add_headers: Mapping[str, str]
) -> dict:
    """Remove hop-by-hop headers and append configured headers."""
    blacklist = {h.lower() for h in strip_list}
    cleaned = {k: v for k, v in headers.items() if k.lower() not in blacklist}
    cleaned.update(add_headers)
    return cleaned


def error_response(status_code: int, message: str, request: Request) -> JSONResponse:
    """Generate unified error response."""
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])
    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "request_id": request_id,
            "path": str(request.url.path),
        },
    )


async def process_response(
    upstream_resp: httpx.Response, route: RouteConfig, config: SystemConfig
) -> Response:
    """Handle upstream response and apply masking when needed."""
    content_type = upstream_resp.headers.get("content-type", "").split(";")[0].strip().lower()
    raw_length = upstream_resp.headers.get("content-length")
    try:
        content_length = int(raw_length) if raw_length else 0
    except ValueError:
        content_length = 0

    if (
        content_type not in MASKABLE_CONTENT_TYPES
        or (content_length and content_length > config.proxy.max_response_size)
    ):
        return StreamingResponse(
            upstream_resp.aiter_bytes(),
            status_code=upstream_resp.status_code,
            headers=dict(upstream_resp.headers),
        )

    content = upstream_resp.text
    masked = mask_content(content, route.response_rules.mask_regex)
    headers = dict(upstream_resp.headers)
    headers.pop("content-length", None)  # avoid mismatch after masking

    return Response(
        content=masked,
        status_code=upstream_resp.status_code,
        headers=headers,
        media_type=content_type or None,
    )


async def forward_request(request: Request, route: RouteConfig) -> Response:
    """Forward incoming request to upstream and handle response."""
    client = get_http_client()
    config = get_config()
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])

    upstream_path = request.url.path[len(route.path) :] if request.url.path.startswith(route.path) else request.url.path
    upstream_url = route.target.rstrip("/") + upstream_path

    req_params = merge_params(request.query_params, route.request_rules)
    req_headers = clean_headers(
        request.headers,
        strip_list=config.proxy.strip_headers,
        add_headers=route.request_rules.add_headers,
    )

    body = await request.body()
    start = time.monotonic()
    try:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream_url,
            params=req_params,
            headers=req_headers,
            content=body,
        )
    except httpx.ConnectError:
        logger.warning(
            "Upstream connection failed",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(502, "Bad Gateway", request)
    except httpx.TimeoutException:
        logger.warning(
            "Upstream timeout",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(504, "Gateway Timeout", request)
    except httpx.HTTPError:
        logger.warning(
            "Upstream HTTP error",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(502, "Bad Gateway", request)

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Request forwarded",
        extra={
            "request_id": request_id,
            "route_name": route.name,
            "upstream_ms": duration_ms,
            "status_code": upstream_resp.status_code,
        },
    )
    return await process_response(upstream_resp, route, config)
