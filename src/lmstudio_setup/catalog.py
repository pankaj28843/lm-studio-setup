from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from lmstudio_setup.constants import allowed_model_ids


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    slug: str
    base_instructions: str
    model_messages: Any | None = None


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[CatalogModel]


def load_catalog(path: Path) -> ModelCatalog:
    try:
        return ModelCatalog.model_validate_json(path.read_text())
    except ValidationError as exc:
        raise ValueError(f"failed to parse model catalog {path}: {exc}") from exc


def validate_catalog(path: Path) -> ModelCatalog:
    catalog = load_catalog(path)
    expected = sorted(allowed_model_ids())
    actual = sorted(model.slug for model in catalog.models)
    if actual != expected:
        raise ValueError(f"catalog slugs mismatch: expected {expected}, got {actual}")
    return catalog
