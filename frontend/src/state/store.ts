import { create } from "zustand";
import rawCatchments from "../../../data/catchments.json";

// ---- Types ----
export type Band = "green" | "amber" | "red";
export type ExposureKey = "pm25" | "no2" | "o3" | "heat" | "combined";
export type Horizon = "now" | "3d" | "7d";
export interface LngLat { lon: number; lat: number; }

export interface Hospital {
  id: string;
  name: string;
  trust: string;
  lat: number;
  lon: number;
  roadside: boolean;
  vulnerabilityWeight: number;
  population: number;
  baseExposure: number; // calm baseline
  exposure: number; // current (after plume)
  capacity: number;
  surgeCapacity: number;
  demandBaseline: number;
  rpi: number;
  band: Band;
}

export interface Wind { dirDeg: number; speedMs: number; }
export interface LayerToggles {
  exposure: boolean; columns: boolean; catchments: boolean; labels: boolean;
}

interface RawHospital {
  id: string; name: string; trust: string; lat: number; lon: number; roadside: boolean;
  vulnerabilityWeight: number;
  population: { value: number };
  capacity: { value: number };
  illustrativeDemandBaseline: { value: number };
}

// ---- model ----
function idJitter(id: string, mod: number): number {
  return id.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % mod;
}
export function bandForRpi(rpi: number): Band {
  if (rpi < 40) return "green";
  if (rpi < 70) return "amber";
  return "red";
}
function baselineExposure(roadside: boolean, id: string): number {
  return Math.max(0.05, Math.min(0.32, 0.08 + (roadside ? 0.14 : 0) + idJitter(id, 17) * 0.008));
}
export function rpiFromExposure(exposure: number, vuln: number, roadside: boolean): number {
  return Math.max(3, Math.min(100, Math.round(exposure * vuln * (roadside ? 1.15 : 1) * 80)));
}
export function projectedDemand(h: Hospital): number {
  return Math.round(h.demandBaseline * (1 + 1.5 * (h.rpi / 100)));
}

// localised plume: exposure rises at the centre, falls off with distance (Gaussian)
export const PLUME = { magnitude: 0.9, sigmaDeg: 0.025 };
export function exposureAt(h: Hospital, center: LngLat | null): number {
  if (!center) return h.baseExposure;
  const d = Math.hypot(h.lat - center.lat, h.lon - center.lon);
  const add = PLUME.magnitude * Math.exp(-((d / PLUME.sigmaDeg) ** 2));
  return Math.max(0, Math.min(1, h.baseExposure + add));
}

const raw = (rawCatchments as { hospitals: RawHospital[] }).hospitals;

function makeHospital(h: RawHospital): Hospital {
  const baseExposure = baselineExposure(h.roadside, h.id);
  const rpi = rpiFromExposure(baseExposure, h.vulnerabilityWeight, h.roadside);
  return {
    id: h.id, name: h.name, trust: h.trust, lat: h.lat, lon: h.lon, roadside: h.roadside,
    vulnerabilityWeight: h.vulnerabilityWeight,
    population: h.population.value,
    baseExposure,
    exposure: baseExposure,
    capacity: h.capacity.value,
    surgeCapacity: Math.round(h.illustrativeDemandBaseline.value * 1.6),
    demandBaseline: h.illustrativeDemandBaseline.value,
    rpi,
    band: bandForRpi(rpi),
  };
}

const hospitals: Hospital[] = raw.map(makeHospital);

// The plume drifts through these hospitals in order (roughly W→E with the SW wind).
export const SEQUENCE = ["st-thomas", "kings-denmark-hill", "royal-london", "newham"];

function commitAt(list: Hospital[], center: LngLat | null): Hospital[] {
  return list.map((h) => {
    const exposure = exposureAt(h, center);
    const rpi = rpiFromExposure(exposure, h.vulnerabilityWeight, h.roadside);
    return { ...h, exposure, rpi, band: bandForRpi(rpi) };
  });
}
function posOf(id: string): LngLat {
  const h = hospitals.find((x) => x.id === id)!;
  return { lon: h.lon, lat: h.lat };
}

interface AppState {
  hospitals: Hospital[];
  selectedId: string | null;
  exposure: ExposureKey;
  horizon: Horizon;
  layers: LayerToggles;
  mode: "LIVE" | "SYNTHETIC" | "MIXED";
  wind: Wind;

  // simulation walkthrough
  simActive: boolean;
  simIndex: number;
  plumeTarget: LngLat | null; // where the plume is heading / sitting
  drifting: boolean;

  select: (id: string | null) => void;
  setExposure: (e: ExposureKey) => void;
  setHorizon: (h: Horizon) => void;
  toggleLayer: (k: keyof LayerToggles) => void;
  startSim: () => void;
  continueSim: () => void;
  arrive: () => void; // called by the map when a drift completes
  reset: () => void;
}

export const useStore = create<AppState>((set, get) => ({
  hospitals,
  selectedId: null,
  exposure: "combined",
  horizon: "now",
  layers: { exposure: true, columns: true, catchments: true, labels: true },
  mode: "SYNTHETIC",
  wind: { dirDeg: 235, speedMs: 4.2 },

  simActive: false,
  simIndex: 0,
  plumeTarget: null,
  drifting: false,

  select: (id) => set({ selectedId: id }),
  setExposure: (exposure) => set({ exposure }),
  setHorizon: (horizon) => set({ horizon }),
  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),

  startSim: () => {
    const center = posOf(SEQUENCE[0]);
    set((s) => ({
      simActive: true,
      simIndex: 0,
      plumeTarget: center,
      drifting: false, // first epicentre appears in place
      mode: "MIXED",
      hospitals: commitAt(s.hospitals, center),
      selectedId: SEQUENCE[0],
    }));
  },
  continueSim: () => {
    const { simIndex } = get();
    const next = simIndex + 1;
    if (next >= SEQUENCE.length) return;
    set({
      simIndex: next,
      plumeTarget: posOf(SEQUENCE[next]),
      drifting: true, // the map eases the plume over; arrive() commits + selects
      selectedId: null,
    });
  },
  arrive: () => {
    const { plumeTarget, simIndex } = get();
    set((s) => ({
      drifting: false,
      hospitals: commitAt(s.hospitals, plumeTarget),
      selectedId: SEQUENCE[simIndex] ?? null,
    }));
  },
  reset: () =>
    set((s) => ({
      simActive: false,
      simIndex: 0,
      plumeTarget: null,
      drifting: false,
      selectedId: null,
      mode: "SYNTHETIC",
      hospitals: commitAt(s.hospitals, null),
    })),
}));

export const BAND_COLOR: Record<Band, string> = {
  green: "#2ec4b6",
  amber: "#ff9f1c",
  red: "#e71d36",
};
