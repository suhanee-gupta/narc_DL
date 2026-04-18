""" 
interfaces.py — The "Contracts" for the Walking Skeleton.

Every concrete implementation (DistilBERT encoder, MABWiser bandit, etc.)
must satisfy these ABCs. The rest of the pipeline talks ONLY to these interfaces.

Team contracts (agreed on Day 1):
┌──────────────────┬─────────────────────────────────┬──────────────────────────┐
│ Module           │ Input                           │ Output                   │
├──────────────────┼─────────────────────────────────┼──────────────────────────┤
│ Encoder          │ ContextObject                   │ np.ndarray shape (1, d)  │
│ Retrieval        │ np.ndarray (1, d)               │ List[str] (Top-K IDs)    │
│ RL / Bandit      │ List[str] + ContextObject       │ List[str] (Ranked Top-N) │
│ FeedbackStore    │ UserID, ArticleID, reward float │ None (async)             │
└──────────────────┴─────────────────────────────────┴──────────────────────────┘
"""

from __future__ import annotations

import numpy as np
from abc import ABC, abstractmethod
from typing import List


# ── Shared data structure ────────────────────────────────────────────────────

class ContextObject:
    """
    Immutable snapshot of everything known about a user at request time.
    Passed through the entire pipeline so each module can read what it needs.
    """

    def __init__(
        self,
        user_id: str,
        mood: str,
        location: str,
        top_k: int,
        time_of_day: str,              # e.g. "morning", "evening"
        history: List[str],            # Last N article IDs (most-recent first)
        explicit_ratings: dict | None = None,   # {article_id: 1-5}
        dwell_times: dict | None = None,        # {article_id: seconds_spent}
    ):
        self.user_id = user_id
        self.mood = mood
        self.top_k = top_k
        self.time_of_day = time_of_day
        self.location = location
        self.history = history
        self.explicit_ratings = explicit_ratings or {}
        self.dwell_times = dwell_times or {}

    def __repr__(self) -> str:
        return (
            f"ContextObject(user={self.user_id!r}, mood={self.mood!r}, "
            f"time={self.time_of_day!r}, history_len={len(self.history)}, location={self.location})"
        )


# ── Abstract Base Classes ────────────────────────────────────────────────────

class BaseEncoder(ABC):
    """
    CONTRACT: User Encoder
    ----------------------
    Takes a ContextObject and returns a user-state vector.

    Implementing teams can use: DistilBERT, TF-IDF + MLP, averaging, etc.
    The pipeline only requires the output shape to be (1, EMBEDDING_DIM).
    """

    @abstractmethod
    def encode(self, context: ContextObject) -> np.ndarray:
        """
        Parameters
        ----------
        context : ContextObject
            Aggregated user signals.

        Returns
        -------
        np.ndarray
            Shape (1, d) — a single user-state vector.
        """
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Must match settings.EMBEDDING_DIM."""
        ...


class BaseRetriever(ABC):
    """
    CONTRACT: Candidate Retriever
    ------------------------------
    Given a user vector, return the Top-K most similar article IDs.
    Implemented with FAISS (or any ANN library).
    """

    @abstractmethod
    def retrieve(self, context: ContextObject) -> List[str]:
        """
        Parameters
        ----------
        user_vector : np.ndarray, shape (1, d)
        top_k : int
            How many candidates to return (default: 200).

        Returns
        -------
        List[str]
            Article IDs sorted by cosine similarity (closest first).
        """
        ...


class BaseBandit(ABC):
    """
    CONTRACT: RL / Contextual Bandit
    ---------------------------------
    Re-ranks retrieved candidates using learned preferences.
    Supports online updates via partial_fit for the feedback loop.

    Implementing teams can use: MABWiser, Vowpal Wabbit, LinUCB, custom RL, etc.
    """

    @abstractmethod
    def rank(
        self,
        candidate_ids: List[str],
        context: ContextObject,
        user_vector: np.ndarray,
        top_n: int,
    ) -> List[str]:
        """
        Parameters
        ----------
        candidate_ids : List[str]
            ~200 article IDs from the retriever.
        context : ContextObject
        user_vector : np.ndarray, shape (1, d)
        top_n : int
            Final number to return (default: 10).

        Returns
        -------
        List[str]
            Article IDs, best match first.
            Must include exploration items (see settings.EXPLORATION_RATIO).
        """
        ...

    @abstractmethod
    def partial_fit(
        self,
        user_id: str,
        article_id: str,
        context: ContextObject,
        reward: float,
    ) -> None:
        """
        Online update after a user click/ignore.

        Parameters
        ----------
        reward : float
            Typically 1.0 (click) or 0.0 (ignore).
            Can also carry dwell-time signals (e.g., 0.5 for partial read).
        """
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """Persist learned weights to disk."""
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        """Restore weights from disk."""
        ...


class BaseFeedbackStore(ABC):
    """
    CONTRACT: Feedback / History Store
    ------------------------------------
    Persists click events and surfaces recent history for context aggregation.
    Backed by Redis, SQLite, or an in-memory dict.
    """

    @abstractmethod
    async def log_click(self, user_id: str, article_id: str, reward: float) -> None:
        """Record a user interaction asynchronously."""
        ...

    @abstractmethod
    async def get_history(self, user_id: str, window: int) -> List[str]:
        """Return the last `window` article IDs clicked by user (newest first)."""
        ...

    @abstractmethod
    async def get_dwell_times(self, user_id: str) -> dict:
        """Return {article_id: seconds_spent} for recently viewed items."""
        ...
    
    @abstractmethod
    async def log_dwell(self, user_id: str, article_id: str, seconds: float) -> None:
        ...
    
    @abstractmethod
    async def log_candidates(self, user_id: str, article_ids: List[str]) -> None:
        ...
    
    @abstractmethod
    async def get_last_candidates(self, user_id: str) -> List[str]:
        ...