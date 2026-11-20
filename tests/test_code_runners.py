"""Multi-language code runners: python_run, javascript_run (Node.js),
bash_run. Same safety model for all: approval gate, workspace cwd,
timeout, capped output, errors as strings."""
import shutil

import pytest

from diviso.safety import ApprovalDenied, ApprovalGate, Sandbox
from diviso.tools import build_registry


def _reg(tmp_path, timeout=30):
    return build_registry(Sandbox(tmp_path), ApprovalGate(auto_approve=True),
                          timeout=timeout)


def test_python_run_still_works(tmp_path):
    assert "py-42" in _reg(tmp_path).get("python_run")("print('py-' + str(40 + 2))")


def test_javascript_run_registered_when_node_present(tmp_path):
    # Node v24 is installed on this machine — the runner must really exist.
    assert shutil.which("node") is not None
    assert "javascript_run" in _reg(tmp_path).names()


def test_javascript_run_executes_and_returns_stdout(tmp_path):
    out = _reg(tmp_path).get("javascript_run")("console.log('js-' + (40 + 2))")
    assert "js-42" in out


def test_bash_run_executes_and_returns_stdout(tmp_path):
    out = _reg(tmp_path).get("bash_run")("echo bash-$((40 + 2))")
    assert "bash-42" in out


def test_runners_go_through_approval_gate(tmp_path):
    reg = build_registry(Sandbox(tmp_path), ApprovalGate(callback=lambda a: False))
    with pytest.raises(ApprovalDenied):
        reg.get("javascript_run")("console.log(1)")
    with pytest.raises(ApprovalDenied):
        reg.get("bash_run")("echo hi")


def test_javascript_timeout_returns_error_string(tmp_path):
    reg = _reg(tmp_path, timeout=1)
    out = reg.get("javascript_run")("while (true) {}")  # must not raise
    assert "timed out" in out


def test_bash_error_returns_error_string(tmp_path):
    out = _reg(tmp_path).get("bash_run")("echo oops >&2\nexit 3")  # must not raise
    assert out.startswith("Error:")
    assert "code 3" in out
    assert "oops" in out


def test_runner_temp_files_are_cleaned_up(tmp_path):
    _reg(tmp_path).get("bash_run")("echo clean")
    assert not list(tmp_path.glob(".diviso-run-*"))
