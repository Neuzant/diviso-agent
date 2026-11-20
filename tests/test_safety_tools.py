import pytest

from diviso.safety import (Action, ApprovalDenied, ApprovalGate, Sandbox,
                           SandboxError, make_diff)
from diviso.tools import build_registry


def test_sandbox_allows_inside(tmp_path):
    sb = Sandbox(tmp_path)
    assert sb.resolve("file.txt") == (tmp_path / "file.txt").resolve()


def test_sandbox_rejects_outside_and_traversal(tmp_path):
    sb = Sandbox(tmp_path)
    with pytest.raises(SandboxError):
        sb.resolve("../escape.txt")
    with pytest.raises(SandboxError):
        sb.resolve("/etc/passwd")


def test_approval_default_denies_mutations():
    gate = ApprovalGate()  # no callback, no auto-approve
    assert gate.require(Action("write", "write file")) is False
    assert gate.require(Action("read", "read file")) is True


def test_approval_callback_allow_and_deny():
    allow = ApprovalGate(callback=lambda a: True)
    deny = ApprovalGate(callback=lambda a: False)
    assert allow.require(Action("shell", "run")) is True
    assert deny.require(Action("shell", "run")) is False


def test_file_write_blocked_when_denied(tmp_path):
    reg = build_registry(Sandbox(tmp_path), ApprovalGate(callback=lambda a: False))
    with pytest.raises(ApprovalDenied):
        reg.get("file_write")("a.txt", "hello")
    assert not (tmp_path / "a.txt").exists()


def test_file_write_allowed_with_diff(tmp_path):
    seen = {}
    reg = build_registry(Sandbox(tmp_path),
                         ApprovalGate(callback=lambda a: seen.setdefault("diff", a.diff) or True))
    out = reg.get("file_write")("a.txt", "hello")
    assert (tmp_path / "a.txt").read_text() == "hello"
    assert "+hello" in seen["diff"]
    assert reg.get("file_read")("a.txt") == "hello"


def test_python_run_through_gate(tmp_path):
    reg = build_registry(Sandbox(tmp_path), ApprovalGate(auto_approve=True))
    assert "42" in reg.get("python_run")("print(42)")
    reg2 = build_registry(Sandbox(tmp_path), ApprovalGate(callback=lambda a: False))
    with pytest.raises(ApprovalDenied):
        reg2.get("python_run")("print(1)")


def test_git_readonly_rejects_mutating(tmp_path):
    reg = build_registry(Sandbox(tmp_path), ApprovalGate(auto_approve=True))
    git = reg.get("git_readonly")
    for bad in ("push", "commit", "reset", "checkout", "add"):
        with pytest.raises(ValueError):
            git(bad)


def test_git_readonly_allows_status(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    reg = build_registry(Sandbox(tmp_path), ApprovalGate(auto_approve=True))
    out = reg.get("git_readonly")("status")
    assert isinstance(out, str)  # runs; content depends on repo state


def test_make_diff_shows_changes():
    diff = make_diff("f.txt", "old\n", "new\n")
    assert "-old" in diff and "+new" in diff
