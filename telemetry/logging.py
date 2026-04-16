"""Structured logging helpers for runtime observability."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


class VisionLogger:
    """Emit either JSON or simple text logs."""

    def __init__(self, json_mode: bool = False) -> None:
        self.json_mode = json_mode

    def log(self, event: str, **fields: object) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.json_mode:
            print(json.dumps({"timestamp": timestamp, "event": event, **fields}), file=sys.stderr)
        else:
            details = " ".join(f"{key}={value}" for key, value in fields.items())
            print(f"[vision-os] {event} {details}".rstrip(), file=sys.stderr)
