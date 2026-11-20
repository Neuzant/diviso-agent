"""Claude via the Anthropic Messages API. Stdlib urllib only."""
from __future__ import annotations

import json
import os
import urllib.request

from .base import ChatResponse, Message, Provider, estimate_cost, estimate_tokens


class AnthropicProvider(Provider):
    name = "anthropic"
    default_model = "claude-sonnet-4-5"

    def __init__(self, api_key: str | None = None, timeout: float = 120):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.timeout = timeout
        self.base_url = "https://api.anthropic.com/v1/messages"

    def chat(self, messages: list[Message], model: str | None = None,
             temperature: float = 0.2) -> ChatResponse:
        use_model = model or self.default_model
        system = "\n".join(m.content for m in messages if m.role == "system")
        convo = [m.to_dict() for m in messages if m.role in ("user", "assistant")]
        payload = {"model": use_model, "max_tokens": 4096, "temperature": temperature,
                   "messages": convo}
        if system:
            payload["system"] = system
        req = urllib.request.Request(
            self.base_url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        usage = data.get("usage") or {}
        pt = usage.get("input_tokens") or sum(estimate_tokens(m.content) for m in messages)
        ct = usage.get("output_tokens") or estimate_tokens(text)
        return ChatResponse(text=text, model=use_model, prompt_tokens=pt,
                            completion_tokens=ct,
                            cost_usd=estimate_cost("claude-sonnet", pt, ct), raw=data)
