"""Pre-bake the Respiratory Readiness Alert briefs -> data/alerts.json (DEMO_MODE insurance).

Generates one brief per demo hospital at its own plume epicentre (the worst-case frame), using the
REAL claude-sonnet-4-6 call when ANTHROPIC_API_KEY is set, else the deterministic template. The
committed file lets DEMO_MODE serve a genuine brief instantly, so the dispatch climax never depends
on a live API call (plan.md §13.10). Re-run this WITH the key to capture real model output.

Usage (from repo root, with backend venv active):
    python data/scripts/build_alerts.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.alert import _template  # noqa: E402
from app.agents.client import agent_client  # noqa: E402
from app.agents.prompts import ALERT_USER, SYSTEM_PROMPT, hospital_context  # noqa: E402
from app.data_loader import load_catchments  # noqa: E402
from app.engine.risk import risk_engine  # noqa: E402
from app.models import LngLat  # noqa: E402
from app.providers.injector import EPISODE_SEQUENCES, exposure_at  # noqa: E402

OUT = ROOT / "data" / "alerts.json"
EPISODE = "pm25_spike"


def _content_for(c, risk) -> tuple[dict, str]:
    """Real-Claude JSON if available, else the deterministic template."""
    raw = agent_client.complete(SYSTEM_PROMPT, ALERT_USER.format(context=hospital_context(c, risk)))
    if raw is not None:
        try:
            s, e = raw.find("{"), raw.rfind("}")
            return json.loads(raw[s : e + 1]), "claude-sonnet-4-6"
        except Exception:
            pass
    return _template(c, risk), "template"


def main() -> None:
    catchments = {c.id: c for c in load_catchments()}
    seq = EPISODE_SEQUENCES.get(EPISODE, [])
    alerts: dict[str, dict] = {}
    gen_modes: set[str] = set()
    for cid in seq:
        c = catchments.get(cid)
        if c is None:
            continue
        center = LngLat(lon=c.lon, lat=c.lat)  # worst-case: plume centred on the hospital
        exposure = exposure_at(c, center, EPISODE)
        risk = risk_engine.compute(c, exposure, "now")
        content, mode = _content_for(c, risk)
        gen_modes.add(mode)
        alerts[cid] = content

    out = {
        "_meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "episode": EPISODE,
            "generatedBy": sorted(gen_modes),
            "note": "Pre-baked briefs served in DEMO_MODE (settings.demo_mode). Re-run WITH ANTHROPIC_API_KEY to capture real claude-sonnet-4-6 output; 'template' entries are deterministic fallbacks.",
        },
        "alerts": alerts,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT} — {len(alerts)} briefs, generatedBy={sorted(gen_modes)}")


if __name__ == "__main__":
    main()
