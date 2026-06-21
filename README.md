# Crosssight

**See the wave before it breaks.**

Crosssight is a live respiratory-readiness console for London hospital and ICB planners. It turns live air quality, heat, and vulnerability data into an explainable **Respiratory Pressure Index (RPI)** per hospital catchment, then uses AI agents to reason about risk and draft **Respiratory Readiness Alerts** — with human approval before dispatch.

Built for the **HealthInClimate London 2026** hackathon (*Before — Prevent + Prepare*).

![Crosssight screenshot](Screenshot%202026-06-20%20at%2015.35.22.png)

## What it does

- **Maps risk on a 3D London view** — photorealistic Cesium map with exposure plume, hospital columns, and catchment overlays
- **Computes RPI deterministically** — live exposure × published effect sizes × vulnerability (no black-box ML predictor)
- **Ingests real datasets** — LAQN air quality, Met Office heat/wind, UKHSA health alerts, Apollo severity profiles
- **Simulates drifting pollution episodes** — step through a plume sequence across catchments
- **Agents reason and act** — streaming reasoning log, alert brief drafting, and optional email dispatch with audit trail

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite, TypeScript, CesiumJS, Zustand |
| Backend | Python, FastAPI, SSE |
| Agents | Anthropic API (streaming) |
| Data | Committed JSON + live feed polling |

## Quick start

### Prerequisites

- Node.js 18+
- Python 3.11+
- [Cesium Ion](https://ion.cesium.com) token (free) for the 3D map
- Optional: Google Maps API key with Map Tiles API for photorealistic tiles; without it, the app falls back to Cesium OSM Buildings

### 1. Clone and configure

```bash
git clone https://github.com/AfthabShiraz/ClimateHack.git
cd ClimateHack
```

**Frontend** — copy `frontend/.env.example` to `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
# Set VITE_CESIUM_ION_TOKEN (required for 3D map)
# Optionally set VITE_GOOGLE_MAPS_KEY for photorealistic tiles
```

**Backend** — copy `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
# Set ANTHROPIC_API_KEY for live agent reasoning
# Set LIVE_DATA=true to poll real feeds (false = synthetic offline mode)
```

### 2. Run the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8008
```

API docs: [http://localhost:8008/docs](http://localhost:8008/docs)

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend falls back to seed data if the backend is unreachable, but full agent and dispatch flows require the API.

## Demo flow

1. Open the map — hospitals appear as coloured columns (green / amber / red by RPI band).
2. Click **Simulate episode** to start a drifting pollution plume across catchments.
3. Open a hospital from the left rail — view drivers, severity mix, and the agent thinking log.
4. Draft a **Respiratory Readiness Alert** and review the brief.
5. Approve dispatch to send (or dry-run log) the alert email.

## API overview

| Endpoint | Description |
|---|---|
| `GET /state` | Current risk snapshot for all hospitals |
| `GET /stream` | SSE stream of state updates |
| `GET /episode/start` | Begin a simulated plume episode |
| `GET /agent/stream` | SSE stream of agent reasoning tokens |
| `POST /alert/draft` | Draft a readiness alert brief |
| `POST /alert/dispatch` | Dispatch alert email (human-approved) |
| `GET /health` | Service health and feed status |

## Project structure

```
ClimateHack/
├── frontend/          # React + Cesium UI
├── backend/           # FastAPI risk engine, feeds, agents, dispatch
├── data/              # Catchments, effect sizes, alerts, build scripts
├── plan.md            # Product specification
├── ARCHITECTURE.md    # System architecture (rendering + data layers)
└── SUSTAINABILITY_ETHICS.md
```

## Data sources

Crosssight is built on the hackathon-provided datasets:

- **LAQN / DEFRA** — London air quality (PM2.5, NO₂, O₃)
- **Met Office** — temperature and wind
- **UKHSA** — heat/cold health alerts
- **Apollo** — COPD severity profiles
- **GLA / Milliman / OSM** — vulnerability, demographics, hospital geometry
- **System climate research graph** — published effect sizes (`data/effect_sizes.json`)

Offline data is pre-built via scripts in `data/scripts/`.

## Documentation

- [`plan.md`](plan.md) — full product spec and feature map
- [`backend/README.md`](backend/README.md) — authoritative backend architecture (feeds, engine, agents, dispatch)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — rendering stack and system overview
- [`SUSTAINABILITY_ETHICS.md`](SUSTAINABILITY_ETHICS.md) — sustainability and ethics notes for judging

## Design principles

- **No predictive ML on admissions** — the provided clinical datasets cannot be backtested for pollution→admissions signal; the engine uses transparent arithmetic instead.
- **Backend is source of truth** — the browser never calls external feeds or Anthropic directly.
- **Human gate on action** — agents draft alerts; a planner approves before email dispatch.
- **Graceful degradation** — synthetic mode, cached state, and map fallbacks keep the demo runnable offline.

## License

Hackathon project — see repository for details.
