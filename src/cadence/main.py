"""Cadence v2 FastAPI application.

This module creates and configures the Cadence multi-tenant AI agent platform API.
"""

# ruff: noqa: E402  — load_dotenv() must run before any cadence imports that read env

import logging
from pathlib import Path

from dotenv import load_dotenv

_dotenv_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

from fastapi import FastAPI

from cadence._middleware import (
    configure_cors_middleware,
    configure_error_handlers_middleware,
    configure_rate_limiting_middleware,
    configure_tenant_context_middleware,
)
from cadence._openapi import build_openapi_schema_generator
from cadence._routers import register_api_routers
from cadence._startup import create_lifespan_handler
from cadence.config.app_settings import AppSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app_settings = AppSettings()

app = FastAPI(
    title="Cadence v2 (rev2.0.1)",
    description="""
# Multi-Tenant AI Orchestration Platform

Production-ready framework for deploying AI agent orchestrators at scale.

## Features

* **Multi-Backend Support**: LangGraph, OpenAI Agents SDK, Google ADK
* **Multi-Tenancy**: Complete tenant isolation with BYOK (Bring Your Own Key)
* **Three Orchestration Modes**: Supervisor, Coordinator, Handoff
* **Hot-Reload**: Configuration changes without restart
* **Scalable Architecture**: Hot/Warm/Cold tier pool (1000+ instances)
* **Streaming**: Server-Sent Events (SSE) for real-time responses

## Authentication

### JWT Authentication
```
Authorization: Bearer <jwt_token>
```

### API Key Authentication
```
X-API-Key: <api_key>
```

## Rate Limiting

All API endpoints are rate-limited per tenant. Default: 100 requests/minute.

## Documentation

* Platform Docs: [README](https://github.com/jonaskahn/cadence)
* SDK Docs: [cadence-sdk](https://github.com/jonaskahn/cadence-sdk)
""",
    version="2.0.0",
    lifespan=create_lifespan_handler(app_settings),
    contact={
        "name": "Cadence Platform Support",
        "url": "https://github.com/jonaskahn/cadence",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://example.com/terms/",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check endpoints for monitoring system availability and database connectivity.",
        },
        {
            "name": "completion",
            "description": "Chat endpoints for interacting with AI orchestrators. Supports both streaming (SSE) and synchronous responses.",
        },
        {
            "name": "orchestrators",
            "description": "CRUD operations for managing orchestrator instances. Includes hot-reload configuration updates.",
        },
        {
            "name": "plugins",
            "description": "Plugin management endpoints for discovering, uploading, and configuring plugins.",
        },
        {
            "name": "tenants",
            "description": "Tenant (organization) management including settings, LLM configurations, and user management.",
        },
        {
            "name": "admin",
            "description": "Administrative endpoints for platform-wide settings, health monitoring, and pool statistics. Requires admin privileges.",
        },
    ],
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
        {
            "url": "https://api.example.com",
            "description": "Production server",
        },
        {
            "url": "https://staging-api.example.com",
            "description": "Staging server",
        },
    ],
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.openapi = build_openapi_schema_generator(app)

cors_origins = app_settings.cors_origins if app_settings.cors_origins else ["*"]
configure_cors_middleware(app, cors_origins)
configure_rate_limiting_middleware(app)
configure_tenant_context_middleware(app, app_settings)
configure_error_handlers_middleware(app, app_settings)

register_api_routers(app)

logger.info("Cadence v2 application configured")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "cadence.main:app",
        host=app_settings.api_host,
        port=app_settings.api_port,
        reload=app_settings.debug,
    )
