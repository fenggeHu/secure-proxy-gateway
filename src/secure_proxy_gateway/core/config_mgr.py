import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import ValidationError

from secure_proxy_gateway.core.exceptions import ConfigError
from secure_proxy_gateway.core.models import SystemConfig

CONFIG_FORMAT = Literal["yaml", "json"]

ENV_CONFIG_PATH = "SPG_CONFIG_PATH"
DEFAULT_CONFIG_BASENAME = "config.yaml"

_write_lock = threading.Lock()


def _find_config_upwards(start: Path, basename: str) -> Path | None:
    current = start
    while True:
        candidate = current / basename
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def resolve_config_path(path: Path | str | None = None) -> Path:
    """Resolve config path from explicit arg, env var, or CWD default."""
    if path is not None:
        return Path(path)
    env_path = (os.getenv(ENV_CONFIG_PATH) or "").strip()
    if env_path:
        return Path(env_path)
    cwd = Path.cwd()
    found = _find_config_upwards(cwd, DEFAULT_CONFIG_BASENAME)
    return found or (cwd / DEFAULT_CONFIG_BASENAME)


def detect_config_format(text: str) -> CONFIG_FORMAT:
    """Detect config format by leading non-space character."""
    stripped = text.lstrip()
    if not stripped:
        return "yaml"
    return "json" if stripped[0] in ("{", "[") else "yaml"


def _load_raw_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_config(text: str, fmt: CONFIG_FORMAT) -> dict:
    if fmt == "json":
        return json.loads(text or "{}")
    return yaml.safe_load(text) or {}


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = Path(str(path) + ".bak")

    with _write_lock:
        if path.exists():
            shutil.copy(path, backup_path)

        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
        tmp_file = Path(tmp_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp_file, path)
        finally:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)


def read_raw_config(path: Path | str | None = None) -> tuple[str, CONFIG_FORMAT]:
    """Return raw config content and detected format."""
    resolved = resolve_config_path(path)
    content = _load_raw_text(resolved)
    return content, detect_config_format(content)


def load_config(path: Path | str | None = None) -> SystemConfig:
    """Load configuration from YAML/JSON file."""
    resolved = resolve_config_path(path)
    raw_text = _load_raw_text(resolved)
    fmt = detect_config_format(raw_text)

    if not raw_text.strip() and not resolved.exists():
        return SystemConfig()

    try:
        data = _parse_config(raw_text, fmt)
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        raise ConfigError(str(exc)) from exc

    try:
        return SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def save_config(
    config: SystemConfig,
    path: Path | str | None = None,
    fmt: Optional[CONFIG_FORMAT] = None,
    minimal: bool = False,
) -> None:
    """Persist configuration with backup and atomic write."""
    resolved = resolve_config_path(path)
    if fmt is None:
        raw_text = _load_raw_text(resolved)
        fmt = detect_config_format(raw_text)

    data = config.model_dump(exclude_defaults=minimal, exclude_none=minimal)
    if fmt == "json":
        content = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    _atomic_write_text(resolved, content)


def validate_config_raw(content: str, fmt: CONFIG_FORMAT = "yaml") -> SystemConfig:
    """Validate raw config content (yaml/json) and return parsed config without writing."""
    fmt_lower = str(fmt).strip().lower()
    if fmt_lower not in {"yaml", "json"}:
        raise ValueError(f"Unsupported format: {fmt}")
    fmt_typed: CONFIG_FORMAT = "json" if fmt_lower == "json" else "yaml"

    try:
        data = _parse_config(content, fmt_typed)
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        raise ConfigError(str(exc)) from exc

    try:
        return SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def save_config_raw(
    content: str,
    fmt: CONFIG_FORMAT = "yaml",
    path: Path | str | None = None,
) -> SystemConfig:
    """Persist raw config content (yaml/json) while validating structure."""
    fmt_lower = str(fmt).strip().lower()
    if fmt_lower not in {"yaml", "json"}:
        raise ValueError(f"Unsupported format: {fmt}")
    fmt_typed: CONFIG_FORMAT = "json" if fmt_lower == "json" else "yaml"

    try:
        data = _parse_config(content, fmt_typed)
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        raise ConfigError(str(exc)) from exc

    try:
        cfg = SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc

    resolved = resolve_config_path(path)
    _atomic_write_text(resolved, content)
    return cfg
