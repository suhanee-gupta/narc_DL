"""
config.py — Central configuration for the Hyper-Personalization Engine.
All values can be overridden via environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── Server ──────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ── Embedding dimension ─────────────────────────────────────────────────
    # All encoder implementations MUST output vectors of this size.
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "128"))

    # ── Retrieval ───────────────────────────────────────────────────────────
    # Number of candidate articles returned by FAISS before RL re-ranking.
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "200"))

    # Final recommendations shown to the user.
    FINAL_TOP_N: int = int(os.getenv("FINAL_TOP_N", "15"))

    # ── History window ──────────────────────────────────────────────────────
    # How many recently clicked article IDs are included in the context.
    HISTORY_WINDOW: int = int(os.getenv("HISTORY_WINDOW", "20"))

    # ── Artifacts paths ─────────────────────────────────────────────────────
    ARTIFACTS_DIR: str = os.getenv("ARTIFACTS_DIR", "artifacts")
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "artifacts/catalog.index")
    METADATA_PATH: str = os.getenv("METADATA_PATH", "artifacts/metadata.json")
    BANDIT_WEIGHTS_PATH: str = os.getenv("BANDIT_WEIGHTS_PATH", "artifacts/bandit_weights.pkl")

    # ── Catalog size (used for mock generation when no FAISS index exists) ──
    MOCK_CATALOG_SIZE: int = int(os.getenv("MOCK_CATALOG_SIZE", "1000"))

    # ── RL Exploration ──────────────────────────────────────────────────────
    # Fraction of final recommendations that are "exploration" items.
    EXPLORATION_RATIO: float = float(os.getenv("EXPLORATION_RATIO", "0.2"))

    # ── Latency budget (ms) ─────────────────────────────────────────────────
    LATENCY_BUDGET_MS: int = int(os.getenv("LATENCY_BUDGET_MS", "2000"))

    # ── Mood options (used for validation) ─────────────────────────────────
    VALID_MOODS: list = field(default_factory=lambda: [
        "happy", "sad", "excited", "calm", "curious",
        "stressed", "bored", "motivated", "neutral"
    ])


# Singleton config object
settings = Config()