"""Alert notification — Slack webhook scaffold.

Kept intentionally minimal. Cron capture (stdout/MAILTO) is the primary
channel; Slack is opt-in via the SLACK_WEBHOOK_URL env var.
"""
from __future__ import annotations

import os
import sys


def send_alert(message: str, level: str = "WARNING") -> None:
    """Emit an alert. Always prints; POSTs to Slack if configured."""
    line = f"[{level}] {message}"
    print(line, file=sys.stdout, flush=True)
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        try:
            import requests  # local import — optional dep at runtime
            requests.post(webhook_url, json={"text": line}, timeout=5)
        except Exception as exc:
            print(f"[notify] slack post failed: {exc}", file=sys.stderr)
