"""Minimal MCP client: JSON-RPC 2.0 over stdio and over HTTP.

Implements initialize, tools/list and tools/call with timeouts.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import urllib.request


class MCPError(Exception):
    pass


class _LineReader:
    """Read stdout lines with a timeout using a background thread + queue."""

    def __init__(self, stream):
        self.q: queue.Queue = queue.Queue()
        self._t = threading.Thread(target=self._pump, args=(stream,), daemon=True)
        self._t.start()

    def _pump(self, stream):
        for line in stream:
            self.q.put(line)

    def readline(self, timeout: float) -> str:
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            raise MCPError(f"MCP server did not respond within {timeout}s")


class MCPStdioClient:
    def __init__(self, command: list[str], timeout: float = 15):
        self.command = command
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self._reader: _LineReader | None = None
        self._id = 0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()

    def start(self) -> dict:
        self.proc = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
        self._reader = _LineReader(self.proc.stdout)
        return self._request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "diviso", "version": "0.1.0"}})

    def _send(self, payload: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        req_id = self._id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method,
                    "params": params or {}})
        assert self._reader
        while True:
            line = self._reader.readline(self.timeout)
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise MCPError(str(msg["error"]))
                return msg.get("result", {})
            # Notifications / other ids are ignored.

    def list_tools(self) -> list[dict]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None


class MCPHttpClient:
    def __init__(self, base_url: str, timeout: float = 15,
                 headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self._id = 0

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method,
                   "params": params or {}}
        req = urllib.request.Request(
            self.base_url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", **self.headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            msg = json.loads(resp.read().decode())
        if "error" in msg:
            raise MCPError(str(msg["error"]))
        return msg.get("result", {})

    def initialize(self) -> dict:
        return self._request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "diviso", "version": "0.1.0"}})

    def list_tools(self) -> list[dict]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})
