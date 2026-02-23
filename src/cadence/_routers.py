"""API router registration for the Cadence application."""

from fastapi import FastAPI

from cadence.controller import (
    admin_controller,
    auth_controller,
    chat_controller,
    health_controller,
    orchestrator_controller,
    plugin_controller,
    system_plugin_controller,
    tenant_controller,
)


def register_api_routers(application: FastAPI) -> None:
    """Register all API route controllers with the application."""
    application.include_router(health_controller.router)
    application.include_router(auth_controller.router)
    application.include_router(chat_controller.router)
    application.include_router(orchestrator_controller.router)
    application.include_router(orchestrator_controller.engine_router)
    application.include_router(plugin_controller.router)
    application.include_router(system_plugin_controller.router)
    application.include_router(tenant_controller.router)
    application.include_router(admin_controller.router)
