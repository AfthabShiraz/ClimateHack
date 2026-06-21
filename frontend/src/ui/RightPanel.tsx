import { useStore, BAND_COLOR } from "../state/store";

export default function RightPanel() {
  const { hospitals, selectedId, select } = useStore();

  const counts = hospitals.reduce(
    (acc, h) => ((acc[h.band]++, acc)),
    { green: 0, amber: 0, red: 0 } as Record<string, number>
  );
  const ranked = [...hospitals].sort((a, b) => b.rpi - a.rpi);

  return (
    <div className="rightpanel">
      <div className="panel">
        <div className="panel-title">City pressure</div>
        <div className="stat-cluster">
          <div className="stat stat-red"><b>{counts.red}</b><span>red</span></div>
          <div className="stat stat-amber"><b>{counts.amber}</b><span>amber</span></div>
          <div className="stat stat-green"><b>{counts.green}</b><span>green</span></div>
        </div>
      </div>

      <div className="panel panel-grow">
        <div className="panel-title">Risk ranking</div>
        <div className="ranking">
          {ranked.map((h, i) => (
            <button
              key={h.id}
              className={selectedId === h.id ? "rank-row active" : "rank-row"}
              onClick={() => select(h.id)}
            >
              <span className="rank-no">{i + 1}</span>
              <span className="rank-chip" style={{ background: BAND_COLOR[h.band] }} />
              <span className="rank-name">{h.name}</span>
              <span className="rank-rpi">{Math.round(h.rpi)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
