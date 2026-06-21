"""StateService — assembles one authoritative /state snapshot (README.md §4, §5).

Orchestrates: exposure (live or injected) -> RiskEngine -> demand -> severity -> /state.
The plume `center` is the only thing that differs between the live frame and an episode frame;
everything downstream is identical ("simulated cause, real response").
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..data_loader import load_catchments
from ..engine import demand
from ..engine.risk import risk_engine
from ..exposure_model import Exposure
from ..models import (
    Episode, ExposureField, HospitalState, LngLat, Simulated, State,
)
from ..providers.exposure import exposure_provider
from ..providers.injector import EPISODE_SEQUENCES, SEQUENCE, exposures_for_center, injector
from ..providers.severity import severity_provider


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# last-good baseline snapshot, persisted so a cold start with a failed build still serves real data
_LAST_GOOD_PATH = Path(__file__).resolve().parents[2] / "last_good_state.json"


class StateService:
    def build(
        self,
        horizon: str = "now",
        exposure_key: str = "combined",
        center: LngLat | None = None,
        episode_name: str | None = None,
        episode_index: int = 0,
    ) -> State:
        catchments = load_catchments()
        ukhsa = exposure_provider.ukhsa_alert()

        # exposures: injected plume frame if a center is given, else live/baseline
        if center is not None:
            exposures = exposures_for_center(center, episode_name or "pm25_spike")
        else:
            exposures = exposure_provider.baseline_exposures()

        hospitals: list[HospitalState] = []
        for c in catchments:
            e = exposures.get(c.id, Exposure())
            r = risk_engine.compute(c, e, horizon, ukhsa_level=ukhsa.level)  # type: ignore[arg-type]
            hospitals.append(
                HospitalState(
                    id=c.id, name=c.name, trust=c.trust, lat=c.lat, lon=c.lon,
                    roadside=c.roadside, exposure=round(e.combined, 3),
                    rpi=r.rpi, band=r.band, topDriver=r.topDriver, leadTimeDays=r.leadTimeDays,
                    drivers=r.drivers, curve=r.curve,
                    vulnerabilityWeight=c.vulnerabilityWeight,
                    population=Simulated(value=c.population, method="GLA+Milliman areal interp"),
                    capacity=Simulated(value=c.capacity),
                    demandBaseline=Simulated(value=c.demandBaseline),
                    projectedDemand=Simulated(value=demand.projected_demand(c, r.rpi)),
                    surgeCapacity=Simulated(value=demand.surge_capacity(c)),
                    severityMix=severity_provider.for_catchment(c),
                )
            )

        episode = None
        if episode_name is not None:
            seq = EPISODE_SEQUENCES.get(episode_name, SEQUENCE)
            episode = Episode(
                active=True, name=episode_name, index=episode_index,
                total=len(seq), simulated=True, sequence=list(seq),
            )

        state = State(
            generatedAt=_now_iso(),
            mode=("MIXED" if episode_name else exposure_provider.mode()),
            horizon=horizon,  # type: ignore[arg-type]
            sources=exposure_provider.sources(),
            wind=exposure_provider.wind(),
            ukhsaAlert=ukhsa,
            episode=episode,
            exposureField=ExposureField(
                center=center, stations=exposure_provider.stations(exposures, exposure_key)
            ),
            hospitals=hospitals,
        )
        # persist the live/baseline frame as last-good (not episode frames — those are simulated)
        if center is None and episode_name is None and state.mode != "SYNTHETIC":
            self._persist(state)
        return state

    def build_safe(self, horizon: str = "now", exposure_key: str = "combined") -> State:
        """Route entry point: never raise. On any build failure serve the last-good disk snapshot."""
        try:
            return self.build(horizon=horizon, exposure_key=exposure_key)
        except Exception:
            last = self.last_good()
            if last is not None:
                for s in last.sources:
                    s.status = "stale"
                return last
            raise

    def _persist(self, state: State) -> None:
        try:
            _LAST_GOOD_PATH.write_text(json.dumps(state.model_dump()))
        except Exception:
            pass  # persistence is best-effort; never break a request over it

    def last_good(self) -> State | None:
        try:
            return State.model_validate(json.loads(_LAST_GOOD_PATH.read_text()))
        except Exception:
            return None

    def episode_frames(self, name: str = "pm25_spike", horizon: str = "now") -> list[State]:
        """Resolve a whole episode to a list of authoritative frames (README.md §1)."""
        frames = injector.resolve_episode(name)
        return [
            self.build(horizon=horizon, center=f.center, episode_name=name, episode_index=f.index)
            for f in frames
        ]


state_service = StateService()
