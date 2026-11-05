"""Orquestación de los casos de uso."""

from pathlib import Path

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import flexure_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.model.loader import ProjectLoadError, load_project
from structurelab_rc.setup import load_engine


def validate_file(path: Path) -> Check:
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return check_from_errors(CHECK_NAME, error.errors)
    return validate_project(project, load_engine().bars)


def verify_file(path: Path) -> tuple[Check, ...]:
    """Validación seguida de las verificaciones por estación; si la entrada es inválida, solo la validación."""
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return (check_from_errors(CHECK_NAME, error.errors),)
    bars = load_engine().bars
    validation = validate_project(project, bars)
    if validation.status is Status.FAIL:
        return (validation,)
    profile = PROFILES[project.profile]
    checks = [validation]
    for member in project.members:
        for station in member.stations:
            checks.extend(flexure_checks(profile, project.materials, member, station, bars))
    return tuple(checks)
