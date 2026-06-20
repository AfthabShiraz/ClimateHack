"""Loads & exposes the build-time JSON artifacts once at startup.

../data/catchments.json   — 27 London hospitals (geometry, vulnerability, capacity)
../data/effect_sizes.json — canonical non-overlapping effect-size terms + bands + calibration
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .config import DATA_DIR


@dataclass(frozen=True)
class Catchment:
    id: str
    name: str
    trust: str
    lat: float
    lon: float
    roadside: bool
    vulnerabilityWeight: float
    population: float
    capacity: float
    demandBaseline: float


def _num(v: Any) -> float:
    """Accept either a bare number or a {"value": n, ...} wrapper."""
    if isinstance(v, dict):
        return float(v.get("value", 0))
    return float(v)


@lru_cache(maxsize=1)
def load_catchments() -> list[Catchment]:
    raw = json.loads((DATA_DIR / "catchments.json").read_text())
    out: list[Catchment] = []
    for h in raw["hospitals"]:
        out.append(
            Catchment(
                id=h["id"],
                name=h["name"],
                trust=h["trust"],
                lat=float(h["lat"]),
                lon=float(h["lon"]),
                roadside=bool(h.get("roadside", False)),
                vulnerabilityWeight=float(h["vulnerabilityWeight"]),
                population=_num(h.get("population", 0)),
                capacity=_num(h.get("capacity", 0)),
                demandBaseline=_num(h.get("illustrativeDemandBaseline", 0)),
            )
        )
    return out


@lru_cache(maxsize=1)
def load_effect_sizes() -> dict[str, Any]:
    return json.loads((DATA_DIR / "effect_sizes.json").read_text())


def catchment_by_id(cid: str) -> Catchment | None:
    return next((c for c in load_catchments() if c.id == cid), None)
