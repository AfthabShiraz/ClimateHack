"""Agent ACT orchestration — supervisor alert + patient outreach (the demo climax).

Yields progress events for SSE; each step calls the same Gmail dispatch layer. Demo mode
routes both emails to DISPATCH_TO (zcabas5@ucl.ac.uk) so the inbox shows the full ACT story.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from ..config import settings
from ..data_loader import Catchment
from ..dispatch.email import send_alert
from ..engine.risk import HospitalRisk
from ..models import ActResult, ActStep, DispatchResult, PatientOutreach, ReadinessAlert
from . import alert as alert_agent
from . import outreach as outreach_agent


def _sse(event: str, payload: dict[str, Any]) -> str:
    if event == "message":
        return f"data: {json.dumps(payload)}\n\n"
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def run_act(
    c: Catchment,
    risk: HospitalRisk,
    *,
    demo_recipient: str | None = None,
) -> Iterator[str]:
    """SSE generator: draft → supervisor send → patient batch send → done."""
    recipient = demo_recipient or settings.dispatch_to

    yield _sse("message", {"phase": "drafting", "label": "Agent drafting readiness brief…"})
    readiness = alert_agent.draft(c, risk)

    yield _sse("message", {"phase": "drafting", "label": "Identifying high-risk patient cohort…"})
    outreach = outreach_agent.draft(c, risk)

    yield _sse("message", {
        "phase": "ready",
        "alert": readiness.model_dump(),
        "outreach": outreach.model_dump(),
        "recipient": recipient,
    })

    # --- Step 1: supervisor ---
    yield _sse("message", {
        "phase": "supervisor",
        "status": "sending",
        "label": f"Emailing hospital supervisor — {c.name}",
        "to": recipient,
    })
    sup = send_alert(
        to=recipient,
        subject=readiness.subject,
        body=readiness.bodyText,
        hospital_id=c.id,
        kind="supervisor",
    )
    yield _sse("message", {
        "phase": "supervisor",
        "status": "done",
        "result": sup.model_dump(),
    })

    # --- Step 2: patient outreach batch ---
    yield _sse("message", {
        "phase": "patients",
        "status": "sending",
        "label": f"Messaging {outreach.cohortSize:,} high-risk patients",
        "count": outreach.cohortSize,
        "to": recipient,
    })
    pat = send_alert(
        to=recipient,
        subject=outreach.subject,
        body=outreach.bodyText,
        hospital_id=c.id,
        kind="patients",
    )
    yield _sse("message", {
        "phase": "patients",
        "status": "done",
        "result": pat.model_dump(),
    })

    result = ActResult(
        ok=sup.ok and pat.ok,
        hospitalId=c.id,
        hospitalName=c.name,
        alert=readiness,
        outreach=outreach,
        steps=[
            ActStep(
                step="supervisor",
                label=f"Supervisor readiness alert → {sup.to}",
                ok=sup.ok,
                sentAt=sup.sentAt,
                to=sup.to,
                messageId=sup.messageId,
                dryRun=sup.dryRun,
                detail=sup.detail,
            ),
            ActStep(
                step="patients",
                label=f"Patient outreach ({outreach.cohortSize:,} contacts) → {pat.to}",
                ok=pat.ok,
                sentAt=pat.sentAt,
                to=pat.to,
                messageId=pat.messageId,
                dryRun=pat.dryRun,
                detail=pat.detail,
            ),
        ],
    )
    yield _sse("done", result.model_dump())
