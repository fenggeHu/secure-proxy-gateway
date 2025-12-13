# Secure Proxy Gateway

轻量级、配置驱动的反向代理网关，基于 FastAPI + HTTPX，支持请求参数/头重写、响应脱敏和可视化配置管理。

## 架构与核心模块
- FastAPI 应用：`secure_proxy_gateway.main.app`，统一入口与健康检查。
- 配置管理：默认 `./config.yaml`（或 env `SPG_CONFIG_PATH` / CLI `--config` 指定）+ Pydantic 校验（`core.config_mgr` / `core.models`）。
- 转发引擎：`proxy.engine` 使用最长前缀匹配路由，基于 HTTPX 异步转发。
- 请求/响应处理：参数合并、头清洗（移除 hop-by-hop）、响应体按正则脱敏，超大或非可脱敏类型直接流式透传。
- 管理接口：Typer CLI（`secure_proxy_gateway.cli.commands`）和 Web UI `/ui`（仅 `admin_host` 访问）。

目录速览：
- `src/secure_proxy_gateway/main.py`：FastAPI 入口与路由聚合
- `src/secure_proxy_gateway/core/`：配置、日志、模型
- `src/secure_proxy_gateway/proxy/`：转发、HTTP 客户端、脱敏逻辑
- `src/secure_proxy_gateway/web/`：Jinja2 Web UI 与配置 API
- `config.yaml`：运行时配置（默认位置，可通过 `SPG_CONFIG_PATH` / `--config` 覆盖）
- `tests/`：Pytest 用例

## 环境准备
- Python 3.10+
- 安装依赖：`pip install -r requirements.txt` 或开发模式 `pip install -e .`

## 配置说明（`config.yaml`）
```yaml
server:
  host: 0.0.0.0      # 服务监听地址
  port: 8000         # 服务端口
  admin_host: 127.0.0.1  # 允许访问 Web UI /api/config 的主机

proxy:
  timeout: {connect: 5.0, read: 30.0, write: 30.0}
  max_response_size: 10485760   # 超过则直接透传，不做脱敏
  strip_headers: [...]          # 转发时移除的 hop-by-hop 头

routes:
  - name: user-service
    path: /api/users            # 最长前缀匹配
    target: https://internal-user-service.local
    method: "*"                 # "*" 表示任意方法
    description: 用户服务代理
    request_rules:
      add_headers: {X-Proxy-Source: secure-gateway}
      add_params: {_from: proxy}
      del_params: [debug]
    response_rules:
      mask_regex:
        - pattern: "(\\d{3})\\d{4}(\\d{4})"
          replacement: "\\1****\\2"
```

要点：
- 路由按最长前缀匹配；若路径匹配但方法不允许，返回 `405`；`method="*"` 代表全方法。
- 请求：先合并 `add_params`/`add_headers`，再删除 `del_params`，并清洗 `strip_headers`。
- 响应：对 `application/json/text/html/text/xml/text/plain/application/xml` 且不超大小的响应按正则脱敏；其余直接流式返回。
- `admin_host` 限制 Web UI/配置 API，仅在本机默认可访问。

## 启动方式
- Typer CLI（推荐）：  
  `python -m secure_proxy_gateway.cli.commands --config ./config.yaml start --host 0.0.0.0 --port 8000 --reload`
- 直接 uvicorn：  
  `SPG_CONFIG_PATH=./config.yaml uvicorn secure_proxy_gateway.main:app --app-dir src --host 0.0.0.0 --port 8000`
- 本地调试脚本：  
  `python src/uvicorn_debug.py --config ./config.yaml --reload --host 0.0.0.0 --port 8000`

健康检查：`GET /healthz`

## 管理与运维
- Web UI：`/ui`（仅允许 `admin_host` 访问），查看/编辑完整配置，提交到 `/api/config`。
- CLI 命令（均在 `config.yaml` 上操作）：  
  - `python -m secure_proxy_gateway.cli.commands --config ./config.yaml ls` 列出路由  
  - `python -m secure_proxy_gateway.cli.commands --config ./config.yaml add --path /api/demo --target https://example.com --method GET` 添加路由  
  - `python -m secure_proxy_gateway.cli.commands --config ./config.yaml rm --name demo` 删除路由  
  - `python -m secure_proxy_gateway.cli.commands --config ./config.yaml mask --name user-service --pattern "(\\d{3})\\d{4}(\\d{4})" --repl "\\1****\\2"` 新增脱敏规则  
  - `python -m secure_proxy_gateway.cli.commands --config ./config.yaml validate` 校验配置

## 日志
- `core.logging.configure_logging` 输出 JSON 结构化日志（stdout），包含时间、等级、路由名、请求 ID、上游耗时、状态码等字段，便于采集分析。

## 测试
- 安装 dev 依赖后运行：`pytest`

## 常见问题
- 无法访问 `/ui`：确认请求来源 IP 等于 `config.server.admin_host`。
- 目标服务证书或联通性问题：查看日志中的 `Bad Gateway` / `Gateway Timeout`，检查上游地址、防火墙或证书。
- 新增路由未生效：确保 `config.yaml` 已保存且进程重新加载（`--reload` 或重启）。
