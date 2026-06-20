"""Context assembly — pulls the RELEVANT slice for ONE hospital into a compact prompt.

This is the heart of "how do we give relevant context for a given location": instead of dumping
every dataset, we select only this catchment's drivers + their System-graph citations, its
Milliman vulnerability, its Apollo severity mix, and its demand gap. Reasoning and the brief
share the same assembled context so they stay consistent.
"""
from __future__ import annotations

from ..data_loader import Catchment
from ..engine import demand
from ..engine.risk import HospitalRisk
from ..providers.severity import severity_provider

SYSTEM_PROMPT = (
    "You are Crosssight's respiratory-readiness analyst for London hospital planners. "
    "You reason ONLY from the supplied evidence and numbers — never invent figures. "
    "The risk index is per-capita and relative (it orders pressure, it is not an admissions "
    "count). Air horizons are PROJECTIONS, not forecasts. Be concise, operational, and cite "
    "the evidence you used. You recommend preparation; a human decides and dispatches."
)


def hospital_context(c: Catchment, risk: HospitalRisk) -> str:
    sev = severity_provider.for_catchment(c)
    lines = [
        f"Hospital: {c.name} ({c.trust})",
        f"Roadside catchment: {c.roadside}",
        f"Respiratory Pressure Index (RPI): {risk.rpi}/100 -> band {risk.band.upper()}",
        f"Lead time to projected surge peak: ~{risk.leadTimeDays} days",
        f"Catchment vulnerability weight: x{c.vulnerabilityWeight:.2f} [Milliman SVI]",
        "Evidence drivers [System climate research graph]:",
    ]
    for d in risk.drivers:
        cite = f"{d.numStudies} studies, effect size {d.effectSize}" if d.numStudies else f"effect size {d.effectSize}"
        sub = " (replaces NO2->asthma for roadside)" if d.substituted else ""
        lines.append(f"  - {d.term}: contribution {d.contribution} ({cite}){sub}")
    lines += [
        f"Clinical severity mix [Apollo, simulated cohort]: "
        f"resp ward {sev.respWardPct}%, ICU {sev.icuPct}%, avg LOS {sev.avgLOS}d",
        f"Demand: projected {demand.projected_demand(c, risk.rpi)} resp. cases vs "
        f"{demand.surge_capacity(c)} surge beds (baseline {c.demandBaseline}) [simulated demand model]",
    ]
    return "\n".join(lines)


REASONING_USER = (
    "Walk through your reasoning step by step (6-8 short lines), as a live analyst log, then "
    "list 3 concrete preparation actions. Use only the context below.\n\n{context}"
)

ALERT_USER = (
    "Produce a Respiratory Readiness Alert brief for the on-call supervisor. Return JSON with "
    "keys: subject, situation, evidence (list of cited strings), projectedImpact, "
    "recommendedPreparation (list), sources (list). Use only the context below.\n\n{context}"
)
