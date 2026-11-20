"""Provider registry."""
from __future__ import annotations

from .anthropic import AnthropicProvider
from .base import ChatResponse, Message, Provider, estimate_cost, estimate_tokens
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai_compatible import PRESETS, OpenAICompatibleProvider

__all__ = ["Provider", "Message", "ChatResponse", "MockProvider", "OllamaProvider",
           "OpenAICompatibleProvider", "AnthropicProvider", "get_provider",
           "list_providers", "estimate_tokens", "estimate_cost", "PRESETS"]


def list_providers() -> list[str]:
    return ["mock", "ollama", "anthropic", "claude"] + sorted(PRESETS.keys())


def get_provider(name: str, **kwargs) -> Provider:
    name = name.lower()
    if name == "mock":
        return MockProvider(**{k: v for k, v in kwargs.items() if k == "scripted"})
    if name == "ollama":
        return OllamaProvider(**{k: v for k, v in kwargs.items()
                                 if k in ("base_url", "timeout")})
    if name in ("anthropic", "claude"):
        return AnthropicProvider(**{k: v for k, v in kwargs.items() if k == "api_key"})
    if name in PRESETS:
        allowed = {k: v for k, v in kwargs.items()
                   if k in ("base_url", "api_key", "timeout")}
        return OpenAICompatibleProvider(preset=name, **allowed)
    raise ValueError(f"Unknown provider '{name}'. Available: {', '.join(list_providers())}")
