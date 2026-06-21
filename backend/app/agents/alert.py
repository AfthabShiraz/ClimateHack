"""Respiratory Readiness Alert — the concrete agent-produced DELIVERABLE (README.md §6).

draft() returns a structured ReadinessAlert (situation, cited evidence, projected impact,
recommended preparation, sources) plus a rendered email-ready bodyText. Three provenance modes:
  - real claude-sonnet-4-6 call            (generatedBy="claude-sonnet-4-6")
  - pre-baked real output from data/alerts.json for DEMO_MODE   (generatedBy="pre-baked")  [B5]
  - templated fallback from engine values   (generatedBy="template-fallback")
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR, settings
from ..data_loader import Catchment
from ..engine import demand
from ..engine.risk import HospitalRisk
from ..models import ReadinessAlert
from .client import agent_client
from .prompts import ALERT_USER, SYSTEM_PROMPT, hospital_context


@lru_cache(maxsize=1)
def _prebaked() -> dict:
    """Committed real-Claude briefs keyed by hospitalId (data/alerts.json) for DEMO_MODE."""
    try:
        return json.loads((DATA_DIR / "alerts.json").read_text()).get("alerts", {})
    except Exception:
        return {}


def _render_body(a: dict, c: Catchment, risk: HospitalRisk) -> str:
    ev = "\n".join(f"  - {e}" for e in a["evidence"])
    prep = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(a["recommendedPreparation"]))
    src = ", ".join(a["sources"])
    return (
        f"RESPIRATORY READINESS ALERT — {c.name}\n"
        f"Severity: {risk.band.upper()} (RPI {risk.rpi}/100) · Lead time: ~{risk.leadTimeDays} days\n\n"
        f"SITUATION\n{a['situation']}\n\n"
        f"EVIDENCE\n{ev}\n\n"
        f"PROJECTED IMPACT\n{a['projectedImpact']}\n\n"
        f"RECOMMENDED PREPARATION\n{prep}\n\n"
        f"Sources: {src}\n"
        f"— Crosssight (decision support; a human approves and dispatches this alert)\n"
    )


def _template(c: Catchment, risk: HospitalRisk) -> dict:
    driver_cite = "29-study traffic-asthma evidence" if c.roadside else "13-study PM2.5 respiratory evidence"
    dem = demand.projected_demand(c, risk.rpi)
    surge = demand.surge_capacity(c)
    over = dem - surge
    return {
        "subject": f"[{risk.band.upper()}] Respiratory readiness — {c.name} (+{risk.leadTimeDays}d lead)",
        "situation": (
            f"A localised pollution episode is driving exposure across the {c.name} catchment. "
            f"Modelled respiratory pressure has reached RPI {risk.rpi}/100 ({risk.band}), with a "
            f"projected surge peak in roughly {risk.leadTimeDays} days."
        ),
        "evidence": [
            f"Top driver: {risk.topDriver} ({driver_cite}) [System climate research graph]",
            f"Catchment vulnerability x{c.vulnerabilityWeight:.2f} [Milliman SVI]",
        ],
        "projectedImpact": (
            f"Projected {dem} respiratory cases against {surge} surge beds"
            + (f" — a ~{over}-bed shortfall." if over > 0 else " — within surge capacity.")
        ),
        "recommendedPreparation": [
            "Pre-position oxygen and nebulisers" + (f" (≈{over}-bed shortfall projected)" if over > 0 else ""),
            "Add a respiratory-ward shift across the 5-7 day surge window",
            "Proactively contact high-risk COPD/asthma patients in the catchment",
        ],
        "sources": ["System climate research graph", "Milliman SVI", "Apollo COPD", "LAQN/Met Office"],
    }


def draft(c: Catchment, risk: HospitalRisk) -> ReadinessAlert:
    generated_by = "template-fallback"
    data: dict | None = None

    # DEMO_MODE: prefer the committed real-Claude brief so the climax never needs a live API call
    if settings.demo_mode:
        pb = _prebaked().get(c.id)
        if pb is not None:
            data = pb
            generated_by = "pre-baked"

    if data is None:
        user = ALERT_USER.format(context=hospital_context(c, risk))
        # the brief is a structured JSON object (~1.2-1.5k tokens); 1024 truncates it mid-object
        # and the parse fails, so give it room to close the braces.
        raw = agent_client.complete(SYSTEM_PROMPT, user, max_tokens=2048)
        if raw is not None:
            try:
                start, end = raw.find("{"), raw.rfind("}")
                data = json.loads(raw[start : end + 1])
                generated_by = "claude-sonnet-4-6"
            except Exception:
                data = None
    if data is None:
        data = _template(c, risk)

    return ReadinessAlert(
        hospitalId=c.id,
        hospitalName=c.name,
        severity=risk.band,
        leadTimeDays=risk.leadTimeDays,
        subject=data["subject"],
        situation=data["situation"],
        evidence=data["evidence"],
        projectedImpact=data["projectedImpact"],
        recommendedPreparation=data["recommendedPreparation"],
        sources=data["sources"],
        bodyText=_render_body(data, c, risk),
        generatedBy=generated_by,
    )
