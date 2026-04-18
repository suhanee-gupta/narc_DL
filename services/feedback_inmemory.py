"""
feedback_inmemory.py — In-Memory Feedback Store

Fast, zero-dependency store for development and hackathon demos.
Replace with RedisFeedbackStore for production / multi-process use.

Stores: 
  • Click history   : user_id → deque of (timestamp, article_id, reward)
  • Dwell times     : user_id → {article_id: float seconds}
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Dict, List

from app.core.config import settings
from app.core.interfaces import BaseFeedbackStore

 
class InMemoryFeedbackStore(BaseFeedbackStore):
    """Thread-safe (asyncio) in-memory feedback store."""

    def __init__(self) -> None:
        # {user_id: deque of (article_id, reward)}
        self._history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=settings.HISTORY_WINDOW * 5)
        )
        # {user_id: {article_id: total_dwell_seconds}}
        self._dwell: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._last_candidates: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    async def log_click(self, user_id: str, article_id: str, reward: float) -> None:
        async with self._lock:
            self._history[user_id].appendleft((article_id, reward))

    async def log_dwell(self, user_id: str, article_id: str, seconds: float) -> None:
        async with self._lock:
            prev = self._dwell[user_id].get(article_id, 0.0)
            self._dwell[user_id][article_id] = prev + seconds

    async def get_history(self, user_id: str, window: int) -> List[str]:
        async with self._lock:
            items = list(self._history[user_id])
        # Return article IDs (newest first) — filter positive interactions
        filtered_history = [aid for aid, reward in items if reward > 0]
        return filtered_history[:window]

    async def get_dwell_times(self, user_id: str) -> dict:
        async with self._lock:
            return dict(self._dwell.get(user_id, {}))
        
    async def log_candidates(self, user_id: str, article_ids: List[str]) -> None:
        async with self._lock:
            self._last_candidates[user_id] = article_ids

    async def get_last_candidates(self, user_id: str) -> List[str]:
        async with self._lock:
            return self._last_candidates.get(user_id, [])
        
    def user_count(self) -> int:
        return len(self._history)