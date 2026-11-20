"""ReAct loop with hard step + cost caps and a visible trace.

Protocol for the model (works with any chat provider):
- Reply `TOOL_CALL: {"name": "<tool>", "args": {...}}` to use a tool.
- Reply `FINAL: <answer>` (or any plain reply) to finish.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Callable

from ..checkpoint import CheckpointManager, RunState
from ..providers.base import Message, Provider
from ..trace import TraceLogger

ToolFn = Callable[..., str]
SYSTEM = ("You are Diviso, a local-first AI agent. Think step by step. "
          "To use a tool reply exactly: TOOL_CALL: {\"name\": \"...\", \"args\": {...}}. "
          "When done reply: FINAL: <answer>")


@dataclass
class ReactResult:
    run_id: str
    answer: str
    steps: int
    cost_usd: float
    stopped_reason: str  # "final" | "max_steps" | "max_cost" | "resumed"
    trace: list[dict] = field(default_factory=list)


class ReactAgent:
    def __init__(self, provider: Provider, tools: dict[str, ToolFn] | None = None,
                 max_steps: int = 20, max_cost_usd: float = 1.0,
                 trace_logger: TraceLogger | None = None,
                 checkpoints: CheckpointManager | None = None,
                 model: str | None = None):
        self.provider = provider
        self.tools = tools or {}
        self.max_steps = max_steps
        self.max_cost_usd = max_cost_usd
        self.trace_logger = trace_logger
        self.checkpoints = checkpoints
        self.model = model

    def _trace(self, event: str, **fields) -> None:
        if self.trace_logger:
            self.trace_logger.log(event, **fields)

    def run(self, task: str, run_id: str | None = None,
            resume_state: RunState | None = None) -> ReactResult:
        run_id = run_id or (resume_state.run_id if resume_state else uuid.uuid4().hex[:12])
        if resume_state:
            messages = [Message(**m) for m in resume_state.messages]
            step = resume_state.step
            cost = resume_state.cost_usd
        else:
            messages = [Message("system", SYSTEM), Message("user", task)]
            step, cost = 0, 0.0
        answer, reason = "", "max_steps"
        while step < self.max_steps:
            step += 1
            resp = self.provider.chat(messages, model=self.model)
            cost += resp.cost_usd
            self._trace("step", step=step, text=resp.text, cost_usd=cost)
            if cost > self.max_cost_usd:
                reason, answer = "max_cost", resp.text
                self._trace("stop", reason=reason, step=step)
                self._save(run_id, task, messages, step, cost, "stopped", answer)
                break
            text = resp.text.strip()
            if text.startswith("TOOL_CALL:"):
                messages.append(Message("assistant", text))
                try:
                    payload = json.loads(text[len("TOOL_CALL:"):].strip())
                    name, args = payload["name"], payload.get("args", {})
                    if name not in self.tools:
                        result = f"Error: unknown tool {name}"
                    else:
                        result = str(self.tools[name](**args))
                except Exception as exc:  # tool errors are observations, not crashes
                    result = f"Error: {exc}"
                self._trace("tool", step=step, result=result[:500])
                messages.append(Message("user", f"Observation: {result}"))
                self._save(run_id, task, messages, step, cost, "running", "")
                continue
            answer = text[len("FINAL:"):].strip() if text.startswith("FINAL:") else text
            reason = "final"
            self._trace("final", step=step, answer=answer)
            self._save(run_id, task, messages, step, cost, "done", answer)
            break
        else:
            self._trace("stop", reason="max_steps", step=step)
            self._save(run_id, task, messages, step, cost, "stopped", answer)
        events = self.trace_logger.events if self.trace_logger else []
        return ReactResult(run_id=run_id, answer=answer, steps=step, cost_usd=cost,
                           stopped_reason=reason, trace=list(events))

    def _save(self, run_id, task, messages, step, cost, status, result) -> None:
        if self.checkpoints:
            self.checkpoints.save(RunState(
                run_id=run_id, task=task, step=step,
                messages=[m.to_dict() for m in messages], cost_usd=cost,
                status=status, result=result))
