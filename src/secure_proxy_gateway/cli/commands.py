import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from secure_proxy_gateway.core.config_mgr import ENV_CONFIG_PATH, load_config, resolve_config_path, save_config
from secure_proxy_gateway.core.exceptions import ConfigError
from secure_proxy_gateway.core.models import (
    MaskRule,
    RequestRules,
    ResponseRules,
    RouteConfig,
)

app = typer.Typer(help="Secure Proxy Gateway CLI")
console = Console()


def _config_path_from_ctx() -> Path:
    ctx = typer.get_current_context()
    config_path = (ctx.obj or {}).get("config_path")
    return resolve_config_path(config_path)


@app.callback()
def _main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Config file path (default: env SPG_CONFIG_PATH or ./config.yaml)",
        envvar=ENV_CONFIG_PATH,
    ),
):
    ctx.obj = {"config_path": config}


@app.command()
def start(host: Optional[str] = None, port: Optional[int] = None, reload: bool = False):
    """Start proxy server."""
    config_path = _config_path_from_ctx()
    os.environ[ENV_CONFIG_PATH] = str(config_path)
    config = load_config(config_path)
    serve_host = host or config.server.host
    serve_port = port or config.server.port
    src_dir = Path(__file__).resolve().parents[2]
    uvicorn.run(
        "secure_proxy_gateway.main:app",
        host=serve_host,
        port=serve_port,
        reload=reload,
        app_dir=str(src_dir),
    )


@app.command("ls")
def list_routes():
    """List configured routes."""
    config = load_config(_config_path_from_ctx())
    table = Table(title="Routes")
    table.add_column("Name")
    table.add_column("Method")
    table.add_column("Path")
    table.add_column("Target")
    table.add_column("Description", overflow="fold")

    for route in config.routes:
        table.add_row(
            route.name,
            route.method,
            route.path,
            route.target,
            route.description or "",
        )
    console.print(table)


@app.command()
def add(
    path: str,
    target: str,
    name: Optional[str] = typer.Option(None, help="Unique route name"),
    method: str = typer.Option("*", help="HTTP method, * for all"),
    description: Optional[str] = typer.Option(None, help="Description"),
):
    """Add new route."""
    config_path = _config_path_from_ctx()
    config = load_config(config_path)
    route_name = name or (path.strip("/") or "root")
    if any(route.name == route_name for route in config.routes):
        console.print(f"[red]Route name '{route_name}' already exists[/red]")
        raise typer.Exit(code=1)

    new_route = RouteConfig(
        name=route_name,
        path=path,
        target=target,
        method=method,
        description=description,
        request_rules=RequestRules(),
        response_rules=ResponseRules(),
    )
    config.routes.append(new_route)
    save_config(config, config_path)
    console.print(f"[green]Added route {route_name}[/green]")


@app.command()
def rm(name: str):
    """Remove a route by name."""
    config_path = _config_path_from_ctx()
    config = load_config(config_path)
    routes = [r for r in config.routes if r.name != name]
    if len(routes) == len(config.routes):
        console.print(f"[red]Route {name} not found[/red]")
        raise typer.Exit(code=1)
    config.routes = routes
    save_config(config, config_path)
    console.print(f"[green]Removed route {name}[/green]")


@app.command()
def mask(
    name: str,
    pattern: str = typer.Option(..., help="Regex pattern"),
    repl: str = typer.Option(..., help="Replacement string"),
):
    """Add masking rule to a route."""
    config_path = _config_path_from_ctx()
    config = load_config(config_path)
    route = next((r for r in config.routes if r.name == name), None)
    if not route:
        console.print(f"[red]Route {name} not found[/red]")
        raise typer.Exit(code=1)

    route.response_rules.mask_regex.append(MaskRule(pattern=pattern, replacement=repl))
    save_config(config, config_path)
    console.print(f"[green]Added mask rule to {name}[/green]")


@app.command()
def validate():
    """Validate config file."""
    try:
        load_config(_config_path_from_ctx())
    except ConfigError as exc:
        console.print(f"[red]Config invalid: {exc}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Config is valid[/green]")


def main():
    app()


if __name__ == "__main__":
    main()
