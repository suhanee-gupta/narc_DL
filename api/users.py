"""users.py — /users endpoints"""

from fastapi import APIRouter
from app.core.registry import ArtifactRegistry
from app.core.config import settings

router = APIRouter()

 
@router.get("/{user_id}/history", summary="Get a user's click history")
async def get_user_history(user_id: str, window: int = settings.HISTORY_WINDOW):
    registry = ArtifactRegistry.get_instance()
    history = await registry.feedback_store.get_history(user_id, window)
    dwell = await registry.feedback_store.get_dwell_times(user_id)
    return {
        "user_id": user_id,
        "history": history,
        "dwell_times": dwell,
    }


@router.get("/{user_id}/profile", summary="Get enriched user profile with metadata")
async def get_user_profile(user_id: str):
    registry = ArtifactRegistry.get_instance()
    history = await registry.feedback_store.get_history(user_id, settings.HISTORY_WINDOW)
    dwell = await registry.feedback_store.get_dwell_times(user_id)

    enriched = []
    for aid in history:
        meta = registry.metadata.get(aid, {})
        enriched.append({"story_id": aid, **meta, "dwell_seconds": dwell.get(aid, 0)})

    return {
        "user_id": user_id,
        "history_count": len(history),
        "is_cold_start": len(history) == 0,
        "recent_articles": enriched,
    } 