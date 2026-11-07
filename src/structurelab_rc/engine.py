"""Orquestación de los casos de uso."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structurelab_rc import __version__
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.checks import footing_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.errors import invalid_input
from structurelab_rc.io.etabs import footings as etabs_footings
from structurelab_rc.io.etabs.footings import FootingImportSummary, build_footing_project
from structurelab_rc.io.etabs.importer import SHEET, EtabsImportError, ImportSummary, build_project
from structurelab_rc.io.etabs.xlsx import XlsxError, read_table
from structurelab_rc.model.loader import ProjectLoadError, load_footing_template, load_project, load_template, validate_input
from structurelab_rc.model.project import Project
from structurelab_rc.reporting.memoir import render_memoir
from structurelab_rc.reporting.pdf import write_pdf
from structurelab_rc.reporting.results import build_results
from structurelab_rc.setup import load_engine


def validate_file(path: Path) -> Check:
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return check_from_errors(CHECK_NAME, error.errors)
    return validate_project(project, load_engine().bars)


def run_project(path: Path) -> tuple[Project | None, tuple[Check, ...]]:
    """Proyecto cargado y sus verificaciones: primero la validación; si la entrada es inválida, solo ella."""
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return None, (check_from_errors(CHECK_NAME, error.errors),)
    bars = load_engine().bars
    validation = validate_project(project, bars)
    if validation.status is Status.FAIL:
        return project, (validation,)
    profile = PROFILES[project.profile]
    checks = [validation]
    for member in project.members:
        for station in member.stations:
            checks.extend(station_checks(profile, project.materials, member, station, bars))
    for footing in project.footings:
        checks.extend(footing_checks(footing))
    return project, tuple(checks)


def verify_file(path: Path) -> tuple[Check, ...]:
    return run_project(path)[1]


@dataclass(frozen=True)
class Report:
    status: str
    files: tuple[Path, ...]
    pdf_written: bool


def report_file(path: Path, output: Path, *, full: bool = False) -> Report:
    """Escribe resultado.json, memoria.txt y, si fpdf2 está instalado, memoria.pdf en la carpeta de salida (D-050)."""
    project, checks = run_project(path)
    results = build_results(project, checks, __version__)
    text = render_memoir(results, full=full)
    output.mkdir(parents=True, exist_ok=True)
    result_path, memoir_path, pdf_path = output / "resultado.json", output / "memoria.txt", output / "memoria.pdf"
    result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    memoir_path.write_text(text, encoding="utf-8", newline="\n")
    pdf_written = write_pdf(text, pdf_path)
    files = (result_path, memoir_path, pdf_path) if pdf_written else (result_path, memoir_path)
    return Report(results["status"], files, pdf_written)


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


def import_etabs_footings(
    service: Path, factored: Path, template_path: Path
) -> tuple[dict[str, Any] | None, FootingImportSummary | None, Check]:
    """Proyecto de zapatas a partir de las reacciones de servicio y mayoradas de ETABS y la plantilla (D-055)."""
    try:
        template = load_footing_template(template_path)
        tables = [read_table(path, etabs_footings.SHEET) for path in (service, factored)]
        project, summary = build_footing_project(template, *tables)
        validation = validate_project(validate_input(project, Project), load_engine().bars)
    except (ProjectLoadError, EtabsImportError) as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    except XlsxError as error:
        return None, None, check_from_errors(CHECK_NAME, [invalid_input(str(error))])
    return project, summary, validation
