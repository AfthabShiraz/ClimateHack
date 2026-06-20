"""Agent reasoning stream — powers the live thinking log (replaces ThinkingLog.tsx lines).

Streams tokens from claude-sonnet-4-6 when available; otherwise streams a TEMPLATED log built
from the SAME engine + dataset values (so the motion and the content survive an API outage).
The templated lines mirror the current frontend stand-in exactly.
"""
from __future__ import annotations

from collections.abc import Iterator

from ..data_loader import Catchment
from ..engine import demand
from ..engine.risk import HospitalRisk
from .client import agent_client
from .prompts import REASONING_USER, SYSTEM_PROMPT, hospital_context


def template_lines(c: Catchment, risk: HospitalRisk) -> list[str]:
    driver = "roadside NO2 (traffic)" if c.roadside else "fine particulates (PM2.5)"
    studies = 29 if c.roadside else 13
    dem = demand.projected_demand(c, risk.rpi)
    surge = demand.surge_capacity(c)
    return [
        f"Reading live exposure for {c.name}...",
        f"Local pollution {risk.drivers[0].exposureLevel * 100:.0f}% of health threshold -> driver: {driver}",
        f"Weighting by catchment vulnerability x{c.vulnerabilityWeight:.2f} [Milliman]",
        f"Matching evidence: {driver} -> respiratory, {studies} studies [System graph]",
        f"Projecting exposure->admission lag -> surge peak in ~{risk.leadTimeDays} days",
        f"Readiness gap: projected {dem} resp. cases vs {surge} surge beds",
        "Drafting preparation plan...",
    ]


def stream_reasoning(c: Catchment, risk: HospitalRisk) -> Iterator[str]:
    user = REASONING_USER.format(context=hospital_context(c, risk))
    live = agent_client.stream(SYSTEM_PROMPT, user)
    if live is not None:
        yield from live
        return
    # templated fallback — yield line by line so the typewriter still animates
    for line in template_lines(c, risk):
        yield line + "\n"
