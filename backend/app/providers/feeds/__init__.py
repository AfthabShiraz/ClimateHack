"""Live data feeds (B3). Each fetcher is best-effort and NEVER raises:

on timeout / network error / parse failure it returns an empty result + a `down` FeedHealth, so
`ExposureProvider` can fall back to its seeded synthetic generator and report MIXED/SYNTHETIC
honestly. The browser never touches these — all external calls live behind FastAPI (README §0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FeedHealth:
    name: str
    status: str  # "live" | "stale" | "down"
    lastUpdated: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in ("live", "stale")


@dataclass(frozen=True)
class StationReading:
    """One air-monitoring site: pollutant values already normalised to 0..1 (or None if absent)."""

    site: str
    lat: float
    lon: float
    pm25: Optional[float] = None
    no2: Optional[float] = None
    o3: Optional[float] = None


@dataclass(frozen=True)
class AirResult:
    stations: list[StationReading] = field(default_factory=list)
    health: FeedHealth = field(default_factory=lambda: FeedHealth("LAQN", "down"))


@dataclass(frozen=True)
class WeatherResult:
    # heat already normalised 0..1 via the heat gate; tempC kept for display/provenance
    heat: Optional[float] = None
    tempC: Optional[float] = None
    windDirDeg: Optional[float] = None
    windSpeedMs: Optional[float] = None
    health: FeedHealth = field(default_factory=lambda: FeedHealth("Met Office", "down"))


@dataclass(frozen=True)
class AlertResult:
    level: str = "none"  # none | yellow | amber | red
    type: str = "heat"  # heat | cold
    health: FeedHealth = field(default_factory=lambda: FeedHealth("UKHSA", "down"))
