"""
pipeline.py — The Inference Pipeline (Request Lifecycle)

Step A: Context Aggregation
Step B: State Encoding     (First Black Box — Encoder)
Step C: Candidate Retrieval (FAISS / ANN)
Step D: RL Ranking          (Second Black Box — Bandit)

Designed for < 2s end-to-end latency.
"""
 
from __future__ import annotations

import asyncio
import logging
import time
from typing import List

from app.core.config import settings
from app.core.interfaces import ContextObject
from app.core.registry import ArtifactRegistry

logger = logging.getLogger("pipeline")


class PipelineResult:
    """Returned to the API layer after a full inference pass."""

    def __init__(
        self,
        user_id: str,
        recommended_ids: List[str],
        latency_ms: float,
        metadata: list,
    ):
        self.user_id = user_id
        self.recommended_ids = recommended_ids
        self.latency_ms = latency_ms
        self.metadata = metadata  # List of {id, title, category, url}

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "recommendations": self.metadata,
            "latency_ms": round(self.latency_ms, 2),
        }

 
async def run_inference(
    user_id: str,
    mood: str,
    time_of_day: str,
    location: str,
    explicit_ratings: dict | None = None,
    dwell_times: dict | None = None,
    top_n: int | None = None,
    top_k: int | None = None,
) -> PipelineResult:
    """
    Full inference pass for one user request.

    Parameters
    ----------
    user_id     : Unique user identifier.
    mood        : Current mood string (see settings.VALID_MOODS).
    time_of_day : "morning" | "afternoon" | "evening" | "night".
    top_n       : Final recommendations to return (default: settings.FINAL_TOP_N).
    top_k       : Candidate pool size (default: settings.RETRIEVAL_TOP_K).
    """

    _top_n = top_n or settings.FINAL_TOP_N
    _top_k = top_k or settings.RETRIEVAL_TOP_K
    t0 = time.perf_counter()

    registry = ArtifactRegistry.get_instance()

    # ────────────────────────────────────────────────────────────────────────
    # STEP A: Context Aggregation
    #   Fetch history from the feedback store and pack everything into a
    #   ContextObject.  This is the "state" that flows through the pipeline.
    # ────────────────────────────────────────────────────────────────────────
    history = await registry.feedback_store.get_history(user_id, settings.HISTORY_WINDOW)
    dwell   = await registry.feedback_store.get_dwell_times(user_id)

    context = ContextObject(
        user_id=user_id,
        mood=mood,
        time_of_day=time_of_day,
        location=location,
        history=history,
        explicit_ratings=explicit_ratings or {},
        dwell_times={**dwell, **(dwell_times or {})},
    )

    logger.debug("Step A done — context: %s", context)

    # ────────────────────────────────────────────────────────────────────────
    # STEP B: State Encoding  (First Black Box)
    #   ContextObject  →  user vector  ∈  ℝ^d
    # ────────────────────────────────────────────────────────────────────────
    # Run CPU-bound encoding in a thread so we don't block the event loop.
    user_vector = await asyncio.get_event_loop().run_in_executor(
        None, registry.encoder.encode, context
    )
    logger.debug("Step B done — vector shape: %s", user_vector.shape)

    # ────────────────────────────────────────────────────────────────────────
    # STEP C: Candidate Retrieval  (ANN / FAISS)
    #   user vector  →  Top-K article IDs  (~5–10 ms with FAISS)
    # ────────────────────────────────────────────────────────────────────────
    candidate_ids = await asyncio.get_event_loop().run_in_executor(
        None, registry.retriever.retrieve, user_vector, _top_k
    )
    logger.debug("Step C done — %d candidates retrieved.", len(candidate_ids))

    # ────────────────────────────────────────────────────────────────────────
    # STEP D: RL Ranking  (Second Black Box)
    #   (Candidates, context, user_vector)  →  Top-N ranked article IDs
    #
    #   The bandit handles:
    #     • Exploitation: highest-confidence recommendations
    #     • Exploration : EXPLORATION_RATIO fraction of "novel" items
    # ────────────────────────────────────────────────────────────────────────
    ranked_ids = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: registry.bandit.rank(candidate_ids, context, user_vector, _top_n),
    )
    logger.debug("Step D done — %d ranked items.", len(ranked_ids))

    # ── Assemble metadata for the response ───────────────────────────────────
    meta = [
        {"story_id": aid, **registry.metadata.get(aid, {"title": "Unknown", "category": "unknown", "google_news_url": ""})}
        for aid in ranked_ids
    ]

    latency_ms = (time.perf_counter() - t0) * 1000
    if latency_ms > settings.LATENCY_BUDGET_MS:
        logger.warning("⚠️  Latency budget exceeded: %.1f ms > %d ms", latency_ms, settings.LATENCY_BUDGET_MS)

    return PipelineResult(
        user_id=user_id,
        recommended_ids=ranked_ids,
        latency_ms=latency_ms,
        metadata=meta,
    )