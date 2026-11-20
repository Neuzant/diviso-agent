"""Deterministic offline provider — used for tests, demos and the quickstart."""
from __future__ import annotations

from .base import ChatResponse, Message, Provider, estimate_tokens


class MockProvider(Provider):
    name = "mock"
    default_model = "mock-1"

    def __init__(self, scripted: list[str] | None = None):
        # scripted: exact responses returned in order; after exhaustion the
        # deterministic echo behaviour is used.
        self._scripted = list(scripted or [])
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message], model: str | None = None,
             temperature: float = 0.2) -> ChatResponse:
        self.calls.append(list(messages))
        last = messages[-1].content if messages else ""
        if self._scripted:
            text = self._scripted.pop(0)
        elif "FINAL:" in last:
            text = last
        else:
            text = f"FINAL: Mock response to: {last}"
        pt = sum(estimate_tokens(m.content) for m in messages)
        return ChatResponse(text=text, model=model or self.default_model,
                            prompt_tokens=pt, completion_tokens=estimate_tokens(text),
                            cost_usd=0.0)
