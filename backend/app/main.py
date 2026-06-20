"""Crosssight FastAPI app — wiring only. Architecture: backend/README.md.

Run:  cd backend && uvicorn app.main:app --reload --port 8000
The frontend points VITE_BACKEND_URL at this and consumes /state (+ SSE).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import agent, health, state

app = FastAPI(title="Crosssight Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),  # Vite dev origin only — no third-party CORS
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(state.router)
app.include_router(agent.router)


@app.get("/")
def root() -> dict:
    return {"service": "crosssight-backend", "docs": "/docs", "health": "/health"}
