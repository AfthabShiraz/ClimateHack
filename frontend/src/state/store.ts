import { create } from "zustand";
import rawCatchments from "../../../data/catchments.json";
import {
  draftAlert as apiDraftAlert,
  getState,
  resetEpisode,
  startEpisode,
} from "../lib/api";
import type {
  Band,
  ExposureKey,
  Horizon,
  HospitalState,
  LngLat,
  Mode,
  ReadinessAlert,
  Source,
  State,
  UkhsaAlert,
  Wind,
} from "../lib/types";

// re-export the contract types so existing imports (`from "../state/store"`) keep working
export type { Band, ExposureKey, Horizon, HospitalState, LngLat, Wind } from "../lib/types";
export type Hospital = HospitalState; // components historically import `Hospital`

export interface LayerToggles {
  exposure: boolean;
  columns: boolean;
  catchments: boolean;
  labels: boolean;
}

export const BAND_COLOR: Record<Band, string> = {
  green: "#2ec4b6",
  amber: "#ff9f1c",
  red: "#e71d36",
};

export function bandForRpi(rpi: number): Band {
  if (rpi < 40) return "green";
  if (rpi < 70) return "amber";
  return "red";
}

export function projectedDemand(h: HospitalState): number {
  return Math.round(h.projectedDemand.value);
}

// ---------------------------------------------------------------------------
// Seed fallback — used only until the first /state arrives, or if the backend
// is unreachable. The backend is the source of truth; this just keeps the map
// alive offline. Rich fields (drivers/severity/curve) are left empty here and
// filled in by the backend when it responds.
// ---------------------------------------------------------------------------
interface RawHospital {
  id: string; name: string; trust: string; lat: number; lon: number; roadside: boolean;
  vulnerabilityWeight: number;
  population: { value: number };
  capacity: { value: number };
  illustrativeDemandBaseline: { value: number };
}

const idJitter = (id: string, mod: number) =>
  id.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % mod;

const seedExposure = (roadside: boolean, id: string) =>
  Math.max(0.05, Math.min(0.32, 0.08 + (roadside ? 0.14 : 0) + idJitter(id, 17) * 0.008));

const seedRpi = (exposure: number, vuln: number, roadside: boolean) =>
  Math.max(3, Math.min(100, Math.round(exposure * vuln * (roadside ? 1.15 : 1) * 80)));

const sim = (value: number) => ({ value, simulated: true });

function seedHospital(h: RawHospital): HospitalState {
  const exposure = seedExposure(h.roadside, h.id);
  const rpi = seedRpi(exposure, h.vulnerabilityWeight, h.roadside);
  const demandBaseline = h.illustrativeDemandBaseline.value;
  return {
    id: h.id, name: h.name, trust: h.trust, lat: h.lat, lon: h.lon, roadside: h.roadside,
    exposure, rpi, band: bandForRpi(rpi),
    topDriver: h.roadside ? "no2" : "pm25",
    leadTimeDays: 5,
    drivers: [],
    curve: [],
    vulnerabilityWeight: h.vulnerabilityWeight,
    population: sim(h.population.value),
    capacity: sim(h.capacity.value),
    demandBaseline: sim(demandBaseline),
    projectedDemand: sim(Math.round(demandBaseline * (1 + 1.5 * (rpi / 100)))),
    surgeCapacity: sim(Math.round(demandBaseline * 1.6)),
    severityMix: { respWardPct: 41, generalPct: 51, icuPct: 8, avgLOS: 6.8, simulated: true },
  };
}

const seededHospitals: HospitalState[] = (
  rawCatchments as { hospitals: RawHospital[] }
).hospitals.map(seedHospital);

// ---------------------------------------------------------------------------

interface AppState {
  hospitals: HospitalState[];
  selectedId: string | null;
  exposure: ExposureKey;
  horizon: Horizon;
  layers: LayerToggles;
  mode: Mode;
  wind: Wind;
  ukhsaAlert: UkhsaAlert;
  sources: Source[];
  connected: boolean; // backend reachable on last fetch
  loading: boolean;

  // episode walkthrough (frames come from the backend)
  episodeFrames: State[] | null;
  episodeSequence: string[];
  episodeName: string;
  simActive: boolean;
  simIndex: number;
  plumeTarget: LngLat | null; // where the plume dome sits / heads
  drifting: boolean;

  init: () => Promise<void>;
  select: (id: string | null) => void;
  setExposure: (e: ExposureKey) => void;
  setHorizon: (h: Horizon) => void;
  toggleLayer: (k: keyof LayerToggles) => void;
  startSim: () => Promise<void>;
  continueSim: () => void;
  arrive: () => void; // called by the map when a drift completes
  reset: () => Promise<void>;
  draftAlert: (hospitalId: string) => Promise<ReadinessAlert>;
  currentCenter: () => LngLat | null;
}

const DEFAULT_UKHSA: UkhsaAlert = { level: "none", type: "heat", source: "UKHSA" };

export const useStore = create<AppState>((set, get) => ({
  hospitals: seededHospitals,
  selectedId: null,
  exposure: "combined",
  horizon: "now",
  layers: { exposure: true, columns: true, catchments: true, labels: true },
  mode: "SYNTHETIC",
  wind: { dirDeg: 235, speedMs: 4.2 },
  ukhsaAlert: DEFAULT_UKHSA,
  sources: [],
  connected: false,
  loading: false,

  episodeFrames: null,
  episodeSequence: [],
  episodeName: "pm25_spike",
  simActive: false,
  simIndex: 0,
  plumeTarget: null,
  drifting: false,

  init: async () => {
    set({ loading: true });
    try {
      const s = await getState(get().horizon, get().exposure);
      applyState(set, s);
      set({ connected: true });
    } catch (e) {
      console.warn("[Crosssight] backend unreachable — using seed data", e);
      set({ connected: false, mode: "SYNTHETIC" });
    } finally {
      set({ loading: false });
    }
  },

  select: (id) => set({ selectedId: id }),

  setExposure: (exposure) => {
    set({ exposure });
    void refresh(set, get);
  },

  setHorizon: (horizon) => {
    set({ horizon });
    void refresh(set, get);
  },

  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),

  startSim: async () => {
    const { episodeName, horizon } = get();
    try {
      const ep = await startEpisode(episodeName, horizon);
      const frames = ep.frames;
      if (!frames.length) return;
      const f0 = frames[0];
      const seq = f0.episode?.sequence ?? [];
      applyState(set, f0);
      set({
        episodeFrames: frames,
        episodeSequence: seq,
        simActive: true,
        simIndex: 0,
        plumeTarget: f0.exposureField.center ?? null,
        drifting: false, // first epicentre appears in place
        selectedId: seq[0] ?? null,
        connected: true,
      });
    } catch (e) {
      console.warn("[Crosssight] episode start failed", e);
    }
  },

  continueSim: () => {
    const { simIndex, episodeFrames } = get();
    if (!episodeFrames) return;
    const next = simIndex + 1;
    if (next >= episodeFrames.length) return;
    set({
      simIndex: next,
      plumeTarget: episodeFrames[next].exposureField.center ?? null,
      drifting: true, // the map eases the dome over; arrive() commits + selects
      selectedId: null,
    });
  },

  arrive: () => {
    const { simIndex, episodeFrames, episodeSequence } = get();
    if (!episodeFrames) {
      set({ drifting: false });
      return;
    }
    const f = episodeFrames[simIndex];
    applyState(set, f);
    set({ drifting: false, selectedId: episodeSequence[simIndex] ?? null });
  },

  reset: async () => {
    const { horizon } = get();
    set({
      simActive: false,
      simIndex: 0,
      episodeFrames: null,
      episodeSequence: [],
      plumeTarget: null,
      drifting: false,
      selectedId: null,
    });
    try {
      const s = await resetEpisode(horizon);
      applyState(set, s);
      set({ connected: true });
    } catch (e) {
      console.warn("[Crosssight] episode reset failed", e);
      set({ mode: "SYNTHETIC" });
    }
  },

  draftAlert: async (hospitalId) => {
    const { horizon, simActive, episodeName } = get();
    const center = get().currentCenter();
    return apiDraftAlert({
      hospitalId,
      horizon,
      episode: simActive ? episodeName : null,
      centerLon: center?.lon ?? null,
      centerLat: center?.lat ?? null,
    });
  },

  currentCenter: () => {
    const { simActive, episodeFrames, simIndex, plumeTarget } = get();
    if (!simActive) return null;
    return episodeFrames?.[simIndex]?.exposureField.center ?? plumeTarget ?? null;
  },
}));

type Setter = (partial: Partial<AppState>) => void;
type Getter = () => AppState;

function applyState(set: Setter, s: State): void {
  set({
    hospitals: s.hospitals,
    mode: s.mode,
    wind: s.wind,
    ukhsaAlert: s.ukhsaAlert ?? DEFAULT_UKHSA,
    sources: s.sources ?? [],
  });
}

// Re-fetch the authoritative snapshot after a horizon/exposure change. During an
// episode we re-resolve the frames (server RPI scales with horizon) and re-apply
// the current frame so the walkthrough position is preserved.
async function refresh(set: Setter, get: Getter): Promise<void> {
  const { horizon, exposure, simActive, episodeName, simIndex } = get();
  try {
    if (simActive) {
      const ep = await startEpisode(episodeName, horizon);
      if (ep.frames.length) {
        const idx = Math.min(simIndex, ep.frames.length - 1);
        applyState(set, ep.frames[idx]);
        set({ episodeFrames: ep.frames, connected: true });
      }
    } else {
      const s = await getState(horizon, exposure);
      applyState(set, s);
      set({ connected: true });
    }
  } catch (e) {
    console.warn("[Crosssight] refresh failed", e);
    set({ connected: false });
  }
}
