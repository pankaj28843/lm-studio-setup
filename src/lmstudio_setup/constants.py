from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL = "qwen3.5-9b-mlx@8bit"
LIGHT_MODEL = "qwen3.5-9b-mlx@4bit"
EXPERIMENTAL_27B_MODEL = "qwen3.6-27b-mlx"
EXPERIMENTAL_35B_MODEL = "qwen/qwen3.6-35b-a3b"
GEMMA_4_E4B_MODEL = "google/gemma-4-e4b"
PHI_4_MINI_REASONING_MODEL = "microsoft/phi-4-mini-reasoning"
QWEN3_4B_THINKING_MODEL = "qwen/qwen3-4b-thinking-2507"
QWEN3_4B_MODEL = "qwen/qwen3-4b-2507"
OLMO_3_7B_MODEL = "allenai/olmo-3-7b"
PHI_4_REASONING_MODEL = "microsoft/phi-4-reasoning"
MAGISTRAL_SMALL_MODEL = "mistralai/magistral-small-2509"
DEEPSEEK_R1_QWEN3_8B_MODEL = "deepseek/deepseek-r1-0528-qwen3-8b"
QWEN3_VL_8B_MODEL = "qwen/qwen3-vl-8b"
GLM_46V_FLASH_MODEL = "zai-org/glm-4.6v-flash"
QWEN3_30B_A3B_THINKING_MODEL = "qwen/qwen3-30b-a3b-thinking-2507"
NOMIC_EMBED_TEXT_MODEL = "text-embedding-nomic-embed-text-v1.5"
GRANITE_EMBEDDING_30M_ENGLISH_MODEL = "text-embedding-granite-embedding-30m-english"
GRANITE_EMBEDDING_278M_MULTILINGUAL_MODEL = "text-embedding-granite-embedding-278m-multilingual"
BGE_SMALL_EN_MODEL = "text-embedding-bge-small-en-v1.5"

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


@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_id: str
    download_source: str


SUPPORTED_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(DEFAULT_MODEL),
    ModelSpec(LIGHT_MODEL),
    ModelSpec(EXPERIMENTAL_27B_MODEL),
    ModelSpec(EXPERIMENTAL_35B_MODEL, max_memory_gib=32.0, reserve_memory_gib=4.0),
    ModelSpec(GEMMA_4_E4B_MODEL),
    ModelSpec(PHI_4_MINI_REASONING_MODEL),
    ModelSpec(QWEN3_4B_THINKING_MODEL),
    ModelSpec(QWEN3_4B_MODEL),
    ModelSpec(OLMO_3_7B_MODEL),
    ModelSpec(PHI_4_REASONING_MODEL),
    ModelSpec(MAGISTRAL_SMALL_MODEL),
    ModelSpec(DEEPSEEK_R1_QWEN3_8B_MODEL),
    ModelSpec(QWEN3_VL_8B_MODEL),
    ModelSpec(GLM_46V_FLASH_MODEL),
    ModelSpec(QWEN3_30B_A3B_THINKING_MODEL),
)

MODEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("codex-lm-studio", DEFAULT_MODEL),
    ("codex-lm-studio-qwen3.5-9b-mlx-8bit", DEFAULT_MODEL),
    ("codex-lm-studio-qwen3.5-9b-mlx-4bit", LIGHT_MODEL),
    ("codex-lm-studio-qwen3.6-27b-mlx-4bit", EXPERIMENTAL_27B_MODEL),
    ("codex-lm-studio-qwen3.6-35b-a3b", EXPERIMENTAL_35B_MODEL),
    ("codex-lm-studio-gemma-4-e4b", GEMMA_4_E4B_MODEL),
    ("codex-lm-studio-phi-4-mini-reasoning", PHI_4_MINI_REASONING_MODEL),
    ("codex-lm-studio-qwen3-4b-thinking-2507", QWEN3_4B_THINKING_MODEL),
    ("codex-lm-studio-qwen3-4b-2507", QWEN3_4B_MODEL),
    ("codex-lm-studio-olmo-3-7b", OLMO_3_7B_MODEL),
    ("codex-lm-studio-phi-4-reasoning", PHI_4_REASONING_MODEL),
    ("codex-lm-studio-magistral-small-2509", MAGISTRAL_SMALL_MODEL),
    ("codex-lm-studio-deepseek-r1-0528-qwen3-8b", DEEPSEEK_R1_QWEN3_8B_MODEL),
    ("codex-lm-studio-qwen3-vl-8b", QWEN3_VL_8B_MODEL),
    ("codex-lm-studio-glm-4.6v-flash", GLM_46V_FLASH_MODEL),
    (
        "codex-lm-studio-qwen3-30b-a3b-thinking-2507",
        QWEN3_30B_A3B_THINKING_MODEL,
    ),
)

ALIASES: tuple[str, ...] = tuple(alias for alias, _ in MODEL_ALIASES)
ALIAS_TO_MODEL: dict[str, str] = dict(MODEL_ALIASES)

LEGACY_ALIASES: tuple[str, ...] = (
    "modelcodex",
    "codex-lm-studio-8bit",
    "modelcodex-8bit",
    "codex-lm-studio-4bit",
    "modelcodex-4bit",
    "codex-lm-studio-qwen35-9b-8bit",
    "modelcodex-qwen35-9b-8bit",
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
    GEMMA_4_E4B_MODEL,
    PHI_4_MINI_REASONING_MODEL,
    QWEN3_4B_THINKING_MODEL,
    QWEN3_4B_MODEL,
    OLMO_3_7B_MODEL,
    PHI_4_REASONING_MODEL,
    MAGISTRAL_SMALL_MODEL,
    DEEPSEEK_R1_QWEN3_8B_MODEL,
    QWEN3_VL_8B_MODEL,
    GLM_46V_FLASH_MODEL,
    QWEN3_30B_A3B_THINKING_MODEL,
)

EMBEDDING_MODELS: tuple[EmbeddingModelSpec, ...] = (
    EmbeddingModelSpec(NOMIC_EMBED_TEXT_MODEL, NOMIC_EMBED_TEXT_MODEL),
    EmbeddingModelSpec(
        GRANITE_EMBEDDING_30M_ENGLISH_MODEL,
        "https://huggingface.co/lmstudio-community/granite-embedding-30m-english-GGUF",
    ),
    EmbeddingModelSpec(
        GRANITE_EMBEDDING_278M_MULTILINGUAL_MODEL,
        "https://huggingface.co/lmstudio-community/granite-embedding-278m-multilingual-GGUF",
    ),
    EmbeddingModelSpec(
        BGE_SMALL_EN_MODEL,
        "https://huggingface.co/ChristianAzinn/bge-small-en-v1.5-gguf",
    ),
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
    if model := ALIAS_TO_MODEL.get(name):
        return model
    if "35b" in name and ("a3b" in name or "35b-a3b" in name):
        return EXPERIMENTAL_35B_MODEL
    if "27b" in name:
        return EXPERIMENTAL_27B_MODEL
    if "4bit" in name:
        return LIGHT_MODEL
    if "8bit" in name:
        return DEFAULT_MODEL
    return DEFAULT_MODEL
