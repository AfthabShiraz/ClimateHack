import { useEffect, useRef, useState } from "react";
import { useStore, type Hospital } from "../state/store";
import { agentStreamUrl } from "../lib/api";

// Live agent reasoning via SSE (/agent/stream). Tokens arrive JSON-encoded as { t }
// and are concatenated to reconstruct the text exactly (Claude tokens or templated lines).
export default function ThinkingLog({ hospital }: { hospital: Hospital }) {
  const [text, setText] = useState("");
  const [streaming, setStreaming] = useState(true);
  const [error, setError] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setText("");
    setStreaming(true);
    setError(false);

    const center = useStore.getState().currentCenter();
    const url = agentStreamUrl({
      hospitalId: hospital.id,
      horizon: useStore.getState().horizon,
      centerLon: center?.lon ?? null,
      centerLat: center?.lat ?? null,
    });

    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        const { t } = JSON.parse(ev.data) as { t: string };
        setText((prev) => prev + t);
      } catch {
        /* ignore keep-alive / malformed frames */
      }
    };
    es.addEventListener("done", () => {
      setStreaming(false);
      es.close();
    });
    es.onerror = () => {
      // EventSource fires onerror both on transient close and on hard failure.
      setStreaming(false);
      if (!es || es.readyState === EventSource.CLOSED) setError(text.length === 0);
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hospital.id]);

  return (
    <div>
      <div className="drawer-section-title">
        Agent reasoning{" "}
        {streaming ? <span className="live-dot" /> : <span className="done-tick">✓</span>}
      </div>
      <div className="thinking" style={{ whiteSpace: "pre-wrap" }}>
        {text || (error ? "Agent stream unavailable (backend offline)." : "")}
        {streaming && <span className="caret" />}
      </div>
    </div>
  );
}
