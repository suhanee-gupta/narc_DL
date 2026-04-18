"""health.py — /health endpoint"""

from fastapi import APIRouter
from app.core.registry import ArtifactRegistry

router = APIRouter()
 

@router.get("/health", summary="System health check")
async def health():
    registry = ArtifactRegistry.get_instance()
    return {
        "status": "ok",
        "catalog_size": len(registry.metadata),
        "encoder": type(registry.encoder).__name__,
        "retriever": type(registry.retriever).__name__,
        "bandit": type(registry.bandit).__name__,
        "feedback_store": type(registry.feedback_store).__name__,
    }