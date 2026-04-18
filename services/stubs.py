"""
stubs.py — Ready-to-Upgrade Stub Implementations

Each stub:
  1. Fully satisfies the interface contract.
  2. Works right now with random data.
  3. Contains inline TODO comments showing exactly where to plug in real logic.

Teams can copy one of these files, rename it, and fill in the TODOs.
"""

from __future__ import annotations

import logging
import pickle
import random
from typing import List

import numpy as np

from app.core.config import settings
from app.core.interfaces import BaseEncoder, BaseBandit, BaseRetriever, ContextObject

logger = logging.getLogger("stubs")


# ── ENCODER STUB ─────────────────────────────────────────────────────────────

class StubEncoder(BaseEncoder):
    """
    Upgrade path:
      1. Copy this file → encoder_distilbert.py (or encoder_tfidf.py, etc.)
      2. Load your model in __init__.
      3. Replace the body of encode() with your forward pass.
      4. Update registry.py: swap StubEncoder → YourEncoder.

    The pipeline only cares that encode() returns shape (1, EMBEDDING_DIM).
    """

    def __init__(self, dim: int = settings.EMBEDDING_DIM):
        self._dim = dim
        logger.info("StubEncoder initialized (dim=%d). Replace with real model.", dim)

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def encode(self, context: ContextObject) -> np.ndarray:
        # ── TODO: Replace this block ─────────────────────────────────────────
        # Example for DistilBERT:
        #   tokens = tokenizer(context.history, return_tensors="pt", truncation=True, padding=True)
        #   with torch.no_grad():
        #       outputs = model(**tokens)
        #   history_vec = outputs.last_hidden_state.mean(dim=1).numpy()   # (N, 768)
        #   # Incorporate mood
        #   mood_vec = mood_embeddings[context.mood]                        # (768,)
        #   combined = np.mean([history_vec.mean(0), mood_vec], axis=0)
        #   return combined.reshape(1, -1)                                  # (1, 768)
        # ────────────────────────────────────────────────────────────────────

        rng = np.random.default_rng(hash(context.user_id + context.mood) & 0xFFFFFFFF)
        vec = rng.standard_normal((1, self._dim)).astype(np.float32)
        vec /= (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9)
        return vec


# ── BANDIT STUB ───────────────────────────────────────────────────────────────

class StubBandit(BaseBandit):
    """
    Upgrade path:
      1. Copy this file → bandit_mabwiser.py (or bandit_linucb.py, etc.)
      2. Initialise your bandit model in __init__.
      3. Replace rank() with real scoring + UCB/Thompson sampling.
      4. Replace partial_fit() with a real online update.
      5. Implement save/load using pickle or your model's native serialization.
      6. Update registry.py.

    Exploration guarantee: the pipeline requires that at least
    EXPLORATION_RATIO * top_n items are "non-greedy" picks.
    """

    def __init__(self):
        self._weights: dict = {}  # Simulated per-arm weights
        logger.info("StubBandit initialized (random ranking). Replace with real RL model.")

    def rank(
        self,
        candidate_ids: List[str],
        context: ContextObject,
        user_vector: np.ndarray,
        top_n: int,
    ) -> List[str]:
        # ── TODO: Replace this block ─────────────────────────────────────────
        # Example for MABWiser LinUCB:
        #   context_features = np.hstack([user_vector.flatten(), encode_mood(context.mood)])
        #   scores = self._mab.predict_expectations(context_features)
        #   # Separate exploitation / exploration
        #   n_exploit = int(top_n * (1 - settings.EXPLORATION_RATIO))
        #   n_explore  = top_n - n_exploit
        #   exploit_ids = sorted(candidate_ids, key=lambda a: scores[a], reverse=True)[:n_exploit]
        #   explore_ids = [a for a in candidate_ids if a not in exploit_ids]
        #   random.shuffle(explore_ids)
        #   return exploit_ids + explore_ids[:n_explore]
        # ────────────────────────────────────────────────────────────────────

        pool = candidate_ids[:]
        random.shuffle(pool)
        return pool[:top_n]

    def partial_fit(
        self,
        user_id: str,
        article_id: str,
        context: ContextObject,
        reward: float,
    ) -> None:
        # ── TODO: Replace with real online update ────────────────────────────
        # self._mab.partial_fit(
        #     decisions=[article_id],
        #     rewards=[reward],
        #     contexts=[encode_context(context)],
        # )
        # ────────────────────────────────────────────────────────────────────
        pass   # No-op until real bandit is plugged in

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(self._weights, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            self._weights = pickle.load(f)


# ── RETRIEVER STUB ─────────────────────────────────────────────────────────────

class StubRetriever(BaseRetriever):
    """
    Upgrade path:
      1. Copy this file → retriever_faiss.py.
      2. Load the FAISS index from disk in __init__.
      3. Replace retrieve() with index.search(user_vector, top_k).
      4. Update registry.py.
    """

    def __init__(self, article_ids: List[str]):
        self._ids = article_ids
        logger.info("StubRetriever initialized (%d articles). Replace with FAISS.", len(article_ids))

    def retrieve(self, user_vector: np.ndarray, top_k: int) -> List[str]:
        # ── TODO: Replace this block ─────────────────────────────────────────
        # distances, indices = self._index.search(user_vector, top_k)
        # return [self._ids[i] for i in indices[0] if i < len(self._ids)]
        # ────────────────────────────────────────────────────────────────────
        k = min(top_k, len(self._ids))
        sampled_ids = np.random.choice(self._ids, size=k, replace=False)
        return [str(aid) for aid in sampled_ids]

    def add_articles(self, article_ids: List[str], vectors: np.ndarray) -> None:
        # ── TODO: self._index.add(vectors); self._ids.extend(article_ids) ───
        self._ids.extend(article_ids)