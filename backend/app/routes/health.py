"""GET /health — liveness + per-source state + dispatch count (README.md §7)."""
from __future__ import annotations

from fastapi import APIRouter

from ..dispatch.audit import dispatch_count
from ..providers.exposure import exposure_provider
from ..providers.feeds.metoffice import budget_status

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "mode": exposure_provider.mode(),
        "sources": [s.model_dump() for s in exposure_provider.sources()],
        "alertsDispatched": dispatch_count(),
        "metofficeBudget": budget_status(),
    }
