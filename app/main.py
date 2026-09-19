from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import DemoAuth, install_auth_middleware
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.deps import AppContainer, build_container
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.static import mount_static
from app.api.static import router as static_router
from app.config import get_settings
from app.logging import configure_logging
from app.warmup import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    container: AppContainer = app.state.container
    if container.settings.warmup_enabled:
        thread = threading.Thread(target=warm_up, args=(container,), daemon=True)
        thread.start()
    yield
    close = getattr(container.repository, "close", None)
    if callable(close):
        close()


def create_app(container: AppContainer | None = None) -> FastAPI:
    if container is None:
        settings = get_settings()
        configure_logging(settings)
        resolved_container = build_container(settings)
    else:
        configure_logging(container.settings)
        resolved_container = container

    app = FastAPI(title="Miniflake", lifespan=lifespan)
    register_error_handlers(app)
    app.state.container = resolved_container

    demo_auth = DemoAuth(app.state.container.settings)
    app.state.demo_auth = demo_auth
    install_auth_middleware(app, demo_auth)

    app.include_router(static_router)
    mount_static(app)
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(auth_router, prefix="/api", tags=["auth"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    return app
