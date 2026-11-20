from diviso.agent.react import ReactAgent
from diviso.providers.base import ChatResponse, Message, Provider
from diviso.providers.mock import MockProvider


class AlwaysToolProvider(Provider):
    name = "always-tool"

    def chat(self, messages, model=None, temperature=0.2):
        return ChatResponse(text='TOOL_CALL: {"name": "noop", "args": {}}',
                            model="t", cost_usd=0.0)


class ExpensiveProvider(Provider):
    name = "expensive"

    def chat(self, messages, model=None, temperature=0.2):
        return ChatResponse(text="some answer", model="t", cost_usd=5.0)


def test_react_final_answer():
    agent = ReactAgent(MockProvider(), max_steps=5, max_cost_usd=1.0)
    result = agent.run("Say hello")
    assert result.stopped_reason == "final"
    assert "Mock response" in result.answer
    assert result.steps == 1


def test_react_tool_call_loop():
    provider = MockProvider(scripted=[
        'TOOL_CALL: {"name": "add", "args": {"a": 2, "b": 3}}',
        "FINAL: The sum is 5",
    ])
    agent = ReactAgent(provider, tools={"add": lambda a, b: str(a + b)},
                       max_steps=5, max_cost_usd=1.0)
    result = agent.run("add numbers")
    assert result.answer == "The sum is 5"
    assert result.steps == 2


def test_react_unknown_tool_becomes_observation_not_crash():
    provider = MockProvider(scripted=[
        'TOOL_CALL: {"name": "missing", "args": {}}', "FINAL: recovered"])
    agent = ReactAgent(provider, tools={}, max_steps=5, max_cost_usd=1.0)
    assert agent.run("x").answer == "recovered"


def test_react_max_steps_cap():
    agent = ReactAgent(AlwaysToolProvider(), tools={"noop": lambda: "ok"},
                       max_steps=3, max_cost_usd=100.0)
    result = agent.run("loop forever")
    assert result.steps == 3
    assert result.stopped_reason == "max_steps"


def test_react_max_cost_cap():
    agent = ReactAgent(ExpensiveProvider(), max_steps=10, max_cost_usd=1.0)
    result = agent.run("too expensive")
    assert result.stopped_reason == "max_cost"
    assert result.cost_usd > 1.0
