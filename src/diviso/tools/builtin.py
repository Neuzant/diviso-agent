"""Built-in tools. Mutating/network tools go through the approval gate and
the workspace sandbox."""
from __future__ import annotations

import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from ..safety import Action, ApprovalGate, Sandbox, make_diff

GIT_ALLOWED = {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files"}
GIT_MUTATING = {"push", "commit", "add", "checkout", "reset", "merge", "rebase",
                "pull", "fetch", "clone", "rm", "mv", "stash", "tag", "clean"}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, object] = {}
        self._descriptions: dict[str, str] = {}

    def register(self, name: str, fn, description: str = "") -> None:
        self._tools[name] = fn
        self._descriptions[name] = description

    def get(self, name: str):
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def as_dict(self) -> dict:
        return dict(self._tools)


def build_registry(sandbox: Sandbox, gate: ApprovalGate,
                   timeout: int = 30) -> ToolRegistry:
    reg = ToolRegistry()

    def python_run(code: str) -> str:
        gate.require_or_raise(Action("shell", f"Run Python code ({len(code)} chars)",
                                     target="python"))
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(sandbox.root),
                              capture_output=True, text=True, timeout=timeout)
        return (proc.stdout + proc.stderr).strip()[:8000] or "(no output)"

    def file_write(path: str, content: str) -> str:
        target = sandbox.resolve(path)
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        diff = make_diff(path, old, content)
        gate.require_or_raise(Action("write", f"Write {path}", diff=diff, target=path))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {path} ({len(content)} chars)\n{diff}"

    def file_read(path: str) -> str:
        target = sandbox.resolve(path)
        return target.read_text(encoding="utf-8")[:8000]

    def run_tests(path: str = "tests") -> str:
        gate.require_or_raise(Action("shell", f"Run tests in {path}", target=path))
        proc = subprocess.run([sys.executable, "-m", "pytest", path, "-q"],
                              cwd=str(sandbox.root), capture_output=True, text=True,
                              timeout=max(timeout, 120))
        return (proc.stdout + proc.stderr).strip()[-4000:]

    def git_readonly(*args: str) -> str:
        if not args:
            raise ValueError("git subcommand required")
        sub = args[0]
        if sub in GIT_MUTATING or sub not in GIT_ALLOWED:
            raise ValueError(f"Mutating or disallowed git subcommand rejected: {sub}")
        proc = subprocess.run(["git", *args], cwd=str(sandbox.root),
                              capture_output=True, text=True, timeout=timeout)
        return (proc.stdout + proc.stderr).strip()[:8000]

    def web_fetch(url: str, max_bytes: int = 1_000_000) -> str:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only http/https URLs can be fetched")
        gate.require_or_raise(Action("network", f"Fetch {url}", target=url))
        req = urllib.request.Request(url, headers={"User-Agent": "Diviso/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
        return data[:max_bytes].decode("utf-8", errors="ignore")

    def web_search(query: str, max_results: int = 5) -> list[dict]:
        gate.require_or_raise(Action("network", f"Web search: {query}", target=query))
        return duckduckgo_search(query, max_results=max_results, timeout=timeout)

    reg.register("python_run", python_run, "Run Python code in the workspace")
    reg.register("file_write", file_write, "Write a file inside the workspace")
    reg.register("file_read", file_read, "Read a file inside the workspace")
    reg.register("run_tests", run_tests, "Run pytest in the workspace")
    reg.register("git_readonly", git_readonly, "Read-only git (status/log/diff/show)")
    reg.register("web_fetch", web_fetch, "Fetch a URL (size-capped)")
    reg.register("web_search", web_search, "Web search (DuckDuckGo Lite)")
    return reg


def duckduckgo_search(query: str, max_results: int = 5, timeout: int = 15) -> list[dict]:
    """DuckDuckGo Lite HTML search. Offline-graceful: returns [] on any error."""
    import urllib.parse
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Diviso/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(2_000_000).decode("utf-8", errors="ignore")
    except Exception:
        return []
    results = []
    for href, title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,})</a>', html):
        if "duckduckgo.com" in href and "uddg=" in href:
            import urllib.parse as up
            qs = up.parse_qs(up.urlparse(href).query)
            href = qs.get("uddg", [href])[0]
        if href.startswith("http"):
            results.append({"url": href, "title": re.sub(r"\s+", " ", title).strip()})
        if len(results) >= max_results:
            break
    return results
