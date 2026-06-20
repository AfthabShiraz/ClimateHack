"""ExposureProvider — per-catchment exposure (0..1), wind, source health.

SCAFFOLD STATE (B1): returns a seeded synthetic baseline that mirrors
frontend/src/state/store.ts `baselineExposure`. No live feeds yet.

B3 (build properly): poll LAQN/DEFRA (air) + Met Office (heat+wind) + UKHSA (alert),
join station readings -> catchment centroids via IDW (k=3, power=2), fall back to this
synthetic generator per-source when a feed is down (=> mode MIXED/SYNTHETIC).
"""
from __future__ import annotations

from ..config import settings
from ..data_loader import Catchment, load_catchments
from ..models import Mode, Source, Station, Wind


def _id_jitter(cid: str, mod: int) -> int:
    return sum(ord(c) for c in cid) % mod


def baseline_exposure(c: Catchment) -> float:
    """Calm-day exposure. Mirrors store.ts so client and server agree pre-episode."""
    base = 0.08 + (0.14 if c.roadside else 0.0) + _id_jitter(c.id, 17) * 0.008
    return max(0.05, min(0.32, base))


class ExposureProvider:
    def baseline_exposures(self) -> dict[str, float]:
        return {c.id: baseline_exposure(c) for c in load_catchments()}

    def wind(self) -> Wind:
        # B3: Met Office wind_deg / wind_speed. Synthetic SW breeze for now.
        return Wind(dirDeg=235, speedMs=4.2, simulated=not settings.live_data)

    def stations(self, exposures: dict[str, float], pollutant: str = "combined") -> list[Station]:
        # B3: real LAQN station points. Stand-in: one point per catchment.
        out: list[Station] = []
        for c in load_catchments():
            out.append(
                Station(
                    lat=c.lat, lon=c.lon, value=exposures.get(c.id, 0.0),
                    pollutant=pollutant, station=c.name, simulated=not settings.live_data,
                )
            )
        return out

    def sources(self) -> list[Source]:
        status = "live" if settings.live_data else "down"
        sim = not settings.live_data
        return [
            Source(name="LAQN", status=status, simulated=sim),
            Source(name="Met Office", status=status, simulated=sim),
        ]

    def mode(self) -> Mode:
        # B3: LIVE if all feeds live, MIXED if some fell back, else SYNTHETIC.
        return "LIVE" if settings.live_data else "SYNTHETIC"


exposure_provider = ExposureProvider()
