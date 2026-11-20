"""Checkpoint / resume: state is saved after every agent step so a crashed
run can be resumed by id."""
from __future__ import annotations

from dataclasses import dataclass

from .memory.store import MemoryStore


@dataclass
class RunState:
    run_id: str
    task: str
    step: int
    messages: list[dict]
    cost_usd: float = 0.0
    status: str = "running"
    result: str = ""

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "task": self.task, "step": self.step,
                "messages": self.messages, "cost_usd": self.cost_usd,
                "status": self.status, "result": self.result}

    @classmethod
    def from_dict(cls, d: dict) -> "RunState":
        return cls(run_id=d["run_id"], task=d.get("task", ""), step=d.get("step", 0),
                   messages=d.get("messages", []), cost_usd=d.get("cost_usd", 0.0),
                   status=d.get("status", "running"), result=d.get("result", ""))


class CheckpointManager:
    def __init__(self, store: MemoryStore):
        self.store = store

    def save(self, state: RunState) -> None:
        self.store.save_checkpoint(state.run_id, state.step, state.to_dict())
        self.store.save_run(state.run_id, state.task, state.status, state.to_dict())

    def resume(self, run_id: str) -> RunState | None:
        cp = self.store.latest_checkpoint(run_id)
        if cp:
            return RunState.from_dict(cp["state"])
        run = self.store.get_run(run_id)
        if run:
            return RunState.from_dict(run["state"])
        return None
