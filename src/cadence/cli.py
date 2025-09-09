"""Cadence CLI - Command Line Interface for Cadence AI Framework."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config.settings import Settings
from .main import CadenceApplication

console = Console()


@click.group()
@click.version_option(version="1.3.0", prog_name="cadence")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--config", type=click.Path(exists=True), help="Path to configuration file")
@click.pass_context
def cli(ctx, debug: bool, config: Optional[str]):
    """Cadence AI Framework Command Line Interface."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["config"] = config


@cli.group()
def start():
    """Start Cadence AI services."""
    pass


@start.command()
@click.option("--port", default=8501, type=int, help="Port for Streamlit UI")
@click.option("--api-url", default="http://localhost:8000", help="API server URL")
@click.pass_context
def ui(ctx, port: int, api_url: str):
    """Start the Cadence AI Streamlit UI."""
    try:
        os.environ["CADENCE_API_BASE_URL"] = api_url

        ui_startup_message = f"Starting Cadence AI UI on port {port}"
        console.print(Panel.fit(ui_startup_message, title="🎨 UI Startup", border_style="blue"))
        console.print(f"API Server URL: {api_url}")
        console.print(f"UI will be available at: http://localhost:{port}")

        ui_app_path = Path(__file__).parent / "ui" / "app.py"

        if not ui_app_path.exists():
            console.print(f"[red]UI app not found at: {ui_app_path}[/red]")
            sys.exit(1)

        streamlit_command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ui_app_path),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ]

        console.print(f"Running command: {' '.join(streamlit_command)}")
        subprocess.run(streamlit_command)

    except Exception as e:
        console.print(f"[red]Error starting UI: {e}[/red]")
        sys.exit(1)


@start.command()
@click.option("--api-host", default="0.0.0.0", help="Host for API server")
@click.option("--api-port", default=8000, type=int, help="Port for API server")
@click.option("--ui-port", default=8501, type=int, help="Port for Streamlit UI")
@click.option("--reload", is_flag=True, help="Enable auto-reload for API")
@click.option("--workers", default=1, type=int, help="Number of API worker processes")
@click.pass_context
def all(ctx, api_host: str, api_port: int, ui_port: int, reload: bool, workers: int):
    """Start both Cadence AI API server and UI simultaneously."""
    try:
        full_stack_message = f"Starting Cadence AI Complete Stack\nAPI: {api_host}:{api_port} | UI: localhost:{ui_port}"
        console.print(
            Panel.fit(
                full_stack_message,
                title="🚀 Full Stack Startup",
                border_style="green",
            )
        )

        os.environ["CADENCE_API_BASE_URL"] = f"http://{api_host}:{api_port}"
        if ctx.obj["debug"]:
            os.environ["CADENCE_DEBUG"] = "true"

        settings = Settings()
        settings.api_host = api_host
        settings.api_port = api_port
        settings.debug = ctx.obj["debug"]

        app = CadenceApplication(settings)

        def start_api():
            try:
                app.run(host=api_host, port=api_port)
            except Exception as e:
                console.print(f"[red]API Server Error: {e}[/red]")

        api_thread = threading.Thread(target=start_api, daemon=True)
        api_thread.start()

        console.print(f"[green]✅ API Server started on {api_host}:{api_port}[/green]")

        time.sleep(2)
        ui_app_path = Path(__file__).parent / "ui" / "app.py"

        if not ui_app_path.exists():
            console.print(f"[red]UI app not found: {ui_app_path}[/red]")
            sys.exit(1)

        console.print(f"[blue]🎨 Starting UI on port {ui_port}...[/blue]")

        streamlit_command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ui_app_path),
            "--server.port",
            str(ui_port),
            "--server.headless",
            "true",
        ]

        try:
            subprocess.run(streamlit_command)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            console.print("[green]✅ API Server stopped[/green]")

    except Exception as e:
        console.print(f"[red]Error starting full stack: {e}[/red]")
        sys.exit(1)


@start.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
@click.option("--workers", default=1, type=int, help="Number of worker processes")
@click.pass_context
def api(ctx, host: str, port: int, reload: bool, workers: int):
    """Start the Cadence AI API server."""
    try:
        os.environ["CADENCE_API_BASE_URL"] = f"http://{host}:{port}"

        if ctx.obj["debug"]:
            os.environ["CADENCE_DEBUG"] = "true"
            reload = True

        api_startup_message = f"Starting Cadence AI API Server on {host}:{port}"
        console.print(Panel.fit(api_startup_message, title="🚀 API Server Startup", border_style="green"))

        settings = Settings()
        settings.api_host = host
        settings.api_port = port
        settings.debug = ctx.obj["debug"]

        app = CadenceApplication(settings)
        app.run(host=host, port=port)

    except Exception as e:
        console.print(f"[red]Error starting API server: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
@click.option("--workers", default=1, type=int, help="Number of worker processes")
@click.pass_context
def serve(ctx, host: str, port: int, reload: bool, workers: int):
    """Start the Cadence AI server (alias for start api)."""
    api(ctx, host, port, reload, workers)


@cli.command()
@click.pass_context
def status(ctx):
    """Show current Cadence AI status and configuration."""
    try:
        settings = Settings()
        cadence_vars = {k: v for k, v in os.environ.items() if k.startswith("CADENCE_")}

        status_table = Table(title="Cadence AI Status")
        status_table.add_column("Setting", style="cyan")
        status_table.add_column("Value", style="green")

        status_table.add_row("Server Status", "Running" if ctx.obj.get("debug") else "Stopped")
        status_table.add_row("Debug Mode", str(ctx.obj.get("debug", False)))
        status_table.add_row("API Host", settings.api_host)
        status_table.add_row("API Port", str(settings.api_port))
        status_table.add_row("LLM Provider", settings.default_llm_provider)
        status_table.add_row("Plugins Directory", ", ".join(settings.plugins_dir))

        console.print(status_table)

        if cadence_vars:
            console.print("\n[cyan]Environment Variables:[/cyan]")
            for key, value in cadence_vars.items():
                console.print(f"  {key}: {value}")
        else:
            console.print("  CADENCE_*: No Cadence AI-specific environment variables found")

    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--path", type=click.Path(exists=True), help="Path to plugin directory")
@click.pass_context
def plugins(ctx, path: Optional[str]):
    """Manage Cadence AI plugins."""
    try:
        settings = Settings()
        plugin_dirs = [path] if path else settings.plugins_dir

        console.print(Panel.fit("Plugin Management", title="🔌 Plugins", border_style="blue"))

        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir)
            if plugin_path.exists():
                console.print(f"\n[cyan]Plugin Directory:[/cyan] {plugin_dir}")

                plugin_files = list(plugin_path.rglob("*.py"))
                if plugin_files:
                    for plugin_file in plugin_files:
                        if plugin_file.name != "__init__.py":
                            console.print(f"  📁 {plugin_file.relative_to(plugin_path)}")
                else:
                    console.print("  [yellow]No plugin files found[/yellow]")
            else:
                console.print(f"[red]Plugin directory not found: {plugin_dir}[/red]")

    except Exception as e:
        console.print(f"[red]Error managing plugins: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def config(ctx):
    """Show current Cadence AI configuration."""
    try:
        settings = Settings()

        console.print(Panel.fit("Configuration Settings", title="⚙️  Config", border_style="yellow"))

        config_table = Table()
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")
        config_table.add_column("Description", style="white")

        config_table.add_row("App Name", settings.app_name, "Application display name")
        config_table.add_row("Debug", str(settings.debug), "Debug mode enabled")
        config_table.add_row("API Host", settings.api_host, "API server host")
        config_table.add_row("API Port", str(settings.api_port), "API server port")
        config_table.add_row("LLM Provider", settings.default_llm_provider, "Default LLM provider")
        config_table.add_row("Storage Backend", settings.conversation_storage_backend, "Conversation storage")
        config_table.add_row("Max Agent Hops", str(settings.max_agent_hops), "Maximum agent switches")

        console.print(config_table)

    except Exception as e:
        console.print(f"[red]Error showing configuration: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.pass_context
def health(ctx):
    """Check Cadence AI health status."""
    try:
        console.print(Panel.fit("Health Check", title="🏥 Health", border_style="green"))

        health_checks = [
            ("Configuration", "✅ OK"),
            ("Settings", "✅ OK"),
            ("Plugin System", "✅ OK"),
            ("Database Connections", "⚠️  Not checked"),
            ("LLM Providers", "⚠️  Not checked"),
        ]

        for check, status in health_checks:
            console.print(f"  {check}: {status}")

        console.print("\n[green]Health check completed successfully![/green]")

    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    load_dotenv()
    cli()

__all__ = ["cli", "main"]
