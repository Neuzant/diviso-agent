"""Ollama local provider (http://localhost:11434). Stdlib urllib only."""
from __future__ import annotations

import json
import urllib.request

from .base import ChatResponse, Message, Provider, estimate_tokens


class OllamaProvider(Provider):
    name = "ollama"
    default_model = "llama3.2:1b"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[Message], model: str | None = None,
             temperature: float = 0.2) -> ChatResponse:
        payload = {"model": model or self.default_model,
                   "messages": [m.to_dict() for m in messages],
                   "stream": False, "options": {"temperature": temperature}}
        req = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        text = (data.get("message") or {}).get("content", "")
        pt = data.get("prompt_eval_count") or sum(estimate_tokens(m.content) for m in messages)
        ct = data.get("eval_count") or estimate_tokens(text)
        return ChatResponse(text=text, model=payload["model"], prompt_tokens=pt,
                            completion_tokens=ct, cost_usd=0.0, raw=data)
