# NARC Engine — Backend Integration Guide

## One-time Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Produce news vectors (run once, takes a few minutes)
```bash
python news_encoder.py \
  --news news.tsv \
  --distilbert distilbert_embeddings.pkl \
  --entity entity_embedding.vec \
  --relation relation_embedding.vec \
  --out news_vectors.pkl
```
Output: `news_vectors.pkl` — do not delete this file. Re-run only if the article set changes.

---

## Starting the Engine

In your backend server (FastAPI / Flask / whatever), initialize once at startup:

```python
from news_pipeline import NewsPipeline
from user_context import UserContextStore
from bandits import LinUCBBandit
from rl_env import RLEnvironment, load_policies
from slow_loop import SlowLoop

# load articles
pipeline = NewsPipeline("news.tsv", "news_vectors.pkl")
pipeline.load()

# load user profiles
policies = load_policies("user_policies.json")

# user context vectors (loads saved state if the file exists)
context_store = UserContextStore()
context_store.load("user_contexts.npz")   # safe to call even if file doesn't exist yet

# bandit
bandit = LinUCBBandit()

# main engine
env = RLEnvironment(policies, pipeline, context_store, bandit)

# start slow loop (updates user vectors every hour in the background)
slow_loop = SlowLoop(context_store, bandit, persist_path="user_contexts.npz")
slow_loop.start_background()
```

---

## Getting Recommendations

Call this when the frontend requests a news feed for a user.

```python
recommendations = env.get_recommendations(user_id="user_000_news_junkie")
```

### Response schema
```python
[
  {
    "news_id":     "N12345",       # str — use this as the article identifier
    "category":    "tech",         # str
    "subcategory": "gadgets",      # str
    "title":       "Apple reveals...",  # str — for display only
    "freshness":   0.94            # float 0–1, higher = more recent
  },
  ...   # 10 items by default (TOP_K_RECS = 10)
]
```

The list is ordered: item 0 is the top recommendation.

---

## Recording User Actions

Call this every time a user interacts with an article. This is what trains the system.

```python
env.record_interaction(
    user_id="user_000_news_junkie",
    news_id="N12345",
    action="dwell_long"
)
```

### Valid actions

| action | meaning | reward signal |
|--------|---------|--------------|
| `click` | user opened the article | +1.0 |
| `dwell_long` | user read fully (>30s or similar threshold) | +2.0 |
| `share` | user shared the article | +3.0 |
| `dwell_short` | user opened but left quickly (<15s) | −0.5 |
| `skip` | user scrolled past without opening | −0.2 |

Map your frontend events to these five strings before calling `record_interaction`.

**This call is fast** — it does one vector multiply and a small matrix update. Safe to call on every single user event.

---

## How Training Works

There are two learning loops running simultaneously.

### Fast loop (per action, immediate)
Every `record_interaction` call updates the LinUCB bandit. The next call to
`get_recommendations` for *any* user benefits from this update. No batching,
no epochs — the model improves in real time as users interact.

### Slow loop (every ~1 hour, background)
Every hour the background thread:
1. Takes all buffered interactions since the last tick
2. Shifts each user's 256-dim context vector toward the articles they engaged with
3. Saves `user_contexts.npz` to disk

This is the "long-term memory" update. After it runs, a cold user who has
clicked a few tech articles will start receiving more tech-focused recommendations.

The slow loop runs automatically once you call `slow_loop.start_background()`.
You can also trigger it manually (e.g. for testing):
```python
n_updated = slow_loop.run_once()
print(f"{n_updated} user vectors updated")
```

---

## Shutdown / Restart

Before shutting down the server, flush the buffer so no interactions are lost:

```python
slow_loop.stop()
slow_loop.run_once()    # final flush + save
```

On restart, `context_store.load("user_contexts.npz")` reloads all user vectors.
The bandit state is NOT persisted — it resets to the uninformed prior on restart.
That is intentional: the bandit re-learns fast from live traffic.

---

## Testing with Simulated Users

To run simulated sessions without a frontend (for load testing or offline evaluation):

```python
# simulate one user session
result = env.run_session("user_000_news_junkie")

print(result.reward)         # float — overall session quality score
print(result.rounds)         # int   — how many rerank rounds ran (max 3)
print(result.interactions)   # list of interaction dicts (see below)
```

### Interaction dict schema (inside result.interactions)
```python
{
  "user_id":     "user_000_news_junkie",
  "article_id":  "N12345",
  "category":    "tech",
  "position":    0,           # 0-indexed position in the feed when shown
  "relevance":   0.74,        # internal score, useful for debugging
  "action":      "dwell_long",
  "mood_before": 0.61,        # simulated user mood at time of interaction
  "step":        2            # step index within the session
}
```

To simulate all 100 users in one call:
```python
results = env.run_batch(list(policies.keys()))
rewards = [r.reward for r in results]
print(f"Mean reward: {sum(rewards)/len(rewards):.3f}")
```

---

## Adding New Users

New users are cold-started automatically — no action needed. When
`get_recommendations` is called with an unknown `user_id`, the engine returns
the freshest articles (no personalization yet). The first few interactions
from that user will start shifting their context vector toward their interests.

If you want to pre-register a user with a known behavioral profile (for
testing), add an entry to `user_policies.json` and reload:

```python
policies = load_policies("user_policies.json")
env.policies = policies
```

---

## Configuration

All tuneable constants are in `config.py`:

| constant | default | meaning |
|----------|---------|---------|
| `TOP_N_CANDIDATES` | 50 | cosine pre-filter pool size |
| `TOP_K_RECS` | 10 | articles returned per feed |
| `FAST_LOOP_ROUNDS` | 3 | rerank passes per simulated session |
| `BANDIT_ALPHA` | 0.5 | exploration weight (higher = more diverse) |
| `SLOW_LOOP_LR` | 0.1 | user vector update step size |
| `SLOW_LOOP_INTERVAL_SEC` | 3600 | slow loop frequency (seconds) |
