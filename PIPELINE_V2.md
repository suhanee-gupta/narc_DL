# NARC Pipeline V2 — Full Integration Document

## What Changed From V1

| V1 (old) | V2 (current) |
|---|---|
| NRMS + DistilBERT encodes articles → 256-dim vec | `bge-reranker-base` scores query-doc pairs directly |
| 256-dim user vector, EMA updated | Click history list (plain JSON), no neural vec |
| Cosine similarity pre-filter | Category-weighted pre-filter + freshness |
| `news_vectors.pkl` offline artifact | No offline artifact needed — reranker runs live |
| MIND dataset (news.tsv) | `google_news_5000.json` (your scraper) |
| Fake users conflict with user_maker.py | infer6.py fake users removed; user_maker.py is ground truth |

NRMS files stay in `src/` — do not delete. They are archived, not active.

---

## Data Source

**File:** `google_news_5000.json`  
**Schema per article:**
```json
{
  "title": "...",
  "summary": "...",
  "category": "Sports",
  "tags": ["cricket", "ipl", ...],
  "published_date": "Sat, 18 Apr 2026 12:00:00 GMT",
  "region": "US",
  "country_code": "US",
  "publisher": "ESPN",
  "story_id": 419373222106,
  "canonical_url": "...",
  "scraped_at": "2026-04-18T12:47:26Z"
}
```

**24 categories in dataset:**
`AI, Bitcoin, Business, Cricket, Crypto, Education, Elections, Entertainment, Environment, Finance, Health, IPL, Inflation, Markets, Movies, OpenAI, Politics, Science, Sports, Startups, Technology, Tesla, War, World`

**Fields used downstream (everything else ignored):**
| Field | Used for |
|---|---|
| `story_id` | Article ID throughout pipeline |
| `title` | Display + query building |
| `summary` | Display + query building |
| `category` | Pre-filter, archetype bias, LinUCB feature |
| `published_date` | Freshness score |
| `region` | Location-based filtering |
| `tags` | Query enrichment |

---

## Session Start Inputs (Frontend → Backend)

Sent as JSON at the start of every session:

```json
{
  "user_id": "user_003_sports_fan",
  "mood": {
    "happy":   0.8,
    "sad":     0.1,
    "angry":   0.0,
    "anxious": 0.2,
    "calm":    0.5,
    "curious": 0.7
  },
  "location": "India",
  "time_of_day": "evening",
  "archetype": "sports_fan"
}
```

**Mood:** 6 independent sliders, each 0.0–1.0. User sets them via the frontend UI.  
**Location:** Exactly one of `"India"`, `"US"`, `"UK"`.  
**Time of day:** Exactly one of `"morning"`, `"afternoon"`, `"evening"`, `"night"`. Can be auto-set from system clock or manually overridden.  
**Archetype:** Exactly one of the 7 values below (set once at onboarding, editable in profile):

| Archetype value | Display label | Strong category bias |
|---|---|---|
| `cold_start` | New here | uniform — all categories equally |
| `sports_fan` | Sports above all | Sports, Cricket, IPL |
| `sci_tech` | Science & Tech | Technology, AI, Science, OpenAI, Startups |
| `finance_biz` | Finance & Business | Finance, Business, Markets, Inflation, Bitcoin, Crypto, Tesla |
| `wellness` | Wellness Seeker | Health, Education, Environment |
| `world_watcher` | World Watcher | World, Politics, Elections, War |
| `foodie_lifestyle` | Foodie & Lifestyle | Entertainment, Movies |

---

## User Profile Schema

Stored in `user_profiles/{user_id}.json`. This replaces the old 256-dim `.npz` vector.

```json
{
  "user_id": "user_003_sports_fan",
  "archetype": "sports_fan",
  "location": "India",
  "created_at": "2026-04-18T10:00:00Z",
  "click_history": [
    {
      "story_id": 419373222106,
      "title": "India beats Pakistan in final",
      "category": "Cricket",
      "action": "dwell_long",
      "timestamp": "2026-04-18T18:35:00Z"
    }
  ],
  "session_count": 4
}
```

**click_history** = every article the user clicked, dwelled on, or shared. Skips are NOT stored.  
Maximum history length: 500 entries (trim oldest when exceeded).  
This is the entire long-term user context — no neural vector needed.

---

## Full Pipeline — Step by Step

### Step 1 — Category Pre-Filter

Goal: reduce 4860 articles → ~200 candidates before the expensive reranker.

```
archetype_weights[archetype]        # base category weights (see table above)
       │
       ▼
mood_adjusted_weights               # mood modifiers applied (see below)
       │
       ▼
freshness_scores                    # freshness = exp(-(age_hours) / 24.0), clipped to [0.01, 1.0]
       │
       ▼
location_filter                     # prefer articles where region == user's location
       │
       ▼
~200 candidate articles             # weighted sample across categories
```

**Mood modifiers on category weights:**
| High mood value | Deprioritize | Boost |
|---|---|---|
| `anxious > 0.6` | War, Elections, Inflation | Health, Science |
| `angry > 0.6` | Politics, Elections | Sports, Entertainment |
| `sad > 0.6` | War, Elections | Entertainment, Movies |
| `happy > 0.7` | nothing | all categories open |
| `curious > 0.7` | nothing | AI, Science, Technology, World |
| `calm > 0.7` | Entertainment, IPL | Finance, Science, World |

Modifier = multiply category weight by 0.2 (deprioritize) or 1.5 (boost), then renormalize.

---

### Step 2 — Query Building

Build a text query that combines session context + click history. Fed to bge-reranker as the "question".

```python
def build_query(archetype, mood, location, time_of_day, click_history, max_titles=5):
    # dominant mood
    dominant_mood = max(mood, key=mood.get)     # e.g. "curious"
    
    # recent clicked titles (last max_titles)
    recent_titles = [h["title"] for h in click_history[-max_titles:]]
    titles_str = " | ".join(recent_titles) if recent_titles else "none yet"
    
    return (
        f"{archetype.replace('_', ' ')} perspective. "
        f"Mood: {dominant_mood}. "
        f"Location: {location}. "
        f"Time: {time_of_day}. "
        f"Recent reads: {titles_str}"
    )
```

Example output:
> `"sports fan perspective. Mood: curious. Location: India. Time: evening. Recent reads: India beats Pakistan in final | Rohit Sharma injury update"`

---

### Step 3 — bge-reranker Scoring

The reranker (from infer6.py, unchanged) scores every candidate against the query:

```python
scores = score_pairs(query, [art["title"] + " " + art["summary"] for art in candidates])
# returns list of logit floats, higher = more relevant
top_100 = sorted(candidates, key=lambda i: scores[i], reverse=True)[:100]
```

This is the most expensive step (GPU/CPU inference). Run on ~200 candidates, not all 4860.

---

### Step 4 — LinUCB Reranking → Top 10

LinUCB gets a **46-dim context vector** per article and reranks top-100 → top-10 with exploration.

**Context vector breakdown:**
```
mood(6) + archetype_onehot(7) + location_onehot(3) + time_onehot(4) +
category_onehot(24) + freshness(1) + reranker_score_normalized(1)
= 46 dimensions
```

| Segment | Dims | Values |
|---|---|---|
| mood | 6 | `[happy, sad, angry, anxious, calm, curious]` each 0–1 |
| archetype | 7 | one-hot over 7 archetypes |
| location | 3 | one-hot: `[India, US, UK]` |
| time_of_day | 4 | one-hot: `[morning, afternoon, evening, night]` |
| category | 24 | one-hot over 24 categories in dataset |
| freshness | 1 | `exp(-(age_hours) / 24.0)` |
| reranker_score | 1 | `sigmoid(raw_logit)` — normalized to 0–1 |

LinUCB picks top-10 using UCB formula: `θ·ctx + α·sqrt(ctx·A_inv·ctx)`

---

### Step 5 — Return to Frontend

```json
[
  {
    "rank": 1,
    "story_id": 419373222106,
    "title": "India beats Pakistan in final",
    "summary": "A thrilling match at...",
    "category": "Cricket",
    "publisher": "ESPNCricinfo",
    "published_date": "2026-04-18T18:00:00Z",
    "freshness": 0.92,
    "canonical_url": "https://..."
  }
]
```

---

### Step 6 — Fast Loop (Per Interaction)

Frontend sends after each user action:

```json
{
  "user_id": "user_003_sports_fan",
  "story_id": 419373222106,
  "action": "dwell_long",
  "session_id": "sess_abc123",
  "context_vec": [0.8, 0.1, 0.0, 0.2, 0.5, 0.7, 0, 1, 0, 0, 0, 0, 0, ...]
}
```

Backend does immediately:
```python
reward = compute_reward(interactions_so_far)   # from user_maker.py
bandit.update(context_vec, reward)             # Sherman-Morrison update
user_context.buffer_interaction(record)        # stage for slow loop
```

Fast loop repeats `FAST_LOOP_ROUNDS = 3` times within a session.

---

### Step 7 — Slow Loop (Hourly Background Thread)

Runs every hour via `SlowLoop.run_once()`:

```python
for user_id, buffered_records in context_store.pending.items():
    positive = [r for r in buffered_records if r["action"] in {"click", "dwell_long", "share"}]
    for rec in positive:
        user_profile[user_id]["click_history"].append({
            "story_id": rec["story_id"],
            "title":    rec["title"],
            "category": rec["category"],
            "action":   rec["action"],
            "timestamp": rec["timestamp"]
        })
    # trim to last 500
    user_profile[user_id]["click_history"] = user_profile[user_id]["click_history"][-500:]
    save_user_profile(user_id)

context_store.clear_buffer()
```

No EMA, no neural update. The history IS the long-term context.

---

## File Map

### Keep, change nothing
| File | Role |
|---|---|
| `user_maker.py` | UserPolicy, UserEngine, compute_reward — simulation ground truth |
| `user_policies.json` | 100 pre-generated simulation users |
| `bandits.py` | LinUCB — only change: `context_dim = 46` in config |

### Rewrite
| File | What changes |
|---|---|
| `user_context.py` | Replace 256-dim EMA with click_history JSON store |
| `news_pipeline.py` | Load from `google_news_5000.json` instead of MIND TSV |
| `rl_env.py` | Wire new pipeline: pre-filter → query build → rerank → LinUCB |
| `config.py` | Add context_dim=46, archetype/mood/location/time constants |
| `slow_loop.py` | flush = append to click_history, not EMA update |

### New files to create
| File | Role |
|---|---|
| `context_encoder.py` | Build 46-dim context vec from session inputs + article features |
| `query_builder.py` | Build text query from archetype + mood + history |
| `user_profile_store.py` | Load/save `user_profiles/{user_id}.json` |

### Archive (keep, but not in active pipeline)
| File | Why archived |
|---|---|
| `news_encoder.py` | Was for NRMS → 256-dim projection. Superseded by bge-reranker |
| `src/` folder | NRMS model, MIND dataset code — no longer in pipeline |
| `infer6.py` | Prototype. Logic absorbed into rl_env.py. Fake users removed. |

### Delete
| File | Why |
|---|---|
| `recommender.py` | Was cosine similarity on 256-dim vecs — replaced by bge-reranker |

---

## Simulation Mode (for testing without frontend)

`user_maker.py` archetypes map to your 7 frontend archetypes:

| user_maker.py archetype | Frontend archetype |
|---|---|
| `news_junkie` | `world_watcher` |
| `casual_browser` | `foodie_lifestyle` |
| `deep_reader` | `finance_biz` |
| `explorer` | `cold_start` |
| `sports_fan` | `sports_fan` |

To simulate a session:
```python
env = RLEnvironment(news_json="google_news_5000.json", profiles_dir="user_profiles/")
result = env.run_session(user_id="user_003_sports_fan", mood={"happy":0.8,"curious":0.7,...}, location="India", time_of_day="evening")
print(result.reward, result.interactions)
```

---

## Implementation Order

1. **`config.py`** — add all new constants (context_dim=46, archetype map, category list, mood modifiers)
2. **`user_profile_store.py`** — load/save user profile JSON with click_history
3. **`context_encoder.py`** — build 46-dim vec from session inputs + article
4. **`query_builder.py`** — build text query string
5. **`news_pipeline.py`** — rewrite to load google_news_5000.json, compute freshness
6. **`user_context.py`** — rewrite flush to append history, not EMA
7. **`rl_env.py`** — wire full pipeline: pre-filter → query → rerank → LinUCB → interact → update
8. **`slow_loop.py`** — rewrite flush_updates
9. **Update `bandits.py`** — change context_dim reference to config value (46)
10. **Update `ENGINE_API.md`** — new session start schema, new interaction schema

---

## What the Frontend Must Send

### Session start (once per session load)
```
POST /session/start
{user_id, mood{6 floats}, location, time_of_day, archetype}
→ returns: session_id
```

### Get recommendations
```
GET /recommendations?user_id=X&session_id=Y
→ returns: [{rank, story_id, title, summary, category, publisher, published_date, freshness, canonical_url}]
```

### Record interaction (after each user action)
```
POST /interaction
{user_id, session_id, story_id, action}
action ∈ {click, dwell_short, dwell_long, share, skip}
→ triggers fast loop update
```

### Behavior log stream (for live dashboard)
```
GET /logs/stream?user_id=X   (SSE or WebSocket)
→ emits interaction records as they happen
```
