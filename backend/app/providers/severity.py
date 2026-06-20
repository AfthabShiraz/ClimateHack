"""SeverityProvider — Apollo COPD clinical texture per hospital (NOT a predictor).

SCAFFOLD STATE: deterministic synthetic mix nudged by vulnerability/roadside, tagged
simulated. B-phase: derive from real Apollo COPD severity profiles joined to the catchment.
"""
from __future__ import annotations

from ..data_loader import Catchment
from ..models import SeverityMix


class SeverityProvider:
    def for_catchment(self, c: Catchment) -> SeverityMix:
        resp = 38.0 + (5.0 if c.roadside else 0.0) + (c.vulnerabilityWeight - 1.0) * 8.0
        resp = max(30.0, min(48.0, resp))
        icu = 6.0 + (c.vulnerabilityWeight - 1.0) * 4.0
        icu = max(4.0, min(12.0, icu))
        general = max(0.0, 100.0 - resp - icu)
        los = 6.0 + (c.vulnerabilityWeight - 1.0) * 2.5
        return SeverityMix(
            respWardPct=round(resp, 1),
            generalPct=round(general, 1),
            icuPct=round(icu, 1),
            avgLOS=round(los, 1),
            simulated=True,
        )


severity_provider = SeverityProvider()
