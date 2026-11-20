"""Web dashboard on stdlib http.server. No external assets or fonts.

Dashboard v2: hero header, live device stat cards (Doctor data), a
provider-status panel (configured or not — key VALUES are never shown),
example-prompt chips, and a features grid.
"""
from __future__ import annotations

import html
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .hardware import detect_hardware, select_profile
from .providers import get_provider
from .providers.base import Message

# --- small inline SVG icons (stroke style, currentColor) -------------------
def _icon(paths: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{paths}</svg>')


ICONS = {
    "ram": _icon('<rect x="7" y="7" width="10" height="10" rx="2"/>'
                 '<path d="M10 7V4M14 7V4M10 20v-3M14 20v-3M7 10H4M7 14H4M20 10h-3M20 14h-3"/>'),
    "cpu": _icon('<rect x="6" y="6" width="12" height="12" rx="2"/>'
                 '<circle cx="12" cy="12" r="2.2"/>'
                 '<path d="M9 6V3M15 6V3M9 21v-3M15 21v-3M6 9H3M6 15H3M21 9h-3M21 15h-3"/>'),
    "gpu": _icon('<rect x="3" y="5" width="18" height="12" rx="2"/>'
                 '<path d="M9 21h6M12 17v4"/>'),
    "server": _icon('<rect x="4" y="4" width="16" height="7" rx="2"/>'
                    '<rect x="4" y="13" width="16" height="7" rx="2"/>'
                    '<path d="M7.5 7.5h.01M7.5 16.5h.01"/>'),
    "gauge": _icon('<path d="M4 15a8 8 0 1 1 16 0"/><path d="M12 15l4.5-4.5"/>'
                   '<path d="M3 19h18"/>'),
    "react": _icon('<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 3v4h-4"/>'),
    "planner": _icon('<path d="M9 6h11M9 12h11M9 18h11"/>'
                     '<path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>'),
    "memory": _icon('<ellipse cx="12" cy="5.5" rx="7" ry="2.8"/>'
                    '<path d="M5 5.5v13c0 1.6 3.1 2.8 7 2.8s7-1.2 7-2.8v-13"/>'
                    '<path d="M5 12c0 1.6 3.1 2.8 7 2.8s7-1.2 7-2.8"/>'),
    "team": _icon('<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/>'
                  '<circle cx="17" cy="9" r="2.6"/><path d="M16 15.2c2.3.3 3.9 1.9 4.4 4.8"/>'),
    "mcp": _icon('<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0V7z"/><path d="M12 16v5"/>'),
    "clock": _icon('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
}

FEATURES = [
    ("react", "ReAct Loop",
     "Reason + act with hard step and cost caps — and a visible trace for every run."),
    ("planner", "Planner",
     "Breaks goals into steps, retries failures with a different approach, then reflects."),
    ("memory", "Memory &amp; RAG",
     "Persistent SQLite memory plus TF-IDF retrieval over your own local files."),
    ("team", "Multi-Agent Team",
     "Researcher, Coder and Reviewer roles with exactly one fix pass."),
    ("mcp", "MCP Client",
     "Connects to MCP servers over stdio and HTTP — every tool stays under your control."),
    ("clock", "Guarded Scheduler",
     "Recurring jobs with per-job token and cost guards. Over-guard jobs are skipped, not run."),
]

EXAMPLE_PROMPTS = [
    "Summarize what Diviso can do",
    "Explain the approval gate in one line",
    "List three benefits of running models locally",
    "Write a haiku about local AI",
]

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Diviso — local-first agent</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#0b1220;color:#e6edf7;margin:0;
background-image:radial-gradient(900px 480px at 85% -10%,rgba(14,165,164,.14),transparent 60%),radial-gradient(800px 500px at -10% 0%,rgba(37,99,235,.16),transparent 60%)}
.wrap{max-width:1060px;margin:0 auto;padding:2.2rem 1.1rem 3rem}
.hero{display:flex;align-items:center;gap:1.1rem;flex-wrap:wrap}
.logo{width:64px;height:64px;border-radius:17px;background:linear-gradient(135deg,#2563eb,#0ea5a4);display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:800;color:#fff;box-shadow:0 10px 28px rgba(14,165,164,.35)}
.hero h1{font-size:2.15rem;margin:0;letter-spacing:-.01em}
.hero h1 span{background:linear-gradient(90deg,#60a5fa,#2dd4bf);-webkit-background-clip:text;background-clip:text;color:transparent}
.tag{color:#9db1d0;margin:.3rem 0 0;font-size:1.02rem}
.pill{margin-left:auto;display:inline-flex;align-items:center;gap:.45rem;background:#0e2233;border:1px solid #14532d;color:#86efac;border-radius:999px;padding:.4rem .85rem;font-size:.82rem;font-weight:600}
.pill i{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.7rem;margin:1.6rem 0}
.stat{background:#111c30;border:1px solid #1e2c47;border-radius:13px;padding:.85rem .95rem}
.stat .top{display:flex;align-items:center;gap:.5rem;color:#7d92b2}
.stat .top svg{width:19px;height:19px;color:#2dd4bf}
.stat .k{font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;font-weight:700}
.stat .v{font-size:1.18rem;font-weight:700;margin-top:.3rem}
.stat .sub{font-size:.78rem;color:#7d92b2;margin-top:.15rem}
.bar{height:7px;background:#0b1425;border:1px solid #1e2c47;border-radius:99px;margin-top:.55rem;overflow:hidden}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#2563eb,#0ea5a4);border-radius:99px}
.grid{display:grid;grid-template-columns:1.55fr 1fr;gap:.9rem;align-items:start}
@media(max-width:820px){.grid{grid-template-columns:1fr}.pill{margin-left:0}}
.card{background:#0f1930;border:1px solid #1e2c47;border-radius:14px;padding:1.1rem 1.15rem}
.card h2{font-size:1rem;margin:0 0 .8rem;color:#e6edf7}
form{display:flex;gap:.6rem}
input[type=text]{flex:1;padding:.72rem .85rem;border-radius:10px;border:1px solid #2a3c5f;background:#0b1425;color:#e6edf7;font-size:.95rem;min-width:0}
input[type=text]:focus{outline:2px solid #0ea5a4;border-color:transparent}
button.run{padding:.72rem 1.5rem;border:0;border-radius:10px;background:linear-gradient(135deg,#2563eb,#0ea5a4);color:#fff;font-weight:700;cursor:pointer;font-size:.95rem}
.chips{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:.85rem}
.chip{background:#111c30;border:1px solid #2a3c5f;color:#c9d8ef;border-radius:999px;padding:.38rem .8rem;font-size:.82rem;cursor:pointer}
.chip:hover{border-color:#0ea5a4;color:#fff}
.prov{display:flex;align-items:center;gap:.6rem;padding:.5rem 0;border-bottom:1px solid #16233c}
.prov:last-child{border-bottom:0}
.prov .dot{width:9px;height:9px;border-radius:50%;background:#475569;flex:none}
.prov .dot.on{background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,.7)}
.prov .name{font-weight:600;font-size:.92rem}
.prov .st{margin-left:auto;font-size:.78rem;color:#7d92b2;text-align:right}
.prov .st.on{color:#86efac}
.feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.7rem;margin-top:.9rem}
.feat{background:#111c30;border:1px solid #1e2c47;border-radius:13px;padding:.95rem 1rem}
.feat svg{width:22px;height:22px;color:#2dd4bf}
.feat h3{margin:.5rem 0 .3rem;font-size:.95rem}
.feat p{margin:0;color:#8ea3c0;font-size:.86rem;line-height:1.45}
.sec-title{font-size:1.05rem;margin:1.7rem 0 .2rem;color:#9fd8d2}
pre{background:#070d18;color:#c9e7c5;padding:1rem;overflow:auto;border-radius:10px;border:1px solid #1e2c47;white-space:pre-wrap;word-break:break-word;font-size:.86rem}
.result h2{font-size:1rem;margin:1.1rem 0 .5rem;color:#9fd8d2}
footer{color:#63769a;font-size:.8rem;margin-top:2.4rem;text-align:center;line-height:1.6}
</style>
</head><body><div class="wrap">
<div class="hero">
<div class="logo">D</div>
<div><h1>Diviso <span>— local-first agent</span></h1>
<p class="tag">Runs 100% on this machine. No cloud account. Your data never leaves this device.</p></div>
<div class="pill"><i></i>Local &amp; private</div>
</div>

<div class="stats">
<div class="stat"><div class="top">__ICON_RAM__<div class="k">RAM</div></div><div class="v">__RAM__ GB</div>__RAM_DETAIL__</div>
<div class="stat"><div class="top">__ICON_CPU__<div class="k">CPUs</div></div><div class="v">__CPUS__</div><div class="sub">cores on this device</div></div>
<div class="stat"><div class="top">__ICON_GPU__<div class="k">GPU</div></div><div class="v">__GPU__</div><div class="sub">acceleration</div></div>
<div class="stat"><div class="top">__ICON_SERVER__<div class="k">Ollama</div></div><div class="v">__OLLAMA__</div><div class="sub">local model server</div></div>
<div class="stat"><div class="top">__ICON_GAUGE__<div class="k">Profile</div></div><div class="v">__PROFILE__</div><div class="sub">auto-selected for this hardware</div></div>
</div>

<div class="grid">
<div class="card"><h2>Run the agent</h2>
<form method="post" action="/run"><input type="text" id="prompt" name="prompt" placeholder="Ask Diviso (mock provider by default)">
<button class="run" type="submit">Run</button></form>
<div class="chips">__CHIPS__</div>
<div class="result">__RESULT__</div>
</div>
<div class="card"><h2>Providers</h2>__PROVIDERS__
<p style="color:#63769a;font-size:.78rem;margin:.7rem 0 0">Status only — API key values are never shown here.</p></div>
</div>

<h2 class="sec-title">What Diviso does</h2>
<div class="feats">__FEATURES__</div>

<footer>Diviso dashboard · Doctor checks this device live on every load · Provider: local / API key of your choice<br>
Stdlib-only core — no third-party packages, no external assets.</footer>
</div>
<script>
document.querySelectorAll('.chip').forEach(function(c){c.addEventListener('click',function(){
var i=document.getElementById('prompt');i.value=c.getAttribute('data-prompt');i.focus();});});
</script>
</body></html>"""


def _ram_detail(ram_gb: float) -> str:
    """RAM usage bar from sysconf available pages; degrades to total-only."""
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        avail = os.sysconf("SC_AVPHYS_PAGES") * page / (1024 ** 3)
        used = max(0.0, ram_gb - avail)
        pct = max(0, min(100, round(used / ram_gb * 100))) if ram_gb else 0
        return (f'<div class="sub">{used:.1f} GB in use</div>'
                f'<div class="bar"><i style="width:{pct}%"></i></div>')
    except (ValueError, OSError, AttributeError):
        return '<div class="sub">total memory on this device</div>'


def _key_present(*names: str) -> bool:
    return any(os.environ.get(n) for n in names)


def _provider_rows(hw) -> str:
    """Provider status: configured or not. Key VALUES are never rendered."""
    def row(name: str, on: bool, status: str) -> str:
        cls = " on" if on else ""
        return (f'<div class="prov"><span class="dot{cls}"></span>'
                f'<span class="name">{html.escape(name)}</span>'
                f'<span class="st{cls}">{html.escape(status)}</span></div>')

    def keyed(name: str, *env_names: str) -> str:
        on = _key_present(*env_names)
        return row(name, on, "key configured" if on else "no key set")

    rows = [
        row("Mock", True, "built-in · offline"),
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
    return "".join(rows)


def _features_html() -> str:
    return "".join(
        f'<div class="feat">{ICONS[key]}<h3>{title}</h3><p>{text}</p></div>'
        for key, title, text in FEATURES)


def _chips_html() -> str:
    return "".join(
        f'<button type="button" class="chip" data-prompt="{html.escape(p, quote=True)}">'
        f'{html.escape(p)}</button>' for p in EXAMPLE_PROMPTS)


def make_handler(provider_name: str = "mock"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep console quiet
            pass

        def _page(self, result_html: str = "") -> bytes:
            hw = detect_hardware()
            page = PAGE
            page = page.replace("__ICON_RAM__", ICONS["ram"])
            page = page.replace("__ICON_CPU__", ICONS["cpu"])
            page = page.replace("__ICON_GPU__", ICONS["gpu"])
            page = page.replace("__ICON_SERVER__", ICONS["server"])
            page = page.replace("__ICON_GAUGE__", ICONS["gauge"])
            page = page.replace("__RAM__", str(hw.ram_gb))
            page = page.replace("__RAM_DETAIL__", _ram_detail(hw.ram_gb))
            page = page.replace("__CPUS__", str(hw.cpu_count))
            page = page.replace("__GPU__", html.escape(hw.gpu or "none"))
            page = page.replace("__OLLAMA__",
                                "running" if hw.ollama_running else "not detected")
            page = page.replace("__PROFILE__", html.escape(select_profile(hw)))
            page = page.replace("__PROVIDERS__", _provider_rows(hw))
            page = page.replace("__FEATURES__", _features_html())
            page = page.replace("__CHIPS__", _chips_html())
            page = page.replace("__RESULT__", result_html)
            return page.encode()

        def do_GET(self):
            if self.path.startswith("/doctor"):
                hw = detect_hardware()
                body = (f"<pre>{html.escape(str(hw.to_dict()))}</pre>"
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
            body = (f"<h2>Trace</h2><pre>prompt: {html.escape(prompt)}\n"
                    f"provider: {provider_name}\nmodel: {html.escape(resp.model)}\n"
                    f"tokens: {resp.total_tokens}</pre>"
                    f"<h2>Answer</h2><pre>{html.escape(resp.text)}</pre>")
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
