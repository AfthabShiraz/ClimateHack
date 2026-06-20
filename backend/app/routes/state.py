"""/state, /stream, /episode/* (README.md §7).

SSE is implemented with a plain StreamingResponse (text/event-stream) so the core has no hard
dependency on sse-starlette to boot. Swap to sse-starlette later if you want reconnection.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..config import settings
from ..models import State
from ..services.state import state_service

router = APIRouter()


@router.get("/state", response_model=State)
def get_state(
    horizon: str = Query("now"),
    exposure: str = Query("combined"),
) -> State:
    return state_service.build(horizon=horizon, exposure_key=exposure)


@router.get("/episode/start")
def episode_start(
    name: str = Query("pm25_spike"),
    horizon: str = Query("now"),
) -> dict:
    """Resolve the whole plume sequence up front; client walks the frames (README.md §1)."""
    frames = state_service.episode_frames(name=name, horizon=horizon)
    return {"name": name, "total": len(frames), "frames": [f.model_dump() for f in frames]}


@router.get("/episode/reset", response_model=State)
def episode_reset(horizon: str = Query("now")) -> State:
    return state_service.build(horizon=horizon)


@router.get("/stream")
async def stream(horizon: str = Query("now"), exposure: str = Query("combined")) -> StreamingResponse:
    """Heartbeat: emit a fresh /state each refresh tick (drives the TopBar heartbeat)."""

    async def gen():
        while True:
            state = state_service.build(horizon=horizon, exposure_key=exposure)
            yield f"data: {json.dumps(state.model_dump())}\n\n"
            await asyncio.sleep(max(2, settings.refresh_seconds))

    return StreamingResponse(gen(), media_type="text/event-stream")
