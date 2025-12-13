from pathlib import Path

import yaml

from secure_proxy_gateway.core import config_mgr
from secure_proxy_gateway.core.models import RequestRules, ResponseRules, RouteConfig, SystemConfig


def test_save_and_load_with_backup(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    route = RouteConfig(
        name="demo",
        path="/api/demo",
        target="https://example.com",
        request_rules=RequestRules(),
        response_rules=ResponseRules(),
    )
    cfg = SystemConfig(routes=[route])

    config_mgr.save_config(cfg, path=cfg_path)
    assert cfg_path.exists()

    # save again to trigger backup creation
    cfg.routes[0].description = "updated"
    config_mgr.save_config(cfg, path=cfg_path)
    backup = Path(str(cfg_path) + ".bak")
    assert backup.exists()

    loaded = config_mgr.load_config(cfg_path)
    assert loaded.routes[0].description == "updated"
    data = yaml.safe_load(cfg_path.read_text())
    assert data["routes"][0]["path"] == "/api/demo"


def test_resolve_config_path_searches_upwards(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    src_dir = repo_root / "src"
    src_dir.mkdir(parents=True)
    cfg_path = repo_root / "config.yaml"
    cfg_path.write_text("server: {}\n", encoding="utf-8")

    monkeypatch.chdir(src_dir)
    monkeypatch.delenv(config_mgr.ENV_CONFIG_PATH, raising=False)

    resolved = config_mgr.resolve_config_path()
    assert resolved == cfg_path
