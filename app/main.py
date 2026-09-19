from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.deps import AppContainer, build_container
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.config import get_settings


def create_app(container: AppContainer | None = None) -> FastAPI:
    app = FastAPI(title="Miniflake")
    register_error_handlers(app)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Miniflake API"}

    if container is None:
        settings = get_settings()
        app.state.container = build_container(settings)
    else:
        app.state.container = container

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    return app
