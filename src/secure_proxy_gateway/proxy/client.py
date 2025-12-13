import httpx

from ..core.models import SystemConfig


def create_http_client(config: SystemConfig) -> httpx.AsyncClient:
    """Create an HTTPX client for proxy forwarding."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=config.proxy.timeout.connect,
            read=config.proxy.timeout.read,
            write=config.proxy.timeout.write,
            pool=config.proxy.timeout.read,
        ),
        follow_redirects=False,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
