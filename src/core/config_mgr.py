import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from core.exceptions import ConfigError
from core.models import SystemConfig

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config.yaml"
BACKUP_PATH = BASE_DIR / "config.yaml.bak"

_config: Optional[SystemConfig] = None
_write_lock = asyncio.Lock()


def load_config(path: Path | str = CONFIG_PATH) -> SystemConfig:
    """Load configuration from YAML file and cache it."""
    resolved_path = Path(path)
    if not resolved_path.exists():
        cfg = SystemConfig()
        set_config(cfg)
        return cfg

    with resolved_path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    try:
        cfg = SystemConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc

    set_config(cfg)
    return cfg


def get_config() -> SystemConfig:
    """Get cached config, loading from disk if needed."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: SystemConfig) -> None:
    """Replace in-memory config."""
    global _config
    _config = config


async def save_config(
    config: Optional[SystemConfig] = None, path: Path | str = CONFIG_PATH
) -> None:
    """Persist configuration with backup and atomic write."""
    cfg = config or get_config()
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    data = cfg.model_dump()
    backup_path = Path(str(resolved_path) + ".bak")

    async with _write_lock:
        if resolved_path.exists():
            shutil.copy(resolved_path, backup_path)

        fd, tmp_path = tempfile.mkstemp(
            dir=resolved_path.parent, prefix=resolved_path.name, suffix=".tmp"
        )
        tmp_file_path = Path(tmp_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                yaml.safe_dump(data, tmp_file, allow_unicode=True, sort_keys=False)
            os.replace(tmp_file_path, resolved_path)
        finally:
            if tmp_file_path.exists():
                tmp_file_path.unlink(missing_ok=True)
