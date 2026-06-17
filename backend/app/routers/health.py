"""Health check endpoint."""

from fastapi import APIRouter

from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> dict[str, str]:
    return {"status": "ok"}
