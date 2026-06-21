"""Per-pollutant exposure value object (B3).

The scaffold (B1) passed a single combined scalar per catchment, which forced the heat term to
be driven by the PM2.5 plume. B3 carries pm25 / no2 / o3 / heat separately (each normalised 0..1
against absolute health thresholds, plan.md §13.3) so the engine drives each canonical term from
its OWN bound feed: PM2.5→respiratory from PM2.5, NO2/roadside→asthma from NO2, heat→mortality
from temperature. O3 is visual-only and never summed (plan.md §13.2/§13.7).

Kept dependency-light (no pydantic / data_loader import) so both providers and the engine can use
it without circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


# canonical-term `exposure` key (effect_sizes.json) -> Exposure field
_TERM_EXPOSURE_FIELD: dict[str, str] = {
    "pm25": "pm25",
    "no2": "no2",
    "no2_roadside": "no2",
    "o3": "o3",
    "heat": "heat",
}


@dataclass(frozen=True)
class Exposure:
    """Normalised (0..1) exposure per pollutant for one catchment at one frame."""

    pm25: float = 0.0
    no2: float = 0.0
    o3: float = 0.0
    heat: float = 0.0

    def for_term_key(self, key: str) -> float:
        """Exposure value a canonical term should use, by its `exposure` key."""
        return getattr(self, _TERM_EXPOSURE_FIELD.get(key, key), 0.0)

    @property
    def combined(self) -> float:
        """Representative intensity for the plume/haze visual + the `exposure` scalar in /state.

        Max of the *summed* pollutants (o3 is visual-only, excluded) so the dome reads the worst
        driver at that point — what actually moves the band.
        """
        return max(self.pm25, self.no2, self.heat)

    def clamped(self) -> "Exposure":
        return Exposure(_clamp01(self.pm25), _clamp01(self.no2), _clamp01(self.o3), _clamp01(self.heat))

    def plus(self, *, pm25: float = 0.0, no2: float = 0.0, o3: float = 0.0, heat: float = 0.0) -> "Exposure":
        return Exposure(self.pm25 + pm25, self.no2 + no2, self.o3 + o3, self.heat + heat).clamped()

    @classmethod
    def broadcast(cls, scalar: float) -> "Exposure":
        """Back-compat: treat a single scalar as the same level across summed pollutants.

        Heat is intentionally left at 0 — a pollution scalar must not light up the heat term.
        """
        return cls(pm25=scalar, no2=scalar, o3=scalar, heat=0.0).clamped()
