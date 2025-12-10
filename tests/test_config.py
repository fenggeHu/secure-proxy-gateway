import asyncio
from pathlib import Path

import yaml

from core import config_mgr
from core.models import RequestRules, ResponseRules, RouteConfig, SystemConfig


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

    config_mgr.set_config(cfg)
    asyncio.run(config_mgr.save_config(cfg, path=cfg_path))
    assert cfg_path.exists()

    # save again to trigger backup creation
    cfg.routes[0].description = "updated"
    asyncio.run(config_mgr.save_config(cfg, path=cfg_path))
    backup = Path(str(cfg_path) + ".bak")
    assert backup.exists()

    loaded = config_mgr.load_config(cfg_path)
    assert loaded.routes[0].description == "updated"
    data = yaml.safe_load(cfg_path.read_text())
    assert data["routes"][0]["path"] == "/api/demo"
