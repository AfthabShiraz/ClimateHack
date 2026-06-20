import { useStore, type ExposureKey, type LayerToggles } from "../state/store";

const EXPOSURES: { key: ExposureKey; label: string; note?: string }[] = [
  { key: "pm25", label: "PM2.5" },
  { key: "no2", label: "NO₂" },
  { key: "o3", label: "O₃", note: "visual only" },
  { key: "heat", label: "Heat" },
  { key: "combined", label: "Combined" },
];

const LAYERS: { key: keyof LayerToggles; label: string }[] = [
  { key: "exposure", label: "Exposure field" },
  { key: "columns", label: "Hospital columns" },
  { key: "catchments", label: "Catchments" },
  { key: "labels", label: "Labels" },
];

export default function LeftRail() {
  const { exposure, setExposure, layers, toggleLayer } = useStore();

  return (
    <div className="leftrail">
      <div className="panel">
        <div className="panel-title">Exposure</div>
        <div className="exposure-grid">
          {EXPOSURES.map((e) => (
            <button
              key={e.key}
              className={exposure === e.key ? "expo active" : "expo"}
              onClick={() => setExposure(e.key)}
              title={e.note}
            >
              {e.label}
              {e.note && <span className="expo-note">{e.note}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">Map layers</div>
        <div className="layer-list">
          {LAYERS.map((l) => (
            <label key={l.key} className="layer-row">
              <input
                type="checkbox"
                checked={layers[l.key]}
                onChange={() => toggleLayer(l.key)}
              />
              <span>{l.label}</span>
            </label>
          ))}
        </div>

        <div className="legend">
          <div className="legend-title">RPI band</div>
          <div className="legend-row"><span className="sw sw-green" /> Green &lt; 40</div>
          <div className="legend-row"><span className="sw sw-amber" /> Amber 40–70</div>
          <div className="legend-row"><span className="sw sw-red" /> Red &gt; 70</div>
        </div>
      </div>
    </div>
  );
}
