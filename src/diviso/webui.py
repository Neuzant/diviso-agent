"""Web console on stdlib http.server. No external assets or fonts.

Dashboard v3: a flat product UI in the style of a developer console —
no decorative effects, no marketing sections. Every value on the
page is read live from this machine: Doctor hardware data, provider
configuration state (key values are never shown), and the run traces
the agent has actually recorded under the data directory.
"""
from __future__ import annotations

import html
import os
import platform
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import __version__
from .config import DivisoConfig
from .hardware import detect_hardware, select_profile
from .providers import get_provider
from .providers.base import Message
from .trace import TraceLogger

CAPABILITIES = [
    ("ReAct loop", "Reasoning and tool use with hard step and cost caps; every run writes a trace."),
    ("Planner", "Breaks a goal into steps, retries a failed step with a different approach, then reflects."),
    ("Memory & RAG", "Persistent memory in SQLite plus TF-IDF retrieval over local files."),
    ("Multi-agent team", "Researcher, Coder and Reviewer roles with exactly one fix pass."),
    ("MCP client", "Connects to MCP servers over stdio and HTTP."),
    ("Guarded scheduler", "Recurring jobs with per-job token and cost guards; over-guard jobs are skipped."),
    ("Code runners", "python_run, javascript_run (Node.js) and bash_run, approval-gated and workspace-only."),
]

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Diviso</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#e6edf3;margin:0;font-size:14px;line-height:1.5}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.muted{color:#7d8590}
.topbar{display:flex;align-items:center;gap:.6rem;padding:0 1.25rem;height:52px;border-bottom:1px solid #30363d;background:#010409}
.mark{width:28px;height:28px;border-radius:6px;background:#1f6feb;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex:none}
.wordmark{font-size:16px;font-weight:600}
.topbar .right{margin-left:auto;display:flex;align-items:center;gap:1rem;font-size:13px;color:#7d8590}
.status{display:inline-flex;align-items:center;gap:.45rem;color:#e6edf3}
.dot{width:8px;height:8px;border-radius:50%;background:#484f58;display:inline-block;flex:none}
.dot.on{background:#238636}
.layout{max-width:1280px;margin:0 auto;padding:1.25rem;display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:1.25rem;align-items:start}
@media(max-width:900px){.layout{grid-template-columns:1fr}}
.col{display:flex;flex-direction:column;gap:1.25rem;min-width:0}
.panel{background:#161b22;border:1px solid #30363d;border-radius:6px}
.panel>h2{font-size:14px;font-weight:600;margin:0;padding:.6rem 1rem;border-bottom:1px solid #30363d}
.panel .body{padding:1rem}
label.flabel{display:block;font-size:13px;font-weight:600;margin-bottom:.4rem}
form.run{display:flex;gap:.5rem}
input[type=text]{flex:1;padding:.45rem .7rem;border-radius:6px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;font-size:14px;min-width:0}
input[type=text]:focus{outline:none;border-color:#1f6feb}
button.run{padding:.45rem 1.1rem;border:1px solid rgba(240,246,252,.1);border-radius:6px;background:#1f6feb;color:#fff;font-weight:500;cursor:pointer;font-size:14px}
button.run:hover{background:#388bfd}
.logbox{margin-top:1rem;border:1px solid #30363d;border-radius:6px;overflow:hidden}
.logbar{display:flex;gap:1rem;flex-wrap:wrap;padding:.45rem .8rem;background:#0d1117;border-bottom:1px solid #30363d;font-size:12px;color:#7d8590}
.logbar .mono{color:#7d8590}
pre.log{margin:0;padding:.8rem;background:#0d1117;color:#e6edf3;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px;line-height:1.55}
.answer{margin-top:1rem}
.answer .alabel{font-size:13px;font-weight:600;margin-bottom:.4rem}
.answer .atext{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:.8rem;white-space:pre-wrap;word-break:break-word}
table.rows{width:100%;border-collapse:collapse}
table.rows td{padding:.45rem 0;border-bottom:1px solid #21262d;vertical-align:top}
table.rows tr:last-child td{border-bottom:0}
table.rows td.k{color:#7d8590;width:38%}
table.rows td.v{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
.bar{height:4px;background:#30363d;border-radius:2px;margin:.35rem 0 .15rem;overflow:hidden}
.bar i{display:block;height:100%;background:#1f6feb}
table.act{width:100%;border-collapse:collapse;font-size:13px}
table.act th{text-align:left;color:#7d8590;font-weight:500;padding:.4rem .6rem .4rem 0;border-bottom:1px solid #30363d}
table.act td{padding:.45rem .6rem .45rem 0;border-bottom:1px solid #21262d;vertical-align:top}
table.act tr:last-child td{border-bottom:0}
table.act td.mono,table.act th.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.prov td .dot{margin-right:.5rem}
.empty{color:#7d8590;margin:0}
ul.caps{list-style:none;margin:0;padding:0}
ul.caps li{padding:.55rem 0;border-bottom:1px solid #21262d}
ul.caps li:last-child{border-bottom:0}
ul.caps .cn{font-weight:600}
ul.caps .cd{color:#7d8590}
footer{max-width:1280px;margin:0 auto;padding:0 1.25rem 1.5rem;color:#7d8590;font-size:12.5px}
</style>
</head><body>
<header class="topbar">
<div class="mark">D</div><div class="wordmark">Diviso</div>
<div class="right"><span>v__VERSION__</span><span class="status"><span class="dot on"></span>Local</span></div>
</header>
<div class="layout">
<div class="col">
<section class="panel"><h2>Run</h2><div class="body">
<label class="flabel" for="prompt">Prompt</label>
<form class="run" method="post" action="/run"><input type="text" id="prompt" name="prompt" placeholder="Enter a prompt" aria-label="Prompt">
<button class="run" type="submit">Run</button></form>
__RESULT__
</div></section>
<section class="panel"><h2>Activity</h2><div class="body">__ACTIVITY__</div></section>
</div>
<div class="col">
<section class="panel"><h2>System</h2><div class="body">__SYSTEM__</div></section>
<section class="panel"><h2>Providers</h2><div class="body">__PROVIDERS__
<p class="muted" style="font-size:12.5px;margin:.8rem 0 0">Configuration state only. API key values are never displayed.</p></div></section>
</div>
</div>
<div style="max-width:1280px;margin:0 auto;padding:0 1.25rem 1.25rem">
<section class="panel"><h2>Capabilities</h2><div class="body"><ul class="caps">__CAPABILITIES__</ul></div></section>
</div>
<footer>Diviso v__VERSION__ · Web console · System data is read live from this machine on every page load.</footer>
</body></html>"""


def _ram_usage(ram_gb: float) -> tuple[float | None, int]:
    """(used GB, used %) from sysconf available pages; (None, 0) if unknown."""
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        avail = os.sysconf("SC_AVPHYS_PAGES") * page / (1024 ** 3)
        used = max(0.0, ram_gb - avail)
        pct = max(0, min(100, round(used / ram_gb * 100))) if ram_gb else 0
        return used, pct
    except (ValueError, OSError, AttributeError):
        return None, 0


def _system_table(hw) -> str:
    used, pct = _ram_usage(hw.ram_gb)
    if used is None:
        ram_cell = f"{hw.ram_gb} GB"
        ram_bar = ""
    else:
        ram_cell = f"{used:.1f} / {hw.ram_gb} GB"
        ram_bar = f'<div class="bar"><i style="width:{pct}%"></i></div>'
    rows = [
        ("RAM", ram_cell + ram_bar),
        ("CPUs", str(hw.cpu_count)),
        ("GPU", html.escape(hw.gpu or "none")),
        ("Ollama", "running" if hw.ollama_running else "not detected"),
        ("Profile", html.escape(select_profile(hw))),
        ("Python", platform.python_version()),
        ("OS", f"{html.escape(platform.system())} {html.escape(platform.release())}"),
    ]
    return ('<table class="rows">' + "".join(
        f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>' for k, v in rows)
        + "</table>")


def _key_present(*names: str) -> bool:
    return any(os.environ.get(n) for n in names)


def _provider_rows(hw) -> str:
    """Provider configuration state. Key VALUES are never rendered."""
    def row(name: str, on: bool, note: str) -> str:
        cls = " on" if on else ""
        return (f'<tr><td><span class="dot{cls}"></span>{html.escape(name)}</td>'
                f'<td class="v" style="font-family:inherit">{html.escape(note)}</td></tr>')

    def keyed(name: str, *env_names: str) -> str:
        on = _key_present(*env_names)
        return row(name, on, "key set" if on else "no key set")

    rows = [
        row("Mock", True, "built-in"),
        row("Ollama", hw.ollama_running,
            "running" if hw.ollama_running else "not detected"),
        keyed("Claude", "ANTHROPIC_API_KEY"),
        keyed("OpenAI", "OPENAI_API_KEY"),
        keyed("Grok (xAI)", "XAI_API_KEY"),
        keyed("Gemini", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
        keyed("Mistral", "MISTRAL_API_KEY"),
        keyed("DeepSeek", "DEEPSEEK_API_KEY"),
        keyed("OpenRouter", "OPENROUTER_API_KEY"),
        keyed("Custom endpoint", "DIVISO_API_KEY", "DIVISO_BASE_URL"),
    ]
    return '<table class="rows prov">' + "".join(rows) + "</table>"


def _traces_dir() -> Path:
    try:
        return DivisoConfig.load().data_dir / "traces"
    except Exception:
        return Path.home() / ".diviso" / "traces"


def _activity_html(limit: int = 5) -> str:
    """Most recent recorded runs from the trace dir. Real data only:
    trace files store ts / run_id / step / cost_usd / final|stop events,
    so those are the columns shown — nothing is reconstructed."""
    trace_dir = _traces_dir()
    try:
        files = sorted(trace_dir.glob("*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        files = []
    entries = []
    for path in files:
        if len(entries) >= limit:
            break
        try:
            events = TraceLogger.read(path)
        except Exception:
            continue  # skip a corrupt trace file rather than fail the page
        if not events:
            continue
        first_ts = events[0].get("ts") or path.stat().st_mtime
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(first_ts))
        run_id = str(events[0].get("run_id") or path.stem)
        steps = max((int(e.get("step", 0)) for e in events), default=0)
        cost = 0.0
        status = "Incomplete"
        for e in events:
            if isinstance(e.get("cost_usd"), (int, float)):
                cost = float(e["cost_usd"])
            if e.get("event") == "final":
                status = "Completed"
            elif e.get("event") == "stop":
                status = f"Stopped ({e.get('reason', 'unknown')})"
        entries.append(
            f'<tr><td class="mono">{html.escape(when)}</td>'
            f'<td class="mono">{html.escape(run_id)}</td>'
            f'<td class="mono">{steps}</td>'
            f'<td class="mono">${cost:.4f}</td>'
            f'<td>{html.escape(status)}</td></tr>')
    if not entries:
        return '<p class="empty">No runs recorded yet.</p>'
    return ('<table class="act"><tr><th>Time</th><th>Run</th><th>Steps</th>'
            '<th>Cost</th><th>Status</th></tr>' + "".join(entries) + "</table>")


def _capabilities_html() -> str:
    return "".join(
        f'<li><span class="cn">{html.escape(name)}</span> '
        f'<span class="cd">— {html.escape(text)}</span></li>'
        for name, text in CAPABILITIES)


def make_handler(provider_name: str = "mock"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep console quiet
            pass

        def _page(self, result_html: str = "") -> bytes:
            hw = detect_hardware()
            page = PAGE
            page = page.replace("__VERSION__", html.escape(__version__))
            page = page.replace("__SYSTEM__", _system_table(hw))
            page = page.replace("__PROVIDERS__", _provider_rows(hw))
            page = page.replace("__ACTIVITY__", _activity_html())
            page = page.replace("__CAPABILITIES__", _capabilities_html())
            page = page.replace("__RESULT__", result_html)
            return page.encode()

        def do_GET(self):
            if self.path.startswith("/doctor"):
                hw = detect_hardware()
                body = (f"<pre class='log'>{html.escape(str(hw.to_dict()))}</pre>"
                        f"<p>Profile: {select_profile(hw)}</p>")
                self._send(self._page(body))
            else:
                self._send(self._page())

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            form = urllib.parse.parse_qs(self.rfile.read(length).decode())
            prompt = (form.get("prompt") or [""])[0]
            provider = get_provider(provider_name)
            resp = provider.chat([Message("user", prompt)])
            body = (f'<div class="logbox"><div class="logbar">'
                    f'<span>trace</span>'
                    f'<span class="mono">provider: {html.escape(provider_name)}</span>'
                    f'<span class="mono">model: {html.escape(resp.model)}</span>'
                    f'<span class="mono">tokens: {resp.total_tokens}</span></div>'
                    f'<pre class="log">prompt: {html.escape(prompt)}</pre></div>'
                    f'<div class="answer"><div class="alabel">Answer</div>'
                    f'<div class="atext">{html.escape(resp.text)}</div></div>')
            self._send(self._page(body))

        def _send(self, data: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765, provider: str = "mock") -> None:
    server = HTTPServer((host, port), make_handler(provider))
    print(f"Diviso web UI at http://{host}:{port} (Ctrl+C to stop)")
    server.serve_forever()
