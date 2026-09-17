"""Structured logging and run metrics for observability."""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


class JsonLogger:
    """Emit one JSON object per line so runs are queryable in a log store."""

    def __init__(self, run_id: str, stream=sys.stderr, log_file: Path | None = None) -> None:
        self.run_id = run_id
        self._stream = stream
        self._log_file = log_file

    def _emit(self, level: str, event: str, **fields: object) -> None:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": level,
            "run_id": self.run_id,
            "event": event,
            **fields,
        }
        line = json.dumps(payload, default=str)
        self._stream.write(line + "\n")
        self._stream.flush()
        if self._log_file is not None:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def info(self, event: str, **fields: object) -> None:
        self._emit("info", event, **fields)

    def warning(self, event: str, **fields: object) -> None:
        self._emit("warning", event, **fields)

    def error(self, event: str, **fields: object) -> None:
        self._emit("error", event, **fields)


@dataclass
class RunMetrics:
    """Aggregate counters and errors for a single pipeline run."""

    run_id: str
    started_at: str
    finished_at: str | None = None
    pages_fetched: int = 0
    pages_failed: int = 0
    items_parsed: int = 0
    items_loaded: int = 0
    errors: list[dict] = field(default_factory=list)

    def record_error(self, url: str, error: str) -> None:
        self.errors.append({"url": url, "error": error})

    def finish(self) -> None:
        self.finished_at = datetime.now(UTC).isoformat()

    def write(self, runs_dir: Path) -> Path:
        runs_dir.mkdir(parents=True, exist_ok=True)
        path = runs_dir / f"{self.run_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path
