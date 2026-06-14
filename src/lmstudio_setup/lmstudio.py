from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lmstudio_setup.constants import (
    DEFAULT_BIND_ADDRESS,
    DEFAULT_MODEL,
    DEFAULT_PARALLEL,
    DEFAULT_PORT,
    MIN_CONTEXT_LENGTH,
    allowed_models_label,
    model_is_allowed,
    model_spec,
)
from lmstudio_setup.paths import with_default_path
from lmstudio_setup.process import CommandResult, run_command

EX_TEMPFAIL = 75


def _positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number, got: {value}") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive number, got: {value}")
    return parsed


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer, got: {value}") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


class EnsureOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str = DEFAULT_MODEL
    context_length: int = MIN_CONTEXT_LENGTH
    max_memory_gib: float = 24.0
    reserve_memory_gib: float = 12.0
    parallel: int = DEFAULT_PARALLEL
    port: int = DEFAULT_PORT
    bind_address: str = DEFAULT_BIND_ADDRESS
    estimate_only: bool = False
    strict: bool = False
    lms_bin: Path = Field(default_factory=lambda: Path.home() / ".lmstudio" / "bin" / "lms")

    @field_validator("model")
    @classmethod
    def _model_is_supported(cls, value: str) -> str:
        if not model_is_allowed(value):
            raise ValueError(
                f"ensure-lmstudio-codex-model only allows CODEX_LM_STUDIO_MODEL in: "
                f"{allowed_models_label()}; got: {value}"
            )
        return value

    @field_validator("context_length", "parallel", "port")
    @classmethod
    def _positive_int_field(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator("max_memory_gib", "reserve_memory_gib")
    @classmethod
    def _positive_float_field(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator("context_length")
    @classmethod
    def _enforce_min_context(cls, value: int) -> int:
        return max(value, MIN_CONTEXT_LENGTH)


@dataclass(frozen=True)
class MemoryEstimate:
    output: str
    total_gib: float
    gpu_gib: float | None


def options_from_env(
    *,
    model: str | None = None,
    context_length: int | None = None,
    max_memory_gib: float | None = None,
    reserve_memory_gib: float | None = None,
    parallel: int | None = None,
    estimate_only: bool = False,
    strict: bool | None = None,
) -> EnsureOptions:
    env = os.environ
    selected_model = model or env.get("CODEX_LM_STUDIO_MODEL", DEFAULT_MODEL)
    spec = model_spec(selected_model)
    return EnsureOptions(
        model=selected_model,
        context_length=context_length
        if context_length is not None
        else _positive_int(
            env.get("CODEX_LM_STUDIO_CONTEXT_LENGTH", str(MIN_CONTEXT_LENGTH)),
            "CODEX_LM_STUDIO_CONTEXT_LENGTH",
        ),
        max_memory_gib=max_memory_gib
        if max_memory_gib is not None
        else _positive_float(
            env.get("CODEX_LM_STUDIO_MAX_MEMORY_GIB", str(spec.max_memory_gib)),
            "CODEX_LM_STUDIO_MAX_MEMORY_GIB",
        ),
        reserve_memory_gib=reserve_memory_gib
        if reserve_memory_gib is not None
        else _positive_float(
            env.get("CODEX_LM_STUDIO_RESERVE_MEMORY_GIB", str(spec.reserve_memory_gib)),
            "CODEX_LM_STUDIO_RESERVE_MEMORY_GIB",
        ),
        parallel=parallel
        if parallel is not None
        else _positive_int(
            env.get("CODEX_LM_STUDIO_PARALLEL", str(DEFAULT_PARALLEL)),
            "CODEX_LM_STUDIO_PARALLEL",
        ),
        port=_positive_int(env.get("LM_STUDIO_PORT", str(DEFAULT_PORT)), "LM_STUDIO_PORT"),
        bind_address=env.get("LM_STUDIO_BIND_ADDRESS", DEFAULT_BIND_ADDRESS),
        estimate_only=estimate_only,
        strict=env.get("CODEX_LM_STUDIO_STRICT", "0") == "1" if strict is None else strict,
        lms_bin=Path(env.get("LMS_BIN", str(Path.home() / ".lmstudio" / "bin" / "lms"))),
    )


def unit_to_gib(value: float, unit: str) -> float:
    match unit:
        case "GiB" | "Gib" | "gib":
            return value
        case "GB" | "Gb" | "gb":
            return value * 1000 * 1000 * 1000 / 1024 / 1024 / 1024
        case "MiB" | "Mib" | "mib":
            return value / 1024
        case "MB" | "Mb" | "mb":
            return value * 1000 * 1000 / 1024 / 1024 / 1024
        case _:
            raise ValueError(f"unknown memory unit: {unit}")


def parse_memory_estimate(output: str) -> MemoryEstimate:
    total_gib: float | None = None
    gpu_gib: float | None = None
    for label, raw_value, unit in re.findall(
        r"Estimated (Total|GPU) Memory:\s*([0-9.]+)\s*([A-Za-z]+)", output
    ):
        value = unit_to_gib(float(raw_value), unit)
        if label == "Total":
            total_gib = value
        elif label == "GPU":
            gpu_gib = value
    if total_gib is None:
        raise ValueError("Could not parse LM Studio memory estimate")
    return MemoryEstimate(output=output, total_gib=total_gib, gpu_gib=gpu_gib)


async def physical_memory_gib() -> float | None:
    result = await run_command(["sysctl", "-n", "hw.memsize"], env=with_default_path())
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw.isdigit():
        return None
    return int(raw) / 1024 / 1024 / 1024


async def ensure_server(options: EnsureOptions) -> int:
    env = with_default_path()
    status = await run_command([str(options.lms_bin), "server", "status"], env=env)
    if status.returncode == 0:
        return 0
    start = await run_command(
        [
            str(options.lms_bin),
            "server",
            "start",
            "--port",
            str(options.port),
            "--bind",
            options.bind_address,
        ],
        env=env,
        capture=False,
    )
    return start.returncode


async def estimate_model(options: EnsureOptions) -> CommandResult:
    return await run_command(
        [
            str(options.lms_bin),
            "load",
            options.model,
            "--context-length",
            str(options.context_length),
            "--parallel",
            str(options.parallel),
            "--estimate-only",
            "--yes",
        ],
        env=with_default_path(),
    )


async def loaded_models(options: EnsureOptions) -> list[dict[str, object]]:
    result = await run_command([str(options.lms_bin), "ps", "--json"], env=with_default_path())
    if result.returncode != 0:
        return []
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


async def unload_model(options: EnsureOptions, identifier: str) -> None:
    await run_command(
        [str(options.lms_bin), "unload", identifier],
        env=with_default_path(),
        capture=True,
    )


def _print(text: str, *, stream: object = sys.stdout) -> None:
    print(text, file=stream, end="" if text.endswith("\n") else "\n")


async def ensure_model(options: EnsureOptions) -> int:
    if not options.lms_bin.exists() or not os.access(options.lms_bin, os.X_OK):
        _print(f"lms CLI not found or not executable: {options.lms_bin}", stream=sys.stderr)
        return 1

    physical_gib = await physical_memory_gib()
    if (
        physical_gib is not None
        and physical_gib < options.max_memory_gib + options.reserve_memory_gib
    ):
        _print(
            f"This machine reports {physical_gib:.2f} GiB RAM, which is below the requested "
            f"{options.max_memory_gib:g} GiB model budget plus "
            f"{options.reserve_memory_gib:g} GiB reserve.",
            stream=sys.stderr,
        )
        return 1

    server_code = await ensure_server(options)
    if server_code != 0:
        return server_code

    estimate_result = await estimate_model(options)
    estimate_output = estimate_result.combined_output
    if estimate_result.returncode != 0:
        _print(estimate_output, stream=sys.stderr)
        return estimate_result.returncode

    try:
        estimate = parse_memory_estimate(estimate_output)
    except ValueError as exc:
        _print(estimate_output, stream=sys.stderr)
        _print(f"{exc} for {options.model}", stream=sys.stderr)
        return 1

    if estimate.total_gib > options.max_memory_gib:
        _print(estimate.output, stream=sys.stderr)
        _print(
            f"Refusing to load {options.model}: estimated total memory "
            f"{estimate.total_gib:.2f} GiB exceeds "
            f"CODEX_LM_STUDIO_MAX_MEMORY_GIB={options.max_memory_gib:g}.",
            stream=sys.stderr,
        )
        return EX_TEMPFAIL

    if options.estimate_only:
        _print(estimate.output)
        _print(
            f"Parsed total estimate: {estimate.total_gib:.2f} GiB; parsed GPU estimate: "
            f"{estimate.gpu_gib:.2f} GiB; budget: {options.max_memory_gib:g} GiB; "
            f"reserve: {options.reserve_memory_gib:g} GiB."
            if estimate.gpu_gib is not None
            else f"Parsed total estimate: {estimate.total_gib:.2f} GiB; parsed GPU estimate: "
            f"unknown GiB; budget: {options.max_memory_gib:g} GiB; "
            f"reserve: {options.reserve_memory_gib:g} GiB."
        )
        return 0

    loaded = await loaded_models(options)
    for model in loaded:
        if model.get("identifier") != options.model:
            continue
        context_length = int(model.get("contextLength") or 0)
        parallel = int(model.get("parallel") or 1)
        if context_length >= options.context_length and parallel >= options.parallel:
            _print(
                f"LM Studio already has {options.model} loaded: total estimate "
                f"{estimate.total_gib:.2f} GiB, GPU estimate "
                f"{estimate.gpu_gib:.2f} GiB, context {options.context_length}, "
                f"parallel {options.parallel}."
                if estimate.gpu_gib is not None
                else f"LM Studio already has {options.model} loaded: total estimate "
                f"{estimate.total_gib:.2f} GiB, GPU estimate unknown, "
                f"context {options.context_length}, parallel {options.parallel}.",
                stream=sys.stderr,
            )
            return 0

    if "will fail to load based on your resource guardrails" in estimate.output.lower():
        _print(estimate.output, stream=sys.stderr)
        _print(
            f"Refusing to unload/reload models: LM Studio resource guardrails predict "
            f"{options.model} will fail to load.",
            stream=sys.stderr,
        )
        _print(
            "Raise LM Studio's model-loading guardrails or reduce "
            "CODEX_LM_STUDIO_CONTEXT_LENGTH before trying this alias.",
            stream=sys.stderr,
        )
        return EX_TEMPFAIL

    for model in loaded:
        identifier = model.get("identifier")
        if isinstance(identifier, str) and identifier != options.model:
            await unload_model(options, identifier)

    await unload_model(options, options.model)
    load = await run_command(
        [
            str(options.lms_bin),
            "load",
            options.model,
            "--context-length",
            str(options.context_length),
            "--parallel",
            str(options.parallel),
            "--identifier",
            options.model,
            "--yes",
        ],
        env=with_default_path(),
        capture=False,
    )
    if load.returncode != 0:
        _print(
            f"LM Studio has not made {options.model} loadable yet; waiting for Desktop "
            "download/indexing to finish.",
            stream=sys.stderr,
        )
        return EX_TEMPFAIL if options.strict else 0

    _print(
        f"Loaded {options.model} for Codex: total estimate {estimate.total_gib:.2f} GiB, "
        f"GPU estimate {estimate.gpu_gib:.2f} GiB, context {options.context_length}, "
        f"parallel {options.parallel}."
        if estimate.gpu_gib is not None
        else f"Loaded {options.model} for Codex: total estimate {estimate.total_gib:.2f} GiB, "
        f"GPU estimate unknown, context {options.context_length}, parallel {options.parallel}.",
        stream=sys.stderr,
    )
    return 0
