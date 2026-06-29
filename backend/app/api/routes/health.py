from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return success_response(
        {
            "name": settings.APP_NAME,
            "status": "running",
            "version": settings.APP_VERSION,
        }
    )
