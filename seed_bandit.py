"""
Seed the LinUCB bandit with known archetype-category preferences.
Run once before demo — takes seconds, no GPU needed.

Usage:
    python3.10 seed_bandit.py
    python3.10 seed_bandit.py --out checkpoints/seeded
"""
import argparse
import numpy as np
from bandits import LinUCBBandit
from config import ARCHETYPE_CATEGORY_WEIGHTS, ARCHETYPES, CATEGORIES, LOCATIONS
import context_encoder

SEED_REWARD  = 3.0   # reward injected per preferred category
SEED_REPEATS = 200   # how many times to inject (more = stronger prior)


def seed(bandit: LinUCBBandit):
    base_mood = {"happy": 0.1, "sad": 0.05, "angry": 0.05,
                 "anxious": 0.05, "calm": 0.4, "curious": 0.35}
    timestamp = "2026-04-19T14:00:00Z"

    for archetype in ARCHETYPES:
        if archetype == "cold_start":
            continue
        weights = ARCHETYPE_CATEGORY_WEIGHTS[archetype]
        for cat, w in weights.items():
            if w < 0.05:
                continue
            reward = SEED_REWARD * w / max(weights.values())
            for loc in LOCATIONS:
                ctx = context_encoder.build(
                    base_mood, archetype, loc, timestamp, cat,
                    freshness=0.8, reranker_score=1.5,
                )
                for _ in range(SEED_REPEATS):
                    bandit.update(ctx, reward)

    print("Seeded bandit with archetype-category priors.")
    theta = bandit.A_inv @ bandit.b
    cat_start = 6 + 7 + 3 + 4
    scores = {CATEGORIES[i]: round(float(theta[cat_start + i]), 3)
              for i in range(len(CATEGORIES))}
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:8]
    print("Top categories by θ:", "  ".join(f"{c}={v:+.3f}" for c, v in top))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="checkpoints/seeded_bandit")
    args = parser.parse_args()

    bandit = LinUCBBandit()
    seed(bandit)
    bandit.save(args.out)
    print(f"Saved → {args.out}.npz")
