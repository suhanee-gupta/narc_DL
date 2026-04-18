"""
LinUCB contextual bandit — shared model across all users.

Context vector: 46-dim explicit features built by context_encoder.py
  mood(6) + archetype_onehot(7) + location_onehot(3) + time_bucket_onehot(4)
  + category_onehot(24) + freshness(1) + reranker_score_sigmoid(1)

UCB score:   θᵀ ctx  +  α √(ctxᵀ A⁻¹ ctx)

A⁻¹ maintained via Sherman-Morrison rank-1 update (O(d²), not O(d³)).
"""

import os
import numpy as np
from config import CONTEXT_DIM, BANDIT_ALPHA


class LinUCBBandit:
    def __init__(self, d: int = CONTEXT_DIM, alpha: float = BANDIT_ALPHA):
        self.d     = d
        self.alpha = alpha
        self.A_inv = np.eye(d, dtype=np.float64)
        self.b     = np.zeros(d, dtype=np.float64)

    def _score(self, ctx: np.ndarray) -> float:
        ctx = ctx.astype(np.float64)
        theta = self.A_inv @ self.b
        v     = self.A_inv @ ctx
        return float(theta @ ctx) + self.alpha * float(np.sqrt(max(ctx @ v, 0.0)))

    def select_topk(self, ctx_vecs: list, candidates: list, k: int) -> list:
        """
        ctx_vecs  : list of np.array(46,), one per candidate
        candidates: list of Article (parallel to ctx_vecs)
        """
        if not candidates:
            return []
        k      = min(k, len(candidates))
        scores = np.array([self._score(c) for c in ctx_vecs])
        idx    = np.argpartition(scores, -k)[-k:]
        idx    = idx[np.argsort(scores[idx])[::-1]]
        return [candidates[i] for i in idx]

    def update(self, ctx: np.ndarray, reward: float) -> None:
        """Sherman-Morrison update."""
        ctx = ctx.astype(np.float64)
        v   = self.A_inv @ ctx
        self.A_inv -= np.outer(v, v) / (1.0 + float(ctx @ v))
        self.b     += reward * ctx

    def reset(self) -> None:
        self.A_inv = np.eye(self.d, dtype=np.float64)
        self.b     = np.zeros(self.d, dtype=np.float64)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        np.savez(path, A_inv=self.A_inv, b=self.b)

    def load(self, path: str) -> None:
        data = np.load(path + ".npz")
        self.A_inv = data["A_inv"]
        self.b     = data["b"]
