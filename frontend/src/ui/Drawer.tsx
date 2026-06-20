import { useStore, BAND_COLOR, projectedDemand } from "../state/store";
import ThinkingLog from "./ThinkingLog";

export default function Drawer() {
  const { hospitals, selectedId, select } = useStore();
  const h = hospitals.find((x) => x.id === selectedId);
  if (!h) return null;

  const flagged = h.rpi >= 70;

  return (
    <div className="drawer">
      <div className="drawer-head">
        <div>
          <div className="drawer-name">{h.name}</div>
          <div className="drawer-trust">{h.trust}</div>
        </div>
        <button className="drawer-close" onClick={() => select(null)}>✕</button>
      </div>

      <div className="drawer-band" style={{ background: BAND_COLOR[h.band] }}>
        RPI {h.rpi} · {h.band.toUpperCase()}
      </div>

      {flagged && (
        <div className="leadtime">
          <div className="leadtime-label">Projected respiratory surge</div>
          <div className="leadtime-value">+5 days</div>
          <div className="leadtime-sub">lead time to prepare</div>
        </div>
      )}

      <div className="drawer-section">
        <div className="drawer-section-title">Why — driver breakdown</div>
        <div className="drivers">
          <div className="driver-row">
            <span className="driver-name">
              {h.roadside ? "Roadside NO₂ → asthma" : "PM2.5 → respiratory"}
            </span>
            <span className="driver-cite">{h.roadside ? "29 studies · 0.296" : "13 studies · 0.060"}</span>
          </div>
          <div className="driver-row">
            <span className="driver-name">Vulnerability ×{h.vulnerabilityWeight.toFixed(2)}</span>
            <span className="driver-cite">Milliman SVI</span>
          </div>
          <div className="driver-row">
            <span className="driver-name">Resp. demand {projectedDemand(h)} / {h.surgeCapacity} surge beds</span>
            <span className="driver-cite sim">simulated</span>
          </div>
        </div>
      </div>

      <div className="drawer-section">
        <ThinkingLog hospital={h} />
      </div>

      <div className="drawer-section">
        <div className="drawer-section-title">
          Severity mix <span className="sim-tag">simulated cohort · Apollo</span>
        </div>
        <div className="sevbar">
          <span className="sev sev-resp" style={{ flex: 41 }} title="Respiratory ward 41%" />
          <span className="sev sev-gen" style={{ flex: 51 }} title="General 51%" />
          <span className="sev sev-icu" style={{ flex: 8 }} title="ICU 8%" />
        </div>
        <div className="sev-legend">
          <span><i className="sw sw-resp" /> Resp ward 41%</span>
          <span><i className="sw sw-icu" /> ICU 8%</span>
          <span>avg LOS 6.8d</span>
        </div>
      </div>
    </div>
  );
}
