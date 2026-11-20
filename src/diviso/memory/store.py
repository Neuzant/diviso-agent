"""SQLite persistent memory: facts, runs, checkpoints + MEMORY.md sync."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: str | Path, memory_md: str | Path | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_md = Path(memory_md) if memory_md else self.db_path.parent / "MEMORY.md"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT, updated REAL);
        CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, task TEXT, status TEXT,
                                          created REAL, state TEXT);
        CREATE TABLE IF NOT EXISTS checkpoints (run_id TEXT, step INTEGER, state TEXT,
                                                created REAL, PRIMARY KEY (run_id, step));
        """)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- facts -------------------------------------------------------------
    def set_fact(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO facts VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value, updated=excluded.updated",
            (key, value, time.time()))
        self.conn.commit()

    def get_fact(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def list_facts(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in
                self.conn.execute("SELECT key, value FROM facts ORDER BY key")}

    def delete_fact(self, key: str) -> None:
        self.conn.execute("DELETE FROM facts WHERE key=?", (key,))
        self.conn.commit()

    # -- MEMORY.md sync ------------------------------------------------------
    def export_to_markdown(self) -> Path:
        lines = ["# Diviso Memory", ""]
        for k, v in self.list_facts().items():
            lines.append(f"- {k}: {v}")
        self.memory_md.parent.mkdir(parents=True, exist_ok=True)
        self.memory_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.memory_md

    def import_from_markdown(self) -> int:
        if not self.memory_md.exists():
            return 0
        count = 0
        for line in self.memory_md.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                key, _, value = line[2:].partition(":")
                key, value = key.strip(), value.strip()
                if key and value:
                    self.set_fact(key, value)
                    count += 1
        return count

    # -- runs / checkpoints --------------------------------------------------
    def save_run(self, run_id: str, task: str, status: str, state: dict) -> None:
        self.conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "status=excluded.status, state=excluded.state",
            (run_id, task, status, time.time(), json.dumps(state)))
        self.conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "task": row["task"], "status": row["status"],
                "created": row["created"], "state": json.loads(row["state"] or "{}")}

    def save_checkpoint(self, run_id: str, step: int, state: dict) -> None:
        self.conn.execute(
            "INSERT INTO checkpoints VALUES (?,?,?,?) ON CONFLICT(run_id, step) "
            "DO UPDATE SET state=excluded.state, created=excluded.created",
            (run_id, step, json.dumps(state), time.time()))
        self.conn.commit()

    def latest_checkpoint(self, run_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM checkpoints WHERE run_id=? ORDER BY step DESC LIMIT 1",
            (run_id,)).fetchone()
        if not row:
            return None
        return {"run_id": row["run_id"], "step": row["step"],
                "state": json.loads(row["state"])}
