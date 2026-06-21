"""ClimateEventInjector — the localised drifting plume (README.md §1, §6.2; plan.md §13.6/§13.14).

Applied at the INPUT layer only: it perturbs per-pollutant exposures on top of the baseline (live
or synthetic); the engine + agents downstream are identical for live vs simulated ("simulated
cause, real response"). Canonical version of the frontend's `exposureAt`/`PLUME`/`SEQUENCE`.

Three episodes, each targeting the right pollutant(s) so the correct canonical terms light up
(plan.md §13.6):
  - pm25_spike    — PM2.5 spike that co-elevates NO2 (real inversion episodes raise both).
  - heatwave      — drives the heat term city-wide.
  - no2_inversion — NO2 concentrated on roadside catchments (isolates the traffic-asthma term).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..data_loader import Catchment, catchment_by_id, load_catchments
from ..exposure_model import Exposure
from ..models import LngLat
from .exposure import baseline_exposure

# The plume drifts through these catchments in order (roughly W->E with the SW wind).
SEQUENCE = ["st-thomas", "kings-denmark-hill", "royal-london", "newham"]

# Gaussian plume: exposure rises at the centre, falls off with distance (degrees).
PLUME_MAGNITUDE = 0.9
PLUME_SIGMA_DEG = 0.025

# Which pollutants each episode perturbs (multiplied by the Gaussian magnitude at distance).
EPISODE_PROFILES: dict[str, dict[str, float]] = {
    "pm25_spike": {"pm25": 1.0, "no2": 0.7, "heat": 0.0},
    "heatwave": {"pm25": 0.0, "no2": 0.0, "heat": 1.0},
    "no2_inversion": {"pm25": 0.10, "no2": 1.0, "heat": 0.0},
}
_DEFAULT_EPISODE = "pm25_spike"

# Heatwave reads as a broad city-wide event, not a tight plume.
_EPISODE_SIGMA: dict[str, float] = {"heatwave": 0.12}

EPISODE_SEQUENCES: dict[str, list[str]] = {
    "pm25_spike": SEQUENCE,
    "no2_inversion": SEQUENCE,
    "heatwave": SEQUENCE,
}


@dataclass(frozen=True)
class Frame:
    """One authoritative step of an episode: the plume centre + perturbed exposures (combined)."""
    index: int
    center: LngLat
    exposures: dict[str, float]


def exposure_at(c: Catchment, center: LngLat | None, episode: str = _DEFAULT_EPISODE) -> Exposure:
    base = baseline_exposure(c)
    if center is None:
        return base
    sigma = _EPISODE_SIGMA.get(episode, PLUME_SIGMA_DEG)
    d = math.hypot(c.lat - center.lat, c.lon - center.lon)
    add = PLUME_MAGNITUDE * math.exp(-((d / sigma) ** 2))
    prof = EPISODE_PROFILES.get(episode, EPISODE_PROFILES[_DEFAULT_EPISODE])
    # NO2 inversion bites hardest on roadside catchments
    no2_gain = prof["no2"] * (1.2 if (episode == "no2_inversion" and c.roadside) else 1.0)
    return base.plus(pm25=add * prof["pm25"], no2=add * no2_gain, heat=add * prof["heat"])


def _center_of(cid: str) -> LngLat:
    c = catchment_by_id(cid)
    if c is None:
        raise KeyError(f"unknown hospital id in SEQUENCE: {cid}")
    return LngLat(lon=c.lon, lat=c.lat)


def exposures_for_center(center: LngLat | None, episode: str = _DEFAULT_EPISODE) -> dict[str, Exposure]:
    return {c.id: exposure_at(c, center, episode) for c in load_catchments()}


class ClimateEventInjector:
    """Resolves a whole episode up front so the client walks known frames (no live recompute)."""

    def resolve_episode(self, name: str = _DEFAULT_EPISODE) -> list[Frame]:
        seq = EPISODE_SEQUENCES.get(name, SEQUENCE)
        frames: list[Frame] = []
        for i, cid in enumerate(seq):
            center = _center_of(cid)
            exps = exposures_for_center(center, name)
            frames.append(Frame(index=i, center=center, exposures={k: round(v.combined, 3) for k, v in exps.items()}))
        return frames


injector = ClimateEventInjector()
