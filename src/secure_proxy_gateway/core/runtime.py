import asyncio
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from ..core.config_mgr import read_raw_config, load_config
from ..core.models import SystemConfig
from ..proxy.client import create_http_client


def _proxy_timeout_signature(config: SystemConfig) -> tuple[float, float, float]:
    t = config.proxy.timeout
    return (float(t.connect), float(t.read), float(t.write))


async def _close_client_later(client, delay_s: float = 5.0) -> None:
    try:
        await asyncio.sleep(delay_s)
        await client.aclose()
    except Exception:
        pass


def init_runtime_state(app, config_path: Path, config: SystemConfig, fmt: str, http_client) -> None:
    app.state.config_path = config_path
    app.state.config_format = fmt
    app.state.config = config
    app.state.http_client = http_client
    app.state.config_reload_lock = asyncio.Lock()
    app.state.config_mtime = config_path.stat().st_mtime if config_path.exists() else 0.0
    app.state.http_client_sig = _proxy_timeout_signature(config)


async def apply_config(app, config: SystemConfig, fmt: str | None = None) -> None:
    """
    Apply new config to app.state and update http client only when needed.

    Route changes should take effect immediately without disrupting in-flight requests.
    """
    if fmt is not None:
        app.state.config_format = fmt
    app.state.config = config

    config_path: Path = app.state.config_path
    app.state.config_mtime = config_path.stat().st_mtime if config_path.exists() else 0.0

    new_sig = _proxy_timeout_signature(config)
    old_sig = getattr(app.state, "http_client_sig", None)
    if old_sig == new_sig:
        return

    old_client = app.state.http_client
    app.state.http_client = create_http_client(config)
    app.state.http_client_sig = new_sig
    asyncio.create_task(_close_client_later(old_client))


async def maybe_reload_app_config(app) -> None:
    """Reload config from disk if mtime has changed (supports multi-worker setups)."""
    config_path: Path = app.state.config_path
    try:
        mtime = config_path.stat().st_mtime
    except FileNotFoundError:
        return

    if mtime <= getattr(app.state, "config_mtime", 0.0):
        return

    async with app.state.config_reload_lock:
        try:
            mtime2 = config_path.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime2 <= getattr(app.state, "config_mtime", 0.0):
            return

        config = await run_in_threadpool(load_config, config_path)
        _, fmt = await run_in_threadpool(read_raw_config, config_path)
        await apply_config(app, config, fmt)
