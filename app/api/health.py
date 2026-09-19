from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    settings = request.app.state.container.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.health_version,
        "environment": settings.environment,
    }
