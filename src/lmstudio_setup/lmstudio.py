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


def _env_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "y", "on"}


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
    override_guardrails: bool = False
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


@dataclass(frozen=True)
class LoadedModelEstimate:
    identifier: str
    model_key: str
    display_name: str
    total_gib: float
    last_used_time: int
    status: str
    source: str


def options_from_env(
    *,
    model: str | None = None,
    context_length: int | None = None,
    max_memory_gib: float | None = None,
    reserve_memory_gib: float | None = None,
    parallel: int | None = None,
    estimate_only: bool = False,
    strict: bool | None = None,
    override_guardrails: bool | None = None,
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
        override_guardrails=_env_truthy(env.get("CODEX_LM_STUDIO_OVERRIDE_GUARDRAILS"))
        if override_guardrails is None
        else override_guardrails,
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


async def estimate_model_key(
    options: EnsureOptions,
    model_key: str,
    *,
    context_length: int,
    parallel: int,
) -> CommandResult:
    return await run_command(
        [
            str(options.lms_bin),
            "load",
            model_key,
            "--context-length",
            str(context_length),
            "--parallel",
            str(parallel),
            "--estimate-only",
            "--yes",
        ],
        env=with_default_path(),
    )


async def estimate_model(options: EnsureOptions) -> CommandResult:
    return await estimate_model_key(
        options,
        options.model,
        context_length=options.context_length,
        parallel=options.parallel,
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


def _loaded_model_identifier(model: dict[str, object]) -> str | None:
    identifier = model.get("identifier")
    return identifier if isinstance(identifier, str) and identifier else None


def _loaded_model_key(model: dict[str, object]) -> str | None:
    for key in ("modelKey", "identifier", "indexedModelIdentifier"):
        value = model.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _loaded_model_display_name(model: dict[str, object], fallback: str) -> str:
    value = model.get("displayName")
    return value if isinstance(value, str) and value else fallback


def _loaded_model_positive_int(
    model: dict[str, object],
    key: str,
    fallback: int,
) -> int:
    value = model.get(key)
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return fallback


def _loaded_model_last_used_time(model: dict[str, object]) -> int:
    return _loaded_model_positive_int(model, "lastUsedTime", 0)


def _loaded_model_status(model: dict[str, object]) -> str:
    value = model.get("status")
    return value if isinstance(value, str) and value else "unknown"


def _loaded_model_size_estimate_gib(model: dict[str, object]) -> float | None:
    value = model.get("sizeBytes")
    if not isinstance(value, int) or value <= 0:
        return None
    # LM Studio estimates for MLX models are usually above file size because context
    # memory is not represented by sizeBytes.
    return value / 1024 / 1024 / 1024 * 1.4


def lmstudio_guardrails_predict_failure(output: str) -> bool:
    return "will fail to load based on your resource guardrails" in output.lower()


def _confirm_guardrail_override(
    options: EnsureOptions,
    estimate: MemoryEstimate,
    reasons: list[str],
) -> bool:
    _print(estimate.output, stream=sys.stderr)
    _print(
        "WARNING: overriding LM Studio setup guardrails for this load attempt.",
        stream=sys.stderr,
    )
    for reason in reasons:
        _print(f"- {reason}", stream=sys.stderr)
    _print(
        "This may unload idle LM Studio models if needed for the budget. "
        "Non-idle models will not be interrupted.",
        stream=sys.stderr,
    )
    try:
        response = input(f"Type YES to continue loading {options.model}, or NO to stop: ")
    except EOFError:
        response = ""
    if response == "YES":
        return True
    _print("Stopped before unloading or loading models.", stream=sys.stderr)
    return False


async def estimate_loaded_models(
    options: EnsureOptions,
    loaded: list[dict[str, object]],
) -> list[LoadedModelEstimate]:
    estimates: list[LoadedModelEstimate] = []
    for model in loaded:
        identifier = _loaded_model_identifier(model)
        model_key = _loaded_model_key(model)
        if identifier is None or model_key is None or identifier == options.model:
            continue

        context_length = _loaded_model_positive_int(
            model,
            "contextLength",
            options.context_length,
        )
        parallel = _loaded_model_positive_int(model, "parallel", options.parallel)
        display_name = _loaded_model_display_name(model, identifier)
        status = _loaded_model_status(model)
        result = await estimate_model_key(
            options,
            model_key,
            context_length=context_length,
            parallel=parallel,
        )
        try:
            estimate = parse_memory_estimate(result.combined_output)
            estimates.append(
                LoadedModelEstimate(
                    identifier=identifier,
                    model_key=model_key,
                    display_name=display_name,
                    total_gib=estimate.total_gib,
                    last_used_time=_loaded_model_last_used_time(model),
                    status=status,
                    source="LM Studio estimate",
                )
            )
            continue
        except ValueError:
            fallback_gib = _loaded_model_size_estimate_gib(model)

        if fallback_gib is not None:
            estimates.append(
                LoadedModelEstimate(
                    identifier=identifier,
                    model_key=model_key,
                    display_name=display_name,
                    total_gib=fallback_gib,
                    last_used_time=_loaded_model_last_used_time(model),
                    status=status,
                    source="sizeBytes heuristic",
                )
            )
    return estimates


def select_unloads_for_budget(
    options: EnsureOptions,
    target_estimate: MemoryEstimate,
    loaded_estimates: list[LoadedModelEstimate],
) -> tuple[list[LoadedModelEstimate], float, float]:
    projected_gib = target_estimate.total_gib + sum(
        estimate.total_gib for estimate in loaded_estimates
    )
    if projected_gib <= options.max_memory_gib:
        return [], projected_gib, projected_gib

    selected: list[LoadedModelEstimate] = []
    remaining_gib = projected_gib
    for estimate in sorted(
        (estimate for estimate in loaded_estimates if estimate.status == "idle"),
        key=lambda item: (-item.total_gib, item.last_used_time),
    ):
        selected.append(estimate)
        remaining_gib -= estimate.total_gib
        if remaining_gib <= options.max_memory_gib:
            break
    return selected, projected_gib, remaining_gib


async def ensure_model(options: EnsureOptions) -> int:
    if not options.lms_bin.exists() or not os.access(options.lms_bin, os.X_OK):
        _print(f"lms CLI not found or not executable: {options.lms_bin}", stream=sys.stderr)
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

    loaded_estimates = await estimate_loaded_models(options, loaded)
    unloads, projected_gib, remaining_gib = select_unloads_for_budget(
        options,
        estimate,
        loaded_estimates,
    )
    non_idle_blockers = [
        loaded for loaded in loaded_estimates if loaded.status != "idle" and loaded not in unloads
    ]
    if remaining_gib > options.max_memory_gib and non_idle_blockers:
        _print(estimate.output, stream=sys.stderr)
        _print(
            f"Refusing to load {options.model}: projected total estimate "
            f"{projected_gib:.2f} GiB exceeds budget {options.max_memory_gib:g} GiB, "
            "and fitting it would require interrupting non-idle LM Studio model(s).",
            stream=sys.stderr,
        )
        for model in non_idle_blockers:
            _print(
                f"- keeping {model.identifier} ({model.status}, "
                f"{model.total_gib:.2f} GiB, {model.source})",
                stream=sys.stderr,
            )
        return EX_TEMPFAIL

    physical_gib = await physical_memory_gib()
    guardrail_reasons: list[str] = []
    if (
        physical_gib is not None
        and physical_gib < options.max_memory_gib + options.reserve_memory_gib
    ):
        guardrail_reasons.append(
            f"this machine reports {physical_gib:.2f} GiB RAM, below the requested "
            f"{options.max_memory_gib:g} GiB model budget plus "
            f"{options.reserve_memory_gib:g} GiB reserve"
        )
    if estimate.total_gib > options.max_memory_gib:
        guardrail_reasons.append(
            f"estimated total memory {estimate.total_gib:.2f} GiB exceeds "
            f"CODEX_LM_STUDIO_MAX_MEMORY_GIB={options.max_memory_gib:g}"
        )
    lmstudio_predicts_failure = lmstudio_guardrails_predict_failure(estimate.output)
    if lmstudio_predicts_failure and not unloads:
        guardrail_reasons.append(
            f"LM Studio resource guardrails predict {options.model} will fail to load"
        )

    if guardrail_reasons:
        if not options.override_guardrails:
            _print(estimate.output, stream=sys.stderr)
            for reason in guardrail_reasons:
                _print(f"Refusing to unload/reload models: {reason}.", stream=sys.stderr)
            _print(
                "Retry with --lmstudio-override-guardrails if you want to manually "
                "confirm this load attempt.",
                stream=sys.stderr,
            )
            return EX_TEMPFAIL
        if not _confirm_guardrail_override(options, estimate, guardrail_reasons):
            return EX_TEMPFAIL

    if lmstudio_predicts_failure and unloads:
        _print(
            "LM Studio's estimator predicted a resource-guardrail failure before "
            "budget-aware unloads; attempting after freeing room.",
            stream=sys.stderr,
        )

    if loaded_estimates and not unloads:
        _print(
            f"Keeping {len(loaded_estimates)} other loaded LM Studio model(s): projected "
            f"total estimate {projected_gib:.2f} GiB is within budget "
            f"{options.max_memory_gib:g} GiB.",
            stream=sys.stderr,
        )
    elif unloads:
        _print(
            f"Unloading {len(unloads)} LM Studio model(s) to fit {options.model}: projected "
            f"total estimate {projected_gib:.2f} GiB exceeds budget "
            f"{options.max_memory_gib:g} GiB.",
            stream=sys.stderr,
        )
        for model in unloads:
            _print(
                f"- {model.identifier} ({model.status}, {model.total_gib:.2f} GiB, {model.source})",
                stream=sys.stderr,
            )
            await unload_model(options, model.identifier)

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
