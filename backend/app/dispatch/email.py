"""The ACT step — send the readiness alert by email via Gmail SMTP (README.md §6).

GOVERNANCE: only ever called by POST /alert/dispatch (explicit human approval). Never fires
autonomously. If DISPATCH_ENABLED is false (or creds missing) it DRY-RUNS: logs and returns
ok with dryRun=true, so rehearsals are safe and the demo never accidentally emails anyone.
Gmail SMTP + app password is the fast path; swap this one function for Resend/SendGrid behind
the same signature without touching anything else.
"""
from __future__ import annotations

import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

from ..config import settings
from ..models import DispatchResult
from .audit import record_dispatch


def send_alert(to: str | None, subject: str, body: str, hospital_id: str = "") -> DispatchResult:
    recipient = to or settings.dispatch_to
    now = datetime.now(timezone.utc).isoformat()
    msg_id = f"crosssight-{uuid.uuid4().hex[:12]}"

    if not recipient:
        return DispatchResult(ok=False, sentAt=now, to="", dryRun=True,
                              detail="no recipient (set DISPATCH_TO)")

    # dry-run: governance-safe default
    if not (settings.dispatch_enabled and settings.gmail_user and settings.gmail_app_password):
        record_dispatch(hospital_id, recipient, subject, msg_id, dry_run=True)
        return DispatchResult(ok=True, sentAt=now, to=recipient, messageId=msg_id, dryRun=True,
                              detail="DISPATCH_ENABLED is off — logged only, no email sent")

    msg = EmailMessage()
    msg["From"] = settings.gmail_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{msg_id}@crosssight>"
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(settings.gmail_user, settings.gmail_app_password)
            smtp.send_message(msg)
    except Exception as e:  # never let a send failure crash the request
        record_dispatch(hospital_id, recipient, subject, msg_id, dry_run=False, error=str(e))
        return DispatchResult(ok=False, sentAt=now, to=recipient, messageId=msg_id, detail=str(e))

    record_dispatch(hospital_id, recipient, subject, msg_id, dry_run=False)
    return DispatchResult(ok=True, sentAt=now, to=recipient, messageId=msg_id, detail="sent")
