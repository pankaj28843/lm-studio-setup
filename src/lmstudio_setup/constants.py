from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL = "qwen3.5-9b-mlx@8bit"
LIGHT_MODEL = "qwen3.5-9b-mlx@4bit"
EXPERIMENTAL_27B_MODEL = "qwen3.6-27b-mlx"
EXPERIMENTAL_35B_MODEL = "qwen/qwen3.6-35b-a3b"

MIN_CONTEXT_LENGTH = 131_072
DEFAULT_MAX_MEMORY_GIB = 24.0
DEFAULT_RESERVE_MEMORY_GIB = 12.0
DEFAULT_PARALLEL = 4
DEFAULT_PORT = 1234
DEFAULT_BIND_ADDRESS = "127.0.0.1"


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    max_memory_gib: float = DEFAULT_MAX_MEMORY_GIB
    reserve_memory_gib: float = DEFAULT_RESERVE_MEMORY_GIB


SUPPORTED_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(DEFAULT_MODEL),
    ModelSpec(LIGHT_MODEL),
    ModelSpec(EXPERIMENTAL_27B_MODEL),
    ModelSpec(EXPERIMENTAL_35B_MODEL, max_memory_gib=32.0, reserve_memory_gib=4.0),
)

ALIASES: tuple[str, ...] = (
    "codex-lm-studio",
    "codex-lm-studio-qwen3.5-9b-mlx-4bit",
    "codex-lm-studio-qwen3.6-27b-mlx-4bit",
    "codex-lm-studio-qwen3.6-35b-a3b",
)

LEGACY_ALIASES: tuple[str, ...] = (
    "modelcodex",
    "codex-lm-studio-8bit",
    "modelcodex-8bit",
    "codex-lm-studio-4bit",
    "modelcodex-4bit",
    "codex-lm-studio-qwen35-9b-8bit",
    "modelcodex-qwen35-9b-8bit",
    "codex-lm-studio-qwen3.5-9b-mlx-8bit",
    "modelcodex-qwen3.5-9b-mlx-8bit",
    "codex-lm-studio-qwen35-9b-4bit",
    "modelcodex-qwen35-9b-4bit",
    "modelcodex-qwen3.5-9b-mlx-4bit",
    "codex-lm-studio-parallel",
    "modelcodex-parallel",
    "codex-lm-studio-8bit-parallel",
    "modelcodex-8bit-parallel",
    "codex-lm-studio-4bit-parallel",
    "modelcodex-4bit-parallel",
    "codex-lm-studio-qwen35-9b-8bit-parallel",
    "modelcodex-qwen35-9b-8bit-parallel",
    "codex-lm-studio-qwen3.5-9b-mlx-8bit-parallel",
    "modelcodex-qwen3.5-9b-mlx-8bit-parallel",
    "codex-lm-studio-qwen35-9b-4bit-parallel",
    "modelcodex-qwen35-9b-4bit-parallel",
    "codex-lm-studio-qwen3.5-9b-mlx-4bit-parallel",
    "modelcodex-qwen3.5-9b-mlx-4bit-parallel",
)

PLAYGROUND_MLX_MODELS: tuple[str, ...] = (
    "google/gemma-4-e4b",
    "microsoft/phi-4-mini-reasoning",
    "qwen/qwen3-4b-thinking-2507",
    "qwen/qwen3-4b-2507",
    "allenai/olmo-3-7b",
    "microsoft/phi-4-reasoning",
    "mistralai/magistral-small-2509",
)


def allowed_model_ids() -> tuple[str, ...]:
    return tuple(spec.model_id for spec in SUPPORTED_MODELS)


def allowed_models_label() -> str:
    return ", ".join(allowed_model_ids())


def model_is_allowed(model: str) -> bool:
    return model in allowed_model_ids()


def model_spec(model: str) -> ModelSpec:
    for spec in SUPPORTED_MODELS:
        if spec.model_id == model:
            return spec
    raise ValueError(f"unsupported model: {model}")


def default_model_for_invocation(invocation_name: str) -> str:
    name = invocation_name.lower()
    if "35b" in name and ("a3b" in name or "35b-a3b" in name):
        return EXPERIMENTAL_35B_MODEL
    if "27b" in name:
        return EXPERIMENTAL_27B_MODEL
    if "4bit" in name:
        return LIGHT_MODEL
    if "8bit" in name:
        return DEFAULT_MODEL
    return DEFAULT_MODEL
