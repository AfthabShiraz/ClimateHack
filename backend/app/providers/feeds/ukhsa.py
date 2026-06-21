"""UKHSA Weather-Health Alerts — the official heat/cold alert level for London (plan.md §13.3).

Surfaced in the F8 banner and used to BOOST the heat term (amber ×1.15 / red ×1.30). There is no
stable keyless JSON contract for the alerts dashboard, so this is best-effort: only attempted when
LIVE_DATA is on, and any failure returns level "none" with `down` health (no boost, no banner) —
never an exception. Wire a confirmed endpoint here when one is available.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ...config import settings
from . import AlertResult, FeedHealth

_TIMEOUT_S = 6.0
# Placeholder for a confirmed UKHSA alerts JSON endpoint (dashboard API not stable/keyless yet).
_URL = ""

_LEVELS = {"none", "yellow", "amber", "red"}


def fetch_alert() -> AlertResult:
    if not settings.live_data or not _URL:
        return AlertResult(level="none", health=FeedHealth("UKHSA", "down", error="no UKHSA endpoint configured"))
    try:
        import httpx

        resp = httpx.get(_URL, timeout=_TIMEOUT_S, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        level = str(data.get("level", "none")).lower()
        if level not in _LEVELS:
            level = "none"
        atype = str(data.get("type", "heat")).lower()
        atype = atype if atype in ("heat", "cold") else "heat"
    except Exception as e:
        return AlertResult(level="none", health=FeedHealth("UKHSA", "down", error=str(e)[:200]))

    return AlertResult(
        level=level,
        type=atype,
        health=FeedHealth("UKHSA", "live", lastUpdated=datetime.now(timezone.utc).isoformat()),
    )
