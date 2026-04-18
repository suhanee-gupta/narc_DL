"""
feedback.py — /feedback endpoints

POST /feedback/click      → Log a click (reward = 1.0)
POST /feedback/ignore     → Log an ignore (reward = 0.0)
POST /feedback/dwell      → Log dwell time (fractional reward)
POST /feedback/rating     → Log explicit 1-5 star rating
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.interfaces import ContextObject
from app.core.registry import ArtifactRegistry

logger = logging.getLogger("feedback")
router = APIRouter()


# ── Request schemas ───────────────────────────────────────────────────────────

class ClickEvent(BaseModel):
    user_id: str
    article_id: str
    mood: str = "neutral"
    time_of_day: str = "morning"


class DwellEvent(BaseModel):
    user_id: str
    article_id: str
    seconds: float = Field(..., gt=0)
    mood: str = "neutral"
    time_of_day: str = "morning"


class RatingEvent(BaseModel):
    user_id: str
    article_id: str
    rating: int = Field(..., ge=1, le=5, description="1–5 star rating")
    mood: str = "neutral"
    time_of_day: str = "morning"


# ── Background tasks ──────────────────────────────────────────────────────────

async def _process_feedback(
    user_id: str,
    article_id: str,
    reward: float,
    mood: str,
    time_of_day: str,
):
    """
    Asynchronous Feedback Loop (Step described in the pipeline):
      1. Log the event to the feedback store (updates history for next request).
      2. Call bandit.partial_fit() to update arm weights online.
         Complexity: O(d²) per upddbaate — fast enough to run in background.
    """
    registry = ArtifactRegistry.get_instance()

    # 1. Persist interaction
    await registry.feedback_store.log_click(user_id, article_id, reward)

    # 2. Build a minimal context for the bandit update
    history = await registry.feedback_store.get_history(user_id, window=10)
    context = ContextObject(
        user_id=user_id,
        mood=mood,
        time_of_day=time_of_day,
        history=history,
    ) 

    # 3. Online bandit update (runs in thread to avoid blocking)
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: registry.bandit.partial_fit(user_id, article_id, context, reward),
    )

    logger.debug(
        "Feedback processed — user=%s article=%s reward=%.2f", user_id, article_id, reward
    )
 

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/click", summary="Log a click (reward = 1.0)")
async def log_click(event: ClickEvent, background_tasks: BackgroundTasks):
    """
    User clicked an article → positive signal.
    The bandit weight update runs in the background so the response is instant.
    """
    background_tasks.add_task(
        _process_feedback,
        event.user_id, event.article_id, 1.0, event.mood, event.time_of_day,
    )
    return {"status": "accepted", "reward": 1.0}


@router.post("/ignore", summary="Log an ignore (reward = 0.0)")
async def log_ignore(event: ClickEvent, background_tasks: BackgroundTasks):
    """User scrolled past an article → negative signal."""
    background_tasks.add_task(
        _process_feedback,
        event.user_id, event.article_id, 0.0, event.mood, event.time_of_day,
    )
    return {"status": "accepted", "reward": 0.0}


@router.post("/dwell", summary="Log dwell time (fractional reward)")
async def log_dwell(event: DwellEvent, background_tasks: BackgroundTasks):
    """
    User spent `seconds` on an article.
    Reward is normalized: 30s → 0.5, 60s+ → 1.0 (capped).
    """
    registry = ArtifactRegistry.get_instance()
    reward = min(event.seconds / 60.0, 1.0)

    # Persist dwell separately for future encoder use
    await registry.feedback_store.log_dwell(event.user_id, event.article_id, event.seconds)

    background_tasks.add_task(
        _process_feedback,
        event.user_id, event.article_id, reward, event.mood, event.time_of_day,
    )
    return {"status": "accepted", "reward": round(reward, 3)}


@router.post("/rating", summary="Log explicit 1-5 star rating")
async def log_rating(event: RatingEvent, background_tasks: BackgroundTasks):
    """Normalize 1-5 rating to [0, 1] reward."""
    reward = (event.rating - 1) / 4.0
    background_tasks.add_task(
        _process_feedback,
        event.user_id, event.article_id, reward, event.mood, event.time_of_day,
    )
    return {"status": "accepted", "reward": round(reward, 3)}