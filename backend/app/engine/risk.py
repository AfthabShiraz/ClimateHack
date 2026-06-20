"""RiskEngine — deterministic, pure, no I/O (README.md §5; plan.md §13.1-§13.4).

Canonical RPI = 100 × clamp(rawScore / referenceRaw, 0, 1),
  rawScore = Σ over APPLICABLE canonical terms ( exposure × effectSize × vulnerabilityWeight ).
Applicable terms = pm25_respiratory (always) + (roadside_asthma if roadside else no2_asthma)
                   + heat_mortality. The roadside/non-roadside asthma terms are mutually
                   exclusive (the double-counting fix, plan.md §13.2).

SCAFFOLD SIMPLIFICATION (B1): the injector supplies ONE combined exposure scalar per catchment,
applied across the applicable terms. B3 splits this into per-pollutant exposures (pm25 / no2 /
heat) from the live feeds so the heat term is driven by temperature, not the PM2.5 plume.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..data_loader import Catchment, load_effect_sizes
from ..models import Band, CurvePoint, Driver, Horizon

HORIZON_SCALE: dict[str, float] = {"now": 1.0, "3d": 1.18, "7d": 1.4}


@dataclass
class HospitalRisk:
    rpi: float
    band: Band
    topDriver: str
    leadTimeDays: int
    drivers: list[Driver]
    curve: list[CurvePoint]


def _applicable_terms(cfg: dict, roadside: bool) -> list[dict]:
    out = []
    for t in cfg["canonical"]:
        gate = t.get("gate")
        if gate == "non_roadside" and roadside:
            continue
        if gate == "roadside" and not roadside:
            continue
        out.append(t)
    return out


def band_for_rpi(rpi: float, cfg: dict) -> Band:
    g0, g1 = cfg["bands"]["green"]
    a0, a1 = cfg["bands"]["amber"]
    if rpi < g1:
        return "green"
    if rpi < a1:
        return "amber"
    return "red"


def _curve(rpi: float, cfg: dict) -> tuple[list[CurvePoint], int]:
    """Project the lag kernel forward into a 0-7 day pressure curve.

    Scaffold: persistence of today's RPI shaped by the lag kernel (peak normalised to rpi).
    leadTimeDays = the peak day of that curve (the preparation window the badge shows).
    """
    weights = cfg["lagKernel"]["weights"]
    peak = max(weights.values()) or 1.0
    pts: list[CurvePoint] = []
    for d in range(8):
        w = weights.get(str(d), 0.0)
        pts.append(CurvePoint(dayOffset=d, rpi=round(rpi * w / peak, 1)))
    lead = max(range(8), key=lambda d: weights.get(str(d), 0.0))
    return pts, lead


class RiskEngine:
    def compute(self, c: Catchment, exposure: float, horizon: Horizon = "now") -> HospitalRisk:
        cfg = load_effect_sizes()
        vuln = c.vulnerabilityWeight
        ref = cfg["rpiCalibration"]["referenceRaw"]
        scale = HORIZON_SCALE.get(horizon, 1.0)

        drivers: list[Driver] = []
        raw = 0.0
        for t in _applicable_terms(cfg, c.roadside):
            contribution = exposure * t["effectSize"] * vuln
            raw += contribution
            drivers.append(
                Driver(
                    term=t["term"],
                    exposureLevel=round(exposure, 3),
                    effectSize=t["effectSize"],
                    numStudies=t.get("numStudies"),
                    highestCited=t.get("highestCited"),
                    sourceRowId=t.get("sourceRowId"),
                    substituted=(t.get("gate") == "roadside"),  # roadside term replaces no2_asthma
                    vulnerabilityWeight=vuln,
                    contribution=round(contribution, 4),
                )
            )

        rpi = max(0.0, min(100.0, 100.0 * (raw / ref) * scale))
        rpi = round(rpi, 1)
        band = band_for_rpi(rpi, cfg)
        top = max(drivers, key=lambda d: d.contribution).term if drivers else ""
        curve, lead = _curve(rpi, cfg)
        return HospitalRisk(rpi=rpi, band=band, topDriver=top, leadTimeDays=lead,
                            drivers=drivers, curve=curve)


risk_engine = RiskEngine()
