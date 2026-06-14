from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_path(env: dict[str, str] | None = None) -> str:
    source = dict(os.environ if env is None else env)
    home = Path.home()
    prefix = [
        str(home / ".lmstudio" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    existing = source.get("PATH", "")
    if existing:
        prefix.append(existing)
    return ":".join(prefix)


def with_default_path(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(os.environ)
    if env is not None:
        merged.update(env)
    merged["PATH"] = default_path(merged)
    return merged
