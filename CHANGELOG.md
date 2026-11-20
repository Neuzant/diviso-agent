# Changelog

All notable changes are documented here. Format follows Keep a Changelog;
versioning follows Semantic Versioning.

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
