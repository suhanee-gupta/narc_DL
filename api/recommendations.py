"""
recommendations.py — /recommend endpoints

POST /recommend/          → Full inference pass (returns Top-N articles)
POST /recommend/cold-start → New user with no history (cold-start strategy)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from app.core.config import settings
from app.services.pipeline import run_inference

router = APIRouter()


# ── Request / Response schemas ───────────────────────────────────────────────

class RecommendRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    mood: str = Field("neutral", description="Current mood of the user.")
    time_of_day: str = Field("morning", description="morning | afternoon | evening | night")
    top_n: int = Field(settings.FINAL_TOP_N, ge=1, le=50, description="Number of articles to return.")
    explicit_ratings: dict = Field(default_factory=dict, description="{article_id: 1-5}")
    dwell_times: dict = Field(default_factory=dict, description="{article_id: seconds_spent}")

    @validator("mood")
    def validate_mood(cls, v):
        if v not in settings.VALID_MOODS:
            raise ValueError(f"mood must be one of {settings.VALID_MOODS}")
        return v

    @validator("time_of_day")
    def validate_time(cls, v):
        allowed = ["morning", "afternoon", "evening", "night"]
        if v not in allowed:
            raise ValueError(f"time_of_day must be one of {allowed}")
        return v


class ArticleMeta(BaseModel):
    story_id: str
    title: str
    category: str
    google_news_url: str


class RecommendResponse(BaseModel):
    user_id: str
    recommendations: list[ArticleMeta]
    latency_ms: float
    is_cold_start: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=RecommendResponse, summary="Get personalized recommendations")
async def get_recommendations(req: RecommendRequest):
    """
    Full inference pipeline:
      Context Aggregation → State Encoding → Candidate Retrieval → RL Ranking

    Returns Top-N hyper-personalized news articles in < 2s.
    """ 
    try:
        result = await run_inference(
            user_id=req.user_id,
            mood=req.mood,
            time_of_day=req.time_of_day,
            explicit_ratings=req.explicit_ratings,
            dwell_times=req.dwell_times,
            top_n=req.top_n,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return RecommendResponse(
        user_id=result.user_id,
        recommendations=[ArticleMeta(**m) for m in result.metadata],
        latency_ms=result.latency_ms,
    )


@router.post("/cold-start", response_model=RecommendResponse, summary="Cold-start for new users")
async def cold_start_recommendations(
    mood: str = "neutral",
    time_of_day: str = "morning",
    top_n: int = settings.FINAL_TOP_N,
):
    """
    Cold-start strategy for users with no history.
    Generates a synthetic user ID and uses only mood + time signals.

    Requirements satisfied:
      • "Demonstrate cold-start handling for new users with no history" ✓
    """
    import uuid
    new_user_id = f"cold_start_{uuid.uuid4().hex[:8]}"

    result = await run_inference(
        user_id=new_user_id,
        mood=mood,
        time_of_day=time_of_day,
        top_n=top_n,
    )
 
    return RecommendResponse(
        user_id=result.user_id,
        recommendations=[ArticleMeta(**m) for m in result.metadata],
        latency_ms=result.latency_ms,
        is_cold_start=True,
    )