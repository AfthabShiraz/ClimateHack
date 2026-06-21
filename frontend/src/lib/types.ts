// Mirrors backend/app/models.py — the /state contract + agent/dispatch bodies.
// Keep field names identical so swapping client-computed -> backend-served stays mechanical.

export type Band = "green" | "amber" | "red";
export type Horizon = "now" | "3d" | "7d";
export type Mode = "LIVE" | "SYNTHETIC" | "MIXED";
export type ExposureKey = "pm25" | "no2" | "o3" | "heat" | "combined";

export interface LngLat {
  lon: number;
  lat: number;
}

export interface Simulated {
  value: number;
  simulated: boolean;
  method?: string | null;
}

export interface Source {
  name: string;
  status: "live" | "stale" | "down";
  lastUpdated?: string | null;
  simulated: boolean;
}

export interface Wind {
  dirDeg: number;
  speedMs: number;
  simulated?: boolean;
}

export interface UkhsaAlert {
  level: "none" | "yellow" | "amber" | "red";
  type: "heat" | "cold";
  source: string;
}

export interface Episode {
  active: boolean;
  name?: string | null;
  index: number;
  total: number;
  simulated: boolean;
  sequence: string[];
}

export interface Station {
  lat: number;
  lon: number;
  value: number;
  pollutant: string;
  station: string;
  simulated: boolean;
}

export interface ExposureField {
  center?: LngLat | null;
  stations: Station[];
}

export interface Driver {
  term: string;
  exposureLevel: number;
  effectSize: number;
  numStudies?: number | null;
  highestCited?: number | null;
  sourceRowId?: string | null;
  substituted: boolean;
  vulnerabilityWeight: number;
  contribution: number;
}

export interface CurvePoint {
  dayOffset: number;
  rpi: number;
}

export interface SeverityMix {
  respWardPct: number;
  generalPct: number;
  icuPct: number;
  avgLOS: number;
  simulated: boolean;
}

export interface HospitalState {
  id: string;
  name: string;
  trust: string;
  lat: number;
  lon: number;
  roadside: boolean;
  exposure: number;
  rpi: number;
  band: Band;
  topDriver: string;
  leadTimeDays: number;
  drivers: Driver[];
  curve: CurvePoint[];
  vulnerabilityWeight: number;
  population: Simulated;
  capacity: Simulated;
  demandBaseline: Simulated;
  projectedDemand: Simulated;
  surgeCapacity: Simulated;
  severityMix: SeverityMix;
}

export interface State {
  generatedAt: string;
  mode: Mode;
  horizon: Horizon;
  sources: Source[];
  wind: Wind;
  ukhsaAlert: UkhsaAlert;
  episode?: Episode | null;
  exposureField: ExposureField;
  hospitals: HospitalState[];
}

// ---- agent / dispatch bodies ----

export interface AlertDraftRequest {
  hospitalId: string;
  horizon?: Horizon;
  episode?: string | null;
  centerLon?: number | null;
  centerLat?: number | null;
}

export interface ReadinessAlert {
  hospitalId: string;
  hospitalName: string;
  severity: Band;
  leadTimeDays: number;
  subject: string;
  situation: string;
  evidence: string[];
  projectedImpact: string;
  recommendedPreparation: string[];
  sources: string[];
  bodyText: string;
  generatedBy: string; // "claude-sonnet-4-6" | "template-fallback" | "pre-baked"
}

export interface DispatchRequest {
  hospitalId: string;
  to?: string | null;
  subject: string;
  body: string;
}

export interface DispatchResult {
  ok: boolean;
  sentAt: string;
  to: string;
  messageId?: string | null;
  dryRun: boolean;
  detail?: string | null;
}

export interface OutreachMessage {
  patientLabel: string;
  channel: "sms" | "email";
  preview: string;
}

export interface PatientOutreach {
  cohortSize: number;
  highRiskCount: number;
  messages: OutreachMessage[];
  subject: string;
  bodyText: string;
}

export interface ActStep {
  step: "supervisor" | "patients";
  label: string;
  ok: boolean;
  sentAt: string;
  to: string;
  messageId?: string | null;
  dryRun: boolean;
  detail?: string | null;
}

export interface ActResult {
  ok: boolean;
  hospitalId: string;
  hospitalName: string;
  alert: ReadinessAlert;
  outreach: PatientOutreach;
  steps: ActStep[];
}

/** SSE progress events from GET /alert/act */
export interface ActProgressEvent {
  phase: "drafting" | "ready" | "supervisor" | "patients";
  label?: string;
  status?: "sending" | "done";
  count?: number;
  to?: string;
  recipient?: string;
  alert?: ReadinessAlert;
  outreach?: PatientOutreach;
  result?: DispatchResult;
}
