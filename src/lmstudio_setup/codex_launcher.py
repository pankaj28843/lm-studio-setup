from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from lmstudio_setup.catalog_builder import write_catalog
from lmstudio_setup.constants import (
    DEFAULT_MODEL,
    DEFAULT_PARALLEL,
    MIN_CONTEXT_LENGTH,
    model_spec,
)
from lmstudio_setup.lmstudio import ensure_model, options_from_env
from lmstudio_setup.local_models import (
    alias_map,
    default_lms_bin,
    list_local_models,
    llm_model_keys,
)
from lmstudio_setup.paths import repo_root, with_default_path
from lmstudio_setup.toml_edit import ensure_root_key

OVERRIDE_GUARDRAILS_FLAG = "--lmstudio-override-guardrails"


def toml_string(value: str) -> str:
    return json.dumps(value)


def has_model_arg(args: list[str]) -> bool:
    return any(arg in {"-m", "--model"} or arg.startswith("--model=") for arg in args)


def model_arg_value(args: list[str]) -> str | None:
    for index, arg in enumerate(args):
        if arg in {"-m", "--model"}:
            return args[index + 1] if index + 1 < len(args) else None
        if arg.startswith("--model="):
            return arg.split("=", 1)[1]
    return None


def split_launcher_args(args: list[str]) -> tuple[list[str], bool]:
    codex_args: list[str] = []
    override_guardrails = False
    for arg in args:
        if arg == OVERRIDE_GUARDRAILS_FLAG:
            override_guardrails = True
        else:
            codex_args.append(arg)
    return codex_args, override_guardrails


def validate_model_args(args: list[str], allowed_models: set[str]) -> None:
    for index, arg in enumerate(args):
        if arg in {"-m", "--model"}:
            if index + 1 >= len(args):
                raise ValueError(f"{arg} requires a model value")
            model = args[index + 1]
        elif arg.startswith("--model="):
            model = arg.split("=", 1)[1]
        else:
            continue
        if model not in allowed_models:
            raise ValueError(
                f"codex-lm-studio only allows downloaded LM Studio LLM models: "
                f"{', '.join(sorted(allowed_models))}; got: {model}"
            )


def positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer, got: {value}") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number, got: {value}") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive number, got: {value}")
    return parsed


def prepare_codex_home(primary_home: Path, lm_home: Path) -> None:
    lm_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    config = lm_home / "config.toml"
    if not config.exists():
        primary_config = primary_home / "config.toml"
        if primary_config.is_file():
            shutil.copyfile(primary_config, config)
        else:
            config.touch()
        config.chmod(0o600)

    auth_json = lm_home / "auth.json"
    if auth_json.is_file() and auth_json.stat().st_size == 0:
        auth_json.unlink()

    if not primary_home.is_dir():
        return

    for source in primary_home.iterdir():
        if source.name in {".", "..", "auth.json", "config.toml"}:
            continue
        target = lm_home / source.name
        if not target.exists() and not target.is_symlink():
            target.symlink_to(source)


async def launch_codex(user_args: list[str]) -> int:
    env = with_default_path()
    root = repo_root()
    static_catalog = root / "config" / "lmstudio-qwen.json"
    invocation_name = env.get(
        "CODEX_LM_STUDIO_INVOCATION_NAME",
        Path(sys.argv[0] if sys.argv else "codex-lm-studio").name,
    )

    if not static_catalog.is_file() or static_catalog.stat().st_size == 0:
        print(f"Model catalog is missing: {static_catalog}", file=sys.stderr)
        return 1

    codex_user_args, override_guardrails = split_launcher_args(user_args)
    try:
        local_models = await list_local_models(default_lms_bin())
        downloaded_llms = set(llm_model_keys(local_models))
        configured_default_model = env.get("CODEX_LM_STUDIO_DEFAULT_MODEL", DEFAULT_MODEL)
        dynamic_alias_map = alias_map(local_models, configured_default_model)
        validate_model_args(codex_user_args, downloaded_llms)
        requested_model = model_arg_value(codex_user_args)
        alias_model = dynamic_alias_map.get(invocation_name)
        default_model = alias_model or env.get("CODEX_LM_STUDIO_DEFAULT_MODEL") or DEFAULT_MODEL
        lm_model = requested_model or env.get(
            "CODEX_LM_STUDIO_MODEL",
            default_model,
        )
        if not lm_model:
            raise ValueError("No downloaded LM Studio LLM models were found")
        if lm_model not in downloaded_llms:
            raise ValueError(
                f"codex-lm-studio only allows CODEX_LM_STUDIO_MODEL to be a downloaded "
                f"LM Studio LLM model; got: {lm_model}"
            )
        spec = model_spec(lm_model)
        parallel = positive_int(
            env.get("CODEX_LM_STUDIO_PARALLEL", str(DEFAULT_PARALLEL)),
            "CODEX_LM_STUDIO_PARALLEL",
        )
        context_length = max(
            positive_int(
                env.get("CODEX_LM_STUDIO_CONTEXT_LENGTH", str(MIN_CONTEXT_LENGTH)),
                "CODEX_LM_STUDIO_CONTEXT_LENGTH",
            ),
            MIN_CONTEXT_LENGTH,
        )
        max_memory_gib = positive_float(
            env.get("CODEX_LM_STUDIO_MAX_MEMORY_GIB", str(spec.max_memory_gib)),
            "CODEX_LM_STUDIO_MAX_MEMORY_GIB",
        )
        reserve_memory_gib = positive_float(
            env.get("CODEX_LM_STUDIO_RESERVE_MEMORY_GIB", str(spec.reserve_memory_gib)),
            "CODEX_LM_STUDIO_RESERVE_MEMORY_GIB",
        )
    except (RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    primary_home = Path(env.get("CODEX_PRIMARY_HOME", str(Path.home() / ".codex")))
    lm_home = Path(env.get("CODEX_LM_STUDIO_HOME", str(Path.home() / ".codex-lm-studio")))
    compact_limit = positive_int(
        env.get(
            "CODEX_LM_STUDIO_AUTO_COMPACT_TOKEN_LIMIT",
            str((context_length * 80 + 99) // 100),
        ),
        "CODEX_LM_STUDIO_AUTO_COMPACT_TOKEN_LIMIT",
    )

    prepare_codex_home(primary_home, lm_home)
    catalog = lm_home / "lmstudio-model-catalog.json"
    write_catalog(catalog, static_catalog, local_models)

    try:
        options = options_from_env(
            model=lm_model,
            context_length=context_length,
            max_memory_gib=max_memory_gib,
            reserve_memory_gib=reserve_memory_gib,
            parallel=parallel,
            strict=True,
            override_guardrails=override_guardrails or None,
        )
    except (ValidationError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    ensure_code = await ensure_model(options)
    if ensure_code != 0:
        return ensure_code

    config_file = lm_home / "config.toml"
    ensure_root_key(config_file, "cli_auth_credentials_store", '"file"')
    ensure_root_key(config_file, "oss_provider", '"lmstudio"')
    ensure_root_key(config_file, "model", toml_string(lm_model))
    ensure_root_key(config_file, "model_reasoning_effort", '"low"')
    ensure_root_key(config_file, "model_reasoning_summary", '"none"')
    ensure_root_key(config_file, "model_context_window", str(context_length))
    ensure_root_key(config_file, "model_auto_compact_token_limit", str(compact_limit))
    ensure_root_key(config_file, "model_catalog_json", toml_string(str(catalog)))

    codex_args = [
        "codex",
        "--oss",
        "--local-provider",
        "lmstudio",
        "--config",
        'model_reasoning_effort="low"',
        "--config",
        'model_reasoning_summary="none"',
        "--config",
        f"model_context_window={context_length}",
        "--config",
        f"model_auto_compact_token_limit={compact_limit}",
        "--config",
        f"model_catalog_json={toml_string(str(catalog))}",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    if not has_model_arg(codex_user_args):
        codex_args.extend(["--model", lm_model])
    codex_args.extend(codex_user_args)

    env["CODEX_HOME"] = str(lm_home)
    try:
        os.execvpe("codex", codex_args, env)
    except FileNotFoundError:
        print("codex executable not found on PATH", file=sys.stderr)
        return 127
    return 127


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(launch_codex(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    main()
