import json
import sys
from pathlib import Path

import pytest

from diviso.mcp_client import MCPStdioClient
from diviso.plugins import discover_plugins, load_plugins
from diviso.skills import discover_skills, load_skill
from diviso.tools import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


def test_load_sample_skill_frontmatter():
    skill = load_skill(ROOT / "examples" / "sample-skill")
    assert skill.name == "commit-message-writer"
    assert "conventional-commit" in skill.description
    assert "type(scope)" in skill.body


def test_discover_skills_in_examples():
    skills = discover_skills(ROOT / "examples")
    assert any(s.name == "commit-message-writer" for s in skills)


def test_remote_skill_rejected():
    with pytest.raises(ValueError):
        load_skill("https://example.com/SKILL.md")
    with pytest.raises(ValueError):
        discover_skills("http://example.com/skills")


def test_missing_skill_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_skill(tmp_path / "nothing-here")


def test_plugin_loading_registers_tool():
    reg = ToolRegistry()
    plugins = load_plugins(ROOT / "examples" / "plugins", registry=reg)
    assert [p.name for p in plugins] == ["hello-plugin"]
    assert reg.get("hello")("Diviso") == "Hello, Diviso! (from hello-plugin)"
    assert discover_plugins(ROOT / "examples" / "plugins")


def test_mcp_stdio_client_against_fixture():
    fixture = str(Path(__file__).parent / "mcp_fixture_server.py")
    with MCPStdioClient([sys.executable, fixture], timeout=10) as client:
        tools = client.list_tools()
        assert [t["name"] for t in tools] == ["echo"]
        result = client.call_tool("echo", {"x": 1})
        assert "echo:" in result["content"][0]["text"]


def test_mcp_http_client_against_local_server():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from diviso.mcp_client import MCPHttpClient

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            msg = json.loads(self.rfile.read(length))
            if msg["method"] == "tools/list":
                result = {"tools": [{"name": "ping"}]}
            else:
                result = {"ok": True}
            body = json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                               "result": result}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = MCPHttpClient(f"http://127.0.0.1:{server.server_port}")
        assert client.list_tools() == [{"name": "ping"}]
        assert client.call_tool("ping") == {"ok": True}
    finally:
        server.shutdown()
