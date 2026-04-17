"""
Long-term user context store.

Each user has a 256-dim vector representing their interest direction in
the article embedding space. Cold-started at zero (all zeros = new user).

The slow loop calls flush_updates() every 1-2 hours to shift each user's
vector toward the centroid of articles they engaged with positively.
"""

import os
import numpy as np
from collections import defaultdict
from config import VEC_DIM, SLOW_LOOP_LR

# Only positive actions move the user vector.
_ACTION_WEIGHTS: dict[str, float] = {
    "share":      3.0,
    "dwell_long": 2.0,
    "click":      1.0,
}


class UserContextStore:
    def __init__(self, vec_dim: int = VEC_DIM, lr: float = SLOW_LOOP_LR):
        self.vec_dim = vec_dim
        self.lr = lr
        self._contexts: dict[str, np.ndarray] = {}
        self._buffer: dict[str, list[dict]] = defaultdict(list)

    # ── read ─────────────────────────────────────────────────────────────────

    def get_vector(self, user_id: str) -> np.ndarray:
        """Returns current context vector. Zero vector for new users (cold start)."""
        if user_id not in self._contexts:
            self._contexts[user_id] = np.zeros(self.vec_dim, dtype=np.float32)
        return self._contexts[user_id].copy()

    # ── write (fast loop feeds this) ─────────────────────────────────────────

    def buffer_interaction(self, record: dict) -> None:
        """
        Buffer one interaction for the next slow-loop update.

        record schema:
            user_id    : str
            article_id : str
            action     : str  — one of click/skip/dwell_short/dwell_long/share
            article_vec: np.ndarray  shape (256,)
        """
        self._buffer[record["user_id"]].append(record)

    # ── slow loop ─────────────────────────────────────────────────────────────

    def flush_updates(self) -> int:
        """
        Apply accumulated interactions to update every buffered user's context vector.
        Clears the buffer. Returns the count of users whose vectors changed.

        Update rule (exponential moving average toward positive-engagement centroid):
            signal    = weighted_mean(article_vecs for positive actions)
            new_vec   = (1 - lr) * old_vec + lr * signal
            new_vec  /= ||new_vec||   (L2-normalize; skip if zero)
        """
        updated = 0

        for user_id, records in self._buffer.items():
            weighted_sum = np.zeros(self.vec_dim, dtype=np.float64)
            total_weight = 0.0

            for rec in records:
                w = _ACTION_WEIGHTS.get(rec["action"], 0.0)
                if w > 0.0:
                    weighted_sum += w * rec["article_vec"].astype(np.float64)
                    total_weight += w

            if total_weight == 0.0:
                continue

            signal = weighted_sum / total_weight
            old = self._contexts.get(user_id, np.zeros(self.vec_dim, dtype=np.float32))
            new_vec = (1.0 - self.lr) * old.astype(np.float64) + self.lr * signal
            norm = float(np.linalg.norm(new_vec))
            if norm > 1e-8:
                new_vec /= norm
            self._contexts[user_id] = new_vec.astype(np.float32)
            updated += 1

        self._buffer.clear()
        return updated

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = "user_contexts.npz") -> None:
        if not self._contexts:
            return
        np.savez(path, **{uid: vec for uid, vec in self._contexts.items()})

    def load(self, path: str = "user_contexts.npz") -> None:
        if not os.path.exists(path):
            return
        data = np.load(path)
        self._contexts = {k: data[k].astype(np.float32) for k in data.files}
        print(f"UserContextStore: loaded {len(self._contexts)} user vectors from {path}")
