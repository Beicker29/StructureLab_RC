"""Carga de proyectos desde JSON."""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.model.design import CombinedDesignProject, FootingDesignProject
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import EtabsCombinedDesignTemplate, EtabsFootingDesignTemplate, EtabsFootingTemplate, EtabsTemplate


class ProjectLoadError(Exception):
    def __init__(self, errors: tuple[StructuredError, ...]) -> None:
        super().__init__("; ".join(error.message for error in errors))
        self.errors = errors


def _load[T: BaseModel](path: Path, model: type[T], what: str) -> T:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectLoadError((invalid_input(f"No se pudo leer {what}: {error}", path=str(path)),)) from error
    return validate_input(raw, model)


def validate_input[T: BaseModel](raw: object, model: type[T]) -> T:
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        errors = tuple(
            invalid_input(detail["msg"], location=".".join(str(part) for part in detail["loc"])) for detail in error.errors()
        )
        raise ProjectLoadError(errors) from error


def load_project(path: Path) -> Project:
    return _load(path, Project, "el proyecto")


def load_template(path: Path) -> EtabsTemplate:
    return _load(path, EtabsTemplate, "la plantilla")


def load_footing_template(path: Path) -> EtabsFootingTemplate | EtabsFootingDesignTemplate | EtabsCombinedDesignTemplate:
    """Plantilla de verificación (tipos asignados a mano), de diseño por tipologías (trae el bloque design, D-069) o de
    diseño de una zapata combinada (trae combined_design, D-112)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectLoadError((invalid_input(f"No se pudo leer la plantilla de zapatas: {error}", path=str(path)),)) from error
    if isinstance(raw, dict) and "design" in raw:
        return validate_input(raw, EtabsFootingDesignTemplate)
    if isinstance(raw, dict) and "combined_design" in raw:
        return validate_input(raw, EtabsCombinedDesignTemplate)
    return validate_input(raw, EtabsFootingTemplate)


def load_design_project(path: Path) -> FootingDesignProject:
    return _load(path, FootingDesignProject, "el proyecto de diseño")


def load_combined_design(path: Path) -> CombinedDesignProject:
    return _load(path, CombinedDesignProject, "el proyecto de diseño de la zapata combinada")
