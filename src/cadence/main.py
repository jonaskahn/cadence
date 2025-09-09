"""Cadence Multi-Agent AI Framework application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .api.routes import router as api_router
from .api.services import global_service_container, initialize_api
from .config.settings import Settings

app_instance: Optional[FastAPI] = None


def get_app() -> FastAPI:
    """Get the configured FastAPI application instance."""
    return create_app()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cadence_app = CadenceApplication()
    return cadence_app.create_app()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next):
        request_log = f"Request: {request.method} {request.url}"
        logging.info(request_log)
        response = await call_next(request)
        response_log = f"Response: {response.status_code}"
        logging.info(response_log)
        return response


class CadenceApplication:
    """Cadence FastAPI application factory with lifecycle management."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the Cadence application."""
        self.settings = settings or Settings()
        self.logger = self._setup_logging()
        self.app: Optional[FastAPI] = None

    def _setup_logging(self) -> logging.Logger:
        """Set up consistent logging format across all components."""
        log_level = logging.DEBUG if self.settings.debug else logging.INFO
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        handlers = [logging.StreamHandler(sys.stdout)]
        if self.settings.debug:
            handlers.append(logging.FileHandler("cadence.log"))
        else:
            handlers.append(logging.NullHandler())

        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers,
        )
        return logging.getLogger(__name__)

    def create_app(self) -> FastAPI:
        """Create and configure the FastAPI application with middleware and routes."""
        lifespan_context = self._create_lifespan_context()

        self.app = FastAPI(
            title="Cadence 🤖 Multi-agents AI Framework",
            description="A plugin-based multi-agent conversational AI framework",
            version="1.3.0",
            lifespan=lifespan_context,
        )

        self._configure_middleware()
        self._configure_routes()
        self._configure_endpoints()

        return self.app

    def _create_lifespan_context(self):
        """Create lifespan context manager for application lifecycle."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self._startup()
            yield
            await self._shutdown()

        return lifespan

    def _configure_middleware(self):
        """Configure application middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.app.add_middleware(RequestLoggingMiddleware)

    def _configure_routes(self):
        """Configure application routes."""
        self.app.include_router(api_router, prefix="/api/v1")

    def _configure_endpoints(self):
        """Configure application endpoints."""

        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "message": "Cadence 🤖 Multi-agents AI Framework", "version": self.app.version}

        @self.app.get("/")
        async def root():
            return {
                "message": "Welcome to Cadence 🤖 Multi-agents AI Framework",
                "version": self.app.version,
                "docs": "/docs",
            }

    async def _startup(self):
        """Initialize services and dependencies on application startup."""
        try:
            startup_message = "Starting Cadence 🤖 Multi-agents AI Framework..."
            self.logger.info(startup_message)

            await initialize_api(self.settings)

            success_message = "Cadence 🤖 Multi-agents AI Framework started successfully"
            self.logger.info(success_message)

        except Exception as e:
            error_message = f"Failed to start Cadence: {e}"
            self.logger.error(error_message)
            raise

    async def _shutdown(self):
        """Clean up resources on application shutdown."""
        try:
            shutdown_message = "Shutting down Cadence 🤖 Multi-agents AI Framework..."
            self.logger.info(shutdown_message)

            if global_service_container:
                await global_service_container.cleanup()

        except Exception as e:
            error_message = f"Error during shutdown: {e}"
            self.logger.error(error_message)

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the Cadence server using Uvicorn."""
        app = self.create_app()

        uvicorn_config = {
            "app": app,
            "host": host,
            "port": port,
            "reload": self.settings.debug,
            "log_level": "debug" if self.settings.debug else "info",
        }

        uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    load_dotenv()
    cadence_application = CadenceApplication()
    cadence_application.run()
