"""
LinUCB contextual bandit — shared model across all users.

Context feature:  ctx = user_vec ⊙ article_vec  (elementwise product, 256-dim)
This encodes user-article affinity: the same article gets a different context
vector for each user, so the single shared model is implicitly personalized.

UCB score:   θᵀ ctx  +  α √(ctxᵀ A⁻¹ ctx)
             ──────     ──────────────────────
           exploitation       exploration

A⁻¹ is maintained via the Sherman-Morrison rank-1 update formula:
    (A + ctx ctxᵀ)⁻¹ = A⁻¹ − (A⁻¹ ctx ctxᵀ A⁻¹) / (1 + ctxᵀ A⁻¹ ctx)
This is O(d²) per update instead of O(d³) for a full matrix inversion.
"""

import numpy as np
from user_maker import Article
from config import VEC_DIM, BANDIT_ALPHA


class LinUCBBandit:
    def __init__(self, d: int = VEC_DIM, alpha: float = BANDIT_ALPHA):
        self.d = d
        self.alpha = alpha
        self.A_inv = np.eye(d, dtype=np.float64)
        self.b = np.zeros(d, dtype=np.float64)

    # ── internal ─────────────────────────────────────────────────────────────

    def _ctx(self, user_vec: np.ndarray, article_vec: np.ndarray) -> np.ndarray:
        return user_vec.astype(np.float64) * article_vec.astype(np.float64)

    def _score(self, ctx: np.ndarray) -> float:
        theta = self.A_inv @ self.b
        exploitation = float(theta @ ctx)
        v = self.A_inv @ ctx
        exploration = self.alpha * float(np.sqrt(max(ctx @ v, 0.0)))
        return exploitation + exploration

    # ── public API ───────────────────────────────────────────────────────────

    def select_topk(
        self,
        user_vec: np.ndarray,
        candidates: list[Article],
        k: int,
    ) -> list[Article]:
        """Score every candidate and return the top-k by UCB score."""
        if not candidates:
            return []
        k = min(k, len(candidates))
        scores = np.array([self._score(self._ctx(user_vec, a.vec)) for a in candidates])
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
        return [candidates[i] for i in top_idx]

    def update(
        self,
        user_vec: np.ndarray,
        article_vec: np.ndarray,
        reward: float,
    ) -> None:
        """Update model given the reward observed for (user_vec, article_vec)."""
        ctx = self._ctx(user_vec, article_vec)
        v = self.A_inv @ ctx
        denom = 1.0 + float(ctx @ v)
        self.A_inv -= np.outer(v, v) / denom
        self.b += reward * ctx

    def reset(self) -> None:
        """Reset to uninformed prior. Call after a slow-loop update if desired."""
        self.A_inv = np.eye(self.d, dtype=np.float64)
        self.b = np.zeros(self.d, dtype=np.float64)
