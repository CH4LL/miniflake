from fastapi import FastAPI

from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Miniflake")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Miniflake API"}

    app.include_router(health_router, prefix="/api", tags=["health"])
    return app
