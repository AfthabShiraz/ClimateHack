"""RiskEngine — deterministic, pure, no I/O (README.md §5; plan.md §13.1-§13.4).

Canonical RPI = 100 × clamp(rawScore / referenceRaw, 0, 1),
  rawScore = Σ over APPLICABLE canonical terms ( exposure × effectSize × vulnerabilityWeight ).
Applicable terms = pm25_respiratory (always) + (roadside_asthma if roadside else no2_asthma)
                   + heat_mortality. The roadside/non-roadside asthma terms are mutually
                   exclusive (the double-counting fix, plan.md §13.2).

B3: each canonical term is driven by its OWN bound feed via the per-pollutant `Exposure`
(pm25 → respiratory, no2/roadside → asthma, heat → mortality) so the heat term reflects
temperature, not the PM2.5 plume. A UKHSA Amber/Red alert boosts the heat term (plan.md §13.3).
A bare float is still accepted (broadcast across the summed pollutants) for back-compat/tests.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..data_loader import Catchment, load_effect_sizes
from ..exposure_model import Exposure
from ..models import Band, CurvePoint, Driver, Horizon

HORIZON_SCALE: dict[str, float] = {"now": 1.0, "3d": 1.18, "7d": 1.4}

# canonical term `exposure` key -> short topDriver code for the /state contract
_DRIVER_CODE: dict[str, str] = {"pm25": "pm25", "no2": "no2", "no2_roadside": "roadside", "heat": "heat"}


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
    def compute(
        self,
        c: Catchment,
        exposure: Exposure | float,
        horizon: Horizon = "now",
        ukhsa_level: str = "none",
    ) -> HospitalRisk:
        cfg = load_effect_sizes()
        exp = exposure if isinstance(exposure, Exposure) else Exposure.broadcast(float(exposure))
        vuln = c.vulnerabilityWeight
        ref = cfg["rpiCalibration"]["referenceRaw"]
        scale = HORIZON_SCALE.get(horizon, 1.0)
        heat_boost = float(cfg["exposureNormalization"]["ukhsaBoost"].get(ukhsa_level, 1.0))

        drivers: list[Driver] = []
        raw = 0.0
        for t in _applicable_terms(cfg, c.roadside):
            key = t.get("exposure", "")
            level = exp.for_term_key(key)
            if key == "heat":  # UKHSA Amber/Red boosts the heat term (plan.md §13.3)
                level = min(1.0, level * heat_boost)
            contribution = level * t["effectSize"] * vuln
            raw += contribution
            drivers.append(
                Driver(
                    term=t["term"],
                    exposureLevel=round(level, 3),
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
        if drivers:
            top_term = max(drivers, key=lambda d: d.contribution)
            top = _DRIVER_CODE.get(
                next((t["exposure"] for t in _applicable_terms(cfg, c.roadside) if t["term"] == top_term.term), ""),
                top_term.term,
            )
        else:
            top = ""
        curve, lead = _curve(rpi, cfg)
        return HospitalRisk(rpi=rpi, band=band, topDriver=top, leadTimeDays=lead,
                            drivers=drivers, curve=curve)


risk_engine = RiskEngine()
