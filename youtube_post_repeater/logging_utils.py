from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JsonLogger:
    log_file: Path | None = None

    def emit(self, level: str, event: str, **fields: Any) -> None:
        payload = {
            "ts": utc_now_iso(),
            "level": level,
            "event": event,
            **fields,
        }
        line = json.dumps(payload, ensure_ascii=True)
        if self.log_file is None:
            return
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
