"""SKILL.md skills — local files only. Remote (http/https) skill sources are
explicitly rejected; Diviso never downloads a skill from the internet."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _reject_remote(source: str) -> None:
    if source.startswith(("http://", "https://", "ftp://", "//")):
        raise ValueError(
            f"Remote skills are not allowed (local files only): {source}")


def parse_skill_md(text: str, path: Path) -> Skill:
    name, description, body = path.parent.name, "", text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for line in front.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    if k.strip() == "name":
                        name = v.strip()
                    elif k.strip() == "description":
                        description = v.strip()
    return Skill(name=name, description=description, body=body, path=path)


def load_skill(source: str | Path) -> Skill:
    _reject_remote(str(source))
    p = Path(source)
    md = p / "SKILL.md" if p.is_dir() else p
    if not md.exists():
        raise FileNotFoundError(f"No SKILL.md at {source}")
    return parse_skill_md(md.read_text(encoding="utf-8"), md)


def discover_skills(root: str | Path) -> list[Skill]:
    _reject_remote(str(root))
    base = Path(root)
    if not base.exists():
        return []
    skills = []
    for md in sorted(base.rglob("SKILL.md")):
        skills.append(parse_skill_md(md.read_text(encoding="utf-8"), md))
    return skills
