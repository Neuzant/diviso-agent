"""Diviso CLI: run / chat / doctor / memory / schedule / resume / serve."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .agent.react import ReactAgent
from .checkpoint import CheckpointManager
from .config import DivisoConfig
from .hardware import MODEL_SUGGESTIONS, check_model_fit, detect_hardware, select_profile
from .memory.store import MemoryStore
from .providers import get_provider, list_providers
from .providers.base import Message
from .safety import ApprovalGate, Sandbox
from .scheduler import Scheduler
from .tools import build_registry
from .trace import TraceLogger


def _store(cfg: DivisoConfig) -> MemoryStore:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return MemoryStore(cfg.data_dir / "diviso.db", cfg.data_dir / "MEMORY.md")


def cmd_doctor(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    hw = detect_hardware()
    profile = select_profile(hw)
    report = {**hw.to_dict(), "profile": profile,
              "suggested_models": MODEL_SUGGESTIONS[profile],
              "config": cfg.redacted_dict(), "providers": list_providers(),
              "version": __version__}
    if cfg.model:
        fit = check_model_fit(cfg.model, hw, profile)
        report["model_fit"] = {"fits": fit.fits, "suggested": fit.suggested_model,
                               "reason": fit.reason}
    print(json.dumps(report, indent=2))
    return 0


def cmd_run(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    cfg.provider = args.provider or cfg.provider
    cfg.model = args.model or cfg.model
    cfg.max_steps = args.max_steps or cfg.max_steps
    cfg.max_cost_usd = args.max_cost if args.max_cost is not None else cfg.max_cost_usd
    provider = get_provider(cfg.provider)
    store = _store(cfg)
    sandbox = Sandbox(cfg.workspace)
    gate = ApprovalGate(auto_approve=cfg.auto_approve or args.yes,
                        callback=None if (cfg.auto_approve or args.yes) else _cli_approve)
    registry = build_registry(sandbox, gate)
    run_id = args.run_id or None
    tracer = TraceLogger(cfg.data_dir / "traces", run_id or "run")
    agent = ReactAgent(provider, tools=registry.as_dict(), max_steps=cfg.max_steps,
                       max_cost_usd=cfg.max_cost_usd, trace_logger=tracer,
                       checkpoints=CheckpointManager(store), model=cfg.model)
    result = agent.run(" ".join(args.prompt), run_id=run_id)
    print(result.answer)
    print(f"\n[run {result.run_id} · steps {result.steps} · "
          f"cost ${result.cost_usd:.4f} · stopped: {result.stopped_reason}]",
          file=sys.stderr)
    store.close()
    return 0


def _cli_approve(action) -> bool:
    print(f"\nApproval needed — {action.kind}: {action.description}")
    if action.diff:
        print(action.diff)
    return input("Approve? [y/N] ").strip().lower() in ("y", "yes")


def cmd_chat(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    provider = get_provider(args.provider or cfg.provider)
    history = [Message("system", "You are Diviso, a helpful local-first agent.")]
    print("Diviso chat — type 'exit' to quit.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in ("exit", "quit"):
            break
        if not line:
            continue
        history.append(Message("user", line))
        resp = provider.chat(history, model=cfg.model)
        print(f"diviso> {resp.text}")
        history.append(Message("assistant", resp.text))
    return 0


def cmd_memory(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    store = _store(cfg)
    if args.action == "add":
        store.set_fact(args.key, " ".join(args.value))
        store.export_to_markdown()
        print(f"Saved {args.key}")
    elif args.action == "get":
        print(store.get_fact(args.key) or "(not found)")
    elif args.action == "list":
        for k, v in store.list_facts().items():
            print(f"- {k}: {v}")
    elif args.action == "import":
        print(f"Imported {store.import_from_markdown()} facts from MEMORY.md")
    elif args.action == "export":
        print(f"Wrote {store.export_to_markdown()}")
    store.close()
    return 0


def cmd_schedule(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    sched = Scheduler(cfg.data_dir / "scheduler.db")
    if args.action == "add":
        jid = sched.add_job(args.name, " ".join(args.prompt),
                            interval_seconds=args.interval, max_tokens=args.max_tokens,
                            max_cost_usd=args.max_cost, est_tokens=args.est_tokens,
                            est_cost_usd=args.est_cost)
        print(f"Added job {jid} (guard: {args.max_tokens} tokens / ${args.max_cost})")
    elif args.action == "list":
        for j in sched.list_jobs():
            print(f"#{j.id} {j.name} every {j.interval_seconds}s "
                  f"guard {j.max_tokens}tok/${j.max_cost_usd} last={j.last_status or '-'}")
    elif args.action == "run":
        provider = get_provider(args.provider or cfg.provider)
        out = sched.run_job(args.job_id,
                            lambda p: provider.chat([Message("user", p)]).text)
        print(json.dumps(out, indent=2))
    elif args.action == "logs":
        for log in sched.logs():
            print(log)
    sched.close()
    return 0


def cmd_resume(args) -> int:
    cfg = DivisoConfig.load(workspace=args.workspace)
    store = _store(cfg)
    state = CheckpointManager(store).resume(args.run_id)
    if state is None:
        print(f"No checkpoint found for run {args.run_id}")
        store.close()
        return 1
    print(json.dumps(state.to_dict(), indent=2))
    if args.continue_run:
        provider = get_provider(args.provider or cfg.provider)
        tracer = TraceLogger(cfg.data_dir / "traces", state.run_id)
        agent = ReactAgent(provider, max_steps=cfg.max_steps,
                           max_cost_usd=cfg.max_cost_usd, trace_logger=tracer,
                           checkpoints=CheckpointManager(store), model=cfg.model)
        result = agent.run(state.task, resume_state=state)
        print(result.answer)
    store.close()
    return 0


def cmd_serve(args) -> int:
    from .webui import serve
    serve(host=args.host, port=args.port, provider=args.provider or "mock")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="diviso",
                                description="Diviso — local-first AI agent")
    p.add_argument("--version", action="version", version=f"diviso {__version__}")
    p.add_argument("--workspace", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="Hardware, profile and provider report")
    d.set_defaults(fn=cmd_doctor)

    r = sub.add_parser("run", help="Run a task through the ReAct agent")
    r.add_argument("prompt", nargs="+")
    r.add_argument("--provider", default=None)
    r.add_argument("--model", default=None)
    r.add_argument("--max-steps", type=int, default=None)
    r.add_argument("--max-cost", type=float, default=None)
    r.add_argument("--run-id", default=None)
    r.add_argument("--yes", action="store_true", help="Auto-approve tool actions")
    r.set_defaults(fn=cmd_run)

    c = sub.add_parser("chat", help="Interactive chat REPL")
    c.add_argument("--provider", default=None)
    c.set_defaults(fn=cmd_chat)

    m = sub.add_parser("memory", help="Persistent memory (SQLite + MEMORY.md)")
    m.add_argument("action", choices=["add", "get", "list", "import", "export"])
    m.add_argument("key", nargs="?", default="")
    m.add_argument("value", nargs="*")
    m.set_defaults(fn=cmd_memory)

    s = sub.add_parser("schedule", help="Scheduled jobs with cost/token guards")
    s.add_argument("action", choices=["add", "list", "run", "logs"])
    s.add_argument("--name", default="job")
    s.add_argument("--prompt", nargs="*", default=[])
    s.add_argument("--interval", type=int, default=3600)
    s.add_argument("--max-tokens", type=int, default=4000)
    s.add_argument("--max-cost", type=float, default=0.10)
    s.add_argument("--est-tokens", type=int, default=1000)
    s.add_argument("--est-cost", type=float, default=0.01)
    s.add_argument("--job-id", type=int, default=1)
    s.add_argument("--provider", default=None)
    s.set_defaults(fn=cmd_schedule)

    rs = sub.add_parser("resume", help="Show or continue a checkpointed run")
    rs.add_argument("run_id")
    rs.add_argument("--continue-run", action="store_true", dest="continue_run")
    rs.add_argument("--provider", default=None)
    rs.set_defaults(fn=cmd_resume)

    sv = sub.add_parser("serve", help="Start the simple web UI")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--provider", default=None)
    sv.set_defaults(fn=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
