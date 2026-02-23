"""OpenAPI schema generation for the Cadence application."""

from typing import Callable

from fastapi import FastAPI


def build_openapi_schema_generator(application: FastAPI) -> Callable[[], dict]:
    """Build a cached OpenAPI schema generator bound to the given application.

    Returns:
        A callable that generates (and caches) the OpenAPI schema on first call.
    """

    def generate_schema() -> dict:
        if application.openapi_schema:
            return application.openapi_schema

        from fastapi.openapi.utils import get_openapi

        openapi_schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
            servers=application.servers,
            tags=application.openapi_tags,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from authentication endpoint. Format: `Bearer <token>`",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication. Format: `X-API-Key: <key>`",
            },
        }

        openapi_schema["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []},
        ]

        openapi_schema["x-rate-limit"] = {
            "default": "100 requests per minute per tenant",
            "configurable": True,
        }

        application.openapi_schema = openapi_schema
        return application.openapi_schema

    return generate_schema
