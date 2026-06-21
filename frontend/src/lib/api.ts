// Thin client for the FastAPI backend. Base URL comes from VITE_BACKEND_URL.
import type {
  AlertDraftRequest,
  DispatchRequest,
  DispatchResult,
  ReadinessAlert,
  State,
} from "./types";

export const API_BASE = (
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8008"
).replace(/\/$/, "");

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { signal });
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const getState = (horizon: string, exposure: string, signal?: AbortSignal) =>
  getJSON<State>(`/state?horizon=${horizon}&exposure=${exposure}`, signal);

export interface EpisodeResponse {
  name: string;
  total: number;
  frames: State[];
}

export const startEpisode = (name: string, horizon: string) =>
  getJSON<EpisodeResponse>(`/episode/start?name=${name}&horizon=${horizon}`);

export const resetEpisode = (horizon: string) => getJSON<State>(`/episode/reset?horizon=${horizon}`);

export const draftAlert = (body: AlertDraftRequest) =>
  postJSON<ReadinessAlert>("/alert/draft", body);

export const dispatchAlert = (body: DispatchRequest) =>
  postJSON<DispatchResult>("/alert/dispatch", body);

// URL for the agent reasoning SSE stream (consumed via EventSource).
export function agentStreamUrl(params: {
  hospitalId: string;
  horizon: string;
  centerLon?: number | null;
  centerLat?: number | null;
}): string {
  const q = new URLSearchParams({ hospitalId: params.hospitalId, horizon: params.horizon });
  if (params.centerLon != null && params.centerLat != null) {
    q.set("centerLon", String(params.centerLon));
    q.set("centerLat", String(params.centerLat));
  }
  return `${API_BASE}/agent/stream?${q.toString()}`;
}

export function actStreamUrl(params: {
  hospitalId: string;
  horizon: string;
  episode?: string | null;
  centerLon?: number | null;
  centerLat?: number | null;
}): string {
  const q = new URLSearchParams({ hospitalId: params.hospitalId, horizon: params.horizon });
  if (params.episode) q.set("episode", params.episode);
  if (params.centerLon != null && params.centerLat != null) {
    q.set("centerLon", String(params.centerLon));
    q.set("centerLat", String(params.centerLat));
  }
  return `${API_BASE}/alert/act?${q.toString()}`;
}
