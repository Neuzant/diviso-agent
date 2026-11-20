"""Simple web UI on stdlib http.server. No external assets."""
from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .hardware import detect_hardware, select_profile
from .providers import get_provider
from .providers.base import Message

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Diviso</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}}body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#0b1220;color:#e6edf7;margin:0}}
.wrap{{max-width:820px;margin:0 auto;padding:2rem 1rem 3rem}}
header{{display:flex;align-items:center;gap:.8rem;margin-bottom:.3rem}}
.logo{{width:42px;height:42px;border-radius:11px;background:linear-gradient(135deg,#2563eb,#0ea5a4);display:flex;align-items:center;justify-content:center;font-size:1.35rem;font-weight:800;color:#fff}}
h1{{font-size:1.55rem;margin:0}}h2{{font-size:1.05rem;margin:1.4rem 0 .5rem;color:#9fd8d2}}
.tag{{color:#8ea3c0;margin:.2rem 0 1.4rem}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin-bottom:1.4rem}}
.stat{{background:#111c30;border:1px solid #1e2c47;border-radius:10px;padding:.7rem .8rem}}
.stat .k{{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:#7d92b2}}
.stat .v{{font-size:1.02rem;font-weight:700;margin-top:.15rem}}
.card{{background:#0f1930;border:1px solid #1e2c47;border-radius:12px;padding:1rem}}
form{{display:flex;gap:.6rem}}input[type=text]{{flex:1;padding:.7rem .8rem;border-radius:9px;border:1px solid #2a3c5f;background:#0b1425;color:#e6edf7;font-size:.95rem}}
button{{padding:.7rem 1.4rem;border:0;border-radius:9px;background:linear-gradient(135deg,#2563eb,#0ea5a4);color:#fff;font-weight:700;cursor:pointer}}
pre{{background:#070d18;color:#c9e7c5;padding:1rem;overflow:auto;border-radius:9px;border:1px solid #1e2c47;white-space:pre-wrap;word-break:break-word}}
footer{{color:#63769a;font-size:.8rem;margin-top:2rem;text-align:center}}
</style>
</head><body><div class="wrap">
<header><div class="logo">D</div><h1>Diviso — local-first agent</h1></header>
<p class="tag">Runs 100% on this machine. No cloud account. Your data never leaves this device.</p>
<div class="stats">
<div class="stat"><div class="k">RAM</div><div class="v">{ram} GB</div></div>
<div class="stat"><div class="k">CPUs</div><div class="v">{cpus}</div></div>
<div class="stat"><div class="k">GPU</div><div class="v">{gpu}</div></div>
<div class="stat"><div class="k">Ollama</div><div class="v">{ollama}</div></div>
<div class="stat"><div class="k">Profile</div><div class="v">{profile}</div></div>
</div>
<div class="card"><form method="post" action="/run"><input type="text" name="prompt" placeholder="Ask Diviso (mock provider by default)">
<button type="submit">Run</button></form></div>
{result}
<footer>Diviso dashboard · Doctor checks this device live on every load · Provider: local / API key of your choice</footer>
</div></body></html>"""


def make_handler(provider_name: str = "mock"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep console quiet
            pass

        def _page(self, result_html: str = "") -> bytes:
            hw = detect_hardware()
            return PAGE.format(ram=hw.ram_gb, cpus=hw.cpu_count, gpu=hw.gpu or "none",
                               ollama="running" if hw.ollama_running else "not detected",
                               profile=select_profile(hw),
                               result=result_html).encode()

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
