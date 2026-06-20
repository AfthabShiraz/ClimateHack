# Crosssight — Backend Architecture

### The source of truth: live feeds → deterministic engine → agents that reason **and act**

> **Read this first.** This is the **current, authoritative** backend design. The root
> `../ARCHITECTURE.md` predates the product pivot and still describes Redirect arcs /
> redistribution / a particle haze — **those are removed**. Where the two disagree, *this
> document wins* for anything backend-, engine-, or agent-related. Product spec lives in
> `../plan.md`; datasets and effect-size config in `../data/`.

---

## 0. What changed (the pivot) and why the backend exists

The shipped product is **alert-centric**, not redirect-centric:

- **Core value = the early-warning ALERT** ("prepare in place"), matching the *Before — Prevent + Prepare* track. Redirect/Reallocate/arcs are gone.
- The demo is a **localised pollution plume that drifts** across a sequence of catchments; each pause invites the planner to open a hospital and watch the system respond.
- Agents don't just **reason** (the live thinking log) — they **act**: they draft a
  **Respiratory Readiness Alert** brief and, on **human approval**, **dispatch it by email**
  to the on-call supervisor. Sense → reason → act, with a human gate.

Right now **all of this is faked in the frontend**: `frontend/src/state/store.ts` holds the
risk engine, and `frontend/src/ui/ThinkingLog.tsx` is a templated stand-in for the agent.
The backend's job is to become the **single source of truth** so those become real:

| Concern | Today (frontend) | Target (backend) |
|---|---|---|
| Risk engine (RPI, bands, drivers) | `store.ts` helpers | `engine/risk.py` — canonical, from `effect_sizes.json` |
| Exposure / plume | `exposureAt()` Gaussian in `store.ts` | `providers/exposure.py` (live LAQN/Met Office) + `providers/injector.py` (episode) |
| Agent reasoning | `ThinkingLog.tsx` templated lines | `agents/reasoning.py` — Anthropic streaming |
| The deliverable (brief) | — (doesn't exist) | `agents/alert.py` — Respiratory Readiness Alert |
| The **act** (email) | — (doesn't exist) | `dispatch/email.py` + `dispatch/audit.py` |
| Severity mix | hardcoded in `Drawer.tsx` | `providers/severity.py` (Apollo) |

**Hard rule (unchanged):** the browser never calls a data feed or Anthropic directly. All
external calls go through FastAPI; keys stay server-side; no CORS to third parties. The
frontend talks only to our backend.

---

## 1. The two clocks (the one architectural seam that matters)

The map animates at 60fps; the truth changes in discrete steps. Keep them separate.

- **Backend = discrete state frames (truth).** For a given plume centre (or live reading),
  the backend computes one authoritative `/state` snapshot: every hospital's RPI, band,
  drivers, curve, severity. It does **not** animate.
- **Frontend = continuous animation between frames.** `CesiumMap.tsx` already eases the plume
  dome between epicentres and tweens column heights. When a drift completes (`arrive()`), the
  client adopts the next authoritative frame.

This is why the demo stays smooth *and* real: the agent reasoning and the engine numbers are
genuine backend output; only the in-between motion is interpolation. It mirrors the old
"animate between two known frames" rule, now applied to plume drift instead of arcs.

**Episode resolution:** when `Simulate episode` is pressed, the backend resolves the **whole
plume sequence up front** (one frame per epicentre in `SEQUENCE`). The client then walks the
frames as the user clicks `Continue simulation →`. No mid-animation recompute, no live
dependency during the climax.

---

## 2. High-level architecture

```
┌─ BROWSER (React + Vite + Cesium) ────────────────────────────────────────────┐
│  CesiumMap  TopBar  LeftRail  RightPanel  Drawer(+ThinkingLog)                 │
│        │ GET /state        │ SSE /stream        │ SSE /agent/stream            │
│        │ GET /episode      │ POST /alert/draft  │ POST /alert/dispatch         │
└────────┼───────────────────┼────────────────────┼────────────────────────────┘
         ▼                   ▼                    ▼
┌─ BACKEND (FastAPI) ───────────────────────────────────────────────────────────┐
│  routes/ ── services/state.py (StateService: assembles /state)                  │
│                 │                                                               │
│                 ├─ providers/exposure.py ─► LAQN/DEFRA (air) + Met Office       │
│                 │        │                   (heat+wind) + UKHSA (alert)        │
│                 │        └─ providers/injector.py  (episode plume + drift)      │
│                 ├─ engine/risk.py  (RPI, band, drivers, curve)  ◄─ effect_sizes │
│                 ├─ engine/demand.py (projectedDemand, surge headroom)           │
│                 ├─ providers/severity.py ─► Apollo COPD profiles                │
│                 │                                                               │
│                 ├─ agents/reasoning.py ─► Anthropic (stream → thinking log)     │
│                 ├─ agents/alert.py     ─► Anthropic (Readiness Alert brief)     │
│                 └─ dispatch/email.py + dispatch/audit.py  (ACT: send + log)     │
│                                                                                 │
│  data_loader.py ◄─ ../data/catchments.json + ../data/effect_sizes.json          │
│  Caches: last-good /state · agent cache · feed response cache                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

Two clean seams: **(a)** frontend ⇄ backend via `/state` + SSE; **(b)** runtime ⇄ build-time
via committed JSON (`effect_sizes.json`, `catchments.json`) — heavy dataset wrangling never
happens live.

---

## 3. Every on-screen element → its backend source (complete mapping)

The renderer is dumb. Every number/string below originates in the backend. ★ = **new UI
element to add** for the agent-act feature (see §6).

| UI element | Component | Backend source |
|---|---|---|
| Brand / subtitle | `TopBar` | static |
| UKHSA alert strip ("No active alert") | `TopBar` | `/state.ukhsaAlert` ← `exposure.py` (UKHSA) |
| Projection `Now / +3d / +7d` | `TopBar` | `/state?horizon=` → `risk.py` curve + horizon scaling |
| `Simulate episode` | `TopBar` | `GET /episode/start` → `injector.py` resolves the frame sequence |
| `Continue simulation →` / `Plume X/N` | `TopBar` | client walks pre-resolved frames; `injector.py` owns `SEQUENCE` |
| `Reset` | `TopBar` | `GET /episode/reset` → back to live/baseline frame |
| Mode chip `LIVE / SYNTHETIC / MIXED` | `TopBar` | `/state.mode` |
| Heartbeat | `TopBar` | `/stream` SSE refresh tick |
| Exposure selector (pm25/no2/o3/heat/combined) | `LeftRail` | `/state?exposure=` → `exposure.py` per-pollutant field |
| Map-layer toggles | `LeftRail` | client-only render toggles (no backend) |
| RPI legend (bands) | `LeftRail` | static; thresholds from `effect_sizes.json.bands` |
| City pressure red/amber/green counts | `RightPanel` | derived from `/state.hospitals[].band` |
| Risk ranking list | `RightPanel` | `/state.hospitals[]` sorted by `rpi` |
| Hospital columns (height + colour) | `CesiumMap` | `/state.hospitals[].rpi` / `.band` |
| Plume dome (position) | `CesiumMap` | `/state.exposureField.center` ← `injector.py` |
| Alert beacons (red glow) | `CesiumMap` | `hospitals[].rpi >= bands.red` |
| Selection ring / halo / fly-to | `CesiumMap` | client selection only |
| Drawer name / trust / RPI band | `Drawer` | `/state.hospitals[]` |
| Lead-time badge (`+5 days`) | `Drawer` | `risk.py` lag-kernel peak → `leadTimeDays` |
| Driver breakdown (term, studies, effect size, vuln, demand) | `Drawer` | `/state.hospitals[].drivers[]` (`risk.py` + `effect_sizes.json`) |
| Agent reasoning stream | `ThinkingLog` | `SSE /agent/stream?type=reasoning` ← `agents/reasoning.py` |
| Recommended preparation list | `ThinkingLog` | structured tail of the agent output / `alert.py` |
| Severity mix (resp/gen/icu, LOS) | `Drawer` | `/state.hospitals[].severityMix` ← `severity.py` (Apollo) |
| ★ `Generate readiness alert` | `Drawer` | `POST /alert/draft` → `agents/alert.py` (the deliverable) |
| ★ Brief preview (situation/evidence/impact/prep/sources) | `Drawer`/modal | response of `/alert/draft` |
| ★ `Dispatch to supervisor` + recipient | `Drawer`/modal | `POST /alert/dispatch` → `dispatch/email.py` |
| ★ `✓ Sent 08:01` confirmation + dispatch log | `Drawer`/modal | `dispatch/audit.py` (governance + measurement) |

No UI region is left without a backend source; no backend field is unused.

---

## 4. The `/state` contract (what the renderer consumes)

This is the canonical payload. It is a trimmed, alert-centric version of the old
`ARCHITECTURE.md §4.3` — **no `redistribution`/`arcs`**, **plus** `exposureField.center`
(plume) and `leadTimeDays`. Field names match `frontend/src/state/store.ts` where possible so
the swap from client-computed to backend-served is mechanical.

```jsonc
{
  "generatedAt": "ISO-8601",
  "mode": "LIVE" | "SYNTHETIC" | "MIXED",
  "horizon": "now" | "3d" | "7d",
  "sources": [
    { "name": "LAQN",       "status": "live|stale|down", "lastUpdated": "ISO", "simulated": false },
    { "name": "Met Office", "status": "live|stale|down", "lastUpdated": "ISO", "simulated": false }
  ],
  "wind": { "dirDeg": 0-360, "speedMs": 0, "simulated": false },
  "ukhsaAlert": { "level": "none|yellow|amber|red", "type": "heat|cold", "source": "UKHSA" },

  "episode": {                       // null when live/steady-state
    "active": true,
    "name": "pm25_spike",
    "index": 0, "total": 4,
    "simulated": true,               // ← "simulated cause, real response"
    "sequence": ["st-thomas", "kings-denmark-hill", "royal-london", "newham"]
  },
  "exposureField": {
    "center": { "lon": -0.118, "lat": 51.498 } | null,   // plume epicentre for this frame
    "stations": [ { "lat","lon","value":0-1,"pollutant","station","simulated" } ]
  },

  "hospitals": [{
    "id","name","trust","lat","lon","roadside",
    "exposure": 0-1,                 // value at this frame (post-plume)
    "rpi": 0-100, "band": "green|amber|red",
    "topDriver": "pm25|no2|roadside|heat",
    "leadTimeDays": 5,              // lag-kernel peak; powers the Drawer badge
    "drivers": [ { "term","exposureLevel","effectSize","numStudies",
                   "highestCited","sourceRowId","substituted",
                   "vulnerabilityWeight","contribution" } ],
    "curve": [ { "dayOffset":0-7, "rpi" } ],
    "vulnerabilityWeight": 0.85-1.40,
    "population":  { "value", "simulated": true, "method" },   // demand layer only — NOT in RPI
    "capacity":    { "value", "simulated": true },
    "demandBaseline": { "value", "simulated": true },
    "projectedDemand": { "value", "simulated": true },         // = baseline × (1 + demandSensitivity × rpi/100)
    "surgeCapacity": { "value", "simulated": true },
    "severityMix": { "respWardPct","generalPct","icuPct","avgLOS","simulated": true }
  }]
}
```

> **Honesty invariants** (judges will probe these): RPI is **per-capita** — population is in
> the demand layer, never in the score. Anything synthetic carries `simulated:true`. Air
> horizons are a **projection**, never a "forecast/prediction". Episode frames are tagged
> `simulated:true` while the engine/agent response to them is genuine.

---

## 5. Backend modules (responsibilities + key signatures)

Pure/deterministic and I/O are kept apart so the engine is testable and the demo is robust.

- **`config.py`** — env-driven settings (`LIVE_DATA`, `SEED`, `REFRESH_SECONDS`, keys,
  `DISPATCH_ENABLED`, `DISPATCH_TO`). One `SEED` drives all synthetic generators → reproducible.
- **`data_loader.py`** — loads & validates `../data/catchments.json` + `effect_sizes.json` once
  at startup; exposes typed catchment + effect-size config.
- **`models.py`** — Pydantic models for the entire `/state` contract (§4) and the agent/dispatch
  request-response bodies. Single schema definition shared by every route.
- **`providers/exposure.py`** — `ExposureProvider`: live LAQN/DEFRA air + Met Office heat/wind +
  UKHSA alert → per-catchment exposure via **IDW (k=3, power=2)** to the centroid; synthetic
  fallback (seeded) when a feed is down → `mode` becomes `MIXED`/`SYNTHETIC`.
  `get_exposures(horizon, pollutant) -> {hospitalId: ExposureLevel}` + `wind` + station points.
- **`providers/injector.py`** — `ClimateEventInjector`: owns `SEQUENCE` + plume params
  (`magnitude`, `sigmaDeg`) and the Gaussian `exposure_at(hospital, center)` (the canonical
  version of the frontend's `exposureAt`). `resolve_episode(name) -> [Frame...]` produces one
  exposure frame per epicentre. Applied **at the input layer only** — engine/agents are
  identical for live vs simulated.
- **`engine/risk.py`** — `RiskEngine`, **pure, no I/O**. `compute(exposures, effect_sizes,
  catchments, horizon) -> {hospitalId: HospitalRisk}` with `rpi`, `band`, `drivers[]`, `curve[]`,
  `leadTimeDays`. Canonical RPI = `100 × clamp(rawScore/referenceRaw, 0, 1)`,
  `rawScore = Σ(exposure × effectSize × vulnerabilityWeight)` over the **non-overlapping** term
  set (PM2.5 resp / NO₂ asthma / roadside asthma *substitutes* NO₂ / heat). Lag kernel → curve →
  `leadTimeDays`.
- **`engine/demand.py`** — `projectedDemand = baseline × (1 + demandSensitivity × rpi/100)`,
  `surgeCapacity`, headroom. Demand layer only; never feeds RPI.
- **`providers/severity.py`** — `SeverityProvider`: Apollo COPD profiles → `severityMix` per
  hospital (clinical texture, not a predictor).
- **`agents/client.py`** — thin Anthropic wrapper (`claude-sonnet-4-6`), streaming + non-stream,
  timeout, retry; **templated fallback** when no key / timeout so motion never dies.
- **`agents/prompts.py`** — context assembly: pulls the *relevant* slice for one hospital
  (its drivers + effect-size citations from System graph, its Milliman vulnerability, its Apollo
  severity, its demand gap) into a compact prompt. The reasoning and brief share this context.
- **`agents/reasoning.py`** — streams the live thinking log (replaces `ThinkingLog.tsx` lines)
  and a structured `recommendedPreparation[]` tail.
- **`agents/alert.py`** — produces the **Respiratory Readiness Alert** brief (the concrete
  deliverable): severity, lead time, situation, evidence (with citations), projected impact,
  recommended preparation, sources. Returns structured JSON + rendered text.
- **`dispatch/email.py`** — the **act**: sends the brief by email via **Gmail SMTP (app
  password)** — `send_alert(to, subject, body) -> DispatchResult`. Guarded by `DISPATCH_ENABLED`
  and **human approval** (only fires on `POST /alert/dispatch`, never autonomously).
- **`dispatch/audit.py`** — append-only dispatch log (who/when/which hospital/recipient/message
  id). Powers the confirmation chip and the "alerts dispatched" measurement metric, and is the
  governance/audit trail for the ethics story.
- **`services/state.py`** — `StateService.build(horizon, exposure, episode) -> State`: orchestrates
  exposure → engine → demand → severity into one `/state`; persists last-good to disk; serves it
  if a live build fails.

---

## 6. The agent **act** feature (new) — flow + UI

The wow factor: the agent completes the loop **sense → reason → act**, governed by a human gate.

```
Drawer (a red hospital is selected)
  │  reasoning already streamed (ThinkingLog)
  ▼
[★ Generate readiness alert]  ──POST /alert/draft──►  agents/alert.py
  │                                                    (real claude-sonnet-4-6 call,
  ▼                                                     or pre-baked real output in DEMO_MODE)
Brief preview  (situation · evidence+citations · projected impact · prep · sources)
  │   recipient = DISPATCH_TO (demo: your inbox = stand-in supervisor)
  ▼
[★ Dispatch to supervisor]   ──POST /alert/dispatch──►  dispatch/email.py  (Gmail SMTP)
  │                                                      dispatch/audit.py  (log)
  ▼
✓ Sent 08:01 · logged    ← confirmation chip from audit
```

Design decisions (these are the defensible ones for judging):

1. **Human-in-the-loop, always.** The agent *drafts*; a person clicks *Dispatch*. The backend
   refuses to send without that explicit call. This matches `../SUSTAINABILITY_ETHICS.md`
   ("recommends, never acts autonomously") and turns a potential ethics risk into an ethics win.
2. **Real send, safe target.** For the demo it emails `DISPATCH_TO` (your own inbox as the
   stand-in on-call respiratory lead). Honest framing in the UI: *"in production this routes to
   the on-call supervisor."*
3. **Gmail SMTP + app password** (stdlib `smtplib`, no OAuth dance) — fastest reliable path.
   Resend/SendGrid are drop-in alternatives behind the same `dispatch/email.py` interface.
4. **Auditable.** Every dispatch is logged → confirmation chip + a countable
   "alerts dispatched / acted on" metric (measurement bonus).
5. **DEMO_MODE safety.** `/alert/draft` can return a **pre-baked real** brief (generated once
   with the real model, committed to `../data/alerts.json`) so the climax never depends on a live
   API call; `DISPATCH_ENABLED=false` no-ops the send and just logs (dry-run for rehearsal).

**Frontend additions required** (small, in `Drawer.tsx`): a `Generate readiness alert` button,
a brief preview block, a `Dispatch to supervisor` button + recipient line, and a sent-confirmation
chip. State for these lives alongside the existing drawer state.

---

## 7. API endpoints

```
GET  /health                         → liveness + per-source live/stale/down
GET  /state?horizon=&exposure=       → one authoritative snapshot (§4)
GET  /stream            (SSE)        → emits a fresh /state each refresh tick (heartbeat)
GET  /episode/start?name=pm25_spike  → resolve + return the full plume frame sequence
GET  /episode/reset                  → return to the live/baseline frame
GET  /agent/stream?type=reasoning&hospitalId=&horizon=   (SSE) → token stream + structured tail
POST /alert/draft     {hospitalId, horizon}              → Respiratory Readiness Alert brief
POST /alert/dispatch  {hospitalId, to, subject, body}    → send (human-approved) + audit entry
```

CORS is open **only** to the Vite dev origin. No third-party CORS — the browser never leaves
our backend.

---

## 8. Config & secrets (`backend/.env`, never shipped to client)

```
ANTHROPIC_API_KEY=...          # agent layer
METOFFICE_API_KEY=...          # heat + wind (LAQN/DEFRA are keyless open data)
LIVE_DATA=true|false           # false → all-synthetic (offline DEMO_MODE)
SEED=1337                      # one seed → reproducible synthetic demo
REFRESH_SECONDS=300            # polite poll; UI heartbeat is separate

# agent-act / dispatch
DISPATCH_ENABLED=true|false    # false → dry-run (log only, no real email)
GMAIL_USER=you@gmail.com       # sender (Gmail SMTP)
GMAIL_APP_PASSWORD=...         # 16-char app password (NOT your account password)
DISPATCH_TO=you@gmail.com      # demo recipient = stand-in on-call supervisor
```

(Frontend keys — `VITE_CESIUM_ION_TOKEN`, `VITE_GOOGLE_MAPS_KEY`, `VITE_BACKEND_URL` — stay in
`frontend/.env`.)

---

## 9. Build order (when we implement for real)

The contract (§4) is frozen first so frontend and backend proceed in parallel.

1. **B1 — Skeleton + contract** *(this scaffold)*: FastAPI boots, `/state` returns
   contract-shaped synthetic data mirroring `store.ts`. Frontend can point at it immediately.
2. **B2 — Engine + episode**: port `risk.py`/`demand.py`/`injector.py` from `store.ts` (canonical
   from `effect_sizes.json`); `/episode/start` resolves the drift frames.
3. **B3 — Live feeds**: `exposure.py` (LAQN/DEFRA + Met Office + UKHSA) with IDW + synthetic
   fallback; `/stream` heartbeat; `mode` reflects real source health.
4. **B4 — Agents (reason)**: `agents/*` streaming; `/agent/stream` replaces `ThinkingLog` lines.
5. **B5 — Agents (act)**: `agents/alert.py` brief + `dispatch/email.py` + `audit.py`; the
   `Drawer` act buttons; pre-bake `../data/alerts.json` for DEMO_MODE.
6. **B6 — Polish**: caching, last-good `/state`, `simulated` tags end-to-end, dry-run rehearsal.

**Must-ship spine:** B1 + B2 + the frontend already working + DEMO_MODE. Live feeds (B3) and the
agent-act climax (B5) are the headline beats but the demo must never *depend* on a live call.
