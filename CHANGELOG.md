# Changelog

All notable changes are documented here. Format follows Keep a Changelog;
versioning follows Semantic Versioning.

## [Unreleased]

### Added

- Multi-language code runners: `javascript_run` (Node.js, registered only
  when `node` is on PATH) and `bash_run`, alongside `python_run`. Same
  safety model — approval gate, workspace-only cwd, subprocess timeout,
  capped output; code runs from a temp file inside the workspace, and
  timeouts/failures return clean error strings instead of raising.
- Dashboard v2 for the web UI: gradient hero header, live device stat
  cards with a RAM usage bar, a provider-status panel (configured or not —
  key values are never shown), example-prompt chips, and a features grid.

## [0.1.0] - 2026-11-20

### Added

- Local-first agent core (Python stdlib only): config, hardware detection
  with lite/balanced/pro profiles and graceful model degradation.
- Providers: Ollama, OpenAI, xAI/Grok, Gemini (OpenAI-compatible endpoint),
  Mistral, DeepSeek, OpenRouter, custom OpenAI-compatible endpoints,
  Anthropic/Claude, and a deterministic offline mock provider.
- ReAct loop with hard step and cost caps, visible trace (JSONL per run).
- Planner with step breakdown, retry-with-different-approach and reflection.
- Persistent memory (SQLite + MEMORY.md sync) and TF-IDF RAG over local files.
- Multi-agent team: Researcher, Coder, Reviewer with exactly one fix pass.
- Tools: Python runner, file edit with diffs, test runner, read-only git,
  web fetch and DuckDuckGo Lite search — behind an approval gate and a
  workspace sandbox.
- Checkpoint/resume after every step; scheduler with per-job cost/token
  guards; local plugin system; MCP client (stdio + HTTP); local-only
  SKILL.md skills.
- CLI (`run`, `chat`, `doctor`, `memory`, `schedule`, `resume`, `serve`)
  and a stdlib web UI. Install scripts for Linux/macOS, Windows, Termux
  and Docker.
