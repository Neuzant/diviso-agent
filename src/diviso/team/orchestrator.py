"""Multi-agent team: Researcher -> Coder -> Reviewer, with exactly ONE fix pass."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..providers.base import Message, Provider

ROLES = {
    "researcher": "You are the Researcher. Gather and summarise the facts needed.",
    "coder": "You are the Coder. Produce a concrete solution based on the research.",
    "reviewer": "You are the Reviewer. If the solution is acceptable reply starting "
                "with 'APPROVED:'. Otherwise reply starting with 'NEEDS_FIX:' and "
                "list what must change.",
}


@dataclass
class TeamResult:
    research: str
    solution: str
    review: str
    fix_passes: int
    approved: bool
    transcript: list[dict] = field(default_factory=list)


class Team:
    def __init__(self, provider: Provider, model: str | None = None):
        self.provider = provider
        self.model = model

    def _ask(self, role: str, prompt: str) -> str:
        return self.provider.chat(
            [Message("system", ROLES[role]), Message("user", prompt)],
            model=self.model).text

    def run(self, task: str) -> TeamResult:
        transcript = []
        research = self._ask("researcher", f"Research this task: {task}")
        transcript.append({"role": "researcher", "text": research})
        solution = self._ask("coder", f"Task: {task}\nResearch:\n{research}")
        transcript.append({"role": "coder", "text": solution})
        review = self._ask("reviewer", f"Task: {task}\nSolution:\n{solution}")
        transcript.append({"role": "reviewer", "text": review})
        fix_passes = 0
        approved = review.strip().startswith("APPROVED")
        if not approved:
            # Exactly one fix pass — never an unbounded review loop.
            fix_passes = 1
            solution = self._ask(
                "coder", f"Task: {task}\nYour previous solution:\n{solution}\n"
                         f"Reviewer feedback:\n{review}\nProduce a fixed solution.")
            transcript.append({"role": "coder", "text": solution, "fix_pass": True})
            review = self._ask("reviewer", f"Task: {task}\nSolution:\n{solution}")
            transcript.append({"role": "reviewer", "text": review})
            approved = review.strip().startswith("APPROVED")
        return TeamResult(research, solution, review, fix_passes, approved, transcript)
