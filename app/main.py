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


def create_app(container: AppContainer | None = None) -> FastAPI:
    app = FastAPI(title="Miniflake")
    register_error_handlers(app)

    if container is None:
        settings = get_settings()
        app.state.container = build_container(settings)
    else:
        app.state.container = container

    demo_auth = DemoAuth(app.state.container.settings)
    app.state.demo_auth = demo_auth
    install_auth_middleware(app, demo_auth)

    app.include_router(static_router)
    mount_static(app)
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(auth_router, prefix="/api", tags=["auth"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    return app
