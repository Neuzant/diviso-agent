from diviso.agent.planner import Planner
from diviso.providers.mock import MockProvider


def test_plan_parses_dash_lines():
    planner = Planner(MockProvider(scripted=["- Research\n- Build\n- Test"]))
    assert planner.plan("anything") == ["Research", "Build", "Test"]


def test_plan_heuristic_fallback():
    planner = Planner(MockProvider(scripted=["no list here"]))
    steps = planner.plan("First do A. Then do B")
    assert len(steps) >= 1


def test_execute_success():
    planner = Planner(MockProvider(scripted=["- Step one"]),
                      executor=lambda prompt: "done")
    result = planner.execute("task")
    assert result.reflection.succeeded
    assert result.steps[0].attempts == 1


def test_retry_with_different_approach():
    prompts = []

    def flaky(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            raise RuntimeError("boom")
        return "second approach worked"

    planner = Planner(MockProvider(scripted=["- Hard step"]), executor=flaky,
                      max_retries=2)
    result = planner.execute("task")
    assert result.steps[0].succeeded and result.steps[0].attempts == 2
    assert prompts[0] != prompts[1]
    assert "different approach" in prompts[1]


def test_reflection_records_failures():
    planner = Planner(MockProvider(scripted=["- Impossible"]),
                      executor=lambda prompt: (_ for _ in ()).throw(RuntimeError("no")),
                      max_retries=1)
    result = planner.execute("task")
    assert not result.reflection.succeeded
    assert result.reflection.failed_steps == 1
    assert result.reflection.lessons
