"""Append-only dispatch log — the governance/audit trail + measurement metric (README.md §6).

Every dispatch (real or dry-run) is recorded. Powers the Drawer confirmation chip and the
"alerts dispatched / acted on" count. JSONL so it is trivially greppable and append-safe.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent.parent / "dispatch_log.jsonl"


def record_dispatch(
    hospital_id: str, to: str, subject: str, message_id: str,
    dry_run: bool, error: str | None = None, kind: str = "supervisor",
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hospitalId": hospital_id,
        "kind": kind,
        "to": to,
        "subject": subject,
        "messageId": message_id,
        "dryRun": dry_run,
        "error": error,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def dispatch_count() -> int:
    if not LOG_PATH.exists():
        return 0
    return sum(1 for _ in LOG_PATH.open())


def recent(limit: int = 20) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text().splitlines()[-limit:]
    return [json.loads(l) for l in lines]
