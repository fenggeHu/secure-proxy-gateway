import asyncio
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from secure_proxy_gateway.core.config_mgr import get_config, load_config, save_config, set_config
from secure_proxy_gateway.core.exceptions import ConfigError
from secure_proxy_gateway.core.models import (
    MaskRule,
    RequestRules,
    ResponseRules,
    RouteConfig,
    SystemConfig,
)

app = typer.Typer(help="Secure Proxy Gateway CLI")
console = Console()


def _persist_config(config: SystemConfig) -> None:
    asyncio.run(save_config(config))


@app.command()
def start(host: Optional[str] = None, port: Optional[int] = None, reload: bool = False):
    """Start proxy server."""
    config = load_config()
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
    config = load_config()
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
    config = load_config()
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
    set_config(config)
    _persist_config(config)
    console.print(f"[green]Added route {route_name}[/green]")


@app.command()
def rm(name: str):
    """Remove a route by name."""
    config = load_config()
    routes = [r for r in config.routes if r.name != name]
    if len(routes) == len(config.routes):
        console.print(f"[red]Route {name} not found[/red]")
        raise typer.Exit(code=1)
    config.routes = routes
    set_config(config)
    _persist_config(config)
    console.print(f"[green]Removed route {name}[/green]")


@app.command()
def mask(
    name: str,
    pattern: str = typer.Option(..., help="Regex pattern"),
    repl: str = typer.Option(..., help="Replacement string"),
):
    """Add masking rule to a route."""
    config = load_config()
    route = next((r for r in config.routes if r.name == name), None)
    if not route:
        console.print(f"[red]Route {name} not found[/red]")
        raise typer.Exit(code=1)

    route.response_rules.mask_regex.append(MaskRule(pattern=pattern, replacement=repl))
    set_config(config)
    _persist_config(config)
    console.print(f"[green]Added mask rule to {name}[/green]")


@app.command()
def validate():
    """Validate config file."""
    try:
        load_config()
    except ConfigError as exc:
        console.print(f"[red]Config invalid: {exc}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Config is valid[/green]")


def main():
    app()


if __name__ == "__main__":
    main()
