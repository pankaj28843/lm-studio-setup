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
from lmstudio_setup.catalog_builder import write_catalog
from lmstudio_setup.constants import (
    DEFAULT_MODEL,
    EMBEDDING_MODELS,
    EXPERIMENTAL_35B_MODEL,
    LEGACY_ALIASES,
    MODEL_PACKS,
    PLAYGROUND_MLX_MODELS,
    SUPPORTED_MODELS,
    ModelDownloadSpec,
)
from lmstudio_setup.lmstudio import ensure_model, options_from_env, parse_memory_estimate
from lmstudio_setup.local_models import (
    ALIAS_PREFIX,
    ModelAlias,
    default_lms_bin,
    embedding_model_keys,
    list_local_models,
    llm_model_keys,
    model_aliases,
)
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


def managed_launcher_aliases(bin_dir: Path) -> list[str]:
    aliases: list[str] = []
    if not bin_dir.is_dir():
        return aliases
    for target in bin_dir.iterdir():
        if target.name == "ensure-lmstudio-codex-model":
            continue
        if target.name.startswith(ALIAS_PREFIX) and managed_target(target):
            aliases.append(target.name)
    return sorted(aliases)


async def dynamic_aliases() -> tuple[ModelAlias, ...]:
    models = await list_local_models(default_lms_bin())
    return model_aliases(models, DEFAULT_MODEL)


async def install(bin_dir: Path) -> int:
    bin_dir.mkdir(parents=True, exist_ok=True)
    main = main_script()
    ensure = ensure_script()
    main.chmod(0o755)
    ensure.chmod(0o755)
    aliases = await dynamic_aliases()
    desired = {alias.alias for alias in aliases}

    for name in (*LEGACY_ALIASES, *managed_launcher_aliases(bin_dir)):
        target = bin_dir / name
        if name not in desired and managed_target(target):
            target.unlink()

    for alias in aliases:
        replace_symlink(bin_dir / alias.alias, main)
    replace_symlink(bin_dir / "ensure-lmstudio-codex-model", ensure)
    print(f"Installed {len(aliases)} LM Studio Codex launchers into {bin_dir}")
    return 0


def uninstall(bin_dir: Path) -> int:
    for name in (
        *managed_launcher_aliases(bin_dir),
        *LEGACY_ALIASES,
        "ensure-lmstudio-codex-model",
    ):
        target = bin_dir / name
        if managed_target(target):
            target.unlink()
    print(f"Removed managed symlinks from {bin_dir}")
    return 0


async def links(bin_dir: Path) -> int:
    aliases = await dynamic_aliases()
    for name in (*(alias.alias for alias in aliases), "ensure-lmstudio-codex-model"):
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
        dynamic_catalog = Path(tmp_home) / "lmstudio-model-catalog.json"
        local_models = await list_local_models(default_lms_bin())
        write_catalog(dynamic_catalog, catalog_path(), local_models)
        env = with_default_path({"CODEX_HOME": tmp_home})
        config_arg = f'model_catalog_json="{dynamic_catalog}"'
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
    for model in llm_model_keys(await list_local_models(default_lms_bin())):
        spec = next((item for item in SUPPORTED_MODELS if item.model_id == model), None)
        max_memory = (
            32.0
            if model == EXPERIMENTAL_35B_MODEL
            else spec.max_memory_gib
            if spec is not None
            else 24.0
        )
        reserve = (
            4.0
            if model == EXPERIMENTAL_35B_MODEL
            else spec.reserve_memory_gib
            if spec is not None
            else 12.0
        )
        try:
            options = options_from_env(
                model=model,
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


async def embedding_models_from_env_or_args(models: Iterable[str]) -> list[str]:
    explicit = [model for model in models if model]
    if explicit:
        return explicit
    env_value = os.environ.get("EMBEDDING_MODELS", "")
    if env_value.strip():
        return env_value.split()
    return list(embedding_model_keys(await list_local_models(default_lms_bin())))


def embedding_download_source(model: str) -> str:
    for spec in EMBEDDING_MODELS:
        if spec.model_id == model or spec.download_source == model:
            return spec.download_source
    return model


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


def download_command(lms: Path, spec: ModelDownloadSpec) -> list[str]:
    command = [str(lms), "get"]
    if spec.kind == "mlx":
        command.append("--mlx")
    elif spec.kind == "gguf":
        command.append("--gguf")
    command.extend(["--yes", spec.source])
    return command


async def download_specs(specs: Iterable[ModelDownloadSpec]) -> int:
    lms = Path(os.environ.get("LMS_BIN", str(Path.home() / ".lmstudio" / "bin" / "lms")))
    failed = False
    for spec in specs:
        print(f"Downloading {spec.kind} model: {spec.source}")
        result = await run_command(
            download_command(lms, spec),
            env=with_default_path(),
            capture=False,
        )
        if result.returncode != 0:
            print(f"Failed to download model: {spec.source}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


async def download_model_pack(pack: str) -> int:
    specs = MODEL_PACKS.get(pack)
    if specs is None:
        available = ", ".join(sorted(MODEL_PACKS))
        print(f"Unknown model pack: {pack}; available packs: {available}", file=sys.stderr)
        return 2
    return await download_specs(specs)


async def download_embedding_models(models: list[str]) -> int:
    specs: list[ModelDownloadSpec] = []
    for model in models:
        source = embedding_download_source(model)
        kind = "gguf" if source.startswith("https://huggingface.co/") else "auto"
        specs.append(ModelDownloadSpec(source, kind))
    return await download_specs(specs)


async def embedding_estimates(models: list[str]) -> int:
    lms = Path(os.environ.get("LMS_BIN", str(Path.home() / ".lmstudio" / "bin" / "lms")))
    for model in models:
        result = await run_command(
            [str(lms), "load", model, "--estimate-only", "--yes"],
            env=with_default_path(),
        )
        if result.returncode != 0:
            print(result.combined_output, file=sys.stderr)
            return result.returncode
        try:
            estimate = parse_memory_estimate(result.combined_output)
        except ValueError as exc:
            print(result.combined_output, file=sys.stderr)
            print(f"{exc} for {model}", file=sys.stderr)
            return 1
        print(
            f"{model}: total estimate {estimate.total_gib:.2f} GiB, "
            f"GPU estimate {estimate.gpu_gib:.2f} GiB"
            if estimate.gpu_gib is not None
            else f"{model}: total estimate {estimate.total_gib:.2f} GiB, GPU estimate unknown"
        )
    return 0


async def embedding_estimates_from_env_or_args(models: Iterable[str]) -> int:
    return await embedding_estimates(await embedding_models_from_env_or_args(models))


async def download_embedding_models_from_env_or_args(models: Iterable[str]) -> int:
    return await download_embedding_models(await embedding_models_from_env_or_args(models))


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

    embedding_estimates_parser = subparsers.add_parser("embedding-estimates")
    embedding_estimates_parser.add_argument("--model", action="append", default=[])

    download_parser = subparsers.add_parser("download-playground-mlx")
    download_parser.add_argument("--model", action="append", default=[])

    download_embeddings_parser = subparsers.add_parser("download-embedding-models")
    download_embeddings_parser.add_argument("--model", action="append", default=[])

    download_pack_parser = subparsers.add_parser("download-pack")
    download_pack_parser.add_argument("pack", choices=sorted(MODEL_PACKS))
    return parser


def main(argv: list[str] | None = None) -> None:
    require_uv()
    parser = build_parser()
    args = parser.parse_args(argv)

    match args.command:
        case "install":
            raise SystemExit(asyncio.run(install(args.bin_dir)))
        case "uninstall":
            raise SystemExit(uninstall(args.bin_dir))
        case "links":
            raise SystemExit(asyncio.run(links(args.bin_dir)))
        case "check":
            raise SystemExit(check())
        case "validate-codex-catalog":
            raise SystemExit(asyncio.run(validate_codex_catalog()))
        case "public-scan":
            raise SystemExit(asyncio.run(public_scan()))
        case "estimates":
            raise SystemExit(asyncio.run(estimates(args.parallel)))
        case "embedding-estimates":
            raise SystemExit(asyncio.run(embedding_estimates_from_env_or_args(args.model)))
        case "download-playground-mlx":
            raise SystemExit(
                asyncio.run(download_playground_mlx(models_from_env_or_args(args.model)))
            )
        case "download-embedding-models":
            raise SystemExit(asyncio.run(download_embedding_models_from_env_or_args(args.model)))
        case "download-pack":
            raise SystemExit(asyncio.run(download_model_pack(args.pack)))
        case _:
            parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
