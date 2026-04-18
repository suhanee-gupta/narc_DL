"""
RLEnvironment — main engine entry point.

Two modes:
  SIMULATION  python rl_env.py --simulate [--users N] [--sessions N]
              Uses UserEngine from user_maker.py to simulate behaviour.
              Updates LinUCB + user_vec on every interaction.

  PRODUCTION  Import RLEnvironment and call:
              get_recommendations(user_id, mood, location, timestamp, archetype)
              record_interaction(user_id, story_id, action, position, session_ctx)
"""

import json
import math
import argparse
import random
from datetime import datetime, timezone
from dataclasses import dataclass, field

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from user_maker import UserPolicy, UserEngine, compute_reward, Article
from news_pipeline import NewsPipeline
from user_context import UserContextStore
from bandits import LinUCBBandit
from slow_loop import SlowLoop
import user_profile_store as ups
import context_encoder
import query_builder
from config import (
    TOP_N_CANDIDATES, TOP_K_RECS, FAST_LOOP_ROUNDS,
    SLOW_LOOP_FLUSH_EVERY, RERANK_REFRESH_EVERY,
    ARCHETYPE_CATEGORY_WEIGHTS, MOOD_MODIFIERS,
    CATEGORIES, LOCATIONS, EMBED_DIM,
)

# ── cross-encoder (bge-reranker) ──────────────────────────────────────────────

_RERANKER_NAME = "BAAI/bge-reranker-base"
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("Loading reranker model...")
_tokenizer = AutoTokenizer.from_pretrained(_RERANKER_NAME)
_model     = AutoModelForSequenceClassification.from_pretrained(_RERANKER_NAME)
_model.to(_DEVICE)
_model.eval()
print("Reranker ready.\n")


@torch.no_grad()
def score_pairs(query: str, docs: list[str], batch_size: int = 8) -> list[float]:
    scores = []
    for i in range(0, len(docs), batch_size):
        batch  = docs[i: i + batch_size]
        pairs  = [[query, d] for d in batch]
        inputs = _tokenizer(pairs, padding=True, truncation=True,
                            max_length=512, return_tensors="pt")
        inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}
        logits = _model(**inputs).logits.view(-1).cpu().tolist()
        scores.extend(logits)
    return scores


# ── per-action reward ─────────────────────────────────────────────────────────

ACTION_REWARDS = {
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


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _candidate_pool(articles: list[Article], user_vec: np.ndarray,
                    embeddings: np.ndarray, archetype: str,
                    mood: dict) -> list[tuple[Article, int]]:
    """
    Returns (article, original_index) pairs, up to TOP_N_CANDIDATES.
    Cold start → category-weighted sample.
    Warm       → cosine similarity on user_vec, then mood/freshness re-score.
    """
    is_cold = float(np.linalg.norm(user_vec)) < 1e-8

    if not is_cold:
        # cosine similarity: embeddings are (N,768), user_vec is (768,)
        u = user_vec.astype(np.float32)
        u = u / (np.linalg.norm(u) + 1e-8)
        sims = embeddings @ u                     # (N,)
        top_idx = np.argpartition(sims, -TOP_N_CANDIDATES)[-TOP_N_CANDIDATES:]
        top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
        pairs = [(articles[i], int(i)) for i in top_idx]
    else:
        cat_weights = ARCHETYPE_CATEGORY_WEIGHTS.get(archetype,
                          {c: 1/24 for c in CATEGORIES})
        # mood modifiers
        adjusted = dict(cat_weights)
        for mood_key, val in mood.items():
            if val > 0.6 and mood_key in MOOD_MODIFIERS:
                mod = MOOD_MODIFIERS[mood_key]
                for c in mod["deprioritize"]:
                    adjusted[c] = adjusted.get(c, 0.01) * 0.2
                for c in mod["boost"]:
                    adjusted[c] = adjusted.get(c, 0.01) * 1.5
        total = sum(adjusted.values()) or 1.0
        adjusted = {k: v / total for k, v in adjusted.items()}

        cats  = list(adjusted.keys())
        probs = [adjusted[c] for c in cats]
        chosen_cats = random.choices(cats, weights=probs, k=TOP_N_CANDIDATES * 3)

        seen, pairs = set(), []
        for cat in chosen_cats:
            if len(pairs) >= TOP_N_CANDIDATES:
                break
            candidates = [(a, i) for i, a in enumerate(articles)
                          if a.category == cat and i not in seen]
            if candidates:
                a, idx = random.choice(candidates)
                seen.add(idx)
                pairs.append((a, idx))

    # re-score by freshness after cosine
    pairs.sort(key=lambda t: t[0].freshness, reverse=True)
    return pairs[:TOP_N_CANDIDATES]


# ── main environment ──────────────────────────────────────────────────────────

class RLEnvironment:
    def __init__(self, pipeline: NewsPipeline, context_store: UserContextStore,
                 bandit: LinUCBBandit):
        self.pipeline = pipeline
        self.ctx      = context_store
        self.bandit   = bandit

    # ── production ───────────────────────────────────────────────────────────

    def get_recommendations(self, user_id: str, mood: dict, location: str,
                            timestamp: str, archetype: str) -> list[dict]:
        profile  = ups.load(user_id)
        user_vec = self.ctx.get_vector(user_id)

        articles   = self.pipeline.get_articles()
        embeddings = self.pipeline.get_all_embeddings()

        pairs = _candidate_pool(articles, user_vec, embeddings, archetype, mood)

        # cross-encoder rerank
        docs   = [f"{a.title}. {a.summary}" for a, _ in pairs]
        query  = query_builder.build(archetype, mood, location, timestamp,
                                     profile.get("click_history", []))
        scores = score_pairs(query, docs)
        ranked = sorted(zip(pairs, scores), key=lambda x: x[1], reverse=True)[:20]

        # LinUCB select top-k
        ctx_vecs   = [context_encoder.build(mood, archetype, location, timestamp,
                                             a.category, a.freshness, s)
                      for (a, _), s in ranked]
        candidates = [a for (a, _), _ in ranked]
        top_k      = self.bandit.select_topk(ctx_vecs, candidates, TOP_K_RECS)

        return [
            {
                "rank":      i + 1,
                "story_id":  a.id,
                "title":     a.title,
                "summary":   a.summary,
                "category":  a.category,
                "freshness": round(a.freshness, 4),
            }
            for i, a in enumerate(top_k)
        ]

    def record_interaction(self, user_id: str, story_id: str, action: str,
                           position: int, session_ctx: dict) -> None:
        if action not in ACTION_REWARDS:
            raise ValueError(f"Unknown action '{action}'")
        article = self.pipeline.get_article(story_id)
        if article is None:
            raise KeyError(f"Unknown story_id: {story_id}")

        embedding = self.pipeline.get_embedding(story_id)

        ctx    = context_encoder.build(
            session_ctx["mood"], session_ctx["archetype"],
            session_ctx["location"], session_ctx["timestamp"],
            article.category, article.freshness,
            session_ctx.get("reranker_score", 0.0),
        )
        reward = ACTION_REWARDS[action] / math.log2(position + 2)

        # fast loop — LinUCB
        self.bandit.update(ctx, reward)

        # fast loop — user_vec
        if embedding is not None:
            self.ctx.fast_update_user_vec(user_id, embedding, action)

        # buffer for slow loop
        self.ctx.buffer_interaction({
            "user_id":           user_id,
            "story_id":          story_id,
            "title":             article.title,
            "category":          article.category,
            "action":            action,
            "timestamp":         session_ctx.get("timestamp", _now_iso()),
            "article_embedding": embedding if embedding is not None
                                  else np.zeros(EMBED_DIM, dtype=np.float32),
        })

    # ── simulation ────────────────────────────────────────────────────────────

    def run_session(self, policy: UserPolicy, mood: dict, location: str,
                    timestamp: str) -> SessionResult:
        archetype = _policy_archetype(policy)
        user_id   = policy.user_id

        profile  = ups.load(user_id)
        if profile["archetype"] == "cold_start":
            profile["archetype"] = archetype
            ups.save(user_id, profile)

        articles   = self.pipeline.get_articles()
        embeddings = self.pipeline.get_all_embeddings()

        _POSITIVE_ACTIONS = {"share", "dwell_long", "click"}

        def _build_candidates(session_interactions: list):
            """Re-run candidate pool + reranker using current user_vec and
            in-session positive clicks appended to click_history."""
            uv     = self.ctx.get_vector(user_id)
            pairs  = _candidate_pool(articles, uv, embeddings, archetype, mood)
            # include in-session positive clicks in query so reranker adapts
            session_pos = [
                {"title": self.pipeline.get_article(ix["article_id"]).title or ""}
                for ix in session_interactions
                if ix["action"] in _POSITIVE_ACTIONS
                and self.pipeline.get_article(ix["article_id"]) is not None
            ]
            q = query_builder.build(
                archetype, mood, location, timestamp,
                profile.get("click_history", []) + session_pos,
            )
            docs    = [f"{a.title}. {a.summary}" for a, _ in pairs]
            scores  = score_pairs(q, docs)
            ranked  = sorted(zip(pairs, scores), key=lambda x: x[1], reverse=True)[:20]
            cvecs   = [context_encoder.build(mood, archetype, location, timestamp,
                                              a.category, a.freshness, s)
                       for (a, _), s in ranked]
            cands   = [a for (a, _), _ in ranked]
            return cvecs, cands

        ctx_vecs, candidates = _build_candidates([])

        engine = UserEngine(policy)
        result = SessionResult(user_id=user_id)

        print(f"    Learning Trajectory (User {user_id[:8]}...): ", end="", flush=True)
        for round_idx in range(FAST_LOOP_ROUNDS):
            # slow loop flush — stable user_vec update every N rounds
            if round_idx > 0 and round_idx % SLOW_LOOP_FLUSH_EVERY == 0:
                self.ctx.flush_updates()

            # refresh reranker every N rounds using in-session clicks
            # Also refresh if the last round was a total failure (reward < 0)
            if round_idx > 0 and (round_idx % RERANK_REFRESH_EVERY == 0):
                profile = ups.load(user_id)
                ctx_vecs, candidates = _build_candidates(result.interactions)

            top_k    = self.bandit.select_topk(ctx_vecs, candidates, TOP_K_RECS)
            top_ctxs = [ctx_vecs[candidates.index(a)] for a in top_k]

            # fresh state each round — session_length applies per round, not total
            state = engine.start_session()
            interactions, _ = engine.interact_with_feed(top_k, state)
            if not interactions:
                print(" [Session End]", end="")
                break

            # Detailed reward breakdown and 'repeaking' check
            r_reward = compute_reward(interactions)
            acts = {"c": 0, "s": 0, "h": 0} # clicks, skips, shares/dwell_long
            for ix in interactions:
                if ix["action"] == "skip": acts["s"] += 1
                elif ix["action"] in ["share", "dwell_long"]: acts["h"] += 1
                else: acts["c"] += 1
            
            # ID Fingerprint: Last 4 chars of top 2 recs
            fingerprint = [str(a.id)[-4:] for a in top_k[:2]]
            print(f"|{r_reward:+.1f} {acts} {fingerprint}| ", end="", flush=True)

            for ix, ctx in zip(interactions, top_ctxs):
                reward = ACTION_REWARDS.get(ix["action"], 0.0) / math.log2(ix["position"] + 2)
                self.bandit.update(ctx, reward)

                emb = self.pipeline.get_embedding(ix["article_id"])
                if emb is not None:
                    self.ctx.fast_update_user_vec(user_id, emb, ix["action"])

                _art = self.pipeline.get_article(ix["article_id"])
                self.ctx.buffer_interaction({
                    "user_id":           user_id,
                    "story_id":          ix["article_id"],
                    "title":             _art.title if _art else "",
                    "category":          ix["category"],
                    "action":            ix["action"],
                    "timestamp":         timestamp,
                    "article_embedding": emb if emb is not None
                                          else np.zeros(EMBED_DIM, dtype=np.float32),
                })

            result.interactions.extend(interactions)
            result.rounds = round_idx + 1

        print("") # newline after trajectory
        result.reward = compute_reward(result.interactions)
        return result


def _policy_archetype(policy: UserPolicy) -> str:
    top_cat = max(policy.category_weights, key=policy.category_weights.get)
    mapping = {
        "Sports": "sports_fan", "Cricket": "sports_fan", "IPL": "sports_fan",
        "Health": "wellness", "Education": "wellness", "Environment": "wellness",
        "Finance": "finance_biz", "Business": "finance_biz", "Markets": "finance_biz",
        "Bitcoin": "finance_biz", "Crypto": "finance_biz", "Inflation": "finance_biz",
        "Technology": "sci_tech", "AI": "sci_tech", "Science": "sci_tech",
        "OpenAI": "sci_tech", "Startups": "sci_tech", "Tesla": "sci_tech",
        "World": "world_watcher", "Politics": "world_watcher",
        "Elections": "world_watcher", "War": "world_watcher",
        "Entertainment": "foodie_lifestyle", "Movies": "foodie_lifestyle",
    }
    return mapping.get(top_cat, "cold_start")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _load_policies(path: str = "user_policies.json") -> list[UserPolicy]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [UserPolicy(**{k: v for k, v in d.items()}) for d in data]


def _random_mood() -> dict:
    keys = ["happy", "sad", "angry", "anxious", "calm", "curious"]
    raw  = {k: random.random() for k in keys}
    total = sum(raw.values())
    return {k: round(v / total, 3) for k, v in raw.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate",         action="store_true")
    parser.add_argument("--users",            type=int, default=100)
    parser.add_argument("--sessions",         type=int, default=5)
    parser.add_argument("--checkpoint-dir",   type=str, default="checkpoints")
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--resume",           type=str, default=None,
                        help="Path to checkpoint .npz (without extension) to resume from")
    args = parser.parse_args()

    pipeline = NewsPipeline()
    pipeline.load()

    ctx_store = UserContextStore()
    bandit    = LinUCBBandit()
    slow      = SlowLoop(ctx_store)
    env       = RLEnvironment(pipeline, ctx_store, bandit)

    start_session = 1
    if args.resume:
        bandit.load(args.resume)
        # infer which session to resume from filename e.g. checkpoints/bandit_session_10
        try:
            start_session = int(args.resume.split("_session_")[-1]) + 1
        except ValueError:
            pass
        print(f"Resumed from {args.resume}.npz — starting at session {start_session}")

    if args.simulate:
        policies     = _load_policies()[:args.users]
        session_rewards: list[float] = []
        sessions_run = 0

        for session_num in range(start_session, args.sessions + 1):
            print(f"\n=== Session {session_num}/{args.sessions} ===", flush=True)
            session_total = 0.0
            for policy in policies:
                mood      = _random_mood()
                location  = random.choice(LOCATIONS)
                timestamp = _now_iso()
                result    = env.run_session(policy, mood, location, timestamp)
                session_total += result.reward
                print(f"  {policy.user_id:35s}  reward={result.reward:+.3f}"
                      f"  rounds={result.rounds}  interactions={len(result.interactions)}",
                      flush=True)

            session_avg = session_total / len(policies)
            session_rewards.append(session_avg)
            sessions_run += 1

            slow.run_once()

            # convergence summary every 5 sessions
            if session_num % 5 == 0:
                window = session_rewards[-5:]
                print(f"\n  [Convergence] last 5 sessions avg reward: "
                      f"{sum(window)/len(window):+.3f}  "
                      f"(was {sum(session_rewards[:5])/len(session_rewards[:5]):+.3f} at start)",
                      flush=True)
                # show what bandit has learned: top categories by theta score
                theta = bandit.A_inv @ bandit.b
                cat_start = 6 + 7 + 3 + 4   # offset into context vec for category_onehot
                cat_scores = {CATEGORIES[i]: float(theta[cat_start + i])
                              for i in range(len(CATEGORIES))}
                top_cats = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                print(f"  [Bandit θ] top categories: "
                      + "  ".join(f"{c}={v:+.3f}" for c, v in top_cats), flush=True)

            if session_num % args.checkpoint_every == 0:
                ckpt = f"{args.checkpoint_dir}/bandit_session_{session_num}"
                bandit.save(ckpt)
                print(f"  [Checkpoint] saved → {ckpt}.npz", flush=True)

        overall_avg = sum(session_rewards) / len(session_rewards) if session_rewards else 0.0
        print(f"\nOverall average reward: {overall_avg:+.3f}")
        print(f"First 5 sessions avg:   {sum(session_rewards[:5])/5:+.3f}")
        print(f"Last  5 sessions avg:   {sum(session_rewards[-5:])/5:+.3f}")
        print("Training complete.")
        final_ckpt = f"{args.checkpoint_dir}/bandit_session_{args.sessions}_final"
        bandit.save(final_ckpt)
        print(f"[Checkpoint] final saved → {final_ckpt}.npz")
