"""Agent endpoints — reasoning stream, brief draft, and the human-approved dispatch (README §6,§7)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..agents import alert as alert_agent
from ..agents.reasoning import stream_reasoning
from ..data_loader import catchment_by_id
from ..dispatch.email import send_alert
from ..engine.risk import risk_engine
from ..models import (
    AlertDraftRequest, DispatchRequest, DispatchResult, LngLat, ReadinessAlert,
)
from ..providers.exposure import baseline_exposure
from ..providers.injector import exposure_at

router = APIRouter()


def _risk_for(hospital_id: str, horizon: str, center: LngLat | None):
    c = catchment_by_id(hospital_id)
    if c is None:
        raise HTTPException(404, f"unknown hospital: {hospital_id}")
    exposure = exposure_at(c, center) if center else baseline_exposure(c)
    return c, risk_engine.compute(c, exposure, horizon)  # type: ignore[arg-type]


@router.get("/agent/stream")
def agent_stream(
    hospitalId: str = Query(...),
    horizon: str = Query("now"),
    centerLon: float | None = Query(None),
    centerLat: float | None = Query(None),
) -> StreamingResponse:
    """SSE token stream for the live thinking log (claude-sonnet-4-6, templated fallback)."""
    center = LngLat(lon=centerLon, lat=centerLat) if centerLon is not None and centerLat is not None else None
    c, risk = _risk_for(hospitalId, horizon, center)

    def gen():
        for token in stream_reasoning(c, risk):
            yield f"data: {token}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/alert/draft", response_model=ReadinessAlert)
def alert_draft(req: AlertDraftRequest) -> ReadinessAlert:
    """Agent drafts the Respiratory Readiness Alert (the deliverable). Does NOT send."""
    center = (
        LngLat(lon=req.centerLon, lat=req.centerLat)
        if req.centerLon is not None and req.centerLat is not None
        else None
    )
    c, risk = _risk_for(req.hospitalId, req.horizon, center)
    return alert_agent.draft(c, risk)


@router.post("/alert/dispatch", response_model=DispatchResult)
def alert_dispatch(req: DispatchRequest) -> DispatchResult:
    """The ACT step — human-approved send. Dry-runs unless DISPATCH_ENABLED + creds are set."""
    return send_alert(to=req.to, subject=req.subject, body=req.body, hospital_id=req.hospitalId)
