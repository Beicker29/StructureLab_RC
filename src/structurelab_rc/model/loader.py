"""Carga de proyectos desde JSON."""

import json
from pathlib import Path

from pydantic import ValidationError

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.model.project import Project


class ProjectLoadError(Exception):
    def __init__(self, errors: tuple[StructuredError, ...]) -> None:
        super().__init__("; ".join(error.message for error in errors))
        self.errors = errors


def load_project(path: Path) -> Project:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectLoadError((invalid_input(f"No se pudo leer el proyecto: {error}", path=str(path)),)) from error
    try:
        return Project.model_validate(raw)
    except ValidationError as error:
        errors = tuple(
            invalid_input(detail["msg"], location=".".join(str(part) for part in detail["loc"])) for detail in error.errors()
        )
        raise ProjectLoadError(errors) from error
