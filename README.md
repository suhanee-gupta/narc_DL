# NARC — News Automated Recommendations with Context

Context-driven news recommendation engine. Every recommendation is shaped by who the user is, how they feel right now, and what they have read before.

---

## Pipeline

```
google_news_5000.json
        │
        ▼  news_pipeline.py
  Article objects  {story_id, title, summary, category, freshness}
        │
  ┌─────────────────────────────────────────────┐
  │  SESSION START (frontend sends)             │
  │  mood × 6 sliders  |  location              │
  │  timestamp          |  archetype            │
  └─────────────────────────────────────────────┘
        │
        ▼
  category pre-filter
  (archetype weights + mood modifiers + freshness)
        → ~200 candidates
        │
        ▼
  query_builder  →  bge-reranker-base (cross-encoder)
  score_pairs(query, [title + summary])
        → top 20 by relevance score
        │
        ▼
  context_encoder  →  LinUCB (46-dim explicit context)
        → top 10  →  frontend feed
        │
        ▼
  user interacts  (click / dwell_long / share / skip / dwell_short)
        │
        ├──  FAST LOOP (per interaction)
        │    reward = action_value × position_discount
        │    LinUCB.update(ctx_46dim, reward)          ← bandit learns immediately
        │    user_vec EMA toward article embedding     ← user vec shifts immediately
        │
        └──  SLOW LOOP (every hour)
             weighted mean over all buffered interactions
             update user_vec (stable, slower)
             append to click_history (max 500)
             save user profile JSON
```

---

## Model

| Model | Type | Used for |
|---|---|---|
| `BAAI/bge-reranker-base` | Cross-encoder | Scores (query, article) pairs. Reranks ~200 → top 20. |

No bi-encoder. No article embeddings. No cosine similarity.

---

## Session Inputs

| Field | Values |
|---|---|
| `mood.happy / sad / angry / anxious / calm / curious` | float 0–1 each |
| `location` | `India` \| `US` \| `UK` |
| `timestamp` | ISO 8601 — backend derives time bucket |
| `archetype` | `cold_start` \| `sports_fan` \| `sci_tech` \| `finance_biz` \| `wellness` \| `world_watcher` \| `foodie_lifestyle` |

---

## LinUCB Context Vector (46-dim)

No embeddings. Fully explicit features:

```
mood(6) + archetype_onehot(7) + location_onehot(3) + time_bucket_onehot(4)
+ category_onehot(24) + freshness(1) + reranker_score_sigmoid(1)
= 46 dimensions
```

LinUCB learns which combinations of context → high reward for each user over time.

---

## Reward Signal

Per-interaction, fed to LinUCB immediately (fast loop):

| Action | Value |
|---|---|
| share | +3.0 |
| dwell_long | +2.0 |
| click | +1.0 |
| dwell_short | −0.5 |
| skip | −0.2 |

With position discount: `reward × 1 / log2(position + 2)`

---

## User Profile

Stored at `user_profiles/{user_id}.json`:

```json
{
  "user_id": "...",
  "archetype": "sports_fan",
  "location": "India",
  "session_count": 4,
  "click_history": [
    {"story_id": 123, "title": "...", "category": "Cricket",
     "action": "dwell_long", "timestamp": "2026-04-19T18:00:00Z"}
  ]
}
```

`click_history` is the only long-term signal. Max 500 entries. Used by `query_builder` to personalise the cross-encoder query each session.

---

## File Map

| File | Role |
|---|---|
| `config.py` | All constants — dims, archetype weights, category list, mood modifiers |
| `news_pipeline.py` | Load `google_news_5000.json`, compute freshness, expose Article objects |
| `user_profile_store.py` | Load/save `user_profiles/{user_id}.json` |
| `context_encoder.py` | Build 46-dim context vector from session inputs + article metadata |
| `query_builder.py` | Build text query string from session context + click history |
| `user_context.py` | Buffer interactions → slow loop appends to click_history |
| `bandits.py` | LinUCB with 46-dim explicit context, Sherman-Morrison update |
| `slow_loop.py` | Hourly thread — flushes buffer, saves click_history |
| `rl_env.py` | Full pipeline wiring. `get_recommendations()` and `record_interaction()` |
| `user_maker.py` | `UserPolicy`, `UserEngine`, `compute_reward` — simulation only, unchanged |
| `user_policies.json` | 100 pre-generated simulation users, unchanged |
| `google_news_5000.json` | News article database |

### Not used / archived
`offline_encode.py`, `article_embeddings.pkl`, `recommender.py`, `news_encoder.py`, `src/`, `infer6.py`

---

## Setup

```bash
pip install transformers torch numpy pandas
```

**Run simulation**
```bash
python rl_env.py --simulate
```

**Serve**
```bash
python rl_env.py --serve
```

---

## Frontend API

```
POST /session/start
     {user_id, mood, location, timestamp, archetype}
     → {session_id}

GET  /recommendations?user_id=X&session_id=Y
     → [{rank, story_id, title, summary, category, publisher, published_date, freshness, canonical_url}]

POST /interaction
     {user_id, session_id, story_id, action, position}

GET  /logs/stream?user_id=X    (SSE)
```
