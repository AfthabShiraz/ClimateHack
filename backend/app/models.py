"""Pydantic models for the /state contract and agent/dispatch bodies (README.md §4, §7).

Single source of schema truth shared by every route. Field names mirror
frontend/src/state/store.ts so swapping client-computed -> backend-served is mechanical.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Band = Literal["green", "amber", "red"]
Horizon = Literal["now", "3d", "7d"]
Mode = Literal["LIVE", "SYNTHETIC", "MIXED"]


class Simulated(BaseModel):
    value: float
    simulated: bool = True
    method: Optional[str] = None


class LngLat(BaseModel):
    lon: float
    lat: float


class Source(BaseModel):
    name: str
    status: Literal["live", "stale", "down"]
    lastUpdated: Optional[str] = None
    simulated: bool = False


class Wind(BaseModel):
    dirDeg: float
    speedMs: float
    simulated: bool = False


class UkhsaAlert(BaseModel):
    level: Literal["none", "yellow", "amber", "red"] = "none"
    type: Literal["heat", "cold"] = "heat"
    source: str = "UKHSA"


class Episode(BaseModel):
    active: bool
    name: Optional[str] = None
    index: int = 0
    total: int = 0
    simulated: bool = True
    sequence: list[str] = []


class Station(BaseModel):
    lat: float
    lon: float
    value: float
    pollutant: str
    station: str
    simulated: bool = False


class ExposureField(BaseModel):
    center: Optional[LngLat] = None  # plume epicentre for this frame (None when live)
    stations: list[Station] = []


class Driver(BaseModel):
    term: str
    exposureLevel: float
    effectSize: float
    numStudies: Optional[int] = None
    highestCited: Optional[int] = None  # System graph `highest_cited` (citation count of top study)
    sourceRowId: Optional[str] = None
    substituted: bool = False
    vulnerabilityWeight: float
    contribution: float


class CurvePoint(BaseModel):
    dayOffset: int
    rpi: float


class SeverityMix(BaseModel):
    respWardPct: float
    generalPct: float
    icuPct: float
    avgLOS: float
    simulated: bool = True


class HospitalState(BaseModel):
    id: str
    name: str
    trust: str
    lat: float
    lon: float
    roadside: bool
    exposure: float
    rpi: float
    band: Band
    topDriver: str
    leadTimeDays: int
    drivers: list[Driver]
    curve: list[CurvePoint]
    vulnerabilityWeight: float
    population: Simulated
    capacity: Simulated
    demandBaseline: Simulated
    projectedDemand: Simulated
    surgeCapacity: Simulated
    severityMix: SeverityMix


class State(BaseModel):
    generatedAt: str
    mode: Mode
    horizon: Horizon
    sources: list[Source]
    wind: Wind
    ukhsaAlert: UkhsaAlert
    episode: Optional[Episode] = None
    exposureField: ExposureField
    hospitals: list[HospitalState]


# ---- agent / dispatch bodies (README.md §7) ----

class AlertDraftRequest(BaseModel):
    hospitalId: str
    horizon: Horizon = "now"
    episode: Optional[str] = None
    # optional plume centre so the brief reflects the current frame, not just baseline
    centerLon: Optional[float] = None
    centerLat: Optional[float] = None


class ReadinessAlert(BaseModel):
    hospitalId: str
    hospitalName: str
    severity: Band
    leadTimeDays: int
    subject: str
    situation: str
    evidence: list[str]
    projectedImpact: str
    recommendedPreparation: list[str]
    sources: list[str]
    bodyText: str  # rendered, ready to email
    generatedBy: str  # "claude-sonnet-4-6" | "template-fallback" | "pre-baked"


class DispatchRequest(BaseModel):
    hospitalId: str
    to: Optional[str] = None  # defaults to settings.dispatch_to
    subject: str
    body: str


class DispatchResult(BaseModel):
    ok: bool
    sentAt: str
    to: str
    messageId: Optional[str] = None
    dryRun: bool = False
    detail: Optional[str] = None


class OutreachMessage(BaseModel):
    patientLabel: str
    channel: Literal["sms", "email"]
    preview: str


class PatientOutreach(BaseModel):
    cohortSize: int
    highRiskCount: int
    messages: list[OutreachMessage]
    subject: str
    bodyText: str


class ActStep(BaseModel):
    step: Literal["supervisor", "patients"]
    label: str
    ok: bool
    sentAt: str
    to: str
    messageId: Optional[str] = None
    dryRun: bool = False
    detail: Optional[str] = None


class ActResult(BaseModel):
    ok: bool
    hospitalId: str
    hospitalName: str
    alert: ReadinessAlert
    outreach: PatientOutreach
    steps: list[ActStep]
