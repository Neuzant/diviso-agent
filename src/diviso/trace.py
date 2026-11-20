"""Streaming trace log: one JSONL file per run, appended as events happen."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import redact_text


class TraceLogger:
    def __init__(self, trace_dir: str | Path, run_id: str):
        self.dir = Path(trace_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.path = self.dir / f"{run_id}.jsonl"
        self.events: list[dict] = []

    def log(self, event: str, **fields) -> dict:
        record = {"ts": time.time(), "run_id": self.run_id, "event": event, **fields}
        record = json.loads(redact_text(json.dumps(record, default=str)))
        self.events.append(record)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return record

    @staticmethod
    def read(path: str | Path) -> list[dict]:
        p = Path(path)
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()]
