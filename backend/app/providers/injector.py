"""ClimateEventInjector — the localised drifting plume (README.md §1, §6.2).

Applied at the INPUT layer only: it perturbs exposures; the engine + agents downstream are
identical for live vs simulated ("simulated cause, real response"). Canonical version of the
frontend's `exposureAt`/`PLUME`/`SEQUENCE` in store.ts — kept in sync so the two clocks agree.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..data_loader import Catchment, catchment_by_id, load_catchments
from ..models import LngLat
from .exposure import baseline_exposure

# The plume drifts through these catchments in order (roughly W->E with the SW wind).
SEQUENCE = ["st-thomas", "kings-denmark-hill", "royal-london", "newham"]

# Gaussian plume: exposure rises at the centre, falls off with distance (degrees).
PLUME_MAGNITUDE = 0.9
PLUME_SIGMA_DEG = 0.025


@dataclass(frozen=True)
class Frame:
    """One authoritative step of an episode: the plume centre + perturbed exposures."""
    index: int
    center: LngLat
    exposures: dict[str, float]


def exposure_at(c: Catchment, center: LngLat | None) -> float:
    if center is None:
        return baseline_exposure(c)
    d = math.hypot(c.lat - center.lat, c.lon - center.lon)
    add = PLUME_MAGNITUDE * math.exp(-((d / PLUME_SIGMA_DEG) ** 2))
    return max(0.0, min(1.0, baseline_exposure(c) + add))


def _center_of(cid: str) -> LngLat:
    c = catchment_by_id(cid)
    if c is None:
        raise KeyError(f"unknown hospital id in SEQUENCE: {cid}")
    return LngLat(lon=c.lon, lat=c.lat)


def exposures_for_center(center: LngLat | None) -> dict[str, float]:
    return {c.id: exposure_at(c, center) for c in load_catchments()}


class ClimateEventInjector:
    """Resolves a whole episode up front so the client walks known frames (no live recompute)."""

    sequences: dict[str, list[str]] = {"pm25_spike": SEQUENCE}

    def resolve_episode(self, name: str = "pm25_spike") -> list[Frame]:
        seq = self.sequences.get(name, SEQUENCE)
        frames: list[Frame] = []
        for i, cid in enumerate(seq):
            center = _center_of(cid)
            frames.append(Frame(index=i, center=center, exposures=exposures_for_center(center)))
        return frames


injector = ClimateEventInjector()
