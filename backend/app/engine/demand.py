"""Demand layer (README.md §5; plan.md §13 demandModel). Never feeds RPI — RPI is per-capita.

projectedDemand = demandBaseline × (1 + demandSensitivity × rpi/100)
surgeCapacity   = demandBaseline × 1.6  (mirrors store.ts)
headroom        = capacity − projectedDemand
"""
from __future__ import annotations

from ..data_loader import Catchment, load_effect_sizes

SURGE_MULTIPLIER = 1.6


def demand_sensitivity() -> float:
    return float(load_effect_sizes()["demandModel"]["demandSensitivity"])


def projected_demand(c: Catchment, rpi: float) -> float:
    return round(c.demandBaseline * (1 + demand_sensitivity() * (rpi / 100.0)))


def surge_capacity(c: Catchment) -> float:
    return round(c.demandBaseline * SURGE_MULTIPLIER)


def headroom(c: Catchment, rpi: float) -> float:
    return round(c.capacity - projected_demand(c, rpi))
