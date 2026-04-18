# Full-Stack Integration: Frontend ↔ Backend ↔ DL Models

## Problem

The frontend ("The Margin" — React/Vite at `news-website/`) and backend engine (`narc_DL/`) are **completely disconnected**:

- **Frontend** (`engine.jsx`) does all scoring **client-side** with a simple JS formula (`scoreArticle()`), loads the JSON directly via `import`, and stores interactions in `localStorage`.
- **Backend** (`rl_env.py`) has the real ML pipeline — `bge-reranker-base` cross-encoder, `bge-small-en-v1.5` bi-encoder embeddings, LinUCB bandit with Sherman-Morrison updates, user profiles with 768-dim learned vectors — but is **never called** by the frontend.

The two systems don't even share the same category taxonomy (frontend uses 6 topics; backend uses 24 categories).

## Goal

Replace the frontend's client-side mock engine with real API calls to a FastAPI backend that runs the full DL pipeline. Every feed load goes through:

```
Onboarding → POST /session/start
Feed load  → GET  /recommendations
User click → POST /interaction
Mood/setting change → new /session/start + /recommendations
Analytics  → GET  /logs/stream (SSE)
```

---

## User Review Required

> [!IMPORTANT]
> **Category Mapping Decision**: The frontend uses 6 display topics (`Tech, Finance, Lifestyle, Geopolitics, Health, Culture`). The backend has 24 real categories. The plan maps backend's 24 categories → frontend's 6 display groups for the UI, while sending the backend's real categories in API calls. Is this acceptable, or do you want the frontend to show all 24 categories?

> [!IMPORTANT]
> **Archetype Mapping**: The frontend currently has 3 profiles (`analyst`, `casual`, `newuser`). The backend has 7 archetypes (`cold_start, sports_fan, sci_tech, finance_biz, wellness, world_watcher, foodie_lifestyle`). The plan replaces the frontend profiles with the backend's 7 archetypes in onboarding. Agreement?

> [!WARNING]
> **Model Loading Time**: The `bge-reranker-base` cross-encoder takes ~10-30 seconds to load on first startup and ~2-4 seconds per recommendation call (scoring 200 articles). The frontend should show a loading state during this. The `title_embeddings.pkl` file must exist — if it doesn't, we'll need to run offline encoding first.

> [!CAUTION]
> **Missing Artifact**: `title_embeddings.pkl` is gitignored (`.gitignore` has `*.pkl`). If it doesn't exist on disk, the pipeline will crash. We need to either (a) generate it with an offline script, or (b) add a fallback path that works without pre-computed embeddings. Please confirm whether `title_embeddings.pkl` exists on your machine.

---

## Proposed Changes

### Component 1 — FastAPI Server (Backend)

Create a clean FastAPI app that wraps `rl_env.py`'s `RLEnvironment` and exposes the 4 endpoints the frontend needs. This replaces the current `main.py` (which uses the old `app/` walking skeleton).

---

#### [NEW] [server.py](file:///d:/e/software%20eng/news/narc_DL/server.py)

New FastAPI entrypoint that:
1. Loads `NewsPipeline`, `UserContextStore`, `LinUCBBandit`, `SlowLoop` at startup
2. Loads the cross-encoder model (`bge-reranker-base`)
3. Exposes these endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /session/start` | POST | Receives `{user_id, mood, location, timestamp, archetype}` → creates/updates session, returns `{session_id}` |
| `GET /recommendations` | GET | `?user_id=X&session_id=Y` → runs full pipeline (cosine → cross-encoder → LinUCB) → returns ranked articles |
| `POST /interaction` | POST | `{user_id, session_id, story_id, action, position}` → `record_interaction()` → fast loop update |
| `GET /logs/stream` | GET | `?user_id=X` — SSE stream of recent interactions for the analytics drawer |
| `GET /health` | GET | Returns model status, catalog size, latency |

Key design decisions:
- CORS enabled for `localhost:5173`
- Session state stored in-memory dict keyed by `session_id`
- SSE via `StreamingResponse` for live analytics
- Startup event loads models + starts slow loop
- Shutdown event flushes + saves

---

#### [MODIFY] [rl_env.py](file:///d:/e/software%20eng/news/narc_DL/rl_env.py)

Add additional article metadata to `get_recommendations()` return value:
- `summary`, `publisher`, `published_date`, `canonical_url` — needed by the frontend to display cards
- These fields exist in `google_news_5000.json` but are currently stripped by `NewsPipeline`

---

#### [MODIFY] [news_pipeline.py](file:///d:/e/software%20eng/news/narc_DL/news_pipeline.py)

Store additional raw fields from `google_news_5000.json` (summary, publisher, published_date, canonical_url, tags) alongside each Article so `server.py` can return them to the frontend.

---

### Component 2 — Frontend API Client

Replace the client-side mock engine with real `fetch()` calls to the backend.

---

#### [NEW] [api.js](file:///d:/e/software%20eng/news/news-website/src/api.js)

Centralized API client module:

```js
const API_BASE = "http://localhost:8000";

export async function startSession(userId, mood, location, archetype) { ... }
export async function getRecommendations(userId, sessionId) { ... }
export async function recordInteraction(userId, sessionId, storyId, action, position) { ... }
export function subscribeToLogs(userId, onEvent) { ... }  // SSE
```

---

#### [MODIFY] [engine.jsx](file:///d:/e/software%20eng/news/news-website/src/engine.jsx)

Major changes:
- **Remove** the static `import newsData from "./google_news_5000.json"` — articles now come from the API
- **Remove** `scoreArticle()`, `getRankedNews()`, `CORPUS`, `PROFILES` — scoring is done server-side
- **Keep** `logInteraction()`, `loadLog()`, bookmark functions — these still work client-side for instant UI feedback, but also fire API calls
- **Add** `mapBackendToFrontend(article)` — maps backend's 24 categories → frontend's 6 display topics, and maps field names (`story_id→id`, `title→headline`, etc.)
- **Update** `TOPICS` to include a mapping table

Category mapping table:

| Backend Categories | Frontend Topic |
|---|---|
| AI, Technology, OpenAI, Startups, Science, Tesla | Tech |
| Finance, Business, Markets, Inflation, Bitcoin, Crypto | Finance |
| Sports, Cricket, IPL, Entertainment, Movies | Lifestyle |
| World, Politics, Elections, War | Geopolitics |
| Health, Education, Environment | Health |
| (fallback / unmapped) | Culture |

---

#### [MODIFY] [newsroom-onboarding.jsx](file:///d:/e/software%20eng/news/news-website/src/newsroom-onboarding.jsx)

- Replace the 3 frontend profiles (`analyst, casual, newuser`) with the backend's 7 archetypes
- Map region options: `Global → India`, `North America → US`, `Europe → UK`, `Asia-Pacific → India`, `Local Area → India`
- On "Initialize Feed" button click: call `startSession()` API, save the returned `session_id`
- Time context: unchanged (already sends morning/evening/etc.)

---

#### [MODIFY] [NewsroomApp.jsx](file:///d:/e/software%20eng/news/news-website/src/NewsroomApp.jsx)

The biggest change — this is where the mock scoring loop is replaced with API calls:

1. **`useEffect` on mount / context change**: Call `startSession()` → then `getRecommendations()` → store results as `ranked`
2. **Remove** the `useMemo` that calls `scoreArticle` on `CORPUS`
3. **Add loading states**: Show skeleton/spinner while API is in flight
4. **`logInteraction()`**: In addition to localStorage, call `recordInteraction()` API
5. **Refresh button**: Re-call `getRecommendations()` to get updated feed after interactions (fast loop effect)
6. **Display real latency**: Show the actual API response time instead of hardcoded "0.4s"
7. **Confidence score**: Use the mean of backend `freshness` scores or a derived metric instead of the client-side calculation

---

#### [MODIFY] [PersonalizationDrawer.jsx](file:///d:/e/software%20eng/news/news-website/src/PersonalizationDrawer.jsx)

- Replace `PROFILES` dropdown with backend's 7 archetypes
- On "Save & Update Feed": call `startSession()` with new context → re-fetch recommendations

---

#### [MODIFY] [AnalyticsDrawer.jsx](file:///d:/e/software%20eng/news/news-website/src/AnalyticsDrawer.jsx)

- Subscribe to SSE stream (`/logs/stream?user_id=X`) for real-time interaction updates
- Show backend-tracked interactions (with actual reward signals) alongside localStorage log
- Display LinUCB-computed metrics if available

---

#### [MODIFY] [SearchOverlay.jsx](file:///d:/e/software%20eng/news/news-website/src/SearchOverlay.jsx)

- Currently searches `CORPUS` (client-side). After integration, search should query a dedicated backend endpoint or use the full article catalog
- **Option A**: Add `GET /search?q=...` endpoint to backend (simple substring match over all 4860 articles)
- **Option B**: Keep client-side search but fetch the full catalog from the backend once at startup.
- **Recommended: Option A** — keeps the frontend lean and lets the backend do title matching across all 4860 articles

---

#### [MODIFY] [newsroom-content.jsx](file:///d:/e/software%20eng/news/news-website/src/newsroom-content.jsx)

- Update `ActionRow` to call `recordInteraction()` API when user likes/dislikes/saves
- Map frontend actions to backend actions: `like → click`, `dislike → skip`, `save → share`, `listen → dwell_long`, `read → click`
- Add `canonical_url` link to articles (the backend returns it)

---

### Component 3 — Vite Dev Proxy

#### [MODIFY] [vite.config.js](file:///d:/e/software%20eng/news/news-website/vite.config.js)

Add proxy to avoid CORS issues during development:

```js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

This lets the frontend call `/api/recommendations` which proxies to `localhost:8000/recommendations`.

---

## Open Questions

> [!IMPORTANT]
> **1. Does `title_embeddings.pkl` exist on your machine?** This is the pre-computed bi-encoder embeddings file (768-dim per article). If not, I'll need to create an offline encoding script using `bge-small-en-v1.5` to generate it from `google_news_5000.json`. This is a one-time ~2min job.

> [!IMPORTANT]
> **2. Should the backend persist between restarts?** Currently LinUCB bandit state resets on restart (by design — it re-learns fast). User profiles in `user_profiles/` persist via JSON. Is this acceptable or do you want bandit checkpoint auto-loading?

> [!IMPORTANT]  
> **3. Action mapping**: The frontend has `like, dislike, save, listen, read` interactions. The backend expects `click, skip, dwell_short, dwell_long, share`. How should we map them?
> 
> Proposed mapping:
> | Frontend Action | Backend Action | Reward |
> |---|---|---|
> | `read` (card click) | `click` | +1.0 |
> | `like` (thumbs up) | `dwell_long` | +2.0 |
> | `dislike` (thumbs down) | `skip` | −0.2 |
> | `save` (bookmark) | `share` | +3.0 |
> | `listen` (voice read) | `dwell_long` | +2.0 |

---

## Verification Plan

### Automated Tests

1. **Backend startup**: `python server.py` — verify model loads without errors, health endpoint returns 200
2. **Session flow**: `curl` test the 4 endpoints in sequence:
   ```bash
   # 1. Start session
   curl -X POST http://localhost:8000/session/start \
     -H "Content-Type: application/json" \
     -d '{"user_id":"test_user","mood":{"happy":0.5,"sad":0,"angry":0,"anxious":0,"calm":0.5,"curious":0.5},"location":"India","timestamp":"2026-04-19T03:00:00Z","archetype":"sci_tech"}'
   
   # 2. Get recommendations
   curl "http://localhost:8000/recommendations?user_id=test_user&session_id=<id>"
   
   # 3. Record interaction
   curl -X POST http://localhost:8000/interaction \
     -H "Content-Type: application/json" \
     -d '{"user_id":"test_user","session_id":"<id>","story_id":"123","action":"click","position":1}'
   
   # 4. Get updated recommendations (should differ from step 2)
   curl "http://localhost:8000/recommendations?user_id=test_user&session_id=<id>"
   ```
3. **Frontend integration**: Open browser, complete onboarding, verify:
   - Feed loads from backend (not the static JSON)
   - Clicking articles sends interactions to backend
   - Feed reranks after interactions
   - Analytics drawer shows backend-tracked data

### Manual Verification

1. Open `http://localhost:5173` in the browser
2. Complete onboarding → verify feed appears with real articles from backend
3. Interact with articles (like/dislike/save) → verify analytics drawer updates
4. Change mood sliders in Personalization Drawer → verify feed reranks
5. Verify the "Re-ranking feed…" animation plays during API calls
6. Check backend console for correct log output (interactions, slow loop, etc.)
