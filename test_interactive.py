"""
Interactive test — loads trained bandit checkpoint, shows recommendations,
lets you interact (click/share/skip etc.) and shows how the feed changes.

Usage:
    python3.10 test_interactive.py --checkpoint checkpoints/bandit_session_50_final
    python3.10 test_interactive.py --checkpoint checkpoints/bandit_session_50_final --user user_000_news_junkie
"""

import argparse
import random
from datetime import datetime, timezone

from news_pipeline import NewsPipeline
from user_context import UserContextStore
from bandits import LinUCBBandit
from rl_env import RLEnvironment, ACTION_REWARDS
from config import LOCATIONS, ARCHETYPES


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _print_feed(recs: list[dict]):
    print("\n  #   Category          Title")
    print("  " + "-" * 70)
    for r in recs:
        title = r["title"][:55] + "…" if len(r["title"]) > 55 else r["title"]
        print(f"  {r['rank']:<3} {r['category']:<18} {title}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--user",       type=str, default="test_interactive_user")
    args = parser.parse_args()

    print("Loading pipeline...")
    pipeline  = NewsPipeline()
    pipeline.load()
    ctx_store = UserContextStore()
    bandit    = LinUCBBandit()

    if args.checkpoint:
        bandit.load(args.checkpoint)
        print(f"Loaded checkpoint: {args.checkpoint}.npz")
    else:
        print("No checkpoint — using untrained bandit.")

    env = RLEnvironment(pipeline, ctx_store, bandit)

    # ── session setup ─────────────────────────────────────────────────────────
    print("\nArchetypes:", ", ".join(ARCHETYPES))
    archetype = input("Your archetype (or press Enter for cold_start): ").strip() or "cold_start"
    if archetype not in ARCHETYPES:
        print(f"Unknown archetype, defaulting to cold_start")
        archetype = "cold_start"

    print("Locations: India, US, UK")
    location  = input("Location (or press Enter for India): ").strip() or "India"

    mood_keys = ["happy", "sad", "angry", "anxious", "calm", "curious"]
    print("\nMood sliders (0.0–1.0 each, or press Enter to randomise all):")
    mood_input = input("  Enter to randomise → ").strip()
    if not mood_input:
        raw = {k: random.random() for k in mood_keys}
        total = sum(raw.values())
        mood = {k: round(v / total, 3) for k, v in raw.items()}
        print("  Randomised mood:", mood)
    else:
        mood = {k: round(1/6, 3) for k in mood_keys}

    session_ctx = {
        "mood":      mood,
        "archetype": archetype,
        "location":  location,
        "timestamp": _now_iso(),
    }

    actions = list(ACTION_REWARDS.keys())
    user_id = args.user

    # ── interaction loop ──────────────────────────────────────────────────────
    round_num = 0
    while True:
        round_num += 1
        session_ctx["timestamp"] = _now_iso()

        print(f"\n{'='*72}")
        print(f" Round {round_num} — fetching recommendations for '{user_id}'...")
        recs = env.get_recommendations(user_id, mood, location,
                                       session_ctx["timestamp"], archetype)
        _print_feed(recs)

        # build story_id lookup
        id_map = {r["rank"]: r for r in recs}

        choice = input("Pick rank to interact with (1-10), or 'q' to quit: ").strip()
        if choice.lower() == "q":
            break
        try:
            rank = int(choice)
            assert 1 <= rank <= len(recs)
        except (ValueError, AssertionError):
            print("Invalid rank, try again.")
            continue

        print(f"Actions: {', '.join(actions)}")
        action = input("Action (or press Enter for 'click'): ").strip() or "click"
        if action not in ACTION_REWARDS:
            print(f"Unknown action '{action}', defaulting to 'click'")
            action = "click"

        article = id_map[rank]
        session_ctx["reranker_score"] = 0.0

        env.record_interaction(
            user_id   = user_id,
            story_id  = article["story_id"],
            action    = action,
            position  = rank,
            session_ctx = session_ctx,
        )

        reward = ACTION_REWARDS[action] / __import__("math").log2(rank + 2)
        print(f"\n  Recorded: '{action}' on [{article['category']}] {article['title'][:60]}")
        print(f"  Reward applied: {reward:+.3f}")
        print("  Fetching updated recommendations...")


if __name__ == "__main__":
    main()
