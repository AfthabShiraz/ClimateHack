import { useStore, BAND_COLOR, projectedDemand } from "../state/store";
import ThinkingLog from "./ThinkingLog";
import AlertPanel from "./AlertPanel";

const TERM_LABEL: Record<string, string> = {
  pm25_respiratory: "PM2.5 → respiratory",
  no2_asthma: "NO₂ → asthma",
  roadside_asthma: "Roadside NO₂ → asthma",
  heat_mortality: "Heat → mortality",
};

export default function Drawer() {
  const { hospitals, selectedId, select } = useStore();
  const h = hospitals.find((x) => x.id === selectedId);
  if (!h) return null;

  const flagged = h.band !== "green";
  const sev = h.severityMix;

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
        RPI {Math.round(h.rpi)} · {h.band.toUpperCase()}
      </div>

      {flagged && (
        <div className="leadtime">
          <div className="leadtime-label">Projected respiratory surge</div>
          <div className="leadtime-value">+{h.leadTimeDays} days</div>
          <div className="leadtime-sub">lead time to prepare</div>
        </div>
      )}

      <div className="drawer-section">
        <div className="drawer-section-title">Why — driver breakdown</div>
        <div className="drivers">
          {h.drivers.length > 0 ? (
            [...h.drivers]
              .sort((a, b) => b.contribution - a.contribution)
              .map((d) => (
                <div className="driver-row" key={d.term}>
                  <span className="driver-name">
                    {TERM_LABEL[d.term] ?? d.term}
                    {d.substituted && <span className="driver-sub-tag"> roadside</span>}
                  </span>
                  <span className="driver-cite">
                    {d.numStudies ?? "—"} studies · {d.effectSize.toFixed(3)}
                  </span>
                </div>
              ))
          ) : (
            <div className="driver-row">
              <span className="driver-name">
                {h.roadside ? "Roadside NO₂ → asthma" : "PM2.5 → respiratory"}
              </span>
              <span className="driver-cite sim">connecting…</span>
            </div>
          )}
          <div className="driver-row">
            <span className="driver-name">Vulnerability ×{h.vulnerabilityWeight.toFixed(2)}</span>
            <span className="driver-cite">Milliman SVI</span>
          </div>
          <div className="driver-row">
            <span className="driver-name">
              Resp. demand {projectedDemand(h)} / {Math.round(h.surgeCapacity.value)} surge beds
            </span>
            <span className="driver-cite">demand model</span>
          </div>
        </div>
      </div>

      <div className="drawer-section">
        <ThinkingLog hospital={h} />
      </div>

      <div className="drawer-section">
        <AlertPanel hospital={h} />
      </div>

      <div className="drawer-section">
        <div className="drawer-section-title">
          Severity mix <span className="sim-tag">Apollo cohort</span>
        </div>
        <div className="sevbar">
          <span className="sev sev-resp" style={{ flex: sev.respWardPct }} title={`Respiratory ward ${sev.respWardPct}%`} />
          <span className="sev sev-gen" style={{ flex: sev.generalPct }} title={`General ${sev.generalPct}%`} />
          <span className="sev sev-icu" style={{ flex: sev.icuPct }} title={`ICU ${sev.icuPct}%`} />
        </div>
        <div className="sev-legend">
          <span><i className="sw sw-resp" /> Resp ward {sev.respWardPct.toFixed(0)}%</span>
          <span><i className="sw sw-icu" /> ICU {sev.icuPct.toFixed(0)}%</span>
          <span>avg LOS {sev.avgLOS.toFixed(1)}d</span>
        </div>
      </div>
    </div>
  );
}
