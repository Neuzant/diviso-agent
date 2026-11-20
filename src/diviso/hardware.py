"""Hardware detection and lite / balanced / pro profiles. Stdlib only."""
from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field

MODEL_SUGGESTIONS = {
    "lite":     ["qwen2.5:0.5b", "llama3.2:1b", "qwen2.5:1.5b"],
    "balanced": ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"],
    "pro":      ["qwen2.5:32b", "llama3.1:70b", "qwen2.5-coder:32b"],
}
# Approximate on-disk / RAM footprint (GB) for common model sizes.
MODEL_SIZE_GB = {"0.5b": 0.4, "1b": 0.8, "1.5b": 1.0, "3b": 2.0, "7b": 4.7,
                 "8b": 5.0, "14b": 9.0, "32b": 19.0, "70b": 40.0}


def _ram_gb() -> float:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / (1024 ** 3), 2)
    except (ValueError, OSError, AttributeError):
        return 4.0


def _gpu_name() -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=3)
        name = out.stdout.strip().splitlines()
        return name[0] if name and out.returncode == 0 else None
    except (subprocess.SubprocessError, OSError):
        return None


def detect_ollama(base_url: str = "http://localhost:11434", timeout: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(base_url + "/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


@dataclass
class HardwareInfo:
    ram_gb: float
    cpu_count: int
    gpu: str | None = None
    ollama_running: bool = False

    def to_dict(self) -> dict:
        return {"ram_gb": self.ram_gb, "cpu_count": self.cpu_count,
                "gpu": self.gpu, "ollama_running": self.ollama_running}


def detect_hardware(check_ollama: bool = True) -> HardwareInfo:
    return HardwareInfo(
        ram_gb=_ram_gb(), cpu_count=os.cpu_count() or 1, gpu=_gpu_name(),
        ollama_running=detect_ollama() if check_ollama else False)


def select_profile(hw: HardwareInfo) -> str:
    if hw.gpu or hw.ram_gb >= 16:
        return "pro"
    if hw.ram_gb >= 6:
        return "balanced"
    return "lite"


def model_size_gb(model: str) -> float | None:
    low = model.lower()
    for tag, size in sorted(MODEL_SIZE_GB.items(), key=lambda kv: -len(kv[0])):
        if f":{tag}" in low or low.endswith(tag):
            return size
    return None


@dataclass
class FitResult:
    fits: bool
    suggested_model: str
    reason: str
    profile: str = ""


def check_model_fit(model: str, hw: HardwareInfo, profile: str | None = None) -> FitResult:
    """Graceful degradation: if a model is too big for RAM, suggest a smaller one."""
    profile = profile or select_profile(hw)
    size = model_size_gb(model)
    if size is None:
        return FitResult(True, model, "Unknown size; assuming it fits.", profile)
    usable = hw.ram_gb * 0.8
    if size <= usable:
        return FitResult(True, model, f"{model} needs ~{size} GB, {usable:.1f} GB usable.", profile)
    for cand in MODEL_SUGGESTIONS[profile] + MODEL_SUGGESTIONS["lite"]:
        csize = model_size_gb(cand)
        if csize is not None and csize <= usable:
            return FitResult(False, cand,
                             f"{model} needs ~{size} GB but only {usable:.1f} GB usable; "
                             f"degrading to {cand}.", profile)
    return FitResult(False, MODEL_SUGGESTIONS["lite"][0],
                     f"{model} too large; degrading to smallest suggested model.", profile)
