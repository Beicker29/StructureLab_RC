"""Orquestación de los casos de uso."""

from pathlib import Path
from typing import Any

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.errors import invalid_input
from structurelab_rc.io.etabs.importer import SHEET, EtabsImportError, ImportSummary, build_project
from structurelab_rc.io.etabs.xlsx import XlsxError, read_table
from structurelab_rc.model.loader import ProjectLoadError, load_project, load_template, validate_input
from structurelab_rc.model.project import Project
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
            checks.extend(station_checks(profile, project.materials, member, station, bars))
    return tuple(checks)


def import_etabs(workbook: Path, template_path: Path) -> tuple[dict[str, Any] | None, ImportSummary | None, Check]:
    """Proyecto JSON a partir del Excel de ETABS y la plantilla, con la validación del resultado (D-042)."""
    try:
        template = load_template(template_path)
        table = read_table(workbook, SHEET)
        project, summary = build_project(template, table)
        validation = validate_project(validate_input(project, Project), load_engine().bars)
    except (ProjectLoadError, EtabsImportError) as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    except XlsxError as error:
        return None, None, check_from_errors(CHECK_NAME, [invalid_input(str(error), path=str(workbook))])
    return project, summary, validation
