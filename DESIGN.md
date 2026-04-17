# NARC — Design Document

## System Overview

```
── OFFLINE (run once, produces news_vectors.pkl) ───────────────────────────
[news.tsv]  [distilbert_embeddings.pkl]  [entity_embedding.vec]  [relation_embedding.vec]
      └──────────────────────┬──────────────────────────┘
                             ▼
                      [news_encoder.py]   ◄── ONLY script that touches raw text/embeddings
                             │
                             ▼
                      [news_vectors.pkl]   {news_id: np.array(256,)}

── ONLINE (per session) ────────────────────────────────────────────────────
[news_vectors.pkl] + [news.tsv metadata]
      │
      ▼
[news_pipeline.py]  →  Article objects
      │
      ▼
[Article Store]   (news_id → Article with .vec)
      │
      ▼
[Cosine Recommender]  ◄── user_vec + article_vecs
      │  top-N candidates
      ▼
[LinUCB Bandit]  ◄── select top-k, rerank after each round
      │  top-k articles
      ▼
[User Policy Engine]  ◄── already in user_maker.py
      │  actions (click / skip / dwell_long / etc.)
      ▼
[LinUCB Bandit Update]  ◄── fast loop: repeat N rounds
      │
      └──► [Interaction Log]  (buffered per user)
                 │
                 │  every 1–2 hours (slow loop)
                 ▼
         [User Context Store]  ◄── update user_vec
                 │
                 └──► fed back into Cosine Recommender next session
```

---

## Components To Build

### 1. `config.py`
Global constants. No logic.

```python
VEC_DIM = 256                   # final news_vec / user_vec dimension

# recommendation stages
TOP_N_CANDIDATES = 50
TOP_K_RECS = 10
FAST_LOOP_ROUNDS = 3

# LinUCB
BANDIT_ALPHA = 0.5

# slow loop
SLOW_LOOP_INTERVAL_SEC = 3600
SLOW_LOOP_LR = 0.1

# news pipeline
FRESHNESS_HALF_LIFE_HOURS = 6.0

# news encoder (offline script)
DISTILBERT_DIM = 768            # fixed — DistilBERT output size
# entity_dim and relation_dim are read from the .vec file headers at runtime
```

---

### 2. `news_encoder.py`  *(offline batch script — run once)*
**Boundary:** this is the ONLY script that reads raw text or source embeddings.  
Everything downstream receives only the output `news_vectors.pkl`.

#### Input files

| File | Format | Content |
|------|--------|---------|
| `news.tsv` | TSV, 8 columns | `news_id, category, subcategory, title, abstract, url, title_entities, abstract_entities` |
| `distilbert_embeddings.pkl` | pickle, `dict[news_id, np.array(768,)]` | Precomputed DistilBERT title embeddings |
| `entity_embedding.vec` | text; line 0: `num_entities dim`; lines 1+: `entity_id f1 f2 …` | KG entity embeddings (Microsoft Satori) |
| `relation_embedding.vec` | same format as entity file | KG relation embeddings |

#### `title_entities` / `abstract_entities` JSON format (per row in news.tsv)
```json
[
  {
    "WikidataId": "Q756",
    "Label": "Netflix",
    "Type": "Organization",
    "OccurrenceOffsets": [0],
    "Confidence": 1.0
  },
  ...
]
```
Entity IDs = the `WikidataId` values.  
Relation IDs are **not** stored per-article; relation_vec falls back to zero vector if no relation IDs are present.

#### Processing pipeline per article

```
1. distilbert_vec  = distilbert_embeddings[news_id]          # (768,)

2. entity_ids      = {e["WikidataId"]
                      for e in title_entities + abstract_entities}
   entity_vecs     = [entity_embedding[eid] for eid in entity_ids
                      if eid in entity_embedding]
   entity_vec      = mean(entity_vecs)  if entity_vecs else zeros(entity_dim)   # (entity_dim,)

3. relation_vec    = zeros(relation_dim)   # no per-article relation IDs in MIND  # (relation_dim,)

4. combined        = concat([distilbert_vec, entity_vec, relation_vec])
                   # shape: (768 + entity_dim + relation_dim,)

5. news_vec        = Linear(combined)      # nn.Linear(input_dim, 256, bias=False)
                                           # Xavier-uniform init, weights frozen (no training)
                   # shape: (256,)
```

#### Output file

```
news_vectors.pkl  →  dict[news_id: str, np.ndarray shape (256,) float32]
```
One entry per row in `news.tsv`. This file is the sole output consumed by `news_pipeline.py`.

#### Class / entry point

```python
class NewsEncoder:
    def __init__(self,
                 news_tsv: str,
                 distilbert_pkl: str,
                 entity_vec: str,
                 relation_vec: str,
                 out_dim: int = 256)

    def _load_embedding_file(self, path: str) -> dict[str, np.ndarray]
        # reads first line for (num, dim), then builds {entity_id: vector} dict

    def encode_all(self) -> dict[str, np.ndarray]
        # runs pipeline above for every article, returns {news_id: vec}

    def save(self, out_path: str = "news_vectors.pkl")
        # pickle.dump(self.encode_all(), out_path)

if __name__ == "__main__":
    # CLI: python news_encoder.py --news news.tsv --distilbert distilbert_embeddings.pkl \
    #                              --entity entity_embedding.vec --relation relation_embedding.vec
```

---

### 3. `news_pipeline.py`
**Responsibility:** read `news_vectors.pkl` + `news.tsv` metadata → produce `Article` objects.  
Does **not** touch raw text beyond reading category/subcategory for the Article fields.  
Does **not** call the encoder — that is already done offline.

**Inputs consumed at runtime:**
```
news_vectors.pkl   — {news_id: np.array(256,)}   produced by news_encoder.py
news.tsv           — metadata only: news_id, category, subcategory, title (for logging)
```

**`news.tsv` row schema used here (columns 0–3 only):**
```
news_id   category   subcategory   title   [abstract, url, … ignored]
```

**Freshness:** MIND is a static dataset — articles have no `published_at`.  
Freshness is assigned by **rank in the file** (earlier rows = more recent), normalized 0→1:
```
freshness = 1 - (row_index / total_rows)
```
This is a proxy. If timestamps become available, swap to:
```
freshness = 2^( -hours_since_published / FRESHNESS_HALF_LIFE_HOURS )
```

**Output — `Article` object (defined in `user_maker.py`, reused by all downstream):**
```python
@dataclass
class Article:
    id:          str            # = news_id from TSV
    category:    str
    subcategory: str
    title:       str            # kept for logging only; not used in any computation
    vec:         np.ndarray     # shape (256,) float32 — loaded from news_vectors.pkl
    freshness:   float          # 0–1
```

**Class:**
```python
class NewsPipeline:
    def __init__(self, news_tsv: str, news_vectors_pkl: str)

    def load(self) -> None
        # reads both files, builds internal store

    def get_articles(self) -> list[Article]
        # returns all articles sorted by freshness desc

    def get_article(self, news_id: str) -> Article | None
        # lookup by id (used by rl_env when enriching interactions with .vec)
```

**Internal store:** `dict[str, Article]`  (keyed by news_id)

---

### 4. `user_context.py`
**Responsibility:** hold and update the long-term context vector for every user.

**User context vector:**
```python
np.ndarray  # shape (256,), dtype float32
            # cold start = np.zeros(256)
            # represents "direction of user interest" in article embedding space
```

**Interaction record written into buffer (comes from rl_env / fast loop):**
```python
{
  "user_id":    str,
  "article_id": str,
  "action":     str,       # click / skip / dwell_short / dwell_long / share
  "article_vec": np.ndarray  # (256,) — looked up from article store
}
```

**Slow-loop update rule:**
```
signal_vec  = weighted_mean(article_vecs of positive interactions)
              weights = action_reward_value (share=3, dwell_long=2, click=1)
new_vec = (1 - LR) * old_vec + LR * signal_vec
new_vec = new_vec / ||new_vec||   (L2-normalize; skip if zero)
```

**Class:**
```python
class UserContextStore:
    def get_vector(self, user_id: str) -> np.ndarray        # cold-start safe
    def buffer_interaction(self, record: dict)              # called each fast-loop step
    def flush_updates(self)                                 # called by slow loop
    def save(self, path: str)
    def load(self, path: str)
```

**Persistence format:** `.npz` file: `{user_id: vec, ...}`

---

### 5. `recommender.py`
**Responsibility:** cosine similarity pre-filter. No state, pure function.

**Input:**
```python
user_vec:  np.ndarray       # shape (256,)
articles:  list[Article]    # full article pool
top_n:     int              # how many candidates to return (default 50)
```

**Output:**
```python
list[Article]   # length ≤ top_n, sorted descending by cosine similarity
```

**Formula:**
```
score(a) = dot(user_vec, a.vec) / (||user_vec|| * ||a.vec||)
```
Edge case: if user_vec is zero (cold start), return articles sorted by freshness only.

**Function (no class needed):**
```python
def cosine_rank(user_vec, articles, top_n=50) -> list[Article]
```

---

### 6. `bandits.py`
**Responsibility:** LinUCB contextual bandit — selects top-k, updates on reward signal.

**Context feature vector (per article, per call):**
```python
ctx = user_vec * article.vec   # elementwise product, shape (256,)
                               # captures user-article interaction
```

**LinUCB model state:**
```python
A:     np.ndarray   # shape (256, 256) — initialized to identity
b:     np.ndarray   # shape (256,)     — initialized to zeros
A_inv: np.ndarray   # shape (256, 256) — cached inverse, updated via Sherman-Morrison
```

**UCB score per article:**
```python
theta = A_inv @ b
score = theta @ ctx + alpha * sqrt(ctx @ A_inv @ ctx)
```

**Sherman-Morrison rank-1 update (O(d²) vs O(d³) for full inversion):**
```python
# after observing reward r for context ctx:
A    += outer(ctx, ctx)
b    += r * ctx
# A_inv update:
v     = A_inv @ ctx
A_inv -= outer(v, v) / (1 + ctx @ v)
```

**Class:**
```python
class LinUCBBandit:
    def select_topk(self, user_vec, candidates: list[Article], k: int) -> list[Article]
    def update(self, user_vec, article_vec: np.ndarray, reward: float)
    def reset()   # call between users or after slow-loop update
```

---

### 7. `rl_env.py`
**Responsibility:** orchestrate the fast loop — one full session for one user.

**Fast loop (per session):**
```
1. get user_vec from UserContextStore
2. cosine_rank(user_vec, all_articles, TOP_N_CANDIDATES) → candidates
3. for round in range(FAST_LOOP_ROUNDS):
     a. bandit.select_topk(user_vec, candidates, TOP_K_RECS) → top_k
     b. user_engine.interact_with_feed(top_k, session_state) → interactions
     c. for each interaction:
          reward_signal = ACTION_REWARDS[action]
          bandit.update(user_vec, article.vec, reward_signal)
          context_store.buffer_interaction({...})
4. return SessionResult
```

**Action reward mapping (used by bandit update, not to be confused with compute_reward):**
```python
ACTION_REWARDS = {
    "share":       3.0,
    "dwell_long":  2.0,
    "click":       1.0,
    "dwell_short": -0.5,
    "skip":        -0.2,
}
```

**Input to `run_session`:**
```python
user_id:  str
```

**Output — `SessionResult`:**
```python
@dataclass
class SessionResult:
    user_id:      str
    interactions: list[dict]     # from UserEngine — see schema below
    reward:       float          # from compute_reward()
    rounds:       int            # how many fast-loop rounds ran
```

**Interaction dict schema** (produced by `UserEngine.interact_with_feed`, passed everywhere):
```python
{
  "user_id":     str,
  "article_id":  str,
  "category":    str,
  "position":    int,
  "relevance":   float,
  "action":      str,        # click / skip / dwell_short / dwell_long / share
  "mood_before": float,
  "step":        int
}
```

**Class:**
```python
class RLEnvironment:
    def __init__(self, policies, news_pipeline, context_store, bandit)
    def run_session(self, user_id: str) -> SessionResult
    def run_batch(self, user_ids: list[str]) -> list[SessionResult]
```

---

### 8. `slow_loop.py`
**Responsibility:** drain the interaction buffer in UserContextStore and update all user vectors. Run every `SLOW_LOOP_INTERVAL_SEC` seconds.

**Trigger options:**
- Called manually after N sessions
- Background thread with `threading.Timer`
- External cron (for production)

**What it does:**
```
1. context_store.flush_updates()  — updates all buffered users
2. context_store.save(path)       — persist to disk
3. (optionally) bandit.reset()    — clear bandit state so it explores fresh
```

**Class:**
```python
class SlowLoop:
    def __init__(self, context_store, bandit, interval_sec, persist_path)
    def run_once()
    def start_background()   # spawns daemon thread
    def stop()
```

---

## Data Flow Summary

```
── OFFLINE ──────────────────────────────────────────────────────────────────
Stage                    Passes                              To
─────────────────────────────────────────────────────────────────────────────
news.tsv                 entity JSON per row                 NewsEncoder
distilbert_embeddings    np.array(768,) per news_id          NewsEncoder
entity_embedding.vec     {entity_id: np.array(E,)}           NewsEncoder
relation_embedding.vec   {relation_id: np.array(R,)}         NewsEncoder
NewsEncoder              concat(768+E+R) → Linear → (256,)  news_vectors.pkl

── ONLINE ───────────────────────────────────────────────────────────────────
Stage                    Passes                              To
─────────────────────────────────────────────────────────────────────────────
news_vectors.pkl         {news_id: np.array(256,)}           NewsPipeline
news.tsv (cols 0–3)      news_id, category, subcategory      NewsPipeline
NewsPipeline             Article(id, cat, vec, freshness)    Article Store
Article Store            list[Article]                       cosine_rank()
cosine_rank()            list[Article] top-N                 LinUCBBandit
LinUCBBandit             list[Article] top-K                 UserEngine
UserEngine               list[interaction_dict]              LinUCBBandit (update)
UserEngine               list[interaction_dict]              UserContextStore (buffer)
UserContextStore         np.array(256,) user_vec             cosine_rank() (next session)
SlowLoop                 triggers flush_updates()            UserContextStore
```

---

## Build Order

```
Step 1   config.py           — no deps
Step 2   news_encoder.py     — deps: config, torch (for nn.Linear + Xavier init), pickle
Step 3   news_pipeline.py    — deps: config, user_maker.Article (import Article)
Step 4   user_context.py     — deps: config
Step 5   recommender.py      — deps: config, user_maker.Article
Step 6   bandits.py          — deps: config, user_maker.Article
Step 7   rl_env.py           — deps: everything above + user_maker
Step 8   slow_loop.py        — deps: user_context, bandits, config
Step 9   requirements.txt
```

---

## External Dependencies

```
numpy>=1.24
torch>=2.0          # nn.Linear + Xavier init in news_encoder.py only
```

No RL framework needed. No sentence-transformers needed (DistilBERT is precomputed).

---

## What Is NOT Included Here

- Frontend / dashboard backend (already done, not in this repo)
- Training the linear projection (Xavier init + frozen is sufficient for dimensionality reduction)
- A/B testing or evaluation harness
- Live RSS ingestion (static MIND dataset used)
