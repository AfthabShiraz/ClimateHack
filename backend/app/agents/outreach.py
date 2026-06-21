"""Patient outreach — the second ACT step after the supervisor readiness alert.

Hospitals hold catchment patient lists in reality; here we derive a high-risk cohort size
from population × vulnerability and draft representative SMS-style contacts grounded in Apollo
COPD profiles. Demo delivery consolidates samples into one email to DISPATCH_TO.
"""
from __future__ import annotations

from ..data_loader import Catchment
from ..engine.risk import HospitalRisk
from ..models import OutreachMessage, PatientOutreach

# illustrative high-risk register: ~3× baseline respiratory demand, scaled by SVI
_COHORT_MULTIPLIER = 3.2


def high_risk_cohort_size(c: Catchment) -> int:
    return max(24, round(c.demandBaseline * _COHORT_MULTIPLIER * c.vulnerabilityWeight))


def _profiles(c: Catchment, risk: HospitalRisk) -> list[dict]:
    driver = "roadside traffic pollution" if c.roadside else "fine particulate (PM2.5) pollution"
    return [
        {
            "label": "Patient A — 78y, COPD + heart failure",
            "channel": "sms",
            "text": (
                f"NHS {c.name.split(' Hospital')[0]}: {driver.title()} is elevated in your area. "
                "If you have COPD, stay indoors where possible, keep your rescue inhaler accessible, "
                "and call 111 if breathing worsens. Your GP has your care plan."
            ),
        },
        {
            "label": "Patient B — 62y, severe asthma, roadside catchment",
            "channel": "sms",
            "text": (
                f"NHS alert: Air quality near {c.name} is high today. Asthma patients should avoid "
                "strenuous outdoor activity, carry your reliever inhaler, and use your preventer as "
                "prescribed. Peak strain expected in ~{days} days.".format(days=risk.leadTimeDays)
            ),
        },
        {
            "label": "Patient C — 71y, COPD (frequent attender)",
            "channel": "email",
            "text": (
                f"Dear patient, we are monitoring a respiratory pressure episode affecting your "
                f"catchment. Given your COPD history, please ensure you have 7 days of medication, "
                f"avoid {driver}, and contact the respiratory team if sputum changes colour or breathlessness "
                "increases at rest."
            ),
        },
    ]


def draft(c: Catchment, risk: HospitalRisk) -> PatientOutreach:
    cohort = high_risk_cohort_size(c)
    samples = _profiles(c, risk)
    messages = [
        OutreachMessage(patientLabel=s["label"], channel=s["channel"], preview=s["text"])  # type: ignore[arg-type]
        for s in samples
    ]

    blocks = []
    for i, s in enumerate(samples, 1):
        blocks.append(
            f"--- Message {i} of {len(samples)} (representative) ---\n"
            f"Profile: {s['label']}\n"
            f"Channel: {s['channel'].upper()}\n\n"
            f"{s['text']}\n"
        )

    body = (
        f"PATIENT OUTREACH BATCH — {c.name}\n"
        f"{'=' * 60}\n\n"
        f"Crosssight identified {cohort:,} high-risk respiratory patients in this catchment "
        f"(COPD/asthma registers × vulnerability weight {c.vulnerabilityWeight:.2f}).\n"
        f"Projected surge peak: ~{risk.leadTimeDays} days · RPI {risk.rpi}/100 ({risk.band}).\n\n"
        f"In production, each message routes individually via NHS SMS/email gateway using the "
        f"hospital patient registry. For this demo, representative samples are consolidated here.\n\n"
        + "\n".join(blocks)
        + f"\n— Crosssight patient outreach (human-approved ACT step)\n"
    )

    short = c.name.split(" Hospital")[0]
    subject = f"[Crosssight] Patient outreach — {short} — {cohort:,} high-risk contacts"

    return PatientOutreach(
        cohortSize=cohort,
        highRiskCount=cohort,
        messages=messages,
        subject=subject,
        bodyText=body,
    )
