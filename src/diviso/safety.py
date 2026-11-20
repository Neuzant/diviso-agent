"""Sandbox + approval gate.

Every write / shell / network action must pass the approval gate with a
dry-run description (and a diff for file writes) before it executes.
Writes are confined to the workspace root by the Sandbox.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


class SandboxError(Exception):
    pass


class ApprovalDenied(Exception):
    pass


class Sandbox:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        resolved = p.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise SandboxError(f"Path escapes workspace: {path} -> {resolved}")
        return resolved

    def check(self, path: str | Path) -> Path:
        return self.resolve(path)


def make_diff(path: str, old: str, new: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}"))


@dataclass
class Action:
    kind: str            # "write" | "shell" | "network" | "read"
    description: str
    diff: str = ""
    target: str = ""


# Callback returns True to approve, False to deny.
ApprovalCallback = Callable[[Action], bool]


@dataclass
class ApprovalGate:
    auto_approve: bool = False
    callback: ApprovalCallback | None = None
    history: list[Action] = field(default_factory=list)
    decisions: list[bool] = field(default_factory=list)

    def require(self, action: Action) -> bool:
        """Return True if approved. Read actions always pass."""
        if action.kind == "read":
            return True
        self.history.append(action)
        if self.auto_approve:
            self.decisions.append(True)
            return True
        if self.callback is None:
            # Safe default: without an explicit approver, deny mutations.
            self.decisions.append(False)
            return False
        ok = bool(self.callback(action))
        self.decisions.append(ok)
        return ok

    def require_or_raise(self, action: Action) -> None:
        if not self.require(action):
            raise ApprovalDenied(f"Approval denied for {action.kind}: {action.description}")
