"""
Interaction buffer + user_vec updates.

Fast loop  — called immediately after each positive interaction:
             EMA-shifts user_vec toward the clicked article's embedding.

Slow loop  — called hourly via slow_loop.py:
             weighted mean over all buffered positive interactions,
             appends to click_history, saves profile JSON.
"""

import numpy as np
from collections import defaultdict
from config import EMBED_DIM, FAST_LOOP_USER_VEC_LR, SLOW_LOOP_LR
import user_profile_store as ups

_POSITIVE = {"share": 3.0, "dwell_long": 2.0, "click": 1.0}


class UserContextStore:
    def __init__(self):
        self._buffer: dict[str, list[dict]] = defaultdict(list)
        self._user_vecs: dict[str, np.ndarray] = {}   # in-memory cache

    # ── user vec (read) ───────────────────────────────────────────────────────

    def get_vector(self, user_id: str) -> np.ndarray:
        if user_id not in self._user_vecs:
            profile = ups.load(user_id)
            self._user_vecs[user_id] = profile["user_vec"].copy()
        return self._user_vecs[user_id].copy()

    # ── fast loop update ──────────────────────────────────────────────────────

    def fast_update_user_vec(self, user_id: str, article_embedding: np.ndarray,
                             action: str) -> None:
        """EMA shift of user_vec toward article embedding. Called per positive action."""
        if action not in _POSITIVE:
            return
        old = self.get_vector(user_id)
        lr  = FAST_LOOP_USER_VEC_LR
        new = (1.0 - lr) * old.astype(np.float64) + lr * article_embedding.astype(np.float64)
        norm = np.linalg.norm(new)
        if norm > 1e-8:
            new /= norm
        self._user_vecs[user_id] = new.astype(np.float32)

    # ── buffer (feeds slow loop) ──────────────────────────────────────────────

    def buffer_interaction(self, record: dict) -> None:
        """
        record schema:
            user_id, story_id, title, category, action, timestamp,
            article_embedding  np.ndarray (768,)
        """
        self._buffer[record["user_id"]].append(record)

    # ── slow loop ─────────────────────────────────────────────────────────────

    def flush_updates(self) -> int:
        """
        For each buffered user:
          1. Weighted-mean EMA update on user_vec (more stable than fast loop).
          2. Append positive interactions to click_history (max 500).
          3. Save profile JSON.
        Returns number of users updated.
        """
        updated = 0
        for user_id, records in self._buffer.items():
            profile = ups.load(user_id)
            old_vec = profile["user_vec"].astype(np.float64)

            weighted_sum = np.zeros(EMBED_DIM, dtype=np.float64)
            total_weight = 0.0
            new_history  = []

            for rec in records:
                w = _POSITIVE.get(rec["action"], 0.0)
                if w > 0.0:
                    weighted_sum += w * rec["article_embedding"].astype(np.float64)
                    total_weight += w
                    new_history.append({
                        "story_id":  rec["story_id"],
                        "title":     rec["title"],
                        "category":  rec["category"],
                        "action":    rec["action"],
                        "timestamp": rec["timestamp"],
                    })

            if total_weight > 0.0:
                signal  = weighted_sum / total_weight
                new_vec = (1.0 - SLOW_LOOP_LR) * old_vec + SLOW_LOOP_LR * signal
                norm    = np.linalg.norm(new_vec)
                if norm > 1e-8:
                    new_vec /= norm
                profile["user_vec"] = new_vec.astype(np.float32)

            profile["click_history"] = (profile["click_history"] + new_history)[-500:]
            ups.save(user_id, profile)
            # sync in-memory cache
            self._user_vecs[user_id] = profile["user_vec"]
            updated += 1

        self._buffer.clear()
        return updated
