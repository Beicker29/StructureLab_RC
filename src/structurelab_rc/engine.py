"""Orquestación de los casos de uso."""

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structurelab_rc import __version__
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing.assignment import available as solver_available
from structurelab_rc.design.footing.profiling import profile_typologies
from structurelab_rc.design.footing.typologies import DesignResult, design_typologies, designed_project, typology_curve
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.checks import combined_footing_checks, footing_checks
from structurelab_rc.domain.footing.combined_diagrams import combined_diagrams
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.errors import invalid_input
from structurelab_rc.io.etabs import footings as etabs_footings
from structurelab_rc.io.etabs.footings import FootingImportSummary, build_footing_design_project, build_footing_project
from structurelab_rc.io.etabs.importer import SHEET, EtabsImportError, ImportSummary, build_project
from structurelab_rc.io.etabs.xlsx import XlsxError, read_table
from structurelab_rc.model.design import FootingDesignProject
from structurelab_rc.model.loader import (
    ProjectLoadError,
    load_design_project,
    load_footing_template,
    load_project,
    load_template,
    validate_input,
)
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import EtabsFootingDesignTemplate
from structurelab_rc.reporting.curve import curve_csv, curve_data, curve_document, curve_svg
from structurelab_rc.reporting.document import report_documents
from structurelab_rc.reporting.figures import diagram_figures, pressure_figures
from structurelab_rc.reporting.pdf import write_pdf
from structurelab_rc.reporting.results import Diagrams, build_results
from structurelab_rc.reporting.text import render_text
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
    if project.soil is not None:
        for footing in project.footings:
            checks.extend(footing_checks(Basis(profile, project.materials, bars, project.seismic.level), footing, project.soil))
        for combined in project.combined_footings:
            checks.extend(combined_footing_checks(Basis(profile, project.materials, bars, project.seismic.level), combined,
                                                  project.soil))
    return project, tuple(checks)


def verify_file(path: Path) -> tuple[Check, ...]:
    return run_project(path)[1]


@dataclass(frozen=True)
class Report:
    status: str
    files: tuple[Path, ...]
    pdf_written: bool


def _combined_diagrams(project: Project | None, checks: tuple[Check, ...]) -> Diagrams:
    """Diagramas envolventes de momento y cortante de cada zapata combinada con casos mayorados en equilibrio (D-095)."""
    if project is None or project.soil is None or checks[0].status is Status.FAIL:
        return {}
    bars = load_engine().bars
    profile = PROFILES[project.profile]
    diagrams: Diagrams = {}
    for footing in project.combined_footings:
        cases, failures = combined_factored_cases(footing, project.soil)
        if cases and not failures:
            basis = Basis(profile, project.materials, bars, project.seismic.level)
            diagrams[footing.id] = combined_diagrams(basis, footing, project.soil, cases)
    return diagrams


def report_file(path: Path, output: Path, *, full: bool = False) -> Report:
    """Escribe resultado.json, memoria.txt y, si fpdf2 está instalado, memoria.pdf en la carpeta de salida (D-050), con
    las figuras de presión y los diagramas de momento y cortante de las zapatas combinadas (D-095)."""
    project, checks = run_project(path)
    results = build_results(project, checks, __version__, _combined_diagrams(project, checks))
    output.mkdir(parents=True, exist_ok=True)
    figures = pressure_figures(results, output)
    diagram_files = diagram_figures(results, output)
    documents = report_documents(results, full=full, figures=figures, diagrams=diagram_files)
    text = render_text(documents)
    result_path, memoir_path, pdf_path = output / "resultado.json", output / "memoria.txt", output / "memoria.pdf"
    result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    memoir_path.write_text(text, encoding="utf-8", newline="\n")
    pdf_written = write_pdf(documents, pdf_path)
    files = (result_path, memoir_path, pdf_path) if pdf_written else (result_path, memoir_path)
    files = (*files, *figures.values(), *(path for paths in diagram_files.values() for path in paths))
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
    service: Path | None, factored: Path | None, template_path: Path
) -> tuple[dict[str, Any] | None, FootingImportSummary | None, Check]:
    """Proyecto de zapatas a partir de las reacciones de servicio y mayoradas de ETABS y la plantilla (D-055). Un Excel
    puede omitirse (None) si la plantilla no pide cargas de su tipo (zapatas combinadas, D-084)."""
    try:
        template = load_footing_template(template_path)
        tables = [None if path is None else read_table(path, etabs_footings.SHEET) for path in (service, factored)]
        if isinstance(template, EtabsFootingDesignTemplate):
            project, summary = build_footing_design_project(template, *tables)
            design = validate_input(project, FootingDesignProject)
            validation = _validate_design(design)
        else:
            project, summary = build_footing_project(template, *tables)
            validation = validate_project(validate_input(project, Project), load_engine().bars)
    except (ProjectLoadError, EtabsImportError) as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    except XlsxError as error:
        return None, None, check_from_errors(CHECK_NAME, [invalid_input(str(error))])
    return project, summary, validation


def _validate_design(design: FootingDesignProject) -> Check:
    """El perfil y el nivel sísmico, y que las barras del bloque design estén en el catálogo."""
    errors = []
    profile = PROFILES.get(design.profile)
    if profile is None:
        errors.append(invalid_input(f"El perfil '{design.profile}' no existe; valores: {', '.join(sorted(PROFILES))}"))
    elif design.seismic.level not in profile.seismic.seismic_levels():
        errors.append(invalid_input(f"El nivel sismico '{design.seismic.level}' no existe en {profile.id}"))
    known = {bar.designation for bar in load_engine().bars}
    for designation in sorted({*design.design.bars, *design.design.dowel_bars} - known):
        errors.append(invalid_input(f"La barra '{designation}' del bloque design no esta en el catalogo"))
    return check_from_errors(CHECK_NAME, errors)


def design_footings(
    path: Path, workers: int = 1, method: str | None = None
) -> tuple[dict[str, Any] | None, DesignResult | None, Check]:
    """Diseño por tipologías (D-069): el proyecto de verificación con una zapata por columna y el resumen; workers es el
    número de procesos entre los que se reparte (no cambia el resultado); method (dp, milp o milp_iter) reemplaza
    design.method."""
    project, result, check, _ = _design_footings(path, workers, method, profile=False)
    return project, result, check


CURVE_MAX = 12  # curva costo–N: N por defecto de 1 a 12, o hasta el número de columnas (D-078)


@dataclass(frozen=True)
class CurveReport:
    data: dict[str, Any]
    files: tuple[Path, ...]


def typology_curve_file(
    path: Path, output: Path, counts: Sequence[int] | None = None, workers: int = 1, method: str | None = None
) -> tuple[CurveReport | None, Check]:
    """Curva costo–N del diseño por tipologías (D-078): resultado.json, curva.csv, curva.svg y la memoria (memoria.txt y,
    si fpdf2 está instalado, memoria.pdf) en la carpeta de salida, con los mismos nombres que las demás salidas."""
    ctx, validation = _design_context(path, method)
    if ctx is None:
        return None, validation
    columns = len(ctx.project.columns)
    wanted = sorted(set(counts)) if counts else list(range(1, min(CURVE_MAX, columns) + 1))
    outside = [count for count in wanted if not 1 <= count <= columns]
    if outside:
        message = f"N debe estar entre 1 y el numero de columnas ({columns}): {', '.join(map(str, outside))}"
        return None, check_from_errors(CHECK_NAME, [invalid_input(message)])
    begin = time.perf_counter()
    points = typology_curve(ctx, wanted, workers)
    data = curve_data(points, ctx.design.method, time.perf_counter() - begin)
    data = {"project": str(path), "profile": ctx.project.profile, **data}
    output.mkdir(parents=True, exist_ok=True)
    json_path, csv_path, svg_path = output / "resultado.json", output / "curva.csv", output / "curva.svg"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    csv_path.write_text(curve_csv(data), encoding="utf-8", newline="\n")
    svg_path.write_text(curve_svg(data), encoding="utf-8", newline="\n")
    blocks = curve_document(data, {"description": ctx.project.description, "profile": ctx.project.profile}, str(svg_path))
    memoir_path, pdf_path = output / "memoria.txt", output / "memoria.pdf"
    memoir_path.write_text(render_text([blocks]), encoding="utf-8", newline="\n")
    files: tuple[Path, ...] = (json_path, csv_path, svg_path, memoir_path)
    if write_pdf([blocks], pdf_path):
        files = (*files, pdf_path)
    return CurveReport(data, files), validation


def profile_footings(
    path: Path, workers: int = 1, method: str | None = None
) -> tuple[dict[str, Any] | None, DesignResult | None, Check, dict[str, Any] | None]:
    """Lo mismo que design_footings, con la medición de tiempos y el análisis de la solución (etapa E0)."""
    return _design_footings(path, workers, method, profile=True)


def _design_context(path: Path, method: str | None) -> tuple[Context | None, Check]:
    """Proyecto de diseño cargado y validado, con el método pedido, listo para diseñar; o el Check que lo impide."""
    try:
        design = load_design_project(path)
    except ProjectLoadError as error:
        return None, check_from_errors(CHECK_NAME, error.errors)
    if method is not None:
        design = design.model_copy(update={"design": design.design.model_copy(update={"method": method})})
    validation = _validate_design(design)
    if validation.status is Status.FAIL:
        return None, validation
    if design.design.method in ("milp", "milp_iter") and not solver_available():
        message = f"El metodo {design.design.method} necesita el solucionador highspy: instale  pip install structurelab-rc[opt]"
        return None, check_from_errors(CHECK_NAME, [invalid_input(message)])
    return Context(design, PROFILES[design.profile], load_engine().bars), validation


def _design_footings(
    path: Path, workers: int, method: str | None, profile: bool
) -> tuple[dict[str, Any] | None, DesignResult | None, Check, dict[str, Any] | None]:
    ctx, validation = _design_context(path, method)
    if ctx is None:
        return None, None, validation, None
    measurement = None
    if profile:
        result, measurement = profile_typologies(ctx, workers)
    else:
        result = design_typologies(ctx, workers)
    if result.fc is None:
        failure = check_from_errors(CHECK_NAME, [invalid_input(f"Sin solucion dentro de los limites: {result.failure}")])
        return None, result, failure, measurement
    return designed_project(ctx, result), result, validation, measurement

