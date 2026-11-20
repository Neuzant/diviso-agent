import json
import os

import pytest

from diviso.config import DivisoConfig, redact_text
from diviso.providers.mock import MockProvider
from diviso.team import Team


def test_redact_text_removes_env_secret(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value-123")
    out = redact_text("key is sk-super-secret-value-123 ok")
    assert "sk-super-secret-value-123" not in out
    assert "***" in out


def test_config_redacted_dict_has_no_secret(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-abcdef")
    cfg = DivisoConfig()
    blob = json.dumps(cfg.redacted_dict())
    assert "sk-ant-secret-abcdef" not in blob
    assert cfg.redacted_dict()["api_keys_present"]["ANTHROPIC_API_KEY"] is True


def test_config_loads_json_file(tmp_path):
    path = tmp_path / "diviso.json"
    path.write_text(json.dumps({"provider": "ollama", "model": "qwen2.5:7b",
                                "max_steps": 7}))
    cfg = DivisoConfig.load(path)
    assert cfg.provider == "ollama" and cfg.model == "qwen2.5:7b"
    assert cfg.max_steps == 7


def test_config_env_overrides_file(tmp_path, monkeypatch):
    path = tmp_path / "diviso.json"
    path.write_text(json.dumps({"provider": "ollama"}))
    monkeypatch.setenv("DIVISO_PROVIDER", "mock")
    assert DivisoConfig.load(path).provider == "mock"


def test_team_approved_without_fix_pass():
    provider = MockProvider(scripted=["facts", "solution", "APPROVED: good"])
    result = Team(provider).run("build a thing")
    assert result.approved and result.fix_passes == 0


def test_team_exactly_one_fix_pass():
    provider = MockProvider(scripted=[
        "facts", "v1", "NEEDS_FIX: broken", "v2", "APPROVED: fixed"])
    result = Team(provider).run("build a thing")
    assert result.approved and result.fix_passes == 1
    assert result.solution == "v2"


def test_team_stops_after_one_fix_pass_even_if_still_bad():
    provider = MockProvider(scripted=[
        "facts", "v1", "NEEDS_FIX: a", "v2", "NEEDS_FIX: b", "v3-unused"])
    result = Team(provider).run("build a thing")
    assert result.fix_passes == 1 and not result.approved


def test_cli_doctor_outputs_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    from diviso.cli import main
    assert main(["--workspace", str(tmp_path), "doctor"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["profile"] in ("lite", "balanced", "pro")
    assert "mock" in report["providers"]


def test_cli_run_mock_demo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    from diviso.cli import main
    assert main(["--workspace", str(tmp_path), "run", "--provider", "mock",
                 "hello diviso"]) == 0
    out = capsys.readouterr().out
    assert "Mock response to: hello diviso" in out


def test_cli_runs_get_unique_trace_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    from diviso.cli import main
    for prompt in ("first run", "second run"):
        assert main(["--workspace", str(tmp_path), "run", "--provider", "mock",
                     prompt]) == 0
    capsys.readouterr()
    trace_files = list(tmp_path.rglob("traces/*.jsonl"))
    assert len(trace_files) == 2
    assert all(f.stem != "run" for f in trace_files)


def test_webui_serves_page(tmp_path):
    import threading
    import urllib.request
    from http.server import HTTPServer

    from diviso.webui import make_handler
    server = HTTPServer(("127.0.0.1", 0), make_handler("mock"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/", timeout=5) as resp:
            page = resp.read().decode()
        assert "Diviso" in page and "Profile" in page
    finally:
        server.shutdown()
