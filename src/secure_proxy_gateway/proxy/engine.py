import logging
import time
import uuid
from typing import Iterable, Mapping

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from ..core.models import RequestRules, RouteConfig, SystemConfig
from ..proxy.masking import MASKABLE_CONTENT_TYPES, mask_content

logger = logging.getLogger(__name__)


def match_route(path: str, method: str, routes: Iterable[RouteConfig]) -> tuple[RouteConfig | None, bool]:
    """
    Match route by longest prefix. Returns (route, has_path_match).

    - has_path_match=False => no prefix match (404)
    - has_path_match=True and route=None => prefix exists but method not allowed (405)
    """
    candidates = [route for route in routes if path.startswith(route.path)]
    if not candidates:
        return None, False

    max_len = max(len(route.path) for route in candidates)
    best = [route for route in candidates if len(route.path) == max_len]

    method_upper = method.upper()
    for route in best:
        if route.method != "*" and route.method.upper() == method_upper:
            return route, True
    for route in best:
        if route.method == "*":
            return route, True
    return None, True


def merge_params(query_params: Mapping[str, str], rules: RequestRules) -> list[tuple[str, str]]:
    """Merge incoming query params with configured add/del rules, preserving multi-values."""
    del_keys = set(rules.del_params)
    add_keys = set(rules.add_params.keys())
    if hasattr(query_params, "multi_items"):
        incoming_items = list(query_params.multi_items())  # type: ignore[attr-defined]
    else:
        incoming_items = list(query_params.items())
    merged = [
        (key, value)
        for key, value in incoming_items
        if key not in del_keys and key not in add_keys
    ]
    for key, value in rules.add_params.items():
        if key not in del_keys:
            merged.append((key, value))
    return merged


def clean_headers(
    headers: Mapping[str, str], strip_list: Iterable[str], add_headers: Mapping[str, str]
) -> dict:
    """Remove hop-by-hop headers and append configured headers."""
    blacklist = {h.lower() for h in strip_list}
    cleaned = {k: v for k, v in headers.items() if k.lower() not in blacklist}
    cleaned.update(add_headers)
    return cleaned


def _request_id(request: Request) -> str:
    value = request.headers.get("X-Request-Id")
    return value or str(uuid.uuid4())[:8]


def error_response(
    status_code: int,
    message: str,
    request: Request,
    request_id: str | None = None,
) -> JSONResponse:
    """Generate unified error response."""
    request_id = request_id or _request_id(request)
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "request_id": request_id,
            "path": str(request.url.path),
        },
    )
    response.headers["X-Request-Id"] = request_id
    return response


async def process_response(
    upstream_resp: httpx.Response, route: RouteConfig, config: SystemConfig, request_id: str
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
        headers = dict(upstream_resp.headers)
        headers["X-Request-Id"] = request_id
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers=headers,
            background=BackgroundTask(upstream_resp.aclose),
        )

    await upstream_resp.aread()
    content = upstream_resp.text
    await upstream_resp.aclose()

    masked = mask_content(content, route.response_rules.mask_regex)
    headers = dict(upstream_resp.headers)
    headers.pop("content-length", None)  # avoid mismatch after masking
    headers["X-Request-Id"] = request_id

    return Response(
        content=masked,
        status_code=upstream_resp.status_code,
        headers=headers,
        media_type=content_type or None,
    )


async def forward_request(request: Request, route: RouteConfig) -> Response:
    """Forward incoming request to upstream and handle response."""
    client: httpx.AsyncClient = request.app.state.http_client
    config: SystemConfig = request.app.state.config
    request_id = _request_id(request)

    upstream_path = request.url.path[len(route.path) :] if request.url.path.startswith(route.path) else request.url.path
    if not upstream_path:
        upstream_path = "/"
    elif not upstream_path.startswith("/"):
        upstream_path = "/" + upstream_path
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
        upstream_req = client.build_request(
            method=request.method,
            url=upstream_url,
            params=req_params,
            headers=req_headers,
            content=body,
        )
        upstream_resp = await client.send(upstream_req, stream=True)
    except httpx.ConnectError:
        logger.warning(
            "Upstream connection failed",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(502, "Bad Gateway", request, request_id)
    except httpx.TimeoutException:
        logger.warning(
            "Upstream timeout",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(504, "Gateway Timeout", request, request_id)
    except httpx.HTTPError:
        logger.warning(
            "Upstream HTTP error",
            extra={"request_id": request_id, "route_name": route.name},
        )
        return error_response(502, "Bad Gateway", request, request_id)

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Request forwarded",
        extra={
            "request_id": request_id,
            "route_name": route.name,
            "upstream_ms": duration_ms,
            "status_code": upstream_resp.status_code,
            "method": request.method.upper(),
            "path": str(request.url.path),
        },
    )
    return await process_response(upstream_resp, route, config, request_id)
