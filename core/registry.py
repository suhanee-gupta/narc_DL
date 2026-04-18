"""
registry.py — Artifact Registry (Factory Pattern)

The single source of truth for all loaded modules.
On startup it:
  1. Loads catalog metadata (ID → title/category).
  2. Initializes the FAISS index (real or mock).
  3. Instantiates the User Encoder (real or stub).
  4. Instantiates the RL Bandit (real or stub).
  
The rest of the app accesses everything through registry.get_instance().
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from typing import Optional

from app.core.config import settings
from app.core.interfaces import BaseEncoder, BaseRetriever, BaseBandit, BaseFeedbackStore

logger = logging.getLogger("registry")

 
class ArtifactRegistry:
    """Singleton registry — one per process."""

    _instance: Optional["ArtifactRegistry"] = None

    # ── Public accessors ─────────────────────────────────────────────────────
    encoder: BaseEncoder
    retriever: BaseRetriever
    bandit: BaseBandit
    feedback_store: BaseFeedbackStore
    metadata: dict   # {article_id: {"title": ..., "category": ..., "url": ...}}

    @classmethod
    def get_instance(cls) -> "ArtifactRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Initialization ────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._load_metadata()
        self._load_retriever()
        self._load_encoder()
        self._load_bandit()
        self._load_feedback_store()
        logger.info("ArtifactRegistry fully initialized.")

    async def shutdown(self) -> None:
        """Persist bandit weights before process exits."""
        try:
            os.makedirs(settings.ARTIFACTS_DIR, exist_ok=True)
            self.bandit.save(settings.BANDIT_WEIGHTS_PATH)
            logger.info("Bandit weights saved to %s", settings.BANDIT_WEIGHTS_PATH)
        except Exception as exc:
            logger.warning("Could not save bandit weights: %s", exc)

    # ── Internal loaders (each tries real artifact first, falls back to stub) ─

    def _load_metadata(self) -> None:
        if os.path.exists(settings.METADATA_PATH):
            with open(settings.METADATA_PATH) as f:
                article_list = json.load(f)
            
            self.metadata = {str(item["story_id"]): item for item in article_list}
            logger.info("Loaded metadata: %d articles", len(self.metadata))
        else:
            logger.warning(
                "metadata.json not found at %s — generating mock catalog (%d items).",
                settings.METADATA_PATH,
                settings.MOCK_CATALOG_SIZE,
            )
            self.metadata = _generate_mock_metadata(settings.MOCK_CATALOG_SIZE)

    def _load_retriever(self) -> None:
        if os.path.exists(settings.FAISS_INDEX_PATH):
            # ── Real path: swap in FAISSRetriever once implemented ────────────
            # from app.services.retriever_faiss import FAISSRetriever
            # self.retriever = FAISSRetriever(settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM)
            logger.info("FAISS index found — using FAISSRetriever (stub for now).")
            self.retriever = _build_stub_retriever(list(self.metadata.keys()))
        else:
            logger.warning("No FAISS index found — using RandomRetriever stub.")
            self.retriever = _build_stub_retriever(list(self.metadata.keys()))

    def _load_encoder(self) -> None:
        # ── Real path example (uncomment when ready): ─────────────────────────
        # from app.services.encoder_distilbert import DistilBERTEncoder
        # self.encoder = DistilBERTEncoder()
        logger.warning("No real encoder found — using RandomVectorEncoder stub.")
        self.encoder = _build_stub_encoder(settings.EMBEDDING_DIM)

    def _load_bandit(self) -> None:
        # ── Real path example (uncomment when ready): ─────────────────────────
        # from app.services.bandit_mabwiser import MABWiserBandit
        # self.bandit = MABWiserBandit(settings.EMBEDDING_DIM)
        # if os.path.exists(settings.BANDIT_WEIGHTS_PATH):
        #     self.bandit.load(settings.BANDIT_WEIGHTS_PATH)
        logger.warning("No real bandit found — using RandomBandit stub.")
        self.bandit = _build_stub_bandit()

    def _load_feedback_store(self) -> None:
        # ── Real path example (Redis): ────────────────────────────────────────
        # from app.services.feedback_redis import RedisFeedbackStore
        # self.feedback_store = RedisFeedbackStore(host="localhost", port=6379)
        from app.services.feedback_inmemory import InMemoryFeedbackStore
        self.feedback_store = InMemoryFeedbackStore()
        logger.info("FeedbackStore: InMemoryFeedbackStore active.")


# ── Stub factory helpers ──────────────────────────────────────────────────────
# These produce VALID interface-compliant objects that return random data.
# They let the entire pipeline run end-to-end on Day 1 with zero real models.

def _generate_mock_metadata(n: int) -> dict:
    categories = ["politics", "tech", "sports", "entertainment", "health", "science", "world"]
    return {
        f"article_{i:06d}": {
            "title": f"Mock Article {i}",
            "category": categories[i % len(categories)],
            "url": f"https://news.example.com/article/{i}",
        }
        for i in range(n)
    }


def _build_stub_encoder(dim: int) -> BaseEncoder:
    import numpy as np
    from app.core.interfaces import ContextObject

    class RandomVectorEncoder(BaseEncoder):
        """Returns a deterministic-ish random vector based on user_id hash."""

        @property
        def embedding_dim(self) -> int:
            return dim

        def encode(self, context: ContextObject) -> np.ndarray:
            rng = np.random.default_rng(hash(context.user_id + context.mood) & 0xFFFFFFFF)
            vec = rng.standard_normal((1, dim)).astype(np.float32)
            # Normalize to unit sphere
            vec /= np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9
            return vec

    return RandomVectorEncoder()


def _build_stub_retriever(article_ids: list) -> BaseRetriever:
    import numpy as np

    class RandomRetriever(BaseRetriever):
        """Returns a random sample of articles (no real ANN search)."""

        def retrieve(self, user_vector: np.ndarray, top_k: int) -> list:
            k = min(top_k, len(article_ids))
            return list(np.random.choice(article_ids, size=k, replace=False))

        def add_articles(self, ids: list, vectors: np.ndarray) -> None:
            article_ids.extend(ids)

    return RandomRetriever()


def _build_stub_bandit() -> BaseBandit:
    import random
    from app.core.interfaces import ContextObject

    class RandomBandit(BaseBandit):
        """Shuffles candidates — no real learning."""

        def rank(self, candidates, context, user_vector, top_n):
            shuffled = candidates[:]
            random.shuffle(shuffled)
            return shuffled[:top_n]

        def partial_fit(self, user_id, article_id, context, reward):
            pass  # No-op until real bandit is plugged in

        def save(self, path):
            pass

        def load(self, path):
            pass

    return RandomBandit()