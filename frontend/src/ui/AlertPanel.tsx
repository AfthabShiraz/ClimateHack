import { useEffect, useRef, useState } from "react";
import { useStore, type Hospital } from "../state/store";
import { actStreamUrl } from "../lib/api";
import type {
  ActProgressEvent,
  ActResult,
  DispatchResult,
  ReadinessAlert,
} from "../lib/types";

const GEN_LABEL: Record<string, string> = {
  "claude-sonnet-4-6": "Claude Sonnet 4.6",
  "pre-baked": "pre-baked",
  "template-fallback": "template",
};

type ActPhase = "idle" | "acting" | "done";

interface TimelineStep {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "error";
  detail?: string;
  result?: DispatchResult;
}

export default function AlertPanel({ hospital }: { hospital: Hospital }) {
  const { draftAlert, horizon, simActive, episodeName } = useStore();
  const [alert, setAlert] = useState<ReadinessAlert | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [actPhase, setActPhase] = useState<ActPhase>("idle");
  const [timeline, setTimeline] = useState<TimelineStep[]>([]);
  const [actResult, setActResult] = useState<ActResult | null>(null);
  const [showBody, setShowBody] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setAlert(null);
    setActPhase("idle");
    setTimeline([]);
    setActResult(null);
    setShowBody(false);
    setError(null);
    esRef.current?.close();
  }, [hospital.id]);

  const onDraft = async () => {
    setDrafting(true);
    setError(null);
    try {
      setAlert(await draftAlert(hospital.id));
    } catch {
      setError("Could not reach the agent (backend offline).");
    } finally {
      setDrafting(false);
    }
  };

  const onAct = () => {
    setActPhase("acting");
    setError(null);
    setTimeline([
      { id: "draft", label: "Agent preparing outreach…", status: "active" },
      { id: "supervisor", label: "Supervisor readiness alert", status: "pending" },
      { id: "patients", label: "High-risk patient outreach", status: "pending" },
    ]);

    const center = useStore.getState().currentCenter();
    const url = actStreamUrl({
      hospitalId: hospital.id,
      horizon,
      episode: simActive ? episodeName : null,
      centerLon: center?.lon ?? null,
      centerLat: center?.lat ?? null,
    });

    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ActProgressEvent;

      if (msg.phase === "drafting" && msg.label) {
        setTimeline((t) =>
          t.map((s) => (s.id === "draft" ? { ...s, label: msg.label!, status: "active" } : s))
        );
      }

      if (msg.phase === "ready") {
        if (msg.alert) setAlert(msg.alert);
        setTimeline((t) =>
          t.map((s) => {
            if (s.id === "draft") return { ...s, status: "done", label: "Brief & cohort ready" };
            if (s.id === "patients" && msg.outreach) {
              return {
                ...s,
                label: `Patient outreach — ${msg.outreach.cohortSize.toLocaleString()} contacts`,
              };
            }
            return s;
          })
        );
      }

      if (msg.phase === "supervisor") {
        if (msg.status === "sending") {
          setTimeline((t) =>
            t.map((s) =>
              s.id === "supervisor"
                ? { ...s, status: "active", label: msg.label ?? s.label, detail: `→ ${msg.to}` }
                : s
            )
          );
        }
        if (msg.status === "done" && msg.result) {
          setTimeline((t) =>
            t.map((s) =>
              s.id === "supervisor"
                ? {
                    ...s,
                    status: msg.result!.ok ? "done" : "error",
                    result: msg.result,
                    detail: msg.result!.dryRun
                      ? `Dry-run → ${msg.result!.to}`
                      : `Sent → ${msg.result!.to}`,
                  }
                : s
            )
          );
        }
      }

      if (msg.phase === "patients") {
        if (msg.status === "sending") {
          setTimeline((t) =>
            t.map((s) =>
              s.id === "patients"
                ? {
                    ...s,
                    status: "active",
                    label: msg.label ?? s.label,
                    detail: msg.count ? `${msg.count.toLocaleString()} messages → ${msg.to}` : undefined,
                  }
                : s
            )
          );
        }
        if (msg.status === "done" && msg.result) {
          setTimeline((t) =>
            t.map((s) =>
              s.id === "patients"
                ? {
                    ...s,
                    status: msg.result!.ok ? "done" : "error",
                    result: msg.result,
                    detail: msg.result!.dryRun
                      ? `Dry-run batch → ${msg.result!.to}`
                      : `Batch sent → ${msg.result!.to}`,
                  }
                : s
            )
          );
        }
      }
    };

    es.addEventListener("done", (ev) => {
      const result = JSON.parse((ev as MessageEvent).data) as ActResult;
      setActResult(result);
      setActPhase("done");
      es.close();
    });

    es.onerror = () => {
      setError("Agent ACT failed (backend offline or stream error).");
      setActPhase("idle");
      es.close();
    };
  };

  const canAct = hospital.band !== "green" || hospital.rpi >= 40 || simActive;

  return (
    <div>
      <div className="drawer-section-title">Agent ACT</div>

      {actPhase === "idle" && (
        <>
          {!alert && (
            <button className="alert-draft-btn act-btn-secondary" onClick={() => void onDraft()} disabled={drafting}>
              {drafting ? "Agent drafting…" : "✎ Preview readiness brief"}
            </button>
          )}

          {alert && (
            <div className="alert-card alert-card-compact">
              <div className="alert-meta">
                <span className={`gen-badge gen-${alert.generatedBy === "claude-sonnet-4-6" ? "live" : "fallback"}`}>
                  {GEN_LABEL[alert.generatedBy] ?? alert.generatedBy}
                </span>
                <span className="alert-sev">+{alert.leadTimeDays}d lead</span>
              </div>
              <div className="alert-subject">{alert.subject}</div>
              <button className="body-toggle" onClick={() => setShowBody((v) => !v)}>
                {showBody ? "Hide brief" : "Preview brief"}
              </button>
              {showBody && <pre className="body-preview">{alert.bodyText}</pre>}
            </div>
          )}

          <button
            className="act-btn"
            onClick={onAct}
            disabled={!canAct}
            title={canAct ? "Email supervisor + message affected patients" : "Run an episode or wait for amber RPI"}
          >
            ⚡ Agent ACT — notify supervisor & patients
          </button>
          {!canAct && (
            <p className="act-hint">Run ⚡ Simulate episode or select an amber/red hospital to unlock ACT.</p>
          )}
        </>
      )}

      {actPhase !== "idle" && (
        <div className="act-timeline">
          {timeline.map((step) => (
            <div key={step.id} className={`act-step act-step-${step.status}`}>
              <span className="act-step-icon">
                {step.status === "done" ? "✓" : step.status === "error" ? "✕" : step.status === "active" ? "◎" : "○"}
              </span>
              <div className="act-step-body">
                <div className="act-step-label">{step.label}</div>
                {step.detail && <div className="act-step-detail">{step.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {actResult && actPhase === "done" && (
        <div className="act-complete">
          <div className="act-complete-head">
            <span className="act-complete-check">✓</span>
            <span>Agent ACT complete</span>
          </div>

          {actResult.outreach.messages.length > 0 && (
            <div className="patient-previews">
              <div className="alert-field-label">Sample patient messages sent</div>
              {actResult.outreach.messages.map((m, i) => (
                <div key={i} className="patient-msg">
                  <div className="patient-msg-head">
                    <span className="patient-msg-label">{m.patientLabel}</span>
                    <span className="patient-msg-channel">{m.channel.toUpperCase()}</span>
                  </div>
                  <p className="patient-msg-text">{m.preview}</p>
                </div>
              ))}
              <p className="patient-msg-note">
                {actResult.outreach.cohortSize.toLocaleString()} high-risk contacts in production;
                demo delivers both emails to your inbox.
              </p>
            </div>
          )}

          {actResult.steps.map((s) => (
            <div key={s.step} className={`dispatch-result ${s.dryRun ? "dry" : "sent"}`}>
              {s.dryRun ? (
                <>
                  <b>Dry-run</b> — {s.label}. Add Gmail creds to send for real.
                </>
              ) : (
                <>
                  <b>✓ Sent</b> — {s.label}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {error && <div className="alert-error">{error}</div>}
    </div>
  );
}
