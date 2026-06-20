import { useEffect, useState } from "react";
import { projectedDemand, type Hospital } from "../state/store";

// Stand-in for the live agent (M4 swaps for an Anthropic stream). Every line is built
// from the engine + datasets — the same inputs the real agent receives.
function steps(h: Hospital): string[] {
  const driver = h.roadside ? "roadside NO₂ (traffic)" : "fine particulates (PM2.5)";
  const studies = h.roadside ? 29 : 13;
  const demand = projectedDemand(h);
  return [
    `Reading live exposure for ${h.name}…`,
    `Local pollution ${(h.exposure * 100).toFixed(0)}% of health threshold → driver: ${driver}`,
    `Weighting by catchment vulnerability ×${h.vulnerabilityWeight.toFixed(2)} [Milliman]`,
    `Matching evidence: ${driver} → respiratory, ${studies} studies [System graph]`,
    `Projecting exposure→admission lag → surge expected in ~5 days`,
    `Readiness gap: projected ${demand} resp. cases vs ${h.surgeCapacity} surge beds`,
    `Drafting preparation plan…`,
  ];
}

function suggestions(h: Hospital): { text: string; cite: string }[] {
  const demand = projectedDemand(h);
  const over = demand - h.surgeCapacity;
  return [
    {
      text: `Pre-position oxygen & nebulisers${over > 0 ? ` (≈${over}-bed shortfall projected)` : ""}`,
      cite: "demand model",
    },
    { text: `Add a respiratory-ward shift across the 5–7 day surge window`, cite: "staffing" },
    {
      text: `Proactively contact high-risk COPD/asthma patients in the catchment`,
      cite: h.roadside ? "29-study traffic-asthma evidence" : "13-study respiratory evidence",
    },
  ];
}

export default function ThinkingLog({ hospital }: { hospital: Hospital }) {
  const lines = steps(hospital);
  const [n, setN] = useState(0);

  useEffect(() => {
    setN(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setN(i);
      if (i >= lines.length) clearInterval(id);
    }, 560);
    return () => clearInterval(id);
  }, [hospital.id]);

  const thinking = n < lines.length;
  const acts = suggestions(hospital);

  return (
    <div>
      <div className="drawer-section-title">
        Agent reasoning {thinking ? <span className="live-dot" /> : <span className="done-tick">✓</span>}
      </div>
      <div className="thinking">
        {lines.slice(0, n).map((l, i) => (
          <div key={i} className={"think-line" + (i === n - 1 && thinking ? " active" : "")}>
            <span className="think-bullet">›</span> {l}
          </div>
        ))}
        {thinking && <div className="think-line ghost"><span className="caret" /></div>}
      </div>

      {!thinking && (
        <div className="suggestions">
          <div className="drawer-section-title" style={{ marginTop: 14 }}>
            ⚠ Recommended preparation
          </div>
          {acts.map((a, i) => (
            <div key={i} className="sugg-row" style={{ animationDelay: `${i * 120}ms` }}>
              <span className="sugg-check">▢</span>
              <span className="sugg-text">{a.text}</span>
              <span className="sugg-cite">{a.cite}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
