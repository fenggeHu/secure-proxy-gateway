import httpx

from core.config_mgr import get_config
from core.models import SystemConfig

_http_client: httpx.AsyncClient | None = None


async def init_http_client(config: SystemConfig | None = None) -> None:
    """Initialize global HTTPX client."""
    global _http_client
    cfg = config or get_config()

    if _http_client is not None:
        await _http_client.aclose()

    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=cfg.proxy.timeout.connect,
            read=cfg.proxy.timeout.read,
            write=cfg.proxy.timeout.write,
        ),
        follow_redirects=False,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )


async def close_http_client() -> None:
    """Close global HTTPX client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    """Return initialized HTTPX client."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client
