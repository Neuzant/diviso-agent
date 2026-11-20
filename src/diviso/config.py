"""Configuration: environment variables + optional diviso.toml / diviso.json.

API keys are read ONLY from environment variables. They are never written to
disk by Diviso and are redacted from any dict/log representation.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

SECRET_ENV_VARS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "MISTRAL_API_KEY", "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY", "DIVISO_API_KEY",
)

_KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|[A-Za-z0-9_\-]{32,})")


def redact_text(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Replace known secret values / key-shaped strings with ***."""
    out = text
    for name in SECRET_ENV_VARS:
        val = os.environ.get(name)
        if val:
            out = out.replace(val, "***")
    for secret in extra_secrets:
        if secret:
            out = out.replace(secret, "***")
    return out


@dataclass
class DivisoConfig:
    provider: str = "mock"
    model: str | None = None
    workspace: Path = field(default_factory=lambda: Path.cwd())
    profile: str = "balanced"
    max_steps: int = 20
    max_cost_usd: float = 1.00
    auto_approve: bool = False
    data_dir: Path = field(default_factory=lambda: Path.home() / ".diviso")
    base_url: str | None = None

    def redacted_dict(self) -> dict:
        d = {
            "provider": self.provider, "model": self.model,
            "workspace": str(self.workspace), "profile": self.profile,
            "max_steps": self.max_steps, "max_cost_usd": self.max_cost_usd,
            "auto_approve": self.auto_approve, "data_dir": str(self.data_dir),
            "base_url": self.base_url,
            "api_keys_present": {
                name: bool(os.environ.get(name)) for name in SECRET_ENV_VARS
            },
        }
        return json.loads(redact_text(json.dumps(d)))

    @classmethod
    def load(cls, config_path: str | Path | None = None,
             workspace: str | Path | None = None) -> "DivisoConfig":
        data: dict = {}
        path = Path(config_path) if config_path else None
        if path is None:
            for cand in (Path.cwd() / "diviso.toml", Path.cwd() / "diviso.json"):
                if cand.exists():
                    path = cand
                    break
        if path is not None and Path(path).exists():
            p = Path(path)
            if p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
            elif p.suffix == ".toml":
                try:
                    import tomllib
                except ModuleNotFoundError:  # Python 3.10
                    import tomli as tomllib  # type: ignore
                with p.open("rb") as fh:
                    data = tomllib.load(fh)
        cfg = cls()
        for key in ("provider", "model", "profile", "base_url"):
            if key in data:
                setattr(cfg, key, data[key])
        for key in ("max_steps", "max_cost_usd"):
            if key in data:
                setattr(cfg, key, data[key])
        if "auto_approve" in data:
            cfg.auto_approve = bool(data["auto_approve"])
        # Environment overrides file.
        cfg.provider = os.environ.get("DIVISO_PROVIDER", cfg.provider)
        cfg.model = os.environ.get("DIVISO_MODEL", cfg.model)
        cfg.base_url = os.environ.get("DIVISO_BASE_URL", cfg.base_url)
        if os.environ.get("DIVISO_MAX_STEPS"):
            cfg.max_steps = int(os.environ["DIVISO_MAX_STEPS"])
        if os.environ.get("DIVISO_MAX_COST_USD"):
            cfg.max_cost_usd = float(os.environ["DIVISO_MAX_COST_USD"])
        if workspace is not None:
            cfg.workspace = Path(workspace)
        elif "workspace" in data:
            cfg.workspace = Path(data["workspace"])
        return cfg
