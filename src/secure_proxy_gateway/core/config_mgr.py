import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from secure_proxy_gateway.core.exceptions import ConfigError
from secure_proxy_gateway.core.models import SystemConfig

BASE_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = BASE_DIR / "config.yaml"

_config: Optional[SystemConfig] = None
_write_lock = asyncio.Lock()


def load_config(path: Path | str = CONFIG_PATH) -> SystemConfig:
    """Load configuration from YAML file and cache it."""
    resolved = Path(path)
    if not resolved.exists():
        cfg = SystemConfig()
        set_config(cfg)
        return cfg

    with resolved.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        cfg = SystemConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc

    set_config(cfg)
    return cfg


def get_config() -> SystemConfig:
    """Return cached configuration, loading if necessary."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: SystemConfig) -> None:
    """Set in-memory configuration."""
    global _config
    _config = config


async def save_config(config: Optional[SystemConfig] = None, path: Path | str = CONFIG_PATH) -> None:
    """Persist configuration with backup and atomic write."""
    cfg = config or get_config()
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    data = cfg.model_dump()
    backup_path = Path(str(resolved) + ".bak")

    async with _write_lock:
        if resolved.exists():
            shutil.copy(resolved, backup_path)

        fd, tmp_path = tempfile.mkstemp(dir=resolved.parent, prefix=resolved.name, suffix=".tmp")
        tmp_file = Path(tmp_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
            os.replace(tmp_file, resolved)
        finally:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
