# Contributing to Diviso

Thanks for helping build a local-first agent everyone can run.

## Development setup

```bash
git clone <your fork>
cd diviso-agent
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Rules

- **Stdlib only for core code.** Diviso must install and run on a clean
  machine, Termux and low-end PCs with no third-party packages. Test-only
  dependencies (pytest) are the exception.
- Every feature ships with tests. Run the full suite before opening a PR.
- No API keys, tokens or personal data in code, tests or examples.
- Mutating tools must go through the approval gate and the workspace sandbox.
- Keep the 60-second quickstart working: `pip install -e .`,
  `diviso doctor`, `diviso run --provider mock "..."`.

## Pull requests

Describe what changed, why, and the exact test output (`pytest -q` summary
line). One topic per PR keeps review fast.
