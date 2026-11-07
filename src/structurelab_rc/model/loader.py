"""Carga de proyectos desde JSON."""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import EtabsFootingTemplate, EtabsTemplate


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


def load_footing_template(path: Path) -> EtabsFootingTemplate:
    return _load(path, EtabsFootingTemplate, "la plantilla de zapatas")
