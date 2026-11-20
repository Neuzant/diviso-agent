"""Local plugin loader. Plugins live on disk only — there is no network
install path in Diviso, by design.

Layout:  plugins/<name>/plugin.json  {"name": "...", "version": "...", "description": "..."}
         plugins/<name>/plugin.py    defines register(registry) or PLUGIN = {...}
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    path: Path
    module: object


def _load_module(name: str, file: Path):
    spec = importlib.util.spec_from_file_location(f"diviso_plugin_{name}", file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load plugin module {file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_plugins(plugins_dir: str | Path) -> list[Path]:
    root = Path(plugins_dir)
    if not root.exists():
        return []
    return sorted(p.parent for p in root.glob("*/plugin.json"))


def load_plugins(plugins_dir: str | Path, registry=None) -> list[Plugin]:
    loaded = []
    for folder in discover_plugins(plugins_dir):
        manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
        name = manifest.get("name", folder.name)
        py_file = folder / "plugin.py"
        if not py_file.exists():
            raise FileNotFoundError(f"Plugin {name} has no plugin.py")
        module = _load_module(name, py_file)
        if registry is not None and hasattr(module, "register"):
            module.register(registry)
        loaded.append(Plugin(name=name, version=manifest.get("version", "0.0.0"),
                             description=manifest.get("description", ""),
                             path=folder, module=module))
    return loaded
