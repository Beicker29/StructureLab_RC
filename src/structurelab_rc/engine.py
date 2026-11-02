"""Orquestación de los casos de uso."""

from pathlib import Path

from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.model.loader import ProjectLoadError, load_project
from structurelab_rc.setup import load_engine


def validate_file(path: Path) -> Check:
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return check_from_errors(CHECK_NAME, error.errors)
    return validate_project(project, load_engine().bars)
