"""ExposureProvider — per-catchment per-pollutant exposure (0..1), wind, UKHSA alert, source health.

Two paths behind the LIVE_DATA flag (plan.md §13.9, ARCHITECTURE.md §3.1/§3.4):

- LIVE_DATA=true  → fetch LAQN air (PM2.5/NO2/O3) + Met Office (temp→heat, wind) + UKHSA alert;
  join station points to each catchment centroid via inverse-distance weighting (k=3, power=2);
  ANY feed that fails falls back to the seeded synthetic generator for its pollutant and the
  mode honestly degrades LIVE → MIXED → SYNTHETIC.
- LIVE_DATA=false → fully seeded synthetic baseline (offline DEMO_MODE), reproducible from SEED.

One `snapshot()` is computed per refresh window (TTL = REFRESH_SECONDS) and the last good one is
kept so a transient upstream failure never blanks the map. The injector adds its plume ON TOP of
this baseline (live or synthetic) — "simulated cause, real response" (§13.14).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from ..config import settings
from ..data_loader import Catchment, load_catchments, load_effect_sizes
from ..exposure_model import Exposure
from ..models import Mode, Source, Station, UkhsaAlert, Wind
from .feeds import StationReading, ukhsa
from .feeds import laqn as laqn_feed
from .feeds import metoffice as metoffice_feed

_IDW_K = 3
_IDW_POWER = 2
_MAX_STATION_KM = 10.0


# ---- seeded synthetic baseline (mirrors store.ts so client/server agree pre-episode) ----

def _id_jitter(cid: str, mod: int) -> int:
    return (sum(ord(c) for c in cid) + settings.seed) % mod


def _synthetic_exposure(c: Catchment) -> Exposure:
    """Calm-day per-pollutant baseline. Roadside catchments carry more NO2; heat stays low."""
    base = 0.08 + (0.14 if c.roadside else 0.0) + _id_jitter(c.id, 17) * 0.008
    base = max(0.05, min(0.32, base))
    no2 = base * (1.25 if c.roadside else 0.9)
    o3 = base * 0.7
    heat = 0.03 + _id_jitter(c.id, 7) * 0.01  # below the 25°C gate on a calm day
    return Exposure(pm25=base, no2=no2, o3=o3, heat=heat).clamped()


# ---- geometry for the station -> catchment IDW join ----

def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular approximation — fine at London scale, cheap."""
    mlat = math.radians((lat1 + lat2) / 2)
    x = math.radians(lon2 - lon1) * math.cos(mlat)
    y = math.radians(lat2 - lat1)
    return 6371.0 * math.hypot(x, y)


def _idw(c: Catchment, stations: list[StationReading], attr: str) -> float | None:
    """Inverse-distance-weighted value of one pollutant at the catchment centroid (k=3, p=2)."""
    pts = [(s, _km(c.centroidLat, c.centroidLon, s.lat, s.lon)) for s in stations if getattr(s, attr) is not None]
    pts = [p for p in pts if p[1] <= _MAX_STATION_KM]
    if not pts:
        return None
    pts.sort(key=lambda p: p[1])
    pts = pts[:_IDW_K]
    num = den = 0.0
    for s, d in pts:
        w = 1.0 / max(d, 1e-3) ** _IDW_POWER
        num += w * float(getattr(s, attr))
        den += w
    return num / den if den else None


@dataclass
class Snapshot:
    exposures: dict[str, Exposure]
    wind: Wind
    sources: list[Source]
    mode: Mode
    ukhsa: UkhsaAlert
    air_stations: list[StationReading]
    ts: float


class ExposureProvider:
    def __init__(self) -> None:
        self._cache: Snapshot | None = None
        self._last_good: Snapshot | None = None

    # ---- public surface used by the rest of the backend ----

    def current(self) -> Snapshot:
        now = time.monotonic()
        if self._cache is not None and (now - self._cache.ts) < max(2, settings.refresh_seconds):
            return self._cache
        snap = self._build_live() if settings.live_data else self._build_synthetic()
        self._cache = snap
        if snap.mode != "SYNTHETIC":
            self._last_good = snap
        return snap

    def baseline_exposures(self) -> dict[str, Exposure]:
        return self.current().exposures

    def baseline_exposure_for(self, c: Catchment) -> Exposure:
        return self.current().exposures.get(c.id, _synthetic_exposure(c))

    def wind(self) -> Wind:
        return self.current().wind

    def sources(self) -> list[Source]:
        return self.current().sources

    def mode(self) -> Mode:
        return self.current().mode

    def ukhsa_alert(self) -> UkhsaAlert:
        return self.current().ukhsa

    def stations(self, exposures: dict[str, Exposure], pollutant: str = "combined") -> list[Station]:
        """Haze field points — one per catchment, coloured by the (possibly injected) frame value.

        Per-catchment points keep the plume dome and the column readings in agreement; the real
        LAQN site points feed the IDW upstream rather than the visual.
        """
        out: list[Station] = []
        sim = self.current().mode != "LIVE"
        for c in load_catchments():
            e = exposures.get(c.id, Exposure())
            value = e.combined if pollutant == "combined" else e.for_term_key(pollutant)
            out.append(
                Station(lat=c.lat, lon=c.lon, value=round(value, 3),
                        pollutant=pollutant, station=c.name, simulated=sim)
            )
        return out

    # ---- snapshot builders ----

    def _build_synthetic(self) -> Snapshot:
        exposures = {c.id: _synthetic_exposure(c) for c in load_catchments()}
        return Snapshot(
            exposures=exposures,
            wind=Wind(dirDeg=235, speedMs=4.2, simulated=True),
            sources=[
                Source(name="LAQN", status="down", simulated=True),
                Source(name="Met Office", status="down", simulated=True),
            ],
            mode="SYNTHETIC",
            ukhsa=UkhsaAlert(level="none"),
            air_stations=[],
            ts=time.monotonic(),
        )

    def _build_live(self) -> Snapshot:
        cfg = load_effect_sizes()
        gate = cfg["exposureNormalization"]["heatGate"]
        air = laqn_feed.fetch_air()
        wx = metoffice_feed.fetch_weather(heat_start_c=gate["startC"], heat_full_c=gate["fullC"])
        alert = ukhsa.fetch_alert()

        catchments = load_catchments()
        exposures: dict[str, Exposure] = {}
        for c in catchments:
            syn = _synthetic_exposure(c)
            pm25 = _idw(c, air.stations, "pm25") if air.health.ok else None
            no2 = _idw(c, air.stations, "no2") if air.health.ok else None
            o3 = _idw(c, air.stations, "o3") if air.health.ok else None
            heat = wx.heat if (wx.health.ok and wx.heat is not None) else None
            exposures[c.id] = Exposure(
                pm25=pm25 if pm25 is not None else syn.pm25,
                no2=no2 if no2 is not None else syn.no2,
                o3=o3 if o3 is not None else syn.o3,
                heat=heat if heat is not None else syn.heat,
            ).clamped()

        if wx.health.ok and wx.windDirDeg is not None:
            wind = Wind(dirDeg=wx.windDirDeg, speedMs=wx.windSpeedMs or 0.0, simulated=False)
        else:
            wind = Wind(dirDeg=235, speedMs=4.2, simulated=True)

        sources = [
            Source(name="LAQN", status=air.health.status, lastUpdated=air.health.lastUpdated,
                   simulated=not air.health.ok),
            Source(name="Met Office", status=wx.health.status, lastUpdated=wx.health.lastUpdated,
                   simulated=not wx.health.ok),
            Source(name="UKHSA", status=alert.health.status, lastUpdated=alert.health.lastUpdated,
                   simulated=not alert.health.ok),
        ]
        live_count = sum(1 for h in (air.health, wx.health) if h.ok)
        mode: Mode = "LIVE" if live_count == 2 else ("MIXED" if live_count == 1 else "SYNTHETIC")

        ukhsa_alert = UkhsaAlert(level=alert.level, type=alert.type) if alert.health.ok else UkhsaAlert(level="none")

        snap = Snapshot(
            exposures=exposures, wind=wind, sources=sources, mode=mode,
            ukhsa=ukhsa_alert, air_stations=air.stations, ts=time.monotonic(),
        )
        # serve last-good if this build degraded fully but we had a good one
        if mode == "SYNTHETIC" and self._last_good is not None:
            return self._last_good
        return snap


exposure_provider = ExposureProvider()


# ---- module-level helpers kept for back-compat (injector + agent route import these) ----

def baseline_exposure(c: Catchment) -> Exposure:
    return exposure_provider.baseline_exposure_for(c)
