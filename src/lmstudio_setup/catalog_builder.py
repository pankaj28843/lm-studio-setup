from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from lmstudio_setup.catalog import ModelCatalog
from lmstudio_setup.constants import MIN_CONTEXT_LENGTH
from lmstudio_setup.local_models import LocalModel, llm_models

BASE_INSTRUCTIONS = (
    "You are Codex, a coding agent running against a local LM Studio model. "
    "Follow the active system and developer instructions, use tools carefully, "
    "prefer concise engineering answers, and ask for clarification only when necessary."
)


def _reasoning_level(model: LocalModel) -> str:
    key = model.model_key.lower()
    name = model.display_name.lower()
    if any(marker in key or marker in name for marker in ("thinking", "reasoning", "r1")):
        return "high" if "30b" in key or "30b" in name else "medium"
    if any(marker in key or marker in name for marker in ("27b", "30b", "35b", "a3b")):
        return "medium"
    return "low"


def _description(model: LocalModel) -> str:
    details = [
        f"Local Codex model discovered from LM Studio: {model.display_name}.",
        f"Model key: {model.model_key}.",
    ]
    if model.max_context_length:
        details.append(f"LM Studio reports max context {model.max_context_length}.")
    if model.vision:
        details.append("LM Studio marks this as a vision-capable model.")
    if model.trained_for_tool_use:
        details.append("LM Studio marks this model as trained for tool use.")
    return " ".join(details)


def _template(static_models: list[dict[str, Any]]) -> dict[str, Any]:
    if not static_models:
        raise ValueError("static catalog must contain at least one model template")
    return static_models[0]


def _generic_entry(
    model: LocalModel,
    template: dict[str, Any],
    *,
    priority: int,
) -> dict[str, Any]:
    entry = copy.deepcopy(template)
    entry.update(
        {
            "slug": model.model_key,
            "display_name": f"{model.display_name} (LM Studio Codex)",
            "description": _description(model),
            "base_instructions": BASE_INSTRUCTIONS,
            "model_messages": None,
            "default_reasoning_level": _reasoning_level(model),
            "priority": priority,
            "context_window": MIN_CONTEXT_LENGTH,
            "max_context_window": MIN_CONTEXT_LENGTH,
            "input_modalities": ["text", "image"] if model.vision else ["text"],
        }
    )
    return entry


def build_catalog(static_catalog_path: Path, local_models: list[LocalModel]) -> dict[str, Any]:
    data = json.loads(static_catalog_path.read_text())
    static_models = data.get("models")
    if not isinstance(static_models, list):
        raise ValueError(f"static catalog has no model list: {static_catalog_path}")

    by_slug = {
        item["slug"]: item
        for item in static_models
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    }
    template = _template(static_models)
    next_priority = max(
        (item.get("priority", 0) for item in static_models if isinstance(item, dict)),
        default=0,
    )

    models = list(static_models)
    for model in sorted(llm_models(local_models), key=lambda item: item.model_key):
        if model.model_key in by_slug:
            continue
        next_priority += 1
        entry = _generic_entry(model, template, priority=next_priority)
        models.append(entry)
        by_slug[model.model_key] = entry

    generated = {**data, "models": models}
    ModelCatalog.model_validate(generated)
    return generated


def write_catalog(path: Path, static_catalog_path: Path, local_models: list[LocalModel]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    generated = build_catalog(static_catalog_path, local_models)
    path.write_text(json.dumps(generated, indent=2) + "\n")
    path.chmod(0o600)
