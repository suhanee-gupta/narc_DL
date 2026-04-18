# NARC — Pipeline V2

---

## Data

**Source:** `google_news_5000.json` — 4,860 articles.

**Fields used:**

| Field | Purpose |
|---|---|
| `story_id` | Unique article ID throughout the pipeline |
| `title` | Display, embedding input, query building |
| `summary` | Display, embedding input, cross-encoder input |
| `category` | Archetype bias, mood filter, LinUCB feature |
| `published_date` | Freshness score |
| `region` | Location filter |

**24 categories in dataset:**
AI, Bitcoin, Business, Cricket, Crypto, Education, Elections, Entertainment, Environment, Finance, Health, IPL, Inflation, Markets, Movies, OpenAI, Politics, Science, Sports, Startups, Technology, Tesla, War, World

---

## Models

Two models run at different stages:

**Bi-encoder — `BAAI/bge-small-en-v1.5`**
Encodes article text (title + summary) into a 768-dim vector independently. These vectors are computed offline once and stored. Also used to build the user vector. Enables fast cosine similarity.

**Cross-encoder — `BAAI/bge-reranker-base`**
Takes a (query string, article text) pair together and outputs a single relevance score. Cannot produce standalone embeddings. Used only for reranking a small candidate set. This is what infer6.py implements.

---

## Offline Step — Article Embedding (Run Once)

Before serving, encode every article with the bi-encoder and save to `article_embeddings.pkl` — a dict of `{story_id: np.array(768,)}`. Re-run whenever new articles are scraped.

---

## Session Start Inputs

Sent by the frontend at the start of each session:

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | Persistent user identifier |
| `mood.happy` | float 0–1 | Independent slider |
| `mood.sad` | float 0–1 | Independent slider |
| `mood.angry` | float 0–1 | Independent slider |
| `mood.anxious` | float 0–1 | Independent slider |
| `mood.calm` | float 0–1 | Independent slider |
| `mood.curious` | float 0–1 | Independent slider |
| `location` | string | One of: `India`, `US`, `UK` |
| `timestamp` | ISO 8601 string | Backend derives time-of-day bucket |
| `archetype` | string | Set at onboarding, see below |

**Archetypes:**

| Value | Display label | Strong category bias |
|---|---|---|
| `cold_start` | New here | Uniform across all categories |
| `sports_fan` | Sports above all | Sports, Cricket, IPL |
| `sci_tech` | Science & Tech | Technology, AI, Science, OpenAI, Startups |
| `finance_biz` | Finance & Business | Finance, Business, Markets, Inflation, Bitcoin, Crypto, Tesla |
| `wellness` | Wellness Seeker | Health, Education, Environment |
| `world_watcher` | World Watcher | World, Politics, Elections, War |
| `foodie_lifestyle` | Foodie & Lifestyle | Entertainment, Movies |

**Time-of-day bucketing (done on backend from timestamp):**
- 00:00–05:59 → `morning`
- 06:00–11:59 → `afternoon`
- 12:00–17:59 → `evening`
- 18:00–23:59 → `night`

---

## User Profile

Stored as `user_profiles/{user_id}.json`.

| Field | Type | Description |
|---|---|---|
| `user_id` | string | |
| `archetype` | string | Set at onboarding |
| `location` | string | Set at onboarding |
| `created_at` | ISO string | |
| `session_count` | int | |
| `user_vec` | list of 768 floats | Running mean of bi-encoder embeddings of all positively-interacted articles. All zeros for cold start. L2-normalized. |
| `click_history` | list of objects | Every article the user clicked, dwelled on, or shared. Max 500 entries. Skips not stored. |

Each `click_history` entry: `{story_id, title, category, action, timestamp}`

---

## Online Pipeline — Per Request

### Step 1 — Cosine Pre-Filter → top 200

The user vector (768-dim) is compared against all article embeddings via dot product (both are L2-normalized, so dot product = cosine similarity). Top 200 articles by score become the candidate pool.

**Cold start exception:** when `user_vec` is all zeros, skip cosine. Instead sample ~200 articles weighted by the archetype's category biases and freshness.

---

### Step 2 — Mood + Freshness + Location Scoring

Each of the 200 candidates gets a composite score adjustment before the expensive cross-encoder:

**Freshness:** `exp(-(age_in_hours) / 24.0)`, clipped to `[0.01, 1.0]`

**Mood modifiers on category weights:**

| Condition | Deprioritize (×0.2) | Boost (×1.5) |
|---|---|---|
| `anxious > 0.6` | War, Elections, Inflation | Health, Science |
| `angry > 0.6` | Politics, Elections | Sports, Entertainment |
| `sad > 0.6` | War, Elections | Entertainment, Movies |
| `curious > 0.7` | — | AI, Science, Technology, World |
| `calm > 0.7` | Entertainment, IPL | Finance, Science, World |

**Location:** articles where `region == user.location` get a ×1.2 score bonus.

Candidates are re-sorted. Bottom half trimmed if needed to keep cross-encoder input under 200.

---

### Step 3 — Cross-Encoder Rerank → top 20

A natural language query is built from the session inputs and click history:

> `"[archetype] perspective. Mood: [dominant mood]. Location: [location]. Time: [time bucket]. Recent reads: [title1] | [title2] | [title3]"`

The cross-encoder scores every (query, article_text) pair. Top 20 by relevance score pass to the next step.

---

### Step 4 — LinUCB → top 10

LinUCB reranks the 20 candidates with Upper Confidence Bound exploration. Each article gets a 46-dim context vector built from explicit session and article features:

| Segment | Dims |
|---|---|
| Mood vector | 6 |
| Archetype one-hot | 7 |
| Location one-hot | 3 |
| Time-of-day one-hot | 4 |
| Category one-hot | 24 |
| Freshness | 1 |
| Cross-encoder score (sigmoid-normalized) | 1 |
| **Total** | **46** |

LinUCB selects top 10 balancing exploitation (high predicted reward) and exploration (uncertainty).

---

### Step 5 — Response to Frontend

Each recommended article returns: `rank, story_id, title, summary, category, publisher, published_date, freshness, canonical_url`

---

## Fast Loop — Per Interaction

After each user action, the backend immediately:
1. Computes reward using `compute_reward()` from `user_maker.py`
2. Updates LinUCB with the 46-dim context vector and reward (Sherman-Morrison rank-1 update)
3. Buffers the interaction (with 768-dim article embedding) for the slow loop

Actions: `click`, `dwell_short`, `dwell_long`, `share`, `skip`

---

## Slow Loop — Hourly

Runs in a background thread every hour:

1. **Update `user_vec`:** compute running mean of bi-encoder embeddings of all positively-interacted articles buffered since last flush. L2-normalize the result.
2. **Append to `click_history`:** add positive interactions only. Trim to last 500.
3. **Save** user profile JSON to disk.
4. **Clear** interaction buffer.

Positive interactions counted: `click`, `dwell_long`, `share`

---

## File Map

### Active pipeline files

| File | Role |
|---|---|
| `offline_encode.py` | Bi-encode all articles → `article_embeddings.pkl` (run once) |
| `config.py` | All constants: dims, thresholds, archetype/category/mood mappings |
| `user_profile_store.py` | Load/save `user_profiles/{user_id}.json` |
| `news_pipeline.py` | Load `google_news_5000.json`, compute freshness scores |
| `context_encoder.py` | Build 46-dim context vector from session inputs + article metadata |
| `query_builder.py` | Build text query string from session context + click history |
| `user_context.py` | Interaction buffer; flush updates `user_vec` + `click_history` |
| `bandits.py` | LinUCB with 46-dim context, Sherman-Morrison update |
| `slow_loop.py` | Hourly background thread that calls flush |
| `rl_env.py` | Wires all steps into the full pipeline; exposes `get_recommendations()` and `record_interaction()` |
| `user_maker.py` | `UserPolicy`, `UserEngine`, `compute_reward` — simulation and reward logic |
| `user_policies.json` | 100 pre-generated simulation users |

### Archived (not in pipeline)
`src/`, `infer6.py`, `news_encoder.py`, `recommender.py`

---

## Frontend API

### Session start
```
POST /session/start
{user_id, mood, location, timestamp, archetype}
→ {session_id}
```

### Get recommendations
```
GET /recommendations?user_id=X&session_id=Y
→ [{rank, story_id, title, summary, category, publisher, published_date, freshness, canonical_url}]
```

### Record interaction
```
POST /interaction
{user_id, session_id, story_id, action}
```

### Live behavior stream (dashboard)
```
GET /logs/stream?user_id=X    (SSE or WebSocket)
```
