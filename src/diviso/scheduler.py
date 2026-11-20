"""Scheduler with per-job cost/token guards.

A job whose estimated tokens or cost exceeds its guard is SKIPPED and logged —
a scheduled job must never burn tokens overnight.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Job:
    id: int
    name: str
    prompt: str
    interval_seconds: int
    max_tokens: int
    max_cost_usd: float
    est_tokens: int
    est_cost_usd: float
    enabled: bool = True
    last_run: float | None = None
    last_status: str = ""


class Scheduler:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, name TEXT, prompt TEXT,
          interval_seconds INTEGER, max_tokens INTEGER, max_cost_usd REAL,
          est_tokens INTEGER, est_cost_usd REAL, enabled INTEGER, last_run REAL,
          last_status TEXT);
        CREATE TABLE IF NOT EXISTS job_log (id INTEGER PRIMARY KEY, job_id INTEGER,
          ts REAL, status TEXT, detail TEXT);
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def add_job(self, name: str, prompt: str, interval_seconds: int = 3600,
                max_tokens: int = 4000, max_cost_usd: float = 0.10,
                est_tokens: int = 1000, est_cost_usd: float = 0.01) -> int:
        cur = self.conn.execute(
            "INSERT INTO jobs (name,prompt,interval_seconds,max_tokens,max_cost_usd,"
            "est_tokens,est_cost_usd,enabled) VALUES (?,?,?,?,?,?,?,1)",
            (name, prompt, interval_seconds, max_tokens, max_cost_usd,
             est_tokens, est_cost_usd))
        self.conn.commit()
        return int(cur.lastrowid)

    def list_jobs(self) -> list[Job]:
        return [Job(**{**dict(r), "enabled": bool(r["enabled"])})
                for r in self.conn.execute("SELECT * FROM jobs ORDER BY id")]

    def guard_check(self, job: Job) -> tuple[bool, str]:
        if job.est_tokens > job.max_tokens:
            return False, f"est_tokens {job.est_tokens} > max_tokens {job.max_tokens}"
        if job.est_cost_usd > job.max_cost_usd:
            return False, f"est_cost ${job.est_cost_usd} > max_cost ${job.max_cost_usd}"
        return True, "within guard"

    def _log(self, job_id: int, status: str, detail: str) -> None:
        self.conn.execute("INSERT INTO job_log (job_id,ts,status,detail) VALUES (?,?,?,?)",
                          (job_id, time.time(), status, detail))
        self.conn.execute("UPDATE jobs SET last_run=?, last_status=? WHERE id=?",
                          (time.time(), status, job_id))
        self.conn.commit()

    def logs(self, job_id: int | None = None) -> list[dict]:
        q = "SELECT * FROM job_log"
        args: tuple = ()
        if job_id is not None:
            q += " WHERE job_id=?"
            args = (job_id,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", args)]

    def run_job(self, job_id: int, executor: Callable[[str], str]) -> dict:
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"No job {job_id}")
        job = Job(**{**dict(row), "enabled": bool(row["enabled"])})
        ok, reason = self.guard_check(job)
        if not ok:
            self._log(job_id, "skipped_guard", reason)
            return {"job_id": job_id, "status": "skipped_guard", "detail": reason}
        result = executor(job.prompt)
        self._log(job_id, "ran", str(result)[:500])
        return {"job_id": job_id, "status": "ran", "result": result}

    def due_jobs(self, now: float | None = None) -> list[Job]:
        now = now or time.time()
        return [j for j in self.list_jobs() if j.enabled and
                (j.last_run is None or now - j.last_run >= j.interval_seconds)]
