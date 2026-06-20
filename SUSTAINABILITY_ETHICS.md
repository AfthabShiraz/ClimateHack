# Crosssight — Sustainability, Measurement & Ethics
### Response to the bonus judging criteria

> Every point below is backed by a concrete design choice in the build (see `plan.md`, `ARCHITECTURE.md`), not an aspiration. Crosssight is a **decision-support** tool for London hospital / ICB planners that converts live air-quality and heat into an early, evidence-cited respiratory-readiness alert — using the **lead-time gap** to *prepare before beds fill*.

---

## 1. Sustainability & Resource Use

**Headline: we deliberately did not build an energy-hungry ML model — and the product exists to *prevent* resource waste.**

- **Near-zero compute core.** The risk engine is deterministic arithmetic (live exposure × published effect size × vulnerability), so there is **no model training** — the carbon-heavy step in most AI projects — and inference is microseconds. We chose this for robustness *and* energy.
- **LLM used sparingly and cached.** The reasoning agents run **on-demand** (only when a hospital is opened or an alert fires), and outputs are **cached by situation**, not regenerated every refresh. Token use and energy are bounded and small; the prose layer can run on a smaller model (e.g. Haiku-class) with no loss of function.
- **No new hardware or materials.** Crosssight reuses existing open data (LAQN air monitors already deployed across London, Met Office, UKHSA). It deploys **zero new sensors** to manufacture, power, or maintain.
- **Low long-term maintenance.** Effect sizes and thresholds live in a config file (`data/effect_sizes.json`) — updates are a *file edit, never a retrain*. A single `/state` contract, graceful degradation, and cached map tiles keep the system simple to run. A lightweight basemap fallback (Cesium OSM Buildings) avoids streaming heavy photorealistic tiles when not needed.
- **It prevents downstream resource/carbon waste.** Preparing days ahead avoids the high-carbon cost of crisis response: emergency inter-hospital transfers, ambulance diversions and miles, and panic over-provisioning of oxygen and staff. Prevention is the sustainable option.

---

## 2. Evidence & Measurement

**Headline: we are honest that the provided datasets cannot be backtested (de-identification destroyed the pollution→admissions signal), so we propose a real measurement framework instead of a fake accuracy number.**

**What we would measure in a deployment**
- **Lead time delivered** *(primary KPI)* — median days of advance warning issued before a verified pollution/heat-driven respiratory surge. This is the product's core promise made measurable.
- **Health outcomes** — respiratory admissions and ED boarding time during *alerted* high-exposure windows versus unalerted controls.
- **Adoption & action** — number of ICBs/hospitals using it, number of alerts acted upon, % of recommended prepare-actions completed.
- **Avoided harm & emissions** — oxygen stockouts prevented, emergency transfers avoided, ambulance diversion-miles reduced (each convertible to a CO₂ figure).

**Study design**
- A **stepped-wedge pilot** across hospital catchments (hospitals adopt the alert at staggered times) cleanly isolates the effect of acting on alerts.
- **Validation:** with *real* (non-de-identified) NHS admissions data, compare alert timing against historical pollution episodes and known admission spikes.

**Honesty note for judges:** we explicitly tested the supplied Apollo/Milliman data for a pollution→admissions signal — it is ~0.00, because de-identification removed the cross-variable relationships. Rather than train a predictor that would pass a flat backtest and fail live, we built on the **published evidence base** and made every number traceable. The inability to backtest *these* datasets is a property of the data, and we surface it rather than hide it.

---

## 3. Ethics & Governance

**Headline: privacy-safe by design, transparent by design, human-in-the-loop by design.**

- **Privacy.** Crosssight uses **no patient-identifiable data**. Apollo is synthetic and used only for *aggregate* clinical texture (e.g. "~41% of a wave needs a respiratory bed"), never individual prediction. Vulnerability is **area-level** (Milliman / GLA indices), not personal. Privacy risk is low *structurally*, not by policy alone.
- **Transparency & contestability.** Every risk score breaks down into its inputs and links to the cited study behind each effect size — **no black box**. Decisions are auditable and challengeable, which matters for public-sector accountability.
- **Equity — acknowledged, not hidden.** The vulnerability weighting deliberately surfaces health inequality (it directs readiness toward older, more deprived catchments). The same mechanism could be *misused* to ration care. Our governance stance: Crosssight is a **planning aid, never automated rationing**; weights are transparent and reviewable; a human always decides.
- **Safety & human-in-the-loop.** The system **recommends**, it does not act. No patient is moved and no resource committed automatically. All outputs are framed as suggestions for a qualified planner.
- **No overclaiming.** We state plainly that this is **evidence-based risk, not prediction**. Refusing to present arithmetic as a clairvoyant model is itself an ethical position.
- **Alert fatigue** is the key operational risk: too many alerts get ignored. Thresholds are **tunable** so alerts stay rare and meaningful.
- **Bounded AI failure modes.** The LLM only *explains and plans* over numbers the deterministic engine computes — it never produces a risk score, so it cannot hallucinate one. A templated fallback covers API outages, and all agent outputs are cited and reviewable.
- **Honest simulation.** When an event is simulated for demonstration, only the *cause* (the exposure input) is synthetic; the engine and reasoning respond exactly as they would to real conditions, and the UI labels it as such.

---

### One-line summary per criterion
- **Sustainability:** a deliberately compute-light, hardware-free tool that prevents the carbon cost of crisis response.
- **Measurement:** honest about un-backtestable data; a concrete lead-time + stepped-wedge outcome framework instead.
- **Ethics:** no PII, fully traceable, human-in-the-loop, and upfront about equity and the limits of the data.
