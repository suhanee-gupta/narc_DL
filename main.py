"""
Hyper-Personalization Engine for Content Recommendation
HCL Hack60 - Problem Statement #10

Walking Skeleton Backend — plug in real encoders/RL models later.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.registry import ArtifactRegistry
from app.api import recommendations, feedback, health, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load all artifacts. Shutdown: flush pending state."""
    print("🚀 Initializing Artifact Registry...")
    registry = ArtifactRegistry.get_instance()
    await registry.initialize()
    print("✅ Registry ready. All modules loaded.")
    yield
    print("🛑 Shutting down. Flushing state...")
    await registry.shutdown()


app = FastAPI(
    title="Hyper-Personalization Engine",
    description=(
        "HCL Hack60 — Problem #10. "
        "Modular pipeline: Context Aggregation → State Encoding → "
        "Candidate Retrieval → RL Ranking → Feedback Loop."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
app.include_router(health.router,           tags=["Health"])
app.include_router(users.router,            prefix="/users",           tags=["Users"])
app.include_router(recommendations.router,  prefix="/recommend",       tags=["Recommendations"])
app.include_router(feedback.router,         prefix="/feedback",        tags=["Feedback"])