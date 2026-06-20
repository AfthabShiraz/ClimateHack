# Crosssight — London Respiratory Readiness Console
### Build specification & handoff document for Claude Code

> **What this document is.** A complete, opinionated specification for an agentic-AI, climate-health product built for the HealthInClimate London 2026 hackathon (track: **Before — Prevent + Prepare**). It describes exactly what the product does, every feature, the exact UI element each feature maps to, the precise user flow, the datasets, and the build priority order. It is written to be handed to Claude Code, which should treat it as the source of truth and refine it into a technical implementation plan.
>
> **Product name:** **Crosssight**. Tagline: *"See the wave before it breaks."*
>
> **Naming consistency (resolved):** The product has exactly **one** name in code and UI: **Crosssight**. Use it everywhere — component names, the logo slot (§7 TOP BAR), the demo script, and any window/title strings. Never ship a second name on screen.
>
> **Authority note:** Where any statement below conflicts with **§13 (Engineering Hardening — Resolved Decisions)**, §13 wins. §13 is the foolproofing layer added after the original spec and resolves its ambiguities with concrete, build-ready choices.

---

## 0. The single most important design constraint (READ FIRST)

We empirically tested the two provided clinical datasets (Apollo COPD, Milliman utilization) for a pollution→admissions signal. **There is none** — correlation between air quality / heat and admissions is ~0.00 in both, because the de-identification / synthetic generation destroyed the cross-variable relationships. **Do not build a machine-learning model that predicts admissions from environmental data. It will produce a flat backtest and fail live.**

Instead, the product core is a **transparent risk calculation** (arithmetic over observable facts × published effect sizes) plus an **AI agent reasoning layer**. Nothing load-bearing is a fitted predictive model. This is a deliberate robustness decision and is also our honesty story to judges. Every feature below respects this constraint.

**Consequences for the build:**
- The "intelligence" of the product comes from (a) an evidence-grounded risk formula and (b) LLM agents that reason, explain, and plan — not from a trained predictor.
- The Apollo and Milliman datasets are used for the jobs they *can* do (clinical texture, vulnerability indices), never as a climate predictor.
- Every risk number on screen must be traceable to its inputs and a cited study. No black boxes.

---

## 1. The problem (one paragraph)

Air pollution and heat drive a predictable, repeating wave of respiratory emergencies — mostly COPD and asthma exacerbations, concentrated in older and more deprived populations — into hospitals, days after conditions worsen. The relationship is established in the research literature. Yet hospitals typically react only once beds are full. There is a lead-time gap of days that nobody operationalises. Crosssight closes that gap: it converts live environmental conditions + population vulnerability + the published evidence base into an early, explainable, actionable hospital-readiness plan.

---

## 2. What the product IS (precise definition)

A **live, single-screen web console** for a London hospital-network / ICB planner. It continuously computes, per hospital catchment, a **per-capita respiratory-pressure index (RPI)** over a short projection horizon (default 7 days), driven by live air quality and heat, weighted by population vulnerability, scaled by published effect sizes; population feeds a separate demand layer, not the index. It then uses AI agents to (a) explain each pressure score with cited evidence, and (b) generate a three-tier action plan: **Alert → Reallocate → Redirect**. The whole thing renders on a 3D map of London where the motion is the model thinking, not decoration.

**It is NOT:** a predictive ML model, a historical replay slider, a generic dashboard of red numbers, or a city-wide coordination platform requiring multi-trust adoption.

---

## 3. How it works — the engine (non-technical)

Three layers, in order of data flow.

### 3.1 The Risk Engine (deterministic, transparent — the spine)
For each hospital catchment, every refresh cycle, compute a **per-capita intensity** raw score, then normalise it to the **Respiratory Pressure Index (RPI)**:

```
rawScore(hospital) =
    Σ over each canonical term T in {PM2.5→resp, NO2→asthma, heat→stress} of:
        ExposureLevel(T, catchment, live)        # from live feeds, normalised 0–1
      × EffectSize(T)                             # relative weight from System research graph
      × VulnerabilityWeight(catchment)            # from GLA + Milliman indices, 0.5–1.5

RPI(hospital) = 100 × clamp( rawScore(hospital) / referenceRaw , 0, 1 )
```

- **Per-capita intensity, NOT volume.** RPI deliberately **excludes population** — it measures *how pressured each person in the catchment is*, so column height is comparable across large and small catchments. Population is a separate **demand-layer** quantity (§13.1/§13.4), modelled as `population: { value, simulated: true, method }` and surfaced with a "simulated" tag. The ranking/summary may note raw volume separately, but it never enters RPI.
- **Deterministic.** No training. Same inputs → same output. Cannot fail a backtest because there is no fitted parameter.
- **Traceable.** Every term is displayable. Click any score → see the three multiplicands (exposure × effect size × vulnerability) and the cited study behind the EffectSize.
- **Fixed absolute calibration.** `referenceRaw` is a fixed constant (stored in `data/effect_sizes.json` under `rpiCalibration.referenceRaw`), NOT a live min/max — so a calm network reads low/green and screenshots stay comparable across refreshes. See §13.1.
- **O₃ is visual-only** — it never enters the sum (§13.2/§13.7); its toggle changes the haze visualisation only.
- **Horizon** is a simple forward projection: apply the established exposure→outcome lag (literature says effects appear within days) so today's air produces a pressure curve over the next N days.

> ⚠️ **This formula is intentionally schematic. Before building it, read §13.1–§13.4**, which resolve the things this block leaves ambiguous and which will otherwise break the build: (1) what RPI is and how it's calibrated against the **fixed absolute `referenceRaw`** (not relative min/max) to a comparable 0–100 band; (2) what `EffectSize` actually *means* (it is a **relative weight**, not an epidemiological relative risk) and which exact term set to use to **avoid double-counting** (incl. roadside *replacing* the base NO₂→asthma term, not adding to it); (3) how `ExposureLevel` is normalised against **absolute health thresholds** (not relative min/max); (4) the **lag kernel + forecasted exposures** that make the horizon a real projection rather than a flat copy of today; plus how **population** and **projectedDemand** live in the demand layer (§13.1/§13.4), kept out of the per-capita RPI.

### 3.2 The Evidence Layer (System research graph — grounds every number)
The `EffectSize` values are NOT invented. They come from the System climate research graph — real aggregated effect sizes across many peer-reviewed studies. Examples actually present in the data (use these exact values):

| Exposure → Outcome | # Studies | Median Effect Size | In canonical set? | Use |
|---|---|---|---|---|
| air pollution → respiratory disease | 13 | 0.060 | ✅ **yes** | core PM2.5 → COPD/respiratory term |
| nitrogen dioxide → asthma | 62 | 0.127 | ✅ **yes (non-roadside catchments)** | NO₂→asthma term; the single NO₂→asthma term per catchment, **replaced** by the roadside row where `roadside=true` |
| traffic-related pollution → asthma | 29 | 0.296 | ✅ **yes (roadside catchments)** | the NO₂→asthma term **for roadside catchments** — used **instead of** the base NO₂ row, not in addition (§13.2/D5) |
| extreme heat → mortality rate | 13 | 0.347 | ✅ **yes (heat-stress modifier, gated)** | **heat-stress modifier** — uses extreme-heat→mortality as a **proxy** for acute heat burden on respiratory-vulnerable populations (distinct outcome; flagged honestly, §13.2/F11); applied only above heat threshold (§13.3) |
| air pollution → mortality rate | 66 | 0.067 | ⛔ no — **overlaps** respiratory term | display-only provenance ("66 studies" broader air-pollution evidence) |
| air pollution → asthma | 56 | 0.127 | ⛔ no — overlaps NO₂/PM asthma | display-only |
| temperature → mortality rate | 75 | 0.249 | ⛔ no — superseded by extreme-heat term | display-only |
| air pollution → cardiovascular disease | 19 | 0.077 | optional secondary | off by default; toggle as a separate cardiac sub-index |

> **Double-counting fix (critical):** the engine sums **only the ✅ canonical set** — **one term per (pollutant → outcome) pair per catchment**, chosen to be mutually non-overlapping. Note the NO₂→asthma pair has **exactly one term per catchment**: the base `nitrogen dioxide → asthma` (0.127) for normal catchments, *replaced by* `traffic-related pollution → asthma` (0.296) where `roadside=true` (it is a **replacement, never additive** — see D5/§13.2). The greyed-out rows are NOT summed (summing "air pollution → mortality" *and* "air pollution → respiratory disease" double-counts the same PM2.5 effect). They remain available as **provenance/citation chips** in F11 (e.g. the headline "66 studies" broader-evidence stat) but never enter the arithmetic. The heat row is summed as a **heat-stress modifier** using the extreme-heat→mortality effect as a transparent **proxy** (§13.2). See §13.2 for the exact term→exposure binding. **O₃ is not in the canonical set at all** — it is visual-only (§13.7) and never enters the sum.
>
> **Before hardcoding these numbers:** verify each row exists with these values in the actual System graph at build time (M2 first task). The exact medians may differ from this shortlist; the *structure* (which terms, non-overlapping) is what matters. If a value is absent, log it and fall back to the nearest available term — and **surface that substitution on screen** ("substituted evidence term", F11/source chip, N5/§13.12) — never silently invent one.

Each effect size carries `numStudies` and `highestCited` — surface these as the provenance ("based on N studies"; show "top study cited ×N" only when `highestCited` is available, since it may be null in the stub — see C2/§F11). `highestCited` may be null; render the citation-count clause conditionally.

### 3.3 The Agent Layer (LLM reasoning — the "intelligence", robust by construction)
Three agent roles. Each reasons over real inputs and **never predicts a number it could get wrong** — it explains, synthesises, and plans.

1. **Briefing Agent** — reads the current PressureScores + which exposures drove them + the cited evidence, and writes a plain-English situational briefing per flagged hospital. ("Pollution in Newham's catchment is elevated; given its large elderly and COPD-prevalent population and the established air-pollution→respiratory effect [13 studies], expect elevated respiratory presentations over the next 5–7 days.")
2. **Recommendation Agent** — for each flagged hospital, produces concrete prepare actions (oxygen pre-positioning, respiratory ward staffing, proactive high-risk patient outreach), each with a one-line justification and its evidence citation.
3. **Redistribution Agent** — given which hospitals are over-pressure and which have headroom, generates the Reallocate and Redirect plans (which neighbours absorb load, suggested ambulance-conveyance steering), justified in plain language.

> Implementation note: agents call the Anthropic API. Use `claude-sonnet-4-6`. Feed them structured JSON (scores, drivers, evidence rows) and require structured + prose output. They format reasoning, they do not compute the risk scores.

---

## 4. The datasets — and the exact job each one does

> Each dataset is used ONLY for the job it can actually support. Do not ask a dataset to do something its data doesn't contain.

| Dataset | Role in product | Why this and not more | Link |
|---|---|---|---|
| **System climate research graph** (repo) | **Evidence engine.** Supplies every `EffectSize` and its provenance (`numStudies`, citations). The single most important dataset. | Only source here with real, quantified climate→health relationships. | `github.com/healthinclimateai/london2026-datasets/tree/main/datasets/system` |
| **London Air (Imperial LAQN)** | **Live trigger.** Real ~15-min PM2.5 / NO₂ / O₃ per station → `ExposureLevel`. Makes it live & local. | Best real-time open London air feed, no auth. | `https://www.londonair.org.uk/` · API: `https://www.londonair.org.uk/Londonair/API/` |
| **DEFRA UK-AIR (AURN)** | **Air backup / wider coverage** for `ExposureLevel`. | Authoritative national network; `pyaurn` access. | `https://uk-air.defra.gov.uk/data/` |
| **Met Office** | **Heat/weather signal** feeding the temperature/heat exposure term. | Live obs + forecast; UKCP for context. | `https://www.metoffice.gov.uk/services/data` |
| **UKHSA Heat/Cold Health Alerts** | **Official alert status** shown as a banner; can gate/boost the heat term. | The recognised national alerting layer. | `https://ukhsa-dashboard.data.gov.uk/weather-health-alerts` |
| **GLA London Datastore** | **Vulnerability weighting** — borough demographics, elderly %, deprivation → `VulnerabilityWeight`; catchment populations (modelled as `population: { value, simulated: true, method }`, demand-layer only, UI-tagged simulated). | Authoritative borough-level London context. | `https://data.london.gov.uk/` |
| **Milliman** (repo) | **Supporting vulnerability reference** — real SVI-style indices (E_AGE65, E_NOVEH, E_UNEMP, E_CROWD, E_MINRTY) to shape/validate the vulnerability weighting. **NOT used as a climate predictor.** | Its env→admissions link is empirically absent; its vulnerability indices are real and useful. | `github.com/healthinclimateai/london2026-datasets/tree/main/datasets/milliman` |
| **Apollo COPD** (repo) | **Patient-level severity texture** — 70k synthetic COPD encounters (comorbidities, labs, LOS, ward type) power the "who needs a bed" layer with realistic clinical profiles. **NOT used as a climate predictor.** | Its env→admissions link is empirically absent; its clinical fields are internally coherent. | `github.com/healthinclimateai/london2026-datasets/tree/main/datasets/apollo_hospitals` |
| **OpenStreetMap UK** | **Hospital locations + road network** for map markers and Redirect routing. | Free, complete enough for London. | `https://download.geofabrik.de/europe/united-kingdom.html` |

**Sandbox/network note for Claude Code:** the build environment may not reach `londonair.org.uk`, `data.london.gov.uk`, etc. Implement every live feed behind an interface with (a) the real fetch implementation and (b) a realistic synthetic generator fallback, switchable by a `LIVE_DATA=true/false` env flag. The demo must never show a blank map because a feed was unreachable. GitHub-hosted repo datasets (System, Apollo, Milliman) are reachable and should be loaded for real.

---

## 5. SCOPE

### In scope (must exist)
- 3D London map console (single screen).
- Live (or synthetic-fallback) air + heat ingestion → Risk Engine → PressureScores per hospital catchment.
- Evidence layer wired from the System graph with visible provenance.
- Three agent roles producing briefings, recommendations, and the Alert/Reallocate/Redirect plans.
- The three-tier action flow with on-map visualisation (rings, headroom highlight, redirect arcs).
- Patient-severity drill-down powered by Apollo profiles.
- "Stress test" injector to guarantee a dynamic demo regardless of live conditions.
- Full traceability: any score → its four inputs + cited study.

### Out of scope (do NOT build)
- Any trained ML predictor of admissions from environment.
- Real-time live hospital bed/ED feeds (don't exist publicly — bed capacity is simulated/seeded, clearly labelled).
- Multi-user accounts, auth, persistence beyond a session.
- Mobile layout (desktop demo only).
- Real ambulance GPS (we show conveyance *recommendations*, not tracked vehicles).

### Honesty rules baked into the build (must hold on screen)
- Simulated/seeded values (bed capacity, projected demand, catchment populations — `population: {value, simulated:true, method}`) carry a small "simulated" tag.
- Apollo/Milliman never labelled as predicting admissions.
- Effect sizes always show their study provenance.

---

## 6. FEATURE → UI ELEMENT MAP (the core of this document)

> Rule: **every feature maps to exactly one primary UI element, and every UI element exists to serve a named feature.** If an element isn't in this table, don't build it. Layout regions referenced are defined in §7.

| # | Feature | What it does | Primary UI element | Region | Interaction |
|---|---|---|---|---|---|
| F1 | **3D London base map** | Spatial context; the stage. Photorealistic 3D base, ~50° pitch, Thames + borough context. | CesiumJS Viewer + Google Photorealistic 3D Tiles base (Cesium OSM Buildings fallback) | MAP | pan / rotate / zoom |
| F2 | **Live exposure field** | Renders current PM2.5/NO₂/heat as a drifting translucent field (green→red). The "weather" of risk. | Cesium ParticleSystem over MAP (advected by wind) | MAP | hover a cell → tooltip with pollutant + value + source station |
| F3 | **Exposure layer toggles** | Switch which exposure drives the field (PM2.5 / NO₂ / O₃ / Heat / Combined). **O₃ is visual-only** — it retints the haze but never changes scores (RPI excludes O₃, §3.1/§13.7). | Segmented control, 5 buttons (O₃ tagged "visual only") | LEFT RAIL top | click PM2.5/NO₂/Heat/Combined → field + scores recompute for that exposure emphasis; click O₃ → haze visualisation only, scores unchanged |
| F4 | **Hospital pressure columns** | One 3D extruded column per hospital; height = RPI (per-capita intensity, not volume), colour = severity band. This is the headline visual. | Cesium cylinder Entities (height = RPI via CallbackProperty) | MAP | hover → mini-card; click → opens Hospital Detail (F12) |
| F5 | **Catchment footprints** | Faint glowing ground polygon per hospital = population it serves; brightness scales with VulnerabilityWeight. Explains *why* a column is high. | Draped Cesium polygons (low opacity, classified onto 3D tiles) | MAP | toggle on/off via F6 |
| F6 | **Map layer panel + RPI colour legend** | Show/hide: exposure field, columns, catchments, arcs, hospital labels (labels owned here + F4 mini-cards). Also **owns the colour-blind-safe RPI band legend** (§13.1: green <40 / amber 40–70 / red >70). Keeps map legible. | Checklist of 5 layer toggles + RPI band legend | LEFT RAIL | click checkboxes; legend is passive reference |
| F7 | **Projection horizon control** | Sets projection window (Now / +3d / +7d). Columns re-height to projected pressure using literature lag. Copy always says "projection", never "forecast". | 3-stop horizon selector (NOT a scrub slider) | TOP BAR | click stop → columns animate to that horizon's projection |
| F8 | **UKHSA alert banner** | Shows current official Heat-/Cold-Health Alert level for London; contextualises the heat term. | Coloured status strip | TOP BAR | click → small popover with alert detail + source |
| F9 | **City pressure summary** | One-glance state of the network: # hospitals in red/amber/green, total projected excess respiratory demand, trend arrow. | Stat cluster (3–4 big figures) | RIGHT PANEL top | live-updates each cycle |
| F10 | **Risk ranking list** | Hospitals sorted by PressureScore, worst first; each row shows name, band chip, top driver exposure. The actionable worklist. | Scrollable ranked list of rows | RIGHT PANEL | click a row → flies map to that hospital + opens Detail (F12) |
| F11 | **Evidence/provenance popover** | Proves a score isn't a black box: shows the RPI multiplicands (exposure × effect size × vulnerability) plus the demand-layer population (tagged simulated) and the cited study. Copy: always "based on N studies"; show "top study cited ×N" **only when `highestCited` is available** (may be null in the stub, C2). If a System-graph row is missing and a nearest-term is used, show a **"substituted evidence term"** chip (N5). Heat term labelled a **heat-stress proxy** (D6). | Popover with breakdown + citation chips | overlays MAP/RIGHT | opens from any score's "ⓘ why?" affordance |
| F12 | **Hospital Detail drawer** | Deep view of one hospital: projected pressure curve over horizon, driver breakdown, the Briefing Agent text, recommended actions, severity mix. | Right-side slide-over drawer | DRAWER | opened by F4/F10; close returns to map |
| F13 | **Briefing Agent output** | Plain-English situational briefing for the selected hospital, evidence-cited. | Prose block inside F12, with citation chips | DRAWER | "regenerate" button re-runs agent |
| F14 | **Patient severity mix** | Uses Apollo profiles to show, within the expected wave, the split of likely severity / bed-need (e.g. % needing respiratory ward, est. avg LOS). Realistic clinical texture. | Small stacked bar + 3 stat chips, with a visible **"simulated cohort / Apollo-derived profiles, not a predictor"** tag beside every severity output (S13) | DRAWER | hover segment → definition; "simulated cohort" tag always shown |
| F15 | **Representative patient cards** | A few example Apollo-derived patient profiles ("78, COPD + heart disease, high exposure → likely 7+ day stay") to make severity tangible. | 2–3 compact profile cards, each carrying the **"simulated cohort / Apollo-derived profiles, not a predictor"** tag (S13) | DRAWER | click → expand comorbidities/labs |
| F16 | **ALERT action (tier 1)** | Marks flagged hospitals; emits prepare actions (oxygen, staffing, outreach) from Recommendation Agent, each justified + cited. | "Alert" button → warning rings on F4 columns + action list in DRAWER/RIGHT | TOP BAR action group + MAP | click → rings pulse, actions populate |
| F17 | **REALLOCATE action (tier 2)** | Finds neighbouring hospitals with headroom; highlights them; shows a sharing suggestion (staff/beds/oxygen). | "Reallocate" button → green highlight on headroom columns + **sharing suggestion list in RIGHT PANEL** (shown when Reallocate active) | TOP BAR action group + MAP + RIGHT | click → headroom columns brighten, sharing list appears in RIGHT PANEL |
| F18 | **REDIRECT action (tier 3)** | Generates optimal load-distribution from over-pressure hospitals to neighbours; draws animated arcs (particles flow red→green); over-pressure columns visibly shrink, headroom rise; shows before/after projected overflow. | "Redirect" button → Cesium polyline arcs (animated flow) + columns re-height + before/after counter | TOP BAR action group + MAP + RIGHT | click → arcs fire, counter animates 240→60 style |
| F19 | **Redistribution plan panel** | The Redirect Agent's written plan + per-arc detail (from→to, est. patients, conveyance note). | Expandable plan list keyed to arcs | RIGHT PANEL (replaces ranking while active) | hover a plan row → its arc highlights on map |
| F20 | **Overflow counter (before/after)** | The thesis-in-one-number: projected unmet respiratory demand before vs after redistribution. | Large animated dual figure — **primary home: RIGHT PANEL** (within the Redistribution plan panel) | RIGHT PANEL | animates on F18 |
| F21 | **Climate-event injector** | Injects a simulated climate event **at the exposure-input layer only** — it raises the live air/heat readings as if a real PM2.5 spike / heatwave / NO₂ inversion were occurring. The **entire real pipeline then responds authentically** (same risk engine, same agents, same redistribution) — nothing downstream is scripted. The *cause* is simulated; the *response* is real. Guarantees a dramatic demo even when live conditions are calm. Labelled "simulated event — real response". | "Simulate climate event" button + dropdown (PM2.5 spike / heatwave / NO₂ inversion) | TOP BAR right | click → exposure field intensifies & drifts; scores, agents, and actions cascade live from the injected conditions |
| F22 | **Live status / data-source chip** | Shows whether feeds are LIVE or SYNTHETIC, last-updated time, and lists active sources. Honesty + "it's live" proof. | Small status chip w/ tooltip listing sources | TOP BAR right corner | hover → source list + timestamps |
| F23 | **Refresh cycle indicator** | Subtle pulse each time the engine recomputes from new data, signalling "alive". | Thin progress tick / breathing dot | TOP BAR | passive |
| F24 | **Wind-driven exposure field** (enhances F2) | The pollution/heat haze **drifts in the real wind direction & speed** from the Met Office feed, so the field visibly moves the way London's actual air is moving. The single strongest "this is live, not a gif" signal. | Cesium ParticleSystem advected by the real wind vector (shares the F2 particle layer) | MAP | passive; direction/speed update each refresh; falls back to a gentle fixed drift if no wind feed |
| F25 | **Streaming agent reasoning** (enhances F13/F16) | When an agent runs, its text **streams in token-by-token** (typewriter) and the relevant **driver chips light up in sequence** as it "reads" them — judges literally watch the AI reason rather than seeing a finished block appear. | Streamed prose + sequential chip highlight in DRAWER/RIGHT | DRAWER / RIGHT | auto on agent run; "regenerate" re-streams; uses Anthropic streaming API |
| F26 | **Choreographed Redirect climax** (enhances F18/F20) | The money shot, timed: particles flow along arcs red→green, over-pressure columns **ease down** while headroom columns **ease up** (~1.5 s), the overflow counter (F20) **ticks** 240→60, and the camera **auto-flies + slow-orbits** the affected cluster. | Coordinated Cesium transition (polyline arcs + cylinder-height CallbackProperty tweens + camera) | MAP + RIGHT | fires on F18; single ~3–4 s sequence |
| F27 | **"Open the black box" column explode** (enhances F11/F4) | A "Show the math" affordance that **explodes a hospital column into its stacked, labelled multiplicands** (exposure × vulnerability × effect-size, with the demand-layer population shown as a tagged side segment) with the citation chip flying in — the honesty thesis as something judges *watch*, not read. | Animated column decomposition + labels overlay | MAP (over selected column) | from F11 / column action; click again to recompose |
| F28 | **Reset actions control** | Returns the action layer to State 0 (clears rings/headroom/arcs), per the interaction-state matrix (§13.11). A named control in the action group so no affordance is anonymous. | "Reset" button in the TOP BAR action group (alongside F16/F17/F18) | TOP BAR action group | click → action overlays clear, map returns to State 0 |
| F29 | **Redirect replay control** | Re-runs the F26 choreographed Redirect climax (for Q&A / a second look) without recomputing — animates between the same two known frames (§13.15). | Small "replay" button in the TOP BAR action group, beside Redirect (F18) | TOP BAR action group + MAP | click → F26 sequence replays |

> Anything not in F1–F29 is out of scope for v1. No settings pages, no charts-for-charts'-sake.
> **F24–F27 are the "alive" tier** — the motion features that carry the demo. Treat them as required, not polish; they are specced concretely in §13.15. **F28 (Reset actions) and F29 (Redirect replay)** are the named action-group controls promoted from §13.11/§13.15 so every affordance maps to a feature.

---

## 7. SCREEN LAYOUT (single screen, desktop)

```
┌──────────────────────────────────────────────────────────────────────┐
│ TOP BAR: [Crosssight logo] [UKHSA alert banner F8] [Horizon: Now/+3/+7 F7]│
│   action group [ Alert F16 | Reallocate F17 | Redirect F18 |            │
│                  Replay F29 | Reset F28 ]                               │
│           [Simulate episode F21]  [LIVE/SYNTH chip F22] [refresh F23]   │
├───────────┬──────────────────────────────────────────┬─────────────────┤
│ LEFT RAIL │                  MAP (F1)                 │  RIGHT PANEL    │
│           │   exposure field F2                       │                 │
│ Exposure  │   hospital columns F4                     │  City summary F9│
│ toggles F3│   catchment footprints F5                 │                 │
│ (O₃ =     │   redirect arcs F18                       │  Risk ranking   │
│  visual)  │                                           │  list F10       │
│           │                                           │   (↔ swaps when │
│ Layer     │                                           │  Reallocate:    │
│ panel +   │                                           │  sharing list   │
│ RPI       │                                           │  F17;  Redirect:│
│ legend F6 │                                           │  Redistribution │
│           │                                           │  plan F19 +     │
│           │                                           │  overflow F20)  │
├───────────┴──────────────────────────────────────────┴─────────────────┤
│ DRAWER (F12, slides over RIGHT+MAP when a hospital is selected):         │
│   pressure curve · driver breakdown F11 · Briefing F13 ·                 │
│   severity mix F14 · patient cards F15 · actions F16                     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 8. PRECISE USER FLOW (end to end)

> This is the exact sequence the product supports, and the exact sequence to demo. Each step names the features/elements involved.

**State 0 — Idle / live (on load).**
- Map (F1) loads, tilted. Exposure field (F2) renders from current data (live or synthetic). Hospital columns (F4) stand at their current PressureScores. City summary (F9) and risk ranking (F10) populate. LIVE/SYNTH chip (F22) shows source state; refresh dot (F23) pulses each cycle.
- Default exposure = Combined (F3). Default horizon = Now (F7).
- *User sees:* a calm, breathing, real map of London respiratory risk right now.

**Step 1 — Read the situation.**
- User scans risk ranking (F10); worst hospitals at top with band chips + top driver. User clicks the top row.
- Map flies to that hospital; its column (F4) emphasised; Hospital Detail drawer (F12) opens.

**Step 2 — Understand why (evidence).**
- In the drawer: projected pressure curve over the horizon, driver breakdown, and the Briefing Agent text (F13) in plain English.
- User clicks "ⓘ why?" on the score → Evidence popover (F11): the four multiplicands and the cited study (e.g. "air pollution → respiratory disease, 13 studies, effect 0.060"). Proves it's grounded, not guessed.

**Step 3 — See the human stakes (severity).**
- Drawer shows severity mix (F14) from Apollo profiles — what share of the incoming wave likely needs a respiratory bed, est. LOS — plus 2–3 representative patient cards (F15). Every severity output and patient card carries the visible **"simulated cohort / Apollo-derived profiles, not a predictor"** tag (S13).

**Step 4 — Project forward.**
- User sets the projection horizon to +7d (F7). All columns (F4) animate up/down to projected pressure; ranking (F10) reorders; summary (F9) updates. The wave's near-future shape is now visible. (Copy reads "projection", never "forecast".)

**Step 5 — Act, tier 1: ALERT.**
- User clicks **Alert** (F16). Flagged hospitals' columns gain pulsing warning rings. Recommendation Agent populates prepare actions (oxygen, staffing, outreach), each with justification + citation, in the drawer/right panel.

**Step 6 — Act, tier 2: REALLOCATE.**
- User clicks **Reallocate** (F17). Neighbouring hospitals with headroom brighten green (F4). The **sharing suggestion list appears in the RIGHT PANEL** (which neighbour can lend beds/staff/oxygen), replacing the ranking while Reallocate is active.

**Step 7 — Act, tier 3: REDIRECT.**
- User clicks **Redirect** (F18). Animated Cesium polyline arcs spring from over-pressure → headroom hospitals, particles flowing. Over-pressure columns visibly shrink, headroom columns rise. Right panel swaps to the Redistribution plan (F19) with the overflow counter (F20) inside it. Overflow counter animates from "before" to "after" (e.g. 240 → 60 projected unmet demand). **This is the climax shot.**
- User hovers a plan row (F19) → its specific arc highlights. **Replay** (F29) re-runs the climax for a second look; **Reset** (F28) clears all action overlays back to State 0.

**Step 8 — Prove it's live / force dynamism.**
- If live conditions are calm, user clicks **Simulate episode** (F21) → "PM2.5 spike" (`pm25_spike`, §13.6: PM2.5 ~50 + NO₂ ~130 µg/m³). The exposure field (F2) intensifies and drifts in the real wind; the **roadside, high-vulnerability cohort lights up first** (Newham, King's-Denmark-Hill, Whittington, Croydon swing amber→red) while cleaner low-vulnerability catchments stay green — the correct public-health picture. The whole Alert→Reallocate→Redirect response then re-runs on this guaranteed-dramatic scenario. Clearly labelled "simulated event — real response".
- User hovers LIVE/SYNTH chip (F22) → sees real sources + timestamps; notes the field has shifted since load (proof of life).

**Exit state.** User closes drawer (F12) → returns to full map in whatever action state is active. Re-running actions or changing horizon/exposure recomputes everything.

---

## 9. DEMO SCRIPT (≈90s, maps to the flow)

1. *"This is London respiratory risk — live where the feeds are reachable. This haze is driven by London's real air monitors; these columns are London's hospitals."* (State 0)
2. *"Our worklist ranks who's most at risk — and it's the deprived, roadside boroughs at the top, exactly as the evidence predicts."* — click the top hospital (e.g. Newham). (Step 1)
3. *"And nothing here is a black box —"* click "why?" — *"every score breaks into live exposure, vulnerability, and the published effect size. The score itself uses the 13-study respiratory term, and we show the broader 66-study air-pollution evidence beside it as context."* (Step 2, F11; population sits in the demand layer, tagged simulated)
4. *"It's not just headcount — Apollo's clinical profiles give us a realistic split of who'll need a bed (a simulated cohort, not a predictor)."* (Step 3)
5. *"Push the projection to seven days —"* the columns grow. (Step 4)
6. *"Now watch the system respond."* — Alert, Reallocate, Redirect in sequence; arcs fire; *"projected unmet demand drops from 240 to 60."* (Steps 5–7)
7. *"And to be honest about our data: we tested whether the clinical datasets actually predict admissions — they don't, so we built on the real published evidence instead, and made every recommendation traceable."* (the integrity beat)
8. *"Live where the feeds reach us — and when we inject an event, the cause is simulated but the response is the genuine pipeline."* — hover the source chip; note the haze has drifted. (Step 8)

---

## 10. BUILD PRIORITY ORDER (for Claude Code)

> Build in this order so there's always a demoable artifact. Each milestone is self-contained.

**M1 — Static map + columns (no data yet).** F1, F4 with hardcoded seed scores, F7 horizon stub, basic layout §7. *Demoable: a 3D London hospital map.*

**M2 — Risk Engine + Evidence.** Load System graph; implement §3.1 formula with real effect sizes; wire GLA/Milliman vulnerability + OSM hospitals/catchments. F2 exposure field (synthetic generator first), F5 catchments, F9 summary, F10 ranking, F11 evidence popover, F3 exposure toggles, F22/F23 status. *Demoable: a grounded, explainable live-style risk console.*

**M3 — Live feeds.** Implement real London Air / DEFRA / Met Office / UKHSA fetchers behind the LIVE_DATA flag with synthetic fallback. F8 alert banner. F21 climate-event injector. **F24 wind-driven exposure field** (Met Office wind lands here). *Demoable: genuinely live (where network allows).*

**M4 — Agents.** Briefing (F13), Recommendation (F16 actions), Redistribution (F19). Anthropic API, `claude-sonnet-4-6`, structured I/O. **F25 streaming agent reasoning** (Anthropic streaming → SSE/WS + sequential driver-chip reveal). *Demoable: the "intelligence" and the written plans, streamed live.*

**M5 — Action choreography + liveness (§13.15).** F16 rings, F17 headroom highlight, **F26 choreographed Redirect climax** (F18 arcs + eased column re-height + F20 tick-counter + camera fly/orbit on one clock), **F27 "open the black box" column explode**, drawer F12 polish, severity F14/F15 from Apollo. *Demoable: the full Alert→Reallocate→Redirect climax, alive.*

**M6 — Polish.** Motion timing, loading states, "simulated" tags everywhere required, source tooltips, demo-mode preset.

**Fallback if time runs short:** M1–M2 + F21 + a scripted Redirect (F18) with pre-computed numbers still delivers the core narrative. Agents (M4) can degrade to templated text if the API is unavailable.

---

## 11. TECH NOTES (non-binding suggestions)
> **Stack authority:** `ARCHITECTURE.md` is the **authoritative source for the rendering/data/agent stack**. Where these notes differ, ARCHITECTURE.md wins. The map is **CesiumJS + Google Photorealistic 3D Tiles** (Cesium OSM Buildings fallback), not deck.gl/MapLibre — see ARCHITECTURE §0 and §2.
- Frontend: React + Vite + TypeScript with a **CesiumJS Viewer** (DOM chrome absolutely-positioned over the canvas). State in React (no browser storage). See ARCHITECTURE §2/§5 for the layer map (cylinder Entities, ParticleSystem haze, draped polygons, polyline arcs).
- Backend: a thin Python (FastAPI) service: polls feeds, runs Risk Engine, calls agents, exposes `/state` (and SSE for the refresh cycle / agent streams). Cache last-good readings so a failed fetch never blanks the map.
- Data prep: load System/Apollo/Milliman from the cloned repo at build time; precompute catchment populations and vulnerability weights into a static `catchments.json`.
- Effect sizes: bake the System shortlist (§3.2 table) into a config the engine reads, each with its provenance.
- Keep all simulated values flagged in the payload (`"simulated": true`) so the UI can tag them.

---

## 12. WHAT SUCCESS LOOKS LIKE (acceptance)
- Open the app → live/synthetic London map with breathing columns, no blank states.
- Click any hospital → drawer with evidence-cited briefing; click "why?" → real study provenance.
- Set +7d → columns reproject.
- Alert → Reallocate → Redirect → arcs + before/after counter animate.
- Stress-test → dynamic cascade on demand.
- Nothing on screen claims a trained admissions predictor; every effect size shows its source; simulated values are tagged.

---

## 13. ENGINEERING HARDENING — RESOLVED DECISIONS (authoritative)

> This section closes the gaps in §1–§12. Where it conflicts with earlier text, **this wins.** It exists to make the build foolproof: every previously-ambiguous quantity now has a single defined behaviour, every external dependency has a fallback, and the demo has a guaranteed-dramatic path that needs zero network.

### 13.1 What `PressureScore` actually is (units, normalisation, honesty)

The raw sum in §3.1 is a **per-capita intensity** (effect-weights only — population is deliberately excluded). Define the index in **two explicit layers** so nothing on screen is a fabricated absolute, and calibrate it against a **fixed absolute reference**, not a live min/max:

1. **Respiratory Pressure Index (RPI)** — the *primary, honest* quantity, a **per-capita intensity index**. Compute the raw weighted sum per hospital **excluding population** (population is a demand-layer quantity, not part of intensity — see layer 2 and §13.4):

   ```
   rawScore(h) = Σ over canonical terms ( exposureLevel × effectSize × vulnerabilityWeight )
   RPI(h)      = 100 × clamp( rawScore(h) / referenceRaw , 0, 1 )
   ```

   `referenceRaw` is a **fixed absolute constant**, stored in `data/effect_sizes.json` under `rpiCalibration.referenceRaw` (the data agent computes it). **Method:** `referenceRaw` = `rawScore` evaluated at **all canonical exposures = 0.6** and **vulnerabilityWeight = 1.25** — i.e. a sustained "high but plausible" London day on a moderately-vulnerable catchment maps to ~RPI 100. This replaces the old per-refresh min–max normalisation entirely: because the reference is fixed, a genuinely **calm day → low rawScore → low RPI → green**, and screenshots/colours are stable and comparable across refreshes and across the network. RPI is what column height and band colour encode; it claims only *per-capita relative intensity*, never a patient count.
2. **Demand layer (population + projectedDemand + illustrative excess)** — the *derived, clearly-labelled* numbers used by the F20 counter, redistribution, and severity mix. **Population lives here, not in RPI**, modelled as `population: { value, simulated:true, method }` and UI-tagged simulated. Per hospital:

   ```
   projectedDemand(h) = round( illustrativeDemandBaseline(h).value × (1 + demandSensitivity × RPI(h)/100) )    # tagged simulated
   headroom(h)        = capacity(h).value − projectedDemand(h)
   overflowBefore     = Σ_h max(0, projectedDemand(h) − capacity(h).value)
   overflowAfter      = same sum after redistribution reassigns demand from over-pressure to headroom hospitals
   ```

   `demandSensitivity` is a fixed constant in `data/effect_sizes.json` under `demandModel.demandSensitivity` (= 1.5). `illustrativeDemandBaseline` is a **seeded, "illustrative" tagged** per-hospital constant (§13.6). Every appearance of `projectedDemand`/overflow carries an "illustrative — not a measured count" tag. This resolves the honesty tension in the 240→60 climax (`overflowBefore`→`overflowAfter`): it is presented as *the model's own arithmetic on transparent inputs under stated assumptions*, never as a prediction or a real ED figure. The ranking/summary may note volume separately, but volume never alters RPI.

Band thresholds (fixed, **absolute**, not relative): **green RPI < 40, amber 40–70, red > 70.** Because RPI is calibrated to the fixed `referenceRaw`, these absolute bands are stable across refreshes and comparable in screenshots.

**Colour palette must be colour-blind-safe** (use a viridis-style or blue→orange→red ramp with luminance separation, not pure green/red), with a legend in the LEFT RAIL.

### 13.2 `EffectSize` semantics + exact term binding (no double-counting)

`EffectSize` values from the System graph are treated as **dimensionless relative weights**, NOT relative risks or betas. The engine never claims "X% more admissions per µg/m³." It claims "this exposure contributes proportionally to the index per its evidence weight." State this in F11 copy.

Canonical, non-overlapping term set the engine sums (and the live feed each binds to):

| Term | Bound exposure feed | EffectSize source row | Gate |
|---|---|---|---|
| PM2.5 → respiratory | LAQN/DEFRA PM2.5 | air pollution → respiratory disease (0.060) | always |
| NO₂ → asthma | LAQN/DEFRA NO₂ | nitrogen dioxide → asthma (0.127) | always |
| Roadside traffic → asthma | NO₂ on roadside-flagged catchments only | traffic-related pollution → asthma (0.296) | only if catchment `roadside=true` |
| Heat → mortality | Met Office temp | extreme heat → mortality rate (0.347) | only above heat threshold (§13.3) |

O₃ is shown in the exposure-field toggle (F3) for visual completeness but, if no coherent O₃ effect row exists in the graph, it does **not** enter the sum (label its toggle "visual only"). Don't fabricate a term to fill a UI button.

### 13.3 `ExposureLevel` normalisation (absolute, health-anchored)

Normalise each exposure to 0–1 against **absolute health-relevant thresholds**, not the live min/max (relative normalisation would paint a genuinely clean day red, destroying credibility):

- **PM2.5:** 0 at 0 µg/m³, 1.0 at 35 µg/m³ (≈ UK DAQI "high" / well above WHO 24h guideline 15). Linear, clamp >1.
- **NO₂:** 0 at 0, 1.0 at 200 µg/m³ (UK hourly objective). Linear, clamp.
- **O₃:** 0 at 0, 1.0 at 180 µg/m³ (visual-only per §13.2).
- **Heat term gate:** the heat term contributes **0 below 25 °C daily max**, then ramps to 1.0 at 32 °C (captures the J-shaped curve — moderate temperatures aren't a respiratory driver). Cold is out of scope for a June demo; the same gating structure supports a cold term later. If a **UKHSA Heat-Health Alert (Amber/Red)** is active (F8), apply a 1.15/1.30 multiplier to the heat term and surface "alert-boosted" in F11.

Document these constants in the effect-size config so they're auditable.

### 13.4 Horizon = real projection, not a flat copy of today (lag kernel)

The +3d/+7d projection (F7) combines two inputs:

1. **Forecasted exposures** where available — Met Office gives temperature forecast; for air, if no forecast feed is reachable, use **persistence** (hold today's level) decayed toward the seasonal/station mean. Label which is in use.
2. **A fixed lag kernel** convolved with the exposure series, reflecting that exposure effects on respiratory presentations peak ~1–3 days later and fade by ~day 7. Bake an explicit, citable kernel into config, e.g. day-offset weights `[0:0.15, 1:0.25, 2:0.22, 3:0.15, 4:0.10, 5:0.07, 6:0.04, 7:0.02]` (sums ≈1; tune to literature). The pressure *curve* shown in F12 is this convolution.

UI copy everywhere says **"projection"/"projected,"** never "forecast"/"prediction," to stay inside the honesty constraint of §0.

### 13.5 Spatial model — hospitals, catchments, station→catchment join

This is the spatial join everything depends on; define it concretely:

- **Hospital set:** a fixed, version-controlled list of London **Type-1 A&E acute hospitals** (~25–30; e.g. Royal London, Newham, King's, St Thomas', UCH, Northwick Park, Croydon, etc.). Hardcode lat/lon + name + trust into `catchments.json`. Do not depend on a live OSM query at runtime — precompute at build time; OSM is the *source*, the committed JSON is the runtime artifact.
- **Catchments:** **Voronoi/Thiessen polygons** around hospital points, clipped to the Greater London boundary (GLA boundary file). Tagged "estimated catchment" in UI (honesty §5). `roadside=true` set for catchments whose centroid is within ~150 m of a major road (OSM motorway/trunk/primary) — drives the roadside term in §13.2.
- **Station → catchment exposure:** **inverse-distance-weighted (k=3 nearest LAQN/AURN stations, power=2)** to each catchment centroid. If <1 station within 10 km, fall back to borough-average then city-average; flag degraded coverage on F22. Never leave a catchment with null exposure.
- **VulnerabilityWeight:** areal/population-weighted interpolation of GLA borough (or LSOA if available) indices to each catchment, blended with Milliman SVI-style indices (E_AGE65, E_NOVEH, E_UNEMP, E_CROWD, E_MINRTY), normalised to a **0.5–1.5 multiplier** so vulnerability *modulates* rather than dominates the index. Precompute into `catchments.json`.

### 13.6 Simulated/seeded values — single source, reproducible

- **One seeded RNG** (fixed seed in config) drives every synthetic generator (air fallback, heat fallback, bed capacity, illustrative baselines, stress episodes). Same seed → byte-identical demo every run. No `Math.random()` anywhere in load-bearing paths.
- **Bed capacity & illustrative demand baseline** per hospital: seeded constants in `catchments.json`, each carrying `"simulated": true`. Headroom (drives F17/F18) = `capacity − projected_demand`. All three numbers tagged on screen.
- The **climate-event episodes** (F21) are deterministic, named scenarios with fixed magnitudes/spatial footprints, so the climax is identical every rehearsal:
  - **`pm25_spike`** (the headline demo episode) — a winter-inversion–style event that traps **PM2.5 to ~50 µg/m³** *and* **co-elevates NO₂ to ~130 µg/m³** (real pollution episodes raise both together) at central/roadside stations, tapering outward. Magnitudes chosen so the **roadside + high-vulnerability cohort** (e.g. Newham, King's-Denmark-Hill, Whittington, Croydon) swings amber→red while cleaner low-vulnerability catchments stay green — which is the epidemiologically correct picture and the demo's point.
  - **`heatwave`** — daily max **to ~34 °C** city-wide; drives the heat-stress term hardest, lighting up the network broadly.
  - **`no2_inversion`** — **NO₂ to ~180 µg/m³** concentrated on roadside catchments; isolates the traffic-asthma term.
  > **Calibration note (why magnitudes matter):** because PM2.5→respiratory's evidence weight (0.060) is intrinsically ~6× smaller than the heat term (0.347), a pollution-only episode mathematically lights up the **roadside/high-vulnerability cohort first**, not every hospital. The demo camera and narrative lean on that cohort by design (§8 Step 8, §9). This is honest, not a workaround. If a future build wants pollution episodes to register network-wide, that is an engine-side recalibration of `rpiCalibration.referenceRaw` (a separate, optional decision) — **do not** silently inflate effect sizes to force it.

### 13.14 Simulated trigger, real response (hard architectural rule)

This is the product's core honesty/robustness doctrine and it constrains *where* simulation is allowed to live:

- **Simulation is permitted at exactly one place: the exposure-input layer.** The F21 injector (and the synthetic fallbacks in §13.9) modify the **`ExposureLevel` feed** — the *cause* — by adding a defined spatial/temporal perturbation on top of whatever the baseline is (live or synthetic). It writes to the same fields a real LAQN/Met Office reading would.
- **Everything downstream of the input layer is the real production pipeline, with no awareness of whether the input was live or injected.** The risk engine (§3.1/§13.1) recomputes RPI normally; the agents (§3.3/§13.8) reason over the new structured inputs normally; the redistribution logic (F17/F18) replans normally. **There is no separate "demo" code path that scripts scores, briefings, or arcs.** If you ever find yourself hardcoding a downstream result, stop — that violates this rule and is exactly the thing we promise judges we don't do.
- **Consequence for the build:** the injector is a transform `baselineExposure → perturbedExposure`, applied before the engine runs. The `episode` query param (§13.7) selects the transform. Removing the injector must leave a fully-working live system; adding it must require zero changes downstream.
- **On-screen honesty:** while an event is active, the LIVE/SYNTH chip (F22) shows **"simulated event — real response"**, and the injected exposure cells carry `simulated:true`. We never claim the *conditions* are real during an injected event; we do claim — truthfully — that the *system's reaction* is the genuine article.
- **Note vs `DEMO_MODE` (§13.10):** `DEMO_MODE` is the *offline insurance* path (all-synthetic baseline, frozen agent text, for dead-wifi safety). F21 is the *online, real-engine* path used when live data is available but calm. Prefer F21 on the day — it's the more honest and more impressive of the two; `DEMO_MODE` is only the fallback if the network or an API dies.

### 13.15 Liveness & motion spec (Tier-1 "alive" features F24–F27)

These are the features that make the screen read as *alive*. Guiding rule (from §2): **every motion encodes meaning** — nothing animates for decoration. Build them in M5, except F24's wind input which lands with Met Office in M3.

**F24 — Wind-driven exposure field.**
- Input: Met Office wind **direction + speed** per refresh (city-level is enough; per-station is a bonus). Expose on `/state` as `wind: { dirDeg, speedMs }`.
- Render: a **Cesium `ParticleSystem`** (see ARCHITECTURE §2.5) advecting the haze along the wind vector via its `updateCallback`; particle velocity ∝ wind speed, emission density/colour ∝ `ExposureLevel` at the emitting station.
- Fallback: no wind feed → gentle fixed-direction drift at constant slow speed so the field is never frozen. Flag `wind.simulated:true`.
- Honesty: the *drift direction is real* even in `DEMO_MODE` if a wind value is available; otherwise it's clearly a placeholder.

**F25 — Streaming agent reasoning.**
- Use the Anthropic **streaming** API; pipe tokens to the client over SSE/WebSocket. Render with a typewriter cursor.
- As the briefing names a driver (PM2.5, NO₂, heat…), **pulse the matching driver chip** (F11) in sequence — drive this off the structured `drivers[]`, revealing each chip on a fixed cadence (~400 ms) synced to the stream, not by parsing prose.
- Determinism: for the canned demo, stream from the **frozen cached text** (§13.8) at a fixed rate so timing is identical every run; live "regenerate" streams fresh.
- Fallback: API down → "stream" the templated text with the same typewriter effect, so the *motion* survives even without the LLM.

**F26 — Choreographed Redirect climax** (the single most important animation in the product).
- One coordinated ~3–4 s sequence on F18 click, timeline:
  1. `0.0s` arcs spring in (ArcLayer), particles begin flowing red→green (`getSourceColor`→`getTargetColor`, animated `getWidth`/particle offset).
  2. `0.2s` over-pressure columns **ease down** and headroom columns **ease up** via the Cesium cylinder-length `CallbackProperty` tweened by the shared animation clock (easeCubicInOut, ~1200 ms; ARCHITECTURE §2.4/§2.6) — heights interpolate to the post-redistribution RPI.
  3. `0.2s` camera auto-flies to the affected cluster and does a slow orbit (`FlyToInterpolator` then a gentle bearing sweep).
  4. `0.4s` overflow counter (F20) **tick-animates** before→after (e.g. 240→60) over ~1500 ms, easing out.
- All four channels share one clock so they feel like a single event. Provide a **"replay"** control (re-runs the sequence) for Q&A.
- Performance: cap particle count; pre-resolve before/after states server-side so the client only animates between two known frames (no mid-animation recompute).

**F27 — "Open the black box" column explode.**
- From F11 / a column action, the selected column **separates vertically into three labelled RPI segments** = its per-capita multiplicands (exposure × vulnerability × effect-size — **population is excluded from RPI**, §13.1), each sized to its `contribution` from `drivers[]`, with the **citation chip** (`numStudies`, top citation when available) flying in beside the effect-size segment. **Population** appears as a separate, clearly-offset **demand-layer side segment** tagged "simulated — not in RPI", so the honesty distinction is visible.
- Animate with staggered ease (each segment ~150 ms apart, ~600 ms total); click again or close to recompose into the single column.
- This is the literal, watchable version of the §0 "no black boxes" promise — make sure the segment heights visibly sum back to the whole column.

**Cross-cutting motion rules.**
- Respect a single global animation clock / easing set so the app feels coherent (suggest easeCubicInOut, durations 600–1500 ms).
- Honour `prefers-reduced-motion`: degrade particle/typewriter/orbit to instant state changes (accessibility + a safe fallback on a struggling laptop).
- Target a steady **60 fps on the presenting machine** (§13.10 budget); if any single feature drops frames, it can be disabled by a feature flag without breaking the rest.

### 13.7 Backend `/state` contract (decouples FE/BE, parallelises build)

> **Canonical schema lives in `ARCHITECTURE.md §4.3` — that is the single source of truth; do not maintain a second copy here.** The summary below is orientation only; if it ever diverges from `ARCHITECTURE.md §4.3`, the architecture file wins.

Shape (summary): `/state?horizon=now|3d|7d&exposure=pm25|no2|o3|heat|combined&episode=none|pm25_spike|heatwave|no2_inversion` returns `generatedAt`, `mode` (LIVE/SYNTHETIC/MIXED), `sources[]` (each with `status`, `simulated`, `degradedReason`), `wind` (drives F24), `ukhsaAlert`, `exposureField.stations[]` (real station points, **not** a hex grid), and per `hospitals[]`: `rpi` (0–100, **per-capita, population excluded**), `band`, `topDriver`, `drivers[]` (exposure × effectSize × vulnerability + provenance + `substituted` flag — **no population multiplicand**), `curve[]`, `population:{value,simulated,method}` (**demand layer only**), `capacity`, `illustrativeDemand`, `projectedDemand:{value,simulated}`, `headroom`, `severityMix`, `patientCards[]`; plus `redistribution` (`arcs[]`, `overflowBefore/After`) and `agents`. See `ARCHITECTURE.md §4.3` for the full field list and the exact `projectedDemand`/`overflow` formulas.

Frontend renders this object and nothing else — no business logic in the client. An SSE channel pushes a new `/state` each refresh cycle; the UI heartbeat (F23) runs on its own cadence independent of upstream (LAQN updates ~hourly — poll politely ~5–10 min and show the real upstream timestamp). **Cache last-good `/state` to disk**; a failed upstream fetch serves stale data with `status:"stale"`, never a blank map.

### 13.8 Agent layer — cost, latency, caching, determinism, fallback

- **Do not call agents every refresh cycle.** Agents run **on demand** (when a hospital drawer opens / an action tier fires) and results are **cached keyed by `(hospitalId, horizon, band, topDriver, episode)`** so an unchanged situation reuses text. This bounds cost and latency and keeps the demo stable.
- **Structured output:** require JSON (tool-use / response schema) for the machine-readable parts (action list, arc plan) plus a prose field for display. Define the schema alongside §13.7. Validate; on schema-invalid, fall back to template.
- **Determinism for demo:** low temperature; **pre-warm and freeze** the briefings/recommendations for the canned demo state (§13.10) so the live run never surprises you with regenerated text. "Regenerate" (F13) is allowed but the default demo uses frozen cache.
- **Resilience:** per-call timeout (e.g. 8 s) + 1 retry; on failure or no API key, **degrade to templated text** assembled from the same structured inputs (the templates are good enough to demo). API key only in backend env (`ANTHROPIC_API_KEY`); never expose to the client.
- Model: the **configured model `claude-sonnet-4-6`** (right cost/latency pick for this agent layer). Keep the model ID in config, not hardcoded, so it can be swapped without code changes.

### 13.9 Network, CORS, and the LIVE/SYNTHETIC contract

- **All external fetches go through the backend** (LAQN, DEFRA, Met Office, UKHSA). The browser never calls them directly — avoids CORS failures and hides keys. Frontend talks only to our `/state`.
- `LIVE_DATA=true` attempts real fetches with per-source timeout; **any source that fails silently falls back to its seeded synthetic generator** and is marked `status:"down"`/`simulated:true` so F22 shows mixed mode honestly. `LIVE_DATA=false` forces all-synthetic (use for offline rehearsal/judging room with no wifi).
- Map basemap: the offline fallback is **Cesium OSM Buildings** (Ion-token-only, no Google billing — a one-line swap from the Photorealistic 3D Tiles route; all column/haze/arc code is identical), and if even Ion is unreachable, a **screen-record for `DEMO_MODE`** (per ARCHITECTURE §2.1/§7/§8). There is no MapLibre/dark-style cache. Include required **attribution** (Cesium, Google/OSM tiles, LAQN/Imperial, DEFRA, Met Office, GLA) via Cesium's credit display (do not hide `viewer.creditContainer`) — licensing compliance and a credibility signal.

### 13.10 Demo robustness — a zero-network guaranteed path

- Ship a **`DEMO_MODE` preset**: `LIVE_DATA=false`, the `pm25_spike` episode pre-loaded, frozen agent text, fixed seed → a fully offline, identical-every-time, dramatic run. This is the fallback if venue wifi, an API, or a feed dies mid-presentation. The "live" version is the aspiration; `DEMO_MODE` is the insurance.
- **Performance budget:** ≤ ~30 columns, hexagon cell count capped (aggregate to ≤ a few thousand cells), arc particle count modest; target a steady 60 fps on the presenting laptop. Test on *that* laptop before the day.

### 13.11 Interaction-state matrix (how controls compose)

Define precedence so combined interactions are predictable:

- **Horizon (F7)** and **Exposure (F3)** are inputs to every recompute; changing either re-fetches `/state` with new params and **re-applies whatever action tier is currently active** (rings/headroom/arcs recompute for the new horizon).
- **Action tiers (F16/17/18)** are cumulative narrative steps but only **one tier's visual is "active" at a time** for legibility; selecting a higher tier supersedes the lower's overlay (Redirect arcs replace Reallocate highlights). A "reset actions" affordance returns to State 0.
- **Climate-event injector (F21)** is an **additive overlay at the input layer** on the current baseline (live or synthetic), toggleable off; it sets the `episode` param and everything downstream cascades through the real pipeline (§13.14).
- **Drawer (F12)** is orthogonal — open over any state; closing returns to the exact prior map/action state.

### 13.12 Error / empty-state catalogue (no dead ends)

Every one of these has a defined, non-blank behaviour: feed down → stale+synthetic fallback (F22 flags it); System graph row missing → nearest-term fallback + log **and an on-screen "substituted evidence term" chip in F11/source chip** (N5); agent timeout/no key → templated text; <1 station near a catchment → borough/city average (F22 degraded flag); map tiles fail → Cesium OSM Buildings fallback, then a `DEMO_MODE` screen-record (no MapLibre cache, §13.9); no hospital selected → full map; empty redistribution (no headroom anywhere) → explicit "network saturated — no headroom to redistribute" message instead of empty arcs.

### 13.13 Time budget & cut lines (hackathon-real)

Map the M1–M6 order (§10) to hard cut lines so there's always a demoable artifact:

- **Must-ship (the spine):** M1 + M2 + the §13.10 `DEMO_MODE` path + a scripted Redirect (F18) with pre-computed numbers. This alone tells the whole story offline.
- **Should-ship:** M4 agents (real, with templated fallback already covering you) + M5 choreography.
- **Nice-to-have:** M3 genuinely-live feeds — valuable for the "it's live" beat but **the demo must not depend on it.** If feeds fight you, fall back to `DEMO_MODE` and spend the time on the climax animation instead.
- **Build the `/state` contract (§13.7) first** so frontend and backend can be built in parallel against the same shape.