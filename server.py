"""
server.py — FastAPI backend wrapping RLEnvironment.

Endpoints:
  POST /session/start       → create/update session context
  GET  /recommendations     → get ranked articles
  POST /interaction         → record user action (fast loop)
  GET  /search              → search articles by query
  GET  /health              → status check

Run:  python server.py   (or uvicorn server:app --reload)
"""

import uuid, time, json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── lazy-load heavy modules inside lifespan to control startup ────────────────

env = None          # RLEnvironment
pipeline = None     # NewsPipeline
ctx_store = None    # UserContextStore
bandit = None       # LinUCBBandit
slow_loop = None    # SlowLoop
_sessions = {}      # session_id → context dict
_interactions = {}  # user_id → list of recent interactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    global env, pipeline, ctx_store, bandit, slow_loop

    from news_pipeline import NewsPipeline
    from user_context import UserContextStore
    from bandits import LinUCBBandit
    from slow_loop import SlowLoop
    from rl_env import RLEnvironment

    pipeline = NewsPipeline()
    pipeline.load()

    ctx_store = UserContextStore()
    bandit = LinUCBBandit()
    slow_loop_obj = SlowLoop(ctx_store)
    slow_loop = slow_loop_obj

    env = RLEnvironment(pipeline, ctx_store, bandit)
    print(f"\nServer ready - {len(pipeline.get_articles())} articles loaded.\n")

    yield                       # app is running

    # shutdown: flush user profiles
    slow_loop_obj.run_once()
    print("Server shutdown — profiles flushed.")


app = FastAPI(title="NARC Engine API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    user_id: str
    mood: dict
    location: str = "India"
    archetype: str = "cold_start"
    timestamp: str | None = None

class InteractionRequest(BaseModel):
    user_id: str
    session_id: str
    story_id: str
    action: str                   # click, skip, dwell_short, dwell_long, share
    position: int = 1


# ── POST /session/start ───────────────────────────────────────────────────────

@app.post("/session/start")
async def session_start(req: SessionStartRequest):
    session_id = str(uuid.uuid4())
    ts = req.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _sessions[session_id] = {
        "user_id":   req.user_id,
        "mood":      req.mood,
        "location":  req.location,
        "archetype": req.archetype,
        "timestamp": ts,
    }
    return {"session_id": session_id, "status": "ok"}


# ── GET /recommendations ─────────────────────────────────────────────────────

@app.get("/recommendations")
async def recommendations(
    user_id: str = Query(...),
    session_id: str = Query(...),
    category: str | None = Query(None),
):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Unknown session_id")

    t0 = time.time()
    recs = env.get_recommendations(
        user_id=user_id,
        mood=session["mood"],
        location=session["location"],
        timestamp=session["timestamp"],
        archetype=session["archetype"],
        category=category,
    )
    latency = round(time.time() - t0, 3)

    return {
        "articles": recs,
        "latency_sec": latency,
        "session_id": session_id,
    }


# ── POST /interaction ─────────────────────────────────────────────────────────

@app.post("/interaction")
async def interaction(req: InteractionRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Unknown session_id")

    try:
        env.record_interaction(
            user_id=req.user_id,
            story_id=req.story_id,
            action=req.action,
            position=req.position,
            session_ctx=session,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))

    # Track for /logs
    if req.user_id not in _interactions:
        _interactions[req.user_id] = []
    _interactions[req.user_id].append({
        "story_id": req.story_id,
        "action": req.action,
        "position": req.position,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    # Keep last 200
    _interactions[req.user_id] = _interactions[req.user_id][-200:]

    return {"status": "ok", "action": req.action}


# ── GET /search ──────────────────────────────────────────────────────────────

@app.get("/search")
async def search(q: str = Query(..., min_length=2)):
    articles = pipeline.get_articles()
    q_low = q.lower()
    results = []
    for a in articles:
        if q_low in a.title.lower() or q_low in a.category.lower():
            raw = pipeline.get_raw(a.id)
            results.append({
                "story_id":  a.id,
                "title":     a.title,
                "category":  a.category,
                "freshness": round(a.freshness, 4),
                **raw,
            })
            if len(results) >= 10:
                break
    return {"results": results, "count": len(results)}


# ── GET /logs ────────────────────────────────────────────────────────────────

@app.get("/logs")
async def logs(user_id: str = Query(...)):
    return {"interactions": _interactions.get(user_id, [])}


# ── GET /health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "articles": len(pipeline.get_articles()) if pipeline else 0,
        "sessions": len(_sessions),
    }


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
