import { useStore, type Horizon, SEQUENCE } from "../state/store";

const HORIZONS: { key: Horizon; label: string }[] = [
  { key: "now", label: "Now" },
  { key: "3d", label: "+3d" },
  { key: "7d", label: "+7d" },
];

export default function TopBar() {
  const { horizon, setHorizon, mode, simActive, simIndex, drifting, startSim, continueSim, reset } =
    useStore();

  const hasNext = simActive && simIndex < SEQUENCE.length - 1;

  return (
    <div className="topbar">
      <div className="brand">
        <span className="brand-mark">◬</span> Crosssight
        <span className="brand-sub">London Respiratory Early-Warning</span>
      </div>

      <div className="topbar-group">
        <span className="group-label">UKHSA</span>
        <span className="alert-strip alert-none">No active alert</span>
      </div>

      <div className="topbar-group">
        <span className="group-label">Projection</span>
        <div className="segmented">
          {HORIZONS.map((h) => (
            <button
              key={h.key}
              className={horizon === h.key ? "seg active" : "seg"}
              onClick={() => setHorizon(h.key)}
            >
              {h.label}
            </button>
          ))}
        </div>
      </div>

      <div className="topbar-right">
        {!simActive ? (
          <button className="sim-btn" onClick={startSim} title="Simulate a pollution episode">
            ⚡ Simulate episode
          </button>
        ) : (
          <>
            <span className="sim-step">
              Plume {simIndex + 1}/{SEQUENCE.length}
            </span>
            <button
              className="sim-btn"
              onClick={continueSim}
              disabled={!hasNext || drifting}
              title="Let the plume drift to the next catchment"
            >
              {drifting ? "Drifting…" : hasNext ? "Continue simulation →" : "End of plume path"}
            </button>
            <button className="act act-reset" onClick={reset}>Reset</button>
          </>
        )}
        <span className={`mode-chip mode-${mode.toLowerCase()}`} title="Data source state">
          <span className="dot" /> {mode}
        </span>
        <span className="heartbeat" title="Engine refresh cycle" />
      </div>
    </div>
  );
}
