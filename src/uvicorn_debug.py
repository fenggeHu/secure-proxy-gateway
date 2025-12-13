"""
用于本地启动Fastapi和调试
"""
import argparse
from pathlib import Path

import uvicorn

from secure_proxy_gateway.core.config_mgr import ENV_CONFIG_PATH, load_config, resolve_config_path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动 Secure Proxy Gateway 调试服务")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径（默认：env SPG_CONFIG_PATH 或 ./config.yaml）",
    )
    parser.add_argument("--host", type=str, default=None, help="服务绑定的主机地址")
    parser.add_argument("--port", type=int, default=None, help="服务监听的端口")
    parser.add_argument("--reload", action="store_true", help="是否启用自动重载（开发环境用）")

    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    # Ensure reload subprocess uses the same config path.
    if args.config:
        import os

        os.environ[ENV_CONFIG_PATH] = str(config_path)

    config = load_config(config_path)
    default_host = config.server.host
    default_port = config.server.port

    uvicorn.run(
        "secure_proxy_gateway.main:app",
        host=args.host or default_host,
        port=args.port or default_port,
        reload=args.reload,
        app_dir=str(ROOT),
    )
