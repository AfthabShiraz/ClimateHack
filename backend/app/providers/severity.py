"""SeverityProvider — COPD clinical texture per hospital, derived from the REAL Apollo dataset.

Loads data/apollo_severity.json (built by data/scripts/build_severity.py from the 70,383 Apollo
COPD encounters) which holds two AGE-stratified anchor profiles — "low" (<65) and "high" (65+).
At runtime we interpolate between these real profiles by each catchment's vulnerabilityWeight, so
a more-vulnerable catchment reads higher respiratory-ward demand, more ICU, and longer LOS — the
relationship that actually exists in the data. Apollo is synthetic, so output stays tagged
`simulated` and is NEVER presented as a climate/admissions predictor (plan.md §0).
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR
from ..data_loader import Catchment
from ..models import SeverityMix

# Fallback anchors (the build-script output) if the JSON is absent — keeps the app booting.
_FALLBACK = {
    "vwMin": 0.85, "vwMax": 1.40,
    "anchors": {
        "low": {"respWardPct": 40.6, "icuPct": 4.1, "avgLOS": 4.3},
        "high": {"respWardPct": 51.5, "icuPct": 4.5, "avgLOS": 5.3},
    },
}


@lru_cache(maxsize=1)
def _profiles() -> dict:
    path = DATA_DIR / "apollo_severity.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return _FALLBACK


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class SeverityProvider:
    def for_catchment(self, c: Catchment) -> SeverityMix:
        p = _profiles()
        lo, hi = p["anchors"]["low"], p["anchors"]["high"]
        vw_min, vw_max = float(p.get("vwMin", 0.85)), float(p.get("vwMax", 1.40))
        t = max(0.0, min(1.0, (c.vulnerabilityWeight - vw_min) / max(1e-6, vw_max - vw_min)))

        resp = _lerp(lo["respWardPct"], hi["respWardPct"], t)
        icu = _lerp(lo["icuPct"], hi["icuPct"], t)
        los = _lerp(lo["avgLOS"], hi["avgLOS"], t)
        general = max(0.0, 100.0 - resp - icu)
        return SeverityMix(
            respWardPct=round(resp, 1),
            generalPct=round(general, 1),
            icuPct=round(icu, 1),
            avgLOS=round(los, 1),
            simulated=True,
        )


severity_provider = SeverityProvider()
