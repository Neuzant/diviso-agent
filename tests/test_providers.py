import pytest

from diviso.providers import get_provider, list_providers
from diviso.providers.base import Message, estimate_cost, estimate_tokens


def test_registry_lists_all_providers():
    names = list_providers()
    for expected in ("mock", "ollama", "openai", "grok", "gemini", "mistral",
                     "deepseek", "openrouter", "anthropic", "custom"):
        assert expected in names


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider("nope-not-a-provider")


def test_mock_is_deterministic():
    p = get_provider("mock")
    a = p.chat([Message("user", "hello")])
    b = p.chat([Message("user", "hello")])
    assert a.text == b.text == "FINAL: Mock response to: hello"
    assert a.cost_usd == 0.0


def test_mock_scripted_responses_in_order():
    p = get_provider("mock", scripted=["one", "two"])
    assert p.chat([Message("user", "x")]).text == "one"
    assert p.chat([Message("user", "x")]).text == "two"


def test_mock_stream_yields_text():
    p = get_provider("mock")
    assert list(p.stream([Message("user", "hi")])) == ["FINAL: Mock response to: hi"]


def test_openai_compatible_presets_have_defaults():
    for preset in ("openai", "xai", "gemini", "mistral", "deepseek", "openrouter"):
        provider = get_provider(preset)
        assert provider.base_url.startswith("https://")
        assert provider.default_model


def test_custom_provider_accepts_base_url():
    provider = get_provider("custom", base_url="http://localhost:9999/v1")
    assert provider.base_url == "http://localhost:9999/v1"


def test_token_and_cost_estimates():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10
    assert estimate_cost("mock-1", 1000, 1000) == 0.0
    assert estimate_cost("gpt-4o", 1000, 0) == pytest.approx(0.005)
