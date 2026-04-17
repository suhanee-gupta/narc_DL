"""
RLEnvironment — the main engine entry point.

Two modes:

  SIMULATION (testing / offline training)
      env.run_session(user_id)  →  SessionResult
      Uses UserEngine from user_maker.py to simulate user behaviour.

  PRODUCTION (real frontend)
      recs = env.get_recommendations(user_id)   →  list of article dicts
      env.record_interaction(user_id, news_id, action)

Both modes update the bandit (fast loop) and buffer interactions for the
slow loop.  The slow loop runs separately via slow_loop.py.
"""

import json
from dataclasses import dataclass, field

import numpy as np

from user_maker import UserPolicy, UserEngine, compute_reward
from news_pipeline import NewsPipeline
from user_context import UserContextStore
from bandits import LinUCBBandit
from recommender import cosine_rank
from config import TOP_N_CANDIDATES, TOP_K_RECS, FAST_LOOP_ROUNDS

# Immediate per-action reward signal fed to the bandit.
# Distinct from compute_reward() which is used for overall session evaluation.
ACTION_REWARDS: dict[str, float] = {
    "share":       3.0,
    "dwell_long":  2.0,
    "click":       1.0,
    "dwell_short": -0.5,
    "skip":        -0.2,
}


@dataclass
class SessionResult:
    user_id: str
    interactions: list[dict] = field(default_factory=list)
    reward: float = 0.0
    rounds: int = 0


# ── policy loader ─────────────────────────────────────────────────────────────

def load_policies(path: str = "user_policies.json") -> dict[str, UserPolicy]:
    """Deserialise user_policies.json → {user_id: UserPolicy}."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        d["user_id"]: UserPolicy(
            user_id=d["user_id"],
            category_weights=d["category_weights"],
            curiosity=d["curiosity"],
            patience=d["patience"],
            recency_bias=d["recency_bias"],
            position_bias=d["position_bias"],
            satiation_rate=d["satiation_rate"],
            session_length=d["session_length"],
            active_hours=d["active_hours"],
            mood_volatility=d["mood_volatility"],
        )
        for d in data
    }


# ── main environment ──────────────────────────────────────────────────────────

class RLEnvironment:
    def __init__(
        self,
        policies: dict[str, UserPolicy],
        news_pipeline: NewsPipeline,
        context_store: UserContextStore,
        bandit: LinUCBBandit,
        top_n: int = TOP_N_CANDIDATES,
        top_k: int = TOP_K_RECS,
        fast_loop_rounds: int = FAST_LOOP_ROUNDS,
    ):
        self.policies = policies
        self.pipeline = news_pipeline
        self.context_store = context_store
        self.bandit = bandit
        self.top_n = top_n
        self.top_k = top_k
        self.fast_loop_rounds = fast_loop_rounds

    # ── shared internals ─────────────────────────────────────────────────────

    def _candidates(self, user_vec: np.ndarray) -> list:
        return cosine_rank(user_vec, self.pipeline.get_articles(), top_n=self.top_n)

    def _update_from_interaction(
        self, user_id: str, user_vec: np.ndarray, ix: dict
    ) -> None:
        article = self.pipeline.get_article(ix["article_id"])
        if article is None:
            return
        reward_signal = ACTION_REWARDS.get(ix["action"], 0.0)
        self.bandit.update(user_vec, article.vec, reward_signal)
        self.context_store.buffer_interaction({
            "user_id":    user_id,
            "article_id": ix["article_id"],
            "action":     ix["action"],
            "article_vec": article.vec,
        })

    # ── simulation mode ───────────────────────────────────────────────────────

    def run_session(self, user_id: str) -> SessionResult:
        """
        Fully simulated session for testing / training.

        Flow per session:
          1. get user_vec (cold = zeros)
          2. cosine pre-filter → top-N candidates
          3. for FAST_LOOP_ROUNDS:
               a. bandit selects top-K from candidates
               b. UserEngine simulates interaction with the feed
               c. bandit updated per action
               d. interactions buffered for slow loop
        """
        policy = self.policies.get(user_id)
        if policy is None:
            raise KeyError(f"Unknown user_id: '{user_id}'")

        user_vec = self.context_store.get_vector(user_id)
        candidates = self._candidates(user_vec)

        engine = UserEngine(policy)
        state = engine.start_session()
        result = SessionResult(user_id=user_id)

        for round_idx in range(self.fast_loop_rounds):
            top_k = self.bandit.select_topk(user_vec, candidates, self.top_k)

            interactions, state = engine.interact_with_feed(top_k, state)
            if not interactions:
                break

            for ix in interactions:
                self._update_from_interaction(user_id, user_vec, ix)

            result.interactions.extend(interactions)
            result.rounds = round_idx + 1

        result.reward = compute_reward(result.interactions)
        return result

    def run_batch(self, user_ids: list[str]) -> list[SessionResult]:
        return [self.run_session(uid) for uid in user_ids]

    # ── production mode ───────────────────────────────────────────────────────

    def get_recommendations(self, user_id: str) -> list[dict]:
        """
        Returns top-K ranked article recommendations for the given user.

        Call this when the frontend requests a feed.
        Does NOT update the bandit or buffer — those happen in record_interaction().

        Response schema (list of dicts):
            news_id     : str
            category    : str
            subcategory : str
            title       : str
            freshness   : float  (0–1)
        """
        user_vec = self.context_store.get_vector(user_id)
        candidates = self._candidates(user_vec)
        top_k = self.bandit.select_topk(user_vec, candidates, self.top_k)
        return [
            {
                "news_id":     a.id,
                "category":    a.category,
                "subcategory": a.subcategory,
                "title":       a.title,
                "freshness":   round(a.freshness, 4),
            }
            for a in top_k
        ]

    def record_interaction(
        self, user_id: str, news_id: str, action: str
    ) -> None:
        """
        Record a real user action from the frontend.

        Immediately updates the bandit (fast loop).
        Buffers the interaction for the next slow-loop context update.

        Parameters
        ----------
        user_id : str   — must be a known user (in policies dict)
        news_id : str   — must be a known article (in news_pipeline)
        action  : str   — one of: click, skip, dwell_short, dwell_long, share
        """
        if action not in ACTION_REWARDS:
            raise ValueError(
                f"Unknown action '{action}'. "
                f"Valid: {list(ACTION_REWARDS.keys())}"
            )
        article = self.pipeline.get_article(news_id)
        if article is None:
            raise KeyError(f"Unknown news_id: '{news_id}'")

        user_vec = self.context_store.get_vector(user_id)
        reward_signal = ACTION_REWARDS[action]
        self.bandit.update(user_vec, article.vec, reward_signal)
        self.context_store.buffer_interaction({
            "user_id":    user_id,
            "article_id": news_id,
            "action":     action,
            "article_vec": article.vec,
        })
