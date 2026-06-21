"""Met Office — temperature (heat term) + wind (drives the haze drift) (ARCHITECTURE.md §3.1).

Met Office Site-Specific DataHub needs an API key, so with no key this returns `down` and the
provider supplies a synthetic SW breeze + calm heat. With a key it pulls the hourly spot forecast
for a central-London point, reads current temperature + wind, and normalises temperature through
the J-shaped heat gate (0 below startC, 1 at fullC) from effect_sizes.json (plan.md §13.3).

City-level wind is enough for F24. Best-effort: any failure -> `down`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ...config import settings
from . import FeedHealth, WeatherResult

# central London (Westminster-ish) — city-level temp + wind is sufficient (ARCHITECTURE §3.1)
_LON, _LAT = -0.118, 51.498
_TIMEOUT_S = 8.0
# Met Office DataHub Site-Specific (Global Spot) hourly point forecast
_URL = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly"

# Persistent daily call budget — survives restarts (--reload), file-locked across processes, so
# the free-tier 360/day cap can NEVER be exceeded. When exhausted we return `down` and the
# provider falls back to last-good/synthetic heat+wind (mode -> MIXED). See settings.metoffice_daily_cap.
_BUDGET_PATH = Path(__file__).resolve().parents[3] / ".metoffice_budget.json"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _reserve_call() -> tuple[bool, int]:
    """Atomically reserve one call against today's budget. Returns (allowed, used_after)."""
    cap = settings.metoffice_daily_cap
    try:
        import fcntl

        _BUDGET_PATH.touch(exist_ok=True)
        with _BUDGET_PATH.open("r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                raw = f.read().strip()
                data = json.loads(raw) if raw else {}
                if data.get("date") != _today():
                    data = {"date": _today(), "count": 0}
                if data["count"] >= cap:
                    return False, data["count"]
                data["count"] += 1
                f.seek(0)
                f.truncate()
                f.write(json.dumps(data))
                return True, data["count"]
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        # if the budget file is unusable, fail SAFE (don't call) so we can't overrun the cap
        return False, cap


def budget_status() -> dict:
    try:
        raw = _BUDGET_PATH.read_text().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}
    used = data.get("count", 0) if data.get("date") == _today() else 0
    cap = settings.metoffice_daily_cap
    return {"date": _today(), "used": used, "cap": cap, "remaining": max(0, cap - used)}


def _heat_unit(temp_c: float, start_c: float, full_c: float) -> float:
    if temp_c <= start_c:
        return 0.0
    return max(0.0, min(1.0, (temp_c - start_c) / max(1e-6, full_c - start_c)))


def fetch_weather(heat_start_c: float = 25.0, heat_full_c: float = 32.0) -> WeatherResult:
    key = settings.metoffice_api_key
    if not key:
        return WeatherResult(health=FeedHealth("Met Office", "down", error="no METOFFICE_API_KEY"))

    allowed, used = _reserve_call()
    if not allowed:
        return WeatherResult(
            health=FeedHealth("Met Office", "down", error=f"daily budget reached ({used}/{settings.metoffice_daily_cap})")
        )

    try:
        import httpx

        resp = httpx.get(
            _URL,
            params={"latitude": _LAT, "longitude": _LON, "dataSource": "BD1"},
            headers={"apikey": key, "Accept": "application/json"},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        # GeoJSON: features[0].properties.timeSeries[] — take the first (current) step
        ts = data["features"][0]["properties"]["timeSeries"][0]
        temp_c = float(ts.get("screenTemperature"))
        wind_dir = float(ts.get("windDirectionFrom10m", 235))
        wind_ms = float(ts.get("windSpeed10m", 4.0))
    except Exception as e:
        return WeatherResult(health=FeedHealth("Met Office", "down", error=str(e)[:200]))

    return WeatherResult(
        heat=_heat_unit(temp_c, heat_start_c, heat_full_c),
        tempC=round(temp_c, 1),
        windDirDeg=wind_dir,
        windSpeedMs=wind_ms,
        health=FeedHealth("Met Office", "live", lastUpdated=datetime.now(timezone.utc).isoformat()),
    )
