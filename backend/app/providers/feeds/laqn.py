"""London Air (LAQN, Imperial) — keyless open air-quality feed (ARCHITECTURE.md §3.1).

ONE call returns the latest hourly Air Quality Index for every London monitoring site, each with
its coordinates and per-species DAQI band. We map the DAQI index (1..10, a health-anchored scale)
to 0..1 — this avoids per-site fan-out and is already normalised against health bands, which is
exactly what plan.md §13.3 wants. PM2.5 / NO2 / O3 are extracted; everything else ignored.

Returns an AirResult with `health.status="down"` and no stations on any failure — the provider
then falls back to its seeded synthetic generator (mode -> MIXED/SYNTHETIC).
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import AirResult, FeedHealth, StationReading

LAQN_URL = "https://api.erg.ic.ac.uk/AirQuality/Hourly/MonitoringIndex/GroupName=London/Json"
_TIMEOUT_S = 8.0

# LAQN species codes -> our pollutant fields
_SPECIES = {"PM25": "pm25", "NO2": "no2", "O3": "o3"}


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _index_to_unit(raw: str | None) -> float | None:
    """DAQI air-quality index 1..10 -> 0..1. None/non-numeric -> None."""
    try:
        idx = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, idx / 10.0))


def _parse_site(site: dict) -> StationReading | None:
    try:
        lat = float(site["@Latitude"])
        lon = float(site["@Longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    name = site.get("@SiteName") or site.get("@SiteCode") or "LAQN site"
    vals: dict[str, float | None] = {"pm25": None, "no2": None, "o3": None}
    for sp in _as_list(site.get("Species")):
        field = _SPECIES.get(sp.get("@SpeciesCode", ""))
        if field:
            vals[field] = _index_to_unit(sp.get("@AirQualityIndex"))
    if all(v is None for v in vals.values()):
        return None
    return StationReading(site=name, lat=lat, lon=lon, pm25=vals["pm25"], no2=vals["no2"], o3=vals["o3"])


def fetch_air() -> AirResult:
    try:
        import httpx

        resp = httpx.get(LAQN_URL, timeout=_TIMEOUT_S, headers={"Accept": "application/json"})
        resp.raise_for_status()
        root = resp.json().get("HourlyAirQualityIndex", {})
    except Exception as e:  # never raise — degrade to synthetic
        return AirResult(stations=[], health=FeedHealth("LAQN", "down", error=str(e)[:200]))

    # structure: HourlyAirQualityIndex.LocalAuthority[].Site[] (LocalAuthority/Site may be single)
    stations: list[StationReading] = []
    for la in _as_list(root.get("LocalAuthority")):
        for site in _as_list(la.get("Site")):
            r = _parse_site(site)
            if r is not None:
                stations.append(r)

    if not stations:
        return AirResult(stations=[], health=FeedHealth("LAQN", "down", error="no usable LAQN sites"))

    return AirResult(
        stations=stations,
        health=FeedHealth("LAQN", "live", lastUpdated=datetime.now(timezone.utc).isoformat()),
    )
