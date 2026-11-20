"""Task planner: break work into steps, retry failures with a different
approach, and reflect on the outcome."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..providers.base import Message, Provider

Executor = Callable[[str], str]  # step prompt -> result text; raise or return "ERROR:..." on failure


@dataclass
class StepResult:
    step: str
    result: str
    attempts: int
    succeeded: bool


@dataclass
class Reflection:
    task: str
    succeeded: bool
    completed_steps: int
    failed_steps: int
    summary: str
    lessons: list[str] = field(default_factory=list)


@dataclass
class PlanResult:
    steps: list[StepResult]
    reflection: Reflection


class Planner:
    def __init__(self, provider: Provider, executor: Executor | None = None,
                 max_retries: int = 2, model: str | None = None):
        self.provider = provider
        self.executor = executor or self._default_executor
        self.max_retries = max_retries
        self.model = model

    def _default_executor(self, prompt: str) -> str:
        return self.provider.chat([Message("user", prompt)], model=self.model).text

    def plan(self, task: str) -> list[str]:
        resp = self.provider.chat([
            Message("system", "Break the task into short steps, one per line, "
                              "each line starting with '- '."),
            Message("user", f"Task: {task}")], model=self.model)
        steps = [line[2:].strip() for line in resp.text.splitlines()
                 if line.strip().startswith("- ") and line.strip()[2:]]
        if steps:
            return steps
        # Heuristic fallback (deterministic, offline): split on sequencing words.
        parts = [p.strip() for p in task.replace(" and then ", ". ").split(". ")
                 if p.strip()]
        return parts or [task]

    def execute(self, task: str) -> PlanResult:
        results: list[StepResult] = []
        for step_text in self.plan(task):
            attempts, result, ok = 0, "", False
            prompt = step_text
            while attempts <= self.max_retries:
                attempts += 1
                try:
                    out = self.executor(prompt)
                    if out.startswith("ERROR:"):
                        raise RuntimeError(out)
                    result, ok = out, True
                    break
                except Exception as exc:
                    result = f"ERROR: {exc}"
                    # Retry with a *different* approach, not the same prompt.
                    prompt = (f"{step_text}\nPrevious attempt failed ({exc}). "
                              f"Try a completely different approach (attempt {attempts + 1}).")
            results.append(StepResult(step_text, result, attempts, ok))
        return PlanResult(results, self.reflect(task, results))

    def reflect(self, task: str, results: list[StepResult]) -> Reflection:
        done = sum(1 for r in results if r.succeeded)
        failed = len(results) - done
        lessons = []
        for r in results:
            if not r.succeeded:
                lessons.append(f"Step '{r.step}' failed after {r.attempts} attempts: {r.result}")
            elif r.attempts > 1:
                lessons.append(f"Step '{r.step}' needed {r.attempts} attempts; "
                               "the alternate approach worked.")
        return Reflection(task=task, succeeded=failed == 0, completed_steps=done,
                          failed_steps=failed,
                          summary=f"{done}/{len(results)} steps completed for: {task}",
                          lessons=lessons)
