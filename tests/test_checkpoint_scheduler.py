from diviso.checkpoint import CheckpointManager, RunState
from diviso.memory.store import MemoryStore
from diviso.scheduler import Scheduler


def make_store(tmp_path):
    return MemoryStore(tmp_path / "m.db", tmp_path / "MEMORY.md")


def test_checkpoint_save_and_resume(tmp_path):
    store = make_store(tmp_path)
    mgr = CheckpointManager(store)
    state = RunState(run_id="r1", task="do thing", step=3,
                     messages=[{"role": "user", "content": "hi"}],
                     cost_usd=0.25, status="running")
    mgr.save(state)
    resumed = mgr.resume("r1")
    assert resumed is not None
    assert resumed.step == 3 and resumed.cost_usd == 0.25
    assert resumed.messages[0]["content"] == "hi"
    store.close()


def test_resume_missing_run_returns_none(tmp_path):
    store = make_store(tmp_path)
    assert CheckpointManager(store).resume("nope") is None
    store.close()


def test_checkpoint_latest_step_wins(tmp_path):
    store = make_store(tmp_path)
    mgr = CheckpointManager(store)
    for step in (1, 2, 5):
        mgr.save(RunState(run_id="r9", task="t", step=step, messages=[]))
    assert mgr.resume("r9").step == 5
    store.close()


def make_sched(tmp_path):
    return Scheduler(tmp_path / "s.db")


def test_scheduler_add_and_list(tmp_path):
    sched = make_sched(tmp_path)
    jid = sched.add_job("nightly", "summarise", interval_seconds=60)
    jobs = sched.list_jobs()
    assert len(jobs) == 1 and jobs[0].id == jid and jobs[0].name == "nightly"
    sched.close()


def test_scheduler_guard_skips_expensive_tokens(tmp_path):
    sched = make_sched(tmp_path)
    jid = sched.add_job("big", "prompt", max_tokens=100, est_tokens=9999)
    out = sched.run_job(jid, lambda p: "should not run")
    assert out["status"] == "skipped_guard"
    assert sched.logs(jid)[0]["status"] == "skipped_guard"
    sched.close()


def test_scheduler_guard_skips_expensive_cost(tmp_path):
    sched = make_sched(tmp_path)
    jid = sched.add_job("pricey", "prompt", max_cost_usd=0.01, est_cost_usd=9.99)
    out = sched.run_job(jid, lambda p: "should not run")
    assert out["status"] == "skipped_guard"
    sched.close()


def test_scheduler_runs_within_guard(tmp_path):
    sched = make_sched(tmp_path)
    jid = sched.add_job("ok", "prompt", max_tokens=4000, est_tokens=100,
                        max_cost_usd=1.0, est_cost_usd=0.01)
    out = sched.run_job(jid, lambda p: f"ran: {p}")
    assert out["status"] == "ran" and out["result"] == "ran: prompt"
    sched.close()
