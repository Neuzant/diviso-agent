"""Provider interface shared by every model backend."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Message:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    text: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def estimate_tokens(text: str) -> int:
    """Rough, dependency-free token estimate (~4 chars/token)."""
    return max(1, (len(text) + 3) // 4)


# USD per 1K tokens (prompt, completion) — public list prices, used only for
# cost caps/estimates, not billing.
PRICING = {
    "mock": (0.0, 0.0), "ollama": (0.0, 0.0),
    "gpt-4o": (0.005, 0.015), "gpt-4o-mini": (0.00015, 0.0006),
    "claude-sonnet": (0.003, 0.015), "claude": (0.003, 0.015),
    "grok": (0.003, 0.015), "gemini": (0.00125, 0.005),
    "mistral": (0.002, 0.006), "deepseek": (0.00027, 0.0011),
    "openrouter": (0.002, 0.006), "default": (0.002, 0.006),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = "default"
    for prefix, price in PRICING.items():
        if model.lower().startswith(prefix) or prefix in model.lower():
            key = prefix
            break
    pin, pout = PRICING[key]
    return prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout


class Provider(ABC):
    name = "base"
    default_model = ""

    @abstractmethod
    def chat(self, messages: list[Message], model: str | None = None,
             temperature: float = 0.2) -> ChatResponse:
        raise NotImplementedError

    def stream(self, messages: list[Message], model: str | None = None,
               temperature: float = 0.2) -> Iterator[str]:
        # Default streaming: yield the full response once. Network providers
        # override where the API supports it; correctness does not depend on it.
        yield self.chat(messages, model=model, temperature=temperature).text
