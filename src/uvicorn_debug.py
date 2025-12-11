"""
用于本地启动Fastapi和调试
"""
import argparse
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from secure_proxy_gateway.core.config_mgr import load_config
from secure_proxy_gateway.main import app

if __name__ == '__main__':
    config = load_config()
    default_host = config.server.host
    default_port = config.server.port

    parser = argparse.ArgumentParser(description="启动 Secure Proxy Gateway 调试服务")
    parser.add_argument(
        "--host",  # 参数名
        type=str,  # 参数类型
        default=default_host,
        help=f"服务绑定的主机地址（默认：{default_host}，来自 config.yaml）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help=f"服务监听的端口（默认：{default_port}，来自 config.yaml）"
    )
    parser.add_argument(
        "--reload",
        action="store_true",  # 无需传值，只要出现该参数就为 True
        help="是否启用自动重载（开发环境用）"
    )

    # 解析参数
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(SRC_DIR),
    )
