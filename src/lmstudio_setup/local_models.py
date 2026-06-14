from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lmstudio_setup.paths import with_default_path
from lmstudio_setup.process import run_command

ALIAS_PREFIX = "codex-lm-studio"


@dataclass(frozen=True)
class LocalModel:
    model_type: str
    model_key: str
    display_name: str
    size_bytes: int | None = None
    max_context_length: int | None = None
    vision: bool | None = None
    trained_for_tool_use: bool | None = None

    @property
    def is_llm(self) -> bool:
        return self.model_type == "llm"

    @property
    def is_embedding(self) -> bool:
        return self.model_type == "embedding"


@dataclass(frozen=True)
class ModelAlias:
    alias: str
    model_key: str


def default_lms_bin() -> Path:
    return Path(os.environ.get("LMS_BIN", str(Path.home() / ".lmstudio" / "bin" / "lms")))


def _string(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) and value else default


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def parse_local_models(payload: str) -> list[LocalModel]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("expected lms ls --json to return a list")

    models: list[LocalModel] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        model_key = _string(item.get("modelKey"))
        model_type = _string(item.get("type"))
        if not model_key or not model_type:
            continue
        models.append(
            LocalModel(
                model_type=model_type,
                model_key=model_key,
                display_name=_string(item.get("displayName"), model_key),
                size_bytes=_optional_int(item.get("sizeBytes")),
                max_context_length=_optional_int(item.get("maxContextLength")),
                vision=_optional_bool(item.get("vision")),
                trained_for_tool_use=_optional_bool(item.get("trainedForToolUse")),
            )
        )
    return models


async def list_local_models(lms_bin: Path | None = None) -> list[LocalModel]:
    binary = lms_bin or default_lms_bin()
    result = await run_command([str(binary), "ls", "--json"], env=with_default_path())
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    return parse_local_models(result.stdout)


def llm_models(models: list[LocalModel]) -> list[LocalModel]:
    return [model for model in models if model.is_llm]


def embedding_models(models: list[LocalModel]) -> list[LocalModel]:
    return [model for model in models if model.is_embedding]


def alias_stem(model_key: str) -> str:
    leaf = model_key.rsplit("/", 1)[-1]
    normalized = leaf.replace("@", "-").lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or "model"


def alias_for_stem(stem: str) -> str:
    return f"{ALIAS_PREFIX}-{stem}"


def model_aliases(models: list[LocalModel], default_model: str) -> tuple[ModelAlias, ...]:
    candidates = [(model.model_key, alias_stem(model.model_key)) for model in llm_models(models)]
    stem_counts: dict[str, int] = {}
    for _, stem in candidates:
        stem_counts[stem] = stem_counts.get(stem, 0) + 1

    aliases = [ModelAlias(ALIAS_PREFIX, default_model)]
    used_aliases = {ALIAS_PREFIX}
    for model_key, stem in sorted(candidates, key=lambda item: item[1]):
        if stem_counts[stem] > 1:
            stem = re.sub(r"[^a-z0-9._-]+", "-", model_key.replace("@", "-").lower()).strip("-")
        alias = alias_for_stem(stem)
        suffix = 2
        while alias in used_aliases:
            alias = alias_for_stem(f"{stem}-{suffix}")
            suffix += 1
        used_aliases.add(alias)
        aliases.append(ModelAlias(alias, model_key))
    return tuple(aliases)


def alias_map(models: list[LocalModel], default_model: str) -> dict[str, str]:
    return {item.alias: item.model_key for item in model_aliases(models, default_model)}


def llm_model_keys(models: list[LocalModel]) -> tuple[str, ...]:
    return tuple(model.model_key for model in llm_models(models))


def embedding_model_keys(models: list[LocalModel]) -> tuple[str, ...]:
    return tuple(model.model_key for model in embedding_models(models))
