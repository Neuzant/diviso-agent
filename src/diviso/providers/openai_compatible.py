"""One OpenAI-compatible client covering OpenAI, xAI/Grok, Gemini (OpenAI-compat
endpoint), Mistral, DeepSeek, OpenRouter and any custom base_url."""
from __future__ import annotations

import json
import os
import urllib.request

from .base import ChatResponse, Message, Provider, estimate_cost, estimate_tokens

PRESETS = {
    "openai":     ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
    "xai":        ("https://api.x.ai/v1", "XAI_API_KEY", "grok-4"),
    "grok":       ("https://api.x.ai/v1", "XAI_API_KEY", "grok-4"),
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/openai/",
                   "GEMINI_API_KEY", "gemini-2.0-flash"),
    "mistral":    ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest"),
    "deepseek":   ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-chat"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                   "openai/gpt-4o-mini"),
    "custom":     ("http://localhost:8000/v1", "DIVISO_API_KEY", "local-model"),
}


class OpenAICompatibleProvider(Provider):
    def __init__(self, preset: str = "openai", base_url: str | None = None,
                 api_key: str | None = None, timeout: float = 120):
        preset = preset.lower()
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset: {preset}")
        default_url, env_var, default_model = PRESETS[preset]
        self.name = preset
        self.base_url = (base_url or default_url).rstrip("/")
        self.api_key = api_key or os.environ.get(env_var, "")
        self.default_model = default_model
        self.timeout = timeout

    def chat(self, messages: list[Message], model: str | None = None,
             temperature: float = 0.2) -> ChatResponse:
        use_model = model or self.default_model
        payload = {"model": use_model, "messages": [m.to_dict() for m in messages],
                   "temperature": temperature}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.base_url + "/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage") or {}
        pt = usage.get("prompt_tokens") or sum(estimate_tokens(m.content) for m in messages)
        ct = usage.get("completion_tokens") or estimate_tokens(text)
        return ChatResponse(text=text, model=use_model, prompt_tokens=pt,
                            completion_tokens=ct,
                            cost_usd=estimate_cost(use_model, pt, ct), raw=data)
