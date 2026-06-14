from __future__ import annotations

import argparse
import asyncio
import compileall
import getpass
import os
import re
import shutil
import sys
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import ValidationError

from lmstudio_setup.catalog import validate_catalog
from lmstudio_setup.constants import (
    ALIASES,
    EXPERIMENTAL_35B_MODEL,
    LEGACY_ALIASES,
    PLAYGROUND_MLX_MODELS,
    SUPPORTED_MODELS,
)
from lmstudio_setup.lmstudio import ensure_model, options_from_env
from lmstudio_setup.paths import repo_root, with_default_path
from lmstudio_setup.process import run_command

SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|github_pat_[A-Za-z0-9]|"
    r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|"
    r"password\s*=|api[_-]?key\s*=|token\s*=|secret\s*=)",
    re.IGNORECASE,
)


def main_script() -> Path:
    return repo_root() / "bin" / "codex-lm-studio"


def ensure_script() -> Path:
    return repo_root() / "bin" / "ensure-lmstudio-codex-model"


def catalog_path() -> Path:
    return repo_root() / "config" / "lmstudio-qwen.json"


def managed_target(target: Path) -> bool:
    if not target.is_symlink():
        return False
    resolved = target.resolve(strict=False)
    managed = {main_script().resolve(), ensure_script().resolve()}
    return resolved in managed or "/lm-studio-setup/bin/" in str(resolved)


def backup_existing(target: Path) -> None:
    if target.exists() and not target.is_symlink():
        backup = target.with_name(f"{target.name}.bak.{time.strftime('%Y%m%d%H%M%S')}")
        target.rename(backup)


def replace_symlink(target: Path, source: Path) -> None:
    backup_existing(target)
    if target.is_symlink() or target.exists():
        target.unlink()
    target.symlink_to(source)


def install(bin_dir: Path) -> int:
    bin_dir.mkdir(parents=True, exist_ok=True)
    main = main_script()
    ensure = ensure_script()
    main.chmod(0o755)
    ensure.chmod(0o755)

    for name in LEGACY_ALIASES:
        target = bin_dir / name
        if managed_target(target):
            target.unlink()

    for name in ALIASES:
        replace_symlink(bin_dir / name, main)
    replace_symlink(bin_dir / "ensure-lmstudio-codex-model", ensure)
    print(f"Installed LM Studio Codex launchers into {bin_dir}")
    return 0


def uninstall(bin_dir: Path) -> int:
    for name in (*ALIASES, *LEGACY_ALIASES, "ensure-lmstudio-codex-model"):
        target = bin_dir / name
        if managed_target(target):
            target.unlink()
    print(f"Removed managed symlinks from {bin_dir}")
    return 0


def links(bin_dir: Path) -> int:
    for name in (*ALIASES, "ensure-lmstudio-codex-model"):
        target = bin_dir / name
        if target.is_symlink():
            print(f"{name:<44} -> {os.readlink(target)}")
        else:
            print(f"{name:<44} missing")
    return 0


def py_files() -> list[Path]:
    root = repo_root()
    files = [root / "bin" / "codex-lm-studio", root / "bin" / "ensure-lmstudio-codex-model"]
    files.extend((root / "src").rglob("*.py"))
    return files


def check() -> int:
    quiet = compileall.compile_file
    for path in py_files():
        if not quiet(str(path), quiet=1):
            return 1
    validate_catalog(catalog_path())
    print("Python and catalog checks passed")
    return 0


async def validate_codex_catalog() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_home:
        env = with_default_path({"CODEX_HOME": tmp_home})
        config_arg = f'model_catalog_json="{catalog_path()}"'
        result = await run_command(
            ["codex", "debug", "models", "-c", config_arg],
            env=env,
        )
    if result.returncode != 0:
        print(result.combined_output, file=sys.stderr)
        return result.returncode
    print("Codex catalog parse passed")
    return 0


async def git_tracked_files() -> list[Path]:
    result = await run_command(["git", "ls-files", "-z"], env=with_default_path())
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    root = repo_root()
    return [root / raw for raw in result.stdout.split("\0") if raw]


async def github_login() -> str | None:
    result = await run_command(["gh", "api", "user", "-q", ".login"], env=with_default_path())
    if result.returncode != 0:
        return None
    login = result.stdout.strip()
    return login or None


def scan_file(path: Path, patterns: Sequence[tuple[str, re.Pattern[str]]]) -> list[str]:
    text = path.read_text(errors="ignore")
    findings: list[str] = []
    for label, pattern in patterns:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: {label}")
    return findings


async def public_scan() -> int:
    username = getpass.getuser()
    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("potential secret", SECRET_PATTERN),
        ("machine-specific home path", re.compile(rf"/Users/{re.escape(username)}")),
    ]
    login = await github_login()
    if login:
        patterns.append(("GitHub username", re.compile(re.escape(login))))

    findings: list[str] = []
    for path in await git_tracked_files():
        if path.is_file():
            findings.extend(scan_file(path, patterns))

    if findings:
        print("Potential public-repo leak found:", file=sys.stderr)
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("Tracked-file public-repo scan passed")
    return 0


async def estimates(parallel: int) -> int:
    for spec in SUPPORTED_MODELS:
        max_memory = 32.0 if spec.model_id == EXPERIMENTAL_35B_MODEL else spec.max_memory_gib
        reserve = 4.0 if spec.model_id == EXPERIMENTAL_35B_MODEL else spec.reserve_memory_gib
        try:
            options = options_from_env(
                model=spec.model_id,
                parallel=parallel,
                max_memory_gib=max_memory,
                reserve_memory_gib=reserve,
                estimate_only=True,
            )
        except (ValidationError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 2
        code = await ensure_model(options)
        if code != 0:
            return code
    return 0


def models_from_env_or_args(models: Iterable[str]) -> list[str]:
    explicit = [model for model in models if model]
    if explicit:
        return explicit
    env_value = os.environ.get("PLAYGROUND_MLX_MODELS", "")
    if env_value.strip():
        return env_value.split()
    return list(PLAYGROUND_MLX_MODELS)


async def download_playground_mlx(models: list[str]) -> int:
    lms = Path(os.environ.get("LMS_BIN", str(Path.home() / ".lmstudio" / "bin" / "lms")))
    for model in models:
        print(f"Downloading MLX playground model: {model}")
        result = await run_command(
            [str(lms), "get", "--mlx", "--yes", model],
            env=with_default_path(),
            capture=False,
        )
        if result.returncode != 0:
            print(
                f"Skipped {model}; LM Studio could not resolve an MLX artifact for it.",
                file=sys.stderr,
            )
    return 0


def require_uv() -> None:
    if shutil.which("uv") is None:
        raise SystemExit("uv is required; install it from https://docs.astral.sh/uv/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lmstudio-setup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("install", "uninstall", "links"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--bin-dir",
            type=Path,
            default=Path.home() / ".local" / "bin",
        )

    subparsers.add_parser("check")
    subparsers.add_parser("validate-codex-catalog")
    subparsers.add_parser("public-scan")

    estimates_parser = subparsers.add_parser("estimates")
    estimates_parser.add_argument("--parallel", type=int, default=4)

    download_parser = subparsers.add_parser("download-playground-mlx")
    download_parser.add_argument("--model", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> None:
    require_uv()
    parser = build_parser()
    args = parser.parse_args(argv)

    match args.command:
        case "install":
            raise SystemExit(install(args.bin_dir))
        case "uninstall":
            raise SystemExit(uninstall(args.bin_dir))
        case "links":
            raise SystemExit(links(args.bin_dir))
        case "check":
            raise SystemExit(check())
        case "validate-codex-catalog":
            raise SystemExit(asyncio.run(validate_codex_catalog()))
        case "public-scan":
            raise SystemExit(asyncio.run(public_scan()))
        case "estimates":
            raise SystemExit(asyncio.run(estimates(args.parallel)))
        case "download-playground-mlx":
            raise SystemExit(
                asyncio.run(download_playground_mlx(models_from_env_or_args(args.model)))
            )
        case _:
            parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
