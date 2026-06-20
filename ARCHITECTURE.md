# Crosssight — Technical System Architecture
### How the whole thing fits together, rendering-first

> ⚠️ **PARTIALLY SUPERSEDED (product pivot).** The product is now **alert-centric**: the
> Redirect arcs / redistribution / particle-haze material below was **removed**. For the
> current backend, engine, `/state` contract, and the agent **reason + act** (email dispatch)
> design, see **`backend/README.md`** — it wins on any disagreement. The Cesium/rendering and
> dataset sections here are still broadly valid; the redistribution/arc sections are historical.

> **What this document is.** The technical architecture for Crosssight (product spec: `plan.md`). It nails down the **UI/rendering stack first** — a photorealistic 3D map of London — then the data, backend, and agent layers that feed it. Feature IDs (F1–F27) refer to `plan.md §6`. Where this document specifies a rendering or data-source choice, it **supersedes** the non-binding tech notes in `plan.md §11` and the deck.gl/MapLibre layer hints in the feature table (those concepts are re-mapped to Cesium below — nothing in the product changes, only the implementation surface).

---

## 0. The stack (decided)

| Concern | Choice | Why |
|---|---|---|
| **3D map base (primary)** | **CesiumJS** + **Cesium Ion** + **Google Photorealistic 3D Tiles** | Real photoreal London (buildings, terrain) — the "wow" stage. Proven in a prior build. |
| **3D map base (no-card fallback)** | **CesiumJS** + **Cesium Ion** + **Cesium OSM Buildings** (Ion asset, free, Ion-token-only) | Instant real 3D city with no Google billing. One-line swap; all column/haze/arc code identical. |
| **Map React integration** | **Vanilla CesiumJS** behind a thin React wrapper (a `useCesium` hook + refs). *Resium* is an acceptable alternative but we need custom primitives (particles, animated arcs, callback-driven columns) that are easier in raw Cesium. | Control over custom primitives & per-frame animation. |
| **UI chrome** | **React + Vite + TypeScript**, DOM absolutely-positioned **over** the Cesium canvas | Top bar, rails, panels, drawer are HTML/CSS; the map is the canvas underneath. |
| **Live air feed (primary)** | **London Air (LAQN, Imperial)** stations → PM2.5/NO₂/O₃; **DEFRA UK-AIR (AURN)** as backup/wider coverage | **Provided hackathon datasets (scored).** Real London stations = credibility. |
| **Heat + wind feed** | **Met Office** observations + forecast → temp (heat term) + **wind dir/speed** (drives F24) | Provided dataset; supplies the heat term and the wind vector for the drifting haze. |
| **Official alerts** | **UKHSA** Heat/Cold Health Alerts | Provided dataset; gates/boosts heat term + F8 banner. |
| **Evidence** | **System climate research graph** (repo) | Effect sizes + provenance. Unchanged from `plan.md §3.2`. |
| **Vulnerability / clinical / geo** | **GLA** (demographics), **Milliman** (SVI indices), **Apollo** (COPD profiles), **OpenStreetMap** (hospitals, roads) | VulnerabilityWeight + severity texture + catchment geometry. Unchanged. |
| **Backend** | **Python FastAPI** | Polls the dataset feeds, runs Risk Engine, calls agents, exposes `/state` + SSE. (Node/Express is a drop-in alternative.) |
| **Agents** | **Anthropic API**, `claude-sonnet-4-6`, **streaming** | Briefing / Recommendation / Redistribution. Streaming powers F25. |
| **Realtime transport** | **SSE** (Server-Sent Events) for the refresh cycle and agent token streams; plain REST for `/state` snapshots | Simpler than WebSockets, one-way is all we need. |

> ⚠️ **Dataset usage is a scoring criterion.** Crosssight is deliberately built on the **provided datasets** (System graph, LAQN, DEFRA, Met Office, UKHSA, GLA, Milliman, Apollo, OSM). Do **not** substitute a single commercial weather/air API for these — the only paid third-party services are the **map base** (Cesium/Google tiles, purely cosmetic) and the **Anthropic API** (the agent layer). Every environmental and clinical number traces to a provided dataset.

**Hard rule (from `plan.md §13.14`):** the browser never calls the data feeds or Anthropic directly. All external calls go through FastAPI (keys/sources stay server-side, no CORS). The frontend talks only to our backend.

---

## 1. High-level architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ BROWSER (React + Vite)                                                      │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │ DOM CHROME (React, absolute over canvas)                           │    │
│  │  TopBar(F7,F8,F16-18,F21,F22,F23) · LeftRail(F3,F6) ·              │    │
│  │  RightPanel(F9,F10,F19,F20) · Drawer(F12-16) · Evidence(F11,F27)   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │ CESIUM VIEWER (the stage)                                          │    │
│  │  Google Photorealistic 3D Tiles (base)                             │    │
│  │  + ColumnEntities(F4) + CatchmentPolygons(F5)                      │    │
│  │  + HazeParticleSystem(F2,F24) + ArcPolylines(F18,F26)              │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│        │  GET /state          │  SSE /stream        │  SSE /agent/stream    │
└────────┼──────────────────────┼─────────────────────┼───────────────────────┘
         ▼                      ▼                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                                           │
│  StateService ── RiskEngine ── EffectSizeConfig (from System graph)         │
│       │              │                                                      │
│       │              ├── ExposureProvider ──► LAQN/DEFRA (air) + Met Office │
│       │              │        │                (temp+wind) + UKHSA (alerts)  │
│       │              │        └─ ClimateEventInjector (F21, input layer)    │
│       │              ├── catchments.json (hospitals, Voronoi, vuln, cap)    │
│       │              └── SeverityProvider ──► Apollo profiles               │
│       │                                                                     │
│       └── AgentService ──► Anthropic (claude-sonnet-4-6, streaming)         │
│            (cached briefings/recs/redistribution + templated fallback)      │
│                                                                            │
│  Caches: last-good /state (disk) · agent cache · LAQN/Met Office response cache │
└──────────────────────────────────────────────────────────────────────────┘
         ▲ build-time (offline) prep
┌──────────────────────────────────────────────────────────────────────────┐
│ DATA PREP (scripts, run once → committed JSON)                              │
│  System graph → effect_sizes.json   |   GLA+Milliman+OSM → catchments.json  │
└──────────────────────────────────────────────────────────────────────────┘
```

Two clean seams: **(a)** frontend ⇄ backend via `/state` + SSE (renderer is dumb, all logic server-side); **(b)** runtime ⇄ build-time via committed JSON (`effect_sizes.json`, `catchments.json`), so the heavy dataset wrangling never happens live.

---

## 2. The rendering layer (Cesium) — in detail

### 2.1 Viewer & photorealistic base

```ts
Cesium.Ion.defaultAccessToken = ION_TOKEN;            // from Cesium Ion

const viewer = new Cesium.Viewer("cesiumContainer", {
  // strip default UI — we render our own chrome
  baseLayerPicker: false, geocoder: false, homeButton: false,
  sceneModePicker: false, navigationHelpButton: false, animation: false,
  timeline: false, fullscreenButton: false, infoBox: false, selectionIndicator: false,
  // photoreal tiles already include ground; turn the ellipsoid globe off to save GPU
  globe: false,
});

// --- BASE TILES: pick ONE. Same viewer, same column/haze/arc code either way. ---

// PRIMARY — Google Photorealistic 3D Tiles (needs a Google Maps key w/ Map Tiles API + billing):
const tileset = await Cesium.createGooglePhotorealistic3DTileset({ key: GOOGLE_MAPS_KEY });
viewer.scene.primitives.add(tileset);

// FALLBACK — Cesium OSM Buildings (Ion token only, no Google, no credit card):
//   viewer.scene.setTerrain(Cesium.Terrain.fromWorldTerrain());   // re-enable globe for this route
//   const tileset = await Cesium.createOsmBuildingsAsync();
//   viewer.scene.primitives.add(tileset);

// London, tilted hero shot
viewer.camera.flyTo({
  destination: Cesium.Cartesian3.fromDegrees(-0.1180, 51.4900, 9000),
  orientation: { heading: Cesium.Math.toRadians(20),
                 pitch: Cesium.Math.toRadians(-45) },  // ~50° tilt from horizon
});
```

**Required attribution:** Google's logo + data attributions must remain visible — Cesium's credit display handles this automatically; do **not** hide `viewer.creditContainer`. This is a licensing requirement *and* a credibility signal (§ honesty).

### 2.2 Occlusion — the one Cesium gotcha that will bite

Photorealistic buildings have real depth, so naively-placed columns/labels get *hidden behind buildings*. **Decided approach (robust + low-effort):**

- **Columns (F4) — anchor to sampled rooftop height, keep depth-test ON.** After the tileset's `initialTilesLoaded` event, **batch-sample all ~30 hospital points once** with `await viewer.scene.sampleHeightMostDetailed(cartographics)`; cache the result as each column's `baseHeight`. Columns then rise *from the rooftops*. Leave depth-testing **on** for the cylinders so they look genuinely 3D (nearer buildings occlude them, tops clear the skyline) — that realism is a feature, not a bug.
- **Labels / billboards / the "ⓘ why?" affordance — depth-test OFF.** Set `disableDepthTestDistance: Number.POSITIVE_INFINITY` so text/markers are *never* lost behind a building. (Only the always-readable bits opt out of depth testing — not the columns.)
- **Catchment polygons (F5):** drape onto the tiles with `classificationType: Cesium.ClassificationType.CESIUM_3D_TILE` so they paint over ground/buildings instead of z-fighting.
- **Fallback if height-sampling is flaky under time pressure:** give every column a **fixed base altitude above the skyline** (~250 m) so they float as a clean data layer above the city — zero sampling, always visible. Slightly less "grounded" but bulletproof. Gate this behind a `COLUMN_ANCHOR=rooftop|floating` flag so you can flip it instantly during rehearsal.

### 2.3 deck.gl-concept → Cesium implementation map

| `plan.md` feature (deck.gl term) | Cesium implementation |
|---|---|
| F4 ColumnLayer (hospital columns) | `Entity` with `cylinder` graphics; `length` = RPI→metres via `CallbackProperty` (animatable); `material` = band colour |
| F2/F24 Heatmap/Hexagon + wind drift | `Cesium.ParticleSystem` over London (wind-advected) **+** optional translucent heatmap imagery/`GroundPrimitive` for the static field |
| F5 PolygonLayer (catchments) | `Entity` `polygon` with `classificationType: CESIUM_3D_TILE`, low `material` alpha scaled by VulnerabilityWeight |
| F18/F26 ArcLayer (redirect) | `Entity` `polyline` with computed parabolic positions + animated flow material (`PolylineGlowMaterialProperty` or custom flowing-texture material) |
| Camera fly-to / orbit | `viewer.camera.flyTo(...)` + per-frame `camera.rotate`/bearing sweep on the `scene.preRender` event |
| Tooltips/hover | `ScreenSpaceEventHandler` (`MOUSE_MOVE` → `scene.pick`) → React tooltip positioned at `scene.cartesianToCanvasCoordinates` |

### 2.4 Hospital columns (F4) + animation (F26 re-height, F27 explode)

- One `Entity` per hospital (~25–30; cheap). Position = `Cartesian3.fromDegrees(lon, lat, baseHeight + length/2)`.
- `length` driven by a `CallbackProperty(() => store.heightFor(id), false)` so the **same entities** animate smoothly when RPI changes (horizon switch, climate event, Redirect) — we never tear down/rebuild.
- A lightweight **animation controller** (rAF loop or a tween lib) interpolates `store.height` between current and target with `easeCubicInOut` over ~1200 ms. Cesium re-reads the callback each frame.
- **F27 explode:** on "Show the math", swap the single cylinder for **four stacked cylinders** (one per multiplicand), each `length` ∝ its `contribution`, staggered in by ~150 ms, with a billboard citation chip beside the effect-size segment (`disableDepthTestDistance`). Recompose reverses it. Segment lengths must visibly sum to the whole column.

### 2.5 Wind-driven haze (F2 + F24) — the "it's alive" centrepiece

Use a **Cesium `ParticleSystem`** anchored over Greater London:

- `modelMatrix` positions the emitter box over the London bbox; `emitter = new Cesium.BoxEmitter(...)` spread across the area.
- Per-cell **emission rate / particle colour ∝ ExposureLevel** at that location (from `/state` grid) → dirtier air = denser, redder haze.
- `updateCallback(particle, dt)` applies the **real wind vector** (`wind.dirDeg`, `wind.speedMs` from `/state`) as a force, so particles **drift the way London's actual air is moving**. Particle speed ∝ wind speed.
- Fallback (no wind): constant slow drift so the field is never frozen; flag `wind.simulated` in the source chip (F22).
- Cap particle count for 60 fps (see §6.3). Optionally underlay a translucent heatmap imagery layer for a solid colour field beneath the particles.

### 2.6 Redirect arcs (F18) + choreographed climax (F26)

- Each arc = an `Entity` `polyline`. Build a **parabolic** path: sample N points along the great circle between source/target hospitals, raising height by a sine bump (peak ∝ distance) so the arc lifts off the city.
- **Flow look:** animated material — simplest is `PolylineGlowMaterialProperty` with a time-varying `glowPower`; richer is a custom `Material` with a scrolling stripe texture (offset advanced on `scene.preRender`) to read as particles flowing source→target.
- **The climax is one shared clock** (§ `plan.md §13.15` F26): on Redirect click, a single timeline drives (1) arcs spring in, (2) over-pressure column `length` eases down + headroom eases up, (3) `camera.flyTo` the affected cluster then slow-orbit, (4) the F20 overflow counter (DOM) ticks before→after. Backend pre-resolves before/after states so the client only animates between two known frames — no mid-animation recompute.

### 2.7 DOM chrome over the canvas

- The Cesium `<div id="cesiumContainer">` fills the viewport; React chrome sits in an absolutely-positioned overlay (`pointer-events: none` on the overlay root, `pointer-events: auto` on actual controls) so map drag/zoom still works between widgets.
- Chrome components map 1:1 to `plan.md §7` regions: `TopBar`, `LeftRail`, `RightPanel`, `Drawer`, `EvidencePopover`. They read from the same client store as the Cesium layer — single source of truth.
- Hover tooltips & the "ⓘ why?" popovers are React elements positioned from Cesium pick results via `scene.cartesianToCanvasCoordinates`.

---

## 3. Data & live feeds

### 3.1 The provided dataset feeds — exactly what `ExposureProvider` pulls

Per refresh, the backend `ExposureProvider` reads from the **provided hackathon datasets** (no commercial weather/air API):

| Need | Source (provided dataset) | Access | Fields |
|---|---|---|---|
| Live air: PM2.5/NO₂/O₃ per **station** | **London Air (LAQN, Imperial)** | LAQN JSON API (`londonair.org.uk/Londonair/API/`) | latest hourly per monitoring site |
| Air backup / wider coverage | **DEFRA UK-AIR (AURN)** | `pyaurn` | hourly per AURN site |
| Temp + **wind dir/speed** | **Met Office** | Met Office DataHub/DataPoint | current temp, wind, + short-range forecast |
| Official heat/cold alert | **UKHSA** | UKHSA weather-health-alerts dashboard | London alert level (F8, heat-term gate) |

**Station → catchment join (back to `plan.md §13.5`, required now that air is station-based):**
- LAQN/AURN give **point readings at station locations**, not a grid. For each of the ~30 catchments, compute `ExposureLevel` by **inverse-distance weighting (k=3 nearest stations, power=2)** to the catchment centroid. If <1 station within 10 km → borough-average → city-average fallback; flag degraded coverage on F22.
- **Haze field (F2/F24):** the particle system emits from the **station points** (coloured by each station's reading) and the wind vector advects them — so the visible haze is literally driven by the real London monitors, which is a stronger story than a smooth commercial grid. Interpolate between stations for visual continuity.
- **Wind (F24):** Met Office `wind_deg`/`wind_speed` (city-level is enough). No wind → gentle fixed drift, `wind.simulated:true`.

- **Cadence:** LAQN updates ~hourly; poll every **5–10 min**, cache aggressively, and let the SSE `/stream` heartbeat (F23) pulse on a shorter UI cycle (the breathing/recompute feel doesn't require new upstream data each tick).

### 3.2 Horizon projection (per `plan.md §13.4`)

Station observations are **not forecasts**, so:
- **Air (+3d/+7d):** persistence of current levels **decayed toward the station/seasonal mean**, convolved with the fixed **lag kernel** (`plan.md §13.4`). Honest and simple.
- **Heat:** use the **Met Office temperature forecast** where available (genuine), else persistence.
- Convolution of the exposure series with the lag kernel produces the F12 pressure curve. UI always says **"projection,"** never "prediction" or "forecast" for air.

### 3.3 Static datasets (build-time → committed JSON)

- `effect_sizes.json` — the canonical non-overlapping term set (`plan.md §13.2`) pulled from the System graph, each with `effectSize`, `numStudies`, `highestCited`. Verified to exist at build time.
- `catchments.json` — the runtime spatial artifact, precomputed once:
  - ~25–30 London Type-1 A&E hospitals: `id, name, trust, lat, lon`.
  - **Voronoi catchment polygon** per hospital, clipped to the GLA Greater-London boundary; `roadside` flag (OSM major-road proximity).
  - `vulnerabilityWeight` (0.5–1.5) from GLA + Milliman SVI, areal-interpolated to the catchment.
  - `population` (object `{value, simulated:true, method}` — demand-layer only, not in RPI), seeded `capacity` + `illustrativeDemandBaseline` (both `"simulated": true`).
- Apollo profiles loaded server-side for the severity mix (F14) and patient cards (F15) — never as a climate predictor (`plan.md §0`).

### 3.4 LIVE_DATA flag, synthetic fallback, climate-event injector

- `LIVE_DATA=true` → real LAQN/DEFRA/Met Office fetches with per-call timeout; any failure falls back to the **seeded synthetic generator** and is marked `status:"down"`/`simulated:true` (F22 shows mixed mode).
- `LIVE_DATA=false` → all-synthetic (offline/`DEMO_MODE`).
- **ClimateEventInjector (F21):** a pure transform `baselineExposure → perturbedExposure` applied **at the input layer only** (`plan.md §13.14`). Selected by the `episode` query param. Everything downstream (engine, agents, arcs) runs identically — no separate demo code path. Injected cells carry `simulated:true`; the chip reads **"simulated event — real response."**

---

## 4. Backend services & API contract

### 4.1 Modules

- **ExposureProvider** — LAQN/DEFRA + Met Office fetch → station→catchment IDW (§3.1) + cache + synthetic fallback + injector. Returns normalised `ExposureLevel` (absolute health thresholds, `plan.md §13.3`) per catchment, the station points for the haze, and `wind`.
- **RiskEngine** — pure function: `(exposures, effect_sizes, catchments, horizon) → {rpi, band, drivers[], curve[]}` per hospital. Deterministic, no I/O (`plan.md §3.1/§13.1`).
- **RedistributionEngine** — computes headroom = `capacity − projectedDemand`, solves over-pressure→headroom assignment, returns arcs + `overflowBefore/After`.
- **SeverityProvider** — Apollo-derived severity mix + patient cards per hospital.
- **AgentService** — Anthropic streaming; cached by `(hospitalId, horizon, band, topDriver, episode)`; templated fallback on timeout/no-key.
- **StateService** — assembles everything into the `/state` payload; persists last-good to disk.

### 4.2 Endpoints

```
GET  /state?horizon=now|3d|7d&exposure=pm25|no2|o3|heat|combined&episode=none|pm25_spike|heatwave|no2_inversion
        → full snapshot (schema below)
GET  /stream            (SSE)  → emits a fresh /state object each refresh cycle (the F23 heartbeat)
GET  /agent/stream?type=briefing|recommendation|redistribution&hospitalId=...&horizon=...&episode=...
        (SSE)  → token-by-token agent text for F25; final event includes structured JSON + citations
GET  /health            → liveness + which sources are live/stale/down
```

### 4.3 `/state` schema (extends `plan.md §13.7` for Cesium)

Additions over §13.7, marked **▲**:

```jsonc
{
  "generatedAt": "ISO-8601",
  "mode": "LIVE" | "SYNTHETIC" | "MIXED",
  "sources": [{ "name": "LAQN", "status": "live|stale|down", "lastUpdated": "ISO", "simulated": bool, "degradedReason": "..." },
              { "name": "Met Office", "status": "...", "lastUpdated": "ISO", "simulated": bool, "degradedReason": null }],
  "wind": { "dirDeg": 0-360, "speedMs": number, "simulated": bool },            // ▲ drives F24
  "ukhsaAlert": { "level": "...", "type": "heat|cold", "source": "..." },
  "exposureField": {                                                            // ▲ Cesium-ready: real station points
    "stations": [{ "lat", "lon", "value": 0-1, "pollutant", "station", "simulated": bool }]
  },
  "hospitals": [{
    "id", "name", "trust", "lat", "lon",
    "baseHeightHint": number,         // ▲ optional; client refines via sampleHeightMostDetailed
    "rpi": 0-100, "band": "green|amber|red", "topDriver": "pm25|no2|roadside|heat",
    // RPI is PER-CAPITA — drivers carry only exposure × effectSize × vulnerability (NO population). F27 segments = these 3.
    "drivers": [{ "term","exposureLevel","effectSize","numStudies","highestCited",
                  "sourceRowId","substituted": bool,                  // ▲ substituted-term disclosure (N5)
                  "vulnerabilityWeight","contribution" }],
    "curve": [{ "dayOffset": 0-7, "rpi" }],
    "population": { "value", "simulated": true, "method": "..." },      // ▲ demand-layer only, NOT in RPI (D1/C7/S11)
    "capacity": { "value", "simulated": true },
    "illustrativeDemand": { "value", "simulated": true },              // baseline before RPI scaling
    "projectedDemand": { "value", "simulated": true },                 // ▲ = illustrativeDemand × (1 + 1.5 × rpi/100) (C6)
    "headroom": number,                                                 // = capacity.value − projectedDemand.value
    "severityMix": { "respWardPct","avgLOS","icuPct","simulated": true },
    "patientCards": [{ "age","comorbidities","exposureContext","likelyLOS","simulated": true }]
  }],
  "redistribution": {
    "arcs": [{ "fromId","toId","estPatients","conveyanceNote" }],
    // overflowBefore = Σ_h max(0, projectedDemand.value − capacity.value); overflowAfter = same after arcs reassign demand
    "overflowBefore","overflowAfter"
  },
  "agents": { "briefings": {id:{text,citations[],cached}}, "recommendations": {...}, "redistributionPlan": {...} }
}
```

The renderer maps `hospitals[]` → column entities, `exposureField.stations` + `wind` → particle system, `redistribution.arcs` → polylines. **No business logic in the client.**

---

## 5. Frontend architecture

### 5.1 Component / module tree

```
src/
  cesium/
    useCesiumViewer.ts      // creates Viewer, loads Google 3D tiles, camera
    layers/
      columns.ts            // F4 entities + height animation (F26) + explode (F27)
      haze.ts               // F2/F24 particle system, wind-advected
      catchments.ts         // F5 draped polygons
      arcs.ts               // F18/F26 parabolic animated polylines
    camera.ts               // flyTo, cluster orbit (F26)
    picking.ts              // hover/click → store
  state/
    store.ts                // single client store (Zustand/Context): /state + UI state
    sse.ts                  // /stream + /agent/stream subscriptions
    animation.ts            // shared clock, easing, tween targets
  ui/                       // DOM chrome over canvas
    TopBar.tsx  LeftRail.tsx  RightPanel.tsx  Drawer.tsx
    EvidencePopover.tsx  OverflowCounter.tsx  StreamingBriefing.tsx  SourceChip.tsx
  App.tsx
```

### 5.2 How `/state` drives the map (diff, don't rebuild)

1. SSE pushes a new `/state` → store updates.
2. Cesium layers **diff against entity ids**: existing hospital entities keep their `CallbackProperty`; only **tween targets** update (heights ease to new RPI). Particle emission rates/colours and wind vector update in place. Arcs added/removed only when redistribution changes.
3. DOM chrome re-renders from the same store. Rankings, summary, drawer stay in sync automatically.

This diffing is why horizon switches, climate events, and Redirect all animate smoothly instead of flickering.

### 5.3 Streaming agent text (F25)

- Drawer opens / action fires → open `/agent/stream` SSE → append tokens to a typewriter component.
- As `drivers[]` are revealed, pulse the matching evidence chips on a fixed cadence (driven by structured data, not prose parsing).
- API down → backend streams the **templated** text the same way, so the motion survives.

---

## 6. Cross-cutting: data flow walkthroughs

### 6.1 One refresh cycle (steady state)
LAQN/Met Office poll → ExposureProvider (station→catchment IDW) normalises → RiskEngine computes RPI/drivers/curve → StateService assembles `/state` → SSE push → store diff → columns ease, haze drifts in real wind, ranking/summary update, F23 heartbeat pulses.

### 6.2 Climate-event button (F21)
User picks `heatwave` → frontend sets `episode=heatwave` on its `/stream` subscription → backend `ClimateEventInjector` perturbs the exposure input → **same** engine + agents + redistribution run → `/state` shows elevated RPI, the haze intensifies, scores cascade, chip flips to "simulated event — real response." Nothing downstream is special-cased.

### 6.3 Redirect climax (F26) — performance-safe
User clicks Redirect → backend returns `redistribution` with pre-resolved before/after RPI + arcs → frontend runs **one shared-clock timeline**: arcs spring in → columns ease (already-known target heights) → camera fly + orbit → DOM counter ticks. Client animates only between two known frames.

**60 fps budget:** ≤30 columns; particle count capped (a few thousand); arc segment counts modest; honour `prefers-reduced-motion` → instant states. Any single liveness feature can be disabled by a feature flag without breaking the rest. Test on the presenting laptop with the 3D tiles loaded (photoreal tiles are the heaviest GPU cost — profile early).

---

## 7. Configuration & secrets

```
# backend .env (never shipped to client)
ANTHROPIC_API_KEY=...
METOFFICE_API_KEY=...     # Met Office DataHub (temp + wind); LAQN/DEFRA are keyless open data
LIVE_DATA=true|false
SEED=1337                 # one seed drives all synthetic generators (reproducible demo)
REFRESH_SECONDS=300       # LAQN updates ~hourly; poll politely, cache, UI heartbeat is separate
COLUMN_ANCHOR=rooftop     # rooftop|floating — occlusion strategy (§2.2)

# frontend build-time (public, restricted-by-referrer)
VITE_CESIUM_ION_TOKEN=... # free, no card
VITE_GOOGLE_MAPS_KEY=...  # only for Photorealistic 3D Tiles route; needs billing; restrict to your domain
VITE_BACKEND_URL=...
```

Quotas to watch: **Google Photorealistic 3D Tiles** (Map Tiles API has usage billing — needs a card; keep the key referrer-restricted; have an offline screen-record as ultimate fallback for `DEMO_MODE`; or swap to free Cesium OSM Buildings), **Cesium Ion** (free tier fine for a demo, no card), **LAQN/DEFRA/Met Office** (open data; respect polite poll intervals + cache).

---

## 8. Project structure

```
ClimateHack/
  plan.md                  # product spec (source of truth for WHAT)
  ARCHITECTURE.md          # this file (HOW)
  data/
    effect_sizes.json      # build-time from System graph
    catchments.json        # build-time from GLA+Milliman+OSM
    scripts/               # prep scripts (run once)
  backend/                 # FastAPI: providers, engines, agents, /state, /stream
  frontend/                # Vite + React + Cesium (structure in §5.1)
```

---

## 9. Build order (Cesium-aware; refines `plan.md §10`)

1. **M1 — Stage + columns.** Cesium viewer + Google 3D tiles + camera; hardcoded columns (F4) with height-sampling + occlusion fixes (§2.2); DOM chrome shell. *Demoable: photoreal London with hospital columns.*
2. **M2 — Engine + evidence + state contract.** `catchments.json`, `effect_sizes.json`, RiskEngine, `/state`, SSE; F5 catchments, F9/F10/F11, F3, F22/F23. Synthetic exposures first. *Demoable: grounded explainable console.*
3. **M3 — Live + haze + injector.** LAQN/DEFRA + Met Office provider (air + temp + wind) with station→catchment IDW, F24 wind-driven particle haze emitting from real station points, F8 UKHSA alert, F21 injector. *Demoable: genuinely live, drifting.*
4. **M4 — Agents.** Briefing/Recommendation/Redistribution, `claude-sonnet-4-6` streaming, F25. *Demoable: streamed reasoning + plans.*
5. **M5 — Choreography.** F26 Redirect climax (arcs + column ease + camera orbit + counter), F27 explode, severity F14/F15. *Demoable: the full alive climax.*
6. **M6 — Polish + `DEMO_MODE`.** Motion timing, "simulated" tags, source tooltips, offline preset, screen-record fallback.

**Build the `/state` contract (§4.3) first** so frontend (Cesium) and backend can proceed in parallel. **Must-ship spine:** M1 + M2 + `DEMO_MODE` + a scripted Redirect. Live feeds (M3) are the "it's live" beat but the demo must never depend on them.
