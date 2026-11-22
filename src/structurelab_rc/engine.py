"""Orquestación de los casos de uso."""

import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structurelab_rc import __version__
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing import combined as combined_design
from structurelab_rc.design.footing.assignment import available as solver_available
from structurelab_rc.design.footing.mixed import combined_part, design_with_pairs, designed_with_pairs
from structurelab_rc.design.footing.profiling import profile_typologies
from structurelab_rc.design.footing.typologies import DesignResult, typology_curve
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.design.pile_cap import search as pile_cap_design
from structurelab_rc.detailing.schedule import BarRun, ScheduleRow, schedule
from structurelab_rc.detailing.units import Member, Unit, units
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.checks import combined_footing_checks, footing_checks
from structurelab_rc.domain.footing.combined_diagrams import combined_diagrams
from structurelab_rc.domain.footing.detailing import combined_runs, face_envelope, footing_runs, moment_envelope
from structurelab_rc.domain.footing.drawing import combined_views, footing_views, location_views
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.neighbors import close_neighbors, footprints, neighbor_text
from structurelab_rc.domain.pile_cap.checks import cap_analysis, pile_cap_checks
from structurelab_rc.domain.pile_cap.drawing import pile_cap_views
from structurelab_rc.domain.pile_cap.loads import CapAnalysis
from structurelab_rc.domain.pile_cap.outline import bar_span
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import CHECK_NAME, validate_project
from structurelab_rc.drawing.dxf import write_dxf
from structurelab_rc.drawing.model import Drawing, View
from structurelab_rc.drawing.svg import view_svg
from structurelab_rc.errors import invalid_input
from structurelab_rc.io.dlnet import TEMPLATE_PATH, TEMPLATE_VARIABLE, DliError, find_template, schedule_dli
from structurelab_rc.io.etabs import footings as etabs_footings
from structurelab_rc.io.etabs.combinations import read_combinations
from structurelab_rc.io.etabs.footings import (
    FootingImportSummary,
    build_combined_design_project,
    build_footing_design_project,
    build_footing_project,
)
from structurelab_rc.io.etabs.importer import SHEET, EtabsImportError, ImportSummary, build_project
from structurelab_rc.io.etabs.pile_caps import PILE_SHEET, build_pile_cap_design_project, build_pile_cap_project
from structurelab_rc.io.etabs.xlsx import XlsxError, read_table
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.design import CombinedDesignProject, FootingDesignProject
from structurelab_rc.model.footing import Footing
from structurelab_rc.model.loader import (
    ProjectLoadError,
    load_combined_design,
    load_design_project,
    load_footing_template,
    load_pile_cap_design,
    load_project,
    load_template,
    validate_input,
)
from structurelab_rc.model.pile_cap import PileCap
from structurelab_rc.model.pile_cap_design import PileCapDesignProject
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import (
    EtabsCombinedDesignTemplate,
    EtabsFootingDesignTemplate,
    EtabsPileCapDesignTemplate,
    EtabsPileCapTemplate,
)
from structurelab_rc.reporting.curve import curve_csv, curve_data, curve_document, curve_svg
from structurelab_rc.reporting.document import report_documents
from structurelab_rc.reporting.figures import diagram_figures, pressure_figures
from structurelab_rc.reporting.pdf import write_pdf
from structurelab_rc.reporting.results import Diagrams, build_results, detailing_csv, detailing_data
from structurelab_rc.reporting.text import render_text
from structurelab_rc.setup import dxf_template, load_engine


class RunError(Exception):
    """`run` no puede preparar el ejemplo: el archivo no se lee o la plantilla no declara sus Excel."""


RUN_KINDS = {"project": "proyecto de verificación", "design": "diseño por tipologías", "curve": "curva costo-N",
             "combined_design": "diseño de zapata combinada",
             "etabs_beams": "plantilla de vigas de ETABS", "etabs_footings": "plantilla de zapatas de ETABS",
             "etabs_design": "plantilla de diseño de zapatas de ETABS",
             "etabs_curve": "plantilla de curva costo-N de ETABS",
             "etabs_combined_design": "plantilla de diseño de zapata combinada de ETABS",
             "pile_cap_design": "diseño de cabezales",
             "etabs_pile_cap_design": "plantilla de diseño de cabezales de ETABS"}


LOCATION = "localizacion"  # el "elemento" del dibujo con las plantas de localización del proyecto (D-130)


@dataclass(frozen=True)
class RunPlan:
    """Lo que `run` hace con un ejemplo (D-096): su tipo, la carpeta de salida y los Excel de ETABS ya resueltos."""

    kind: str
    path: Path
    output: Path
    workbook: Path | None = None
    service: Path | None = None
    factored: Path | None = None
    locations: Path | None = None  # tabla de coordenadas de los nudos (D-130)
    combinations: Path | None = None  # Excel de combinaciones (D-137)


def default_output(path: Path) -> Path:
    """results/<perfil>/<elemento>/<nombre>/ para un ejemplo de examples/<perfil>/<elemento>/ (D-058), junto a la carpeta
    examples; results/<nombre>/ en la carpeta actual para cualquier otro archivo."""
    parts = path.resolve().parts
    if "examples" in parts[:-1]:
        index = len(parts) - 1 - parts[::-1].index("examples")
        return Path(*parts[:index], "results", *parts[index + 1 : -1], path.stem)
    return Path("results") / path.stem


def _footing_template(data: dict[str, Any]) -> bool:
    """Si el JSON es una plantilla de cimentaciones de ETABS: sus zapatas, columnas o grupos se ligan a nudos de ETABS
    (Unique Name) o declara Excel de reacciones o de combinaciones (D-137)."""
    files = data.get("etabs_files") or {}
    if isinstance(files, dict) and any(key in files for key in ("service", "factored", "combinations")):
        return True
    caps = [*(data.get("pile_caps") or []), *(data.get("caps") or [])]  # cabezales (D-138) y su diseño (D-141)
    items = [*(data.get("footings") or []), *(data.get("columns") or []), *caps]
    for cap in caps:  # la columna o sus pilotes llevan el Unique Name
        items += cap.get("piles") or [] if isinstance(cap, dict) else []
    for footing in data.get("combined_footings") or []:
        items += footing.get("columns") or [] if isinstance(footing, dict) else []
    keys = ("etabs_unique_names", "etabs_unique_name", "column_unique_name")
    return any(isinstance(item, dict) and any(key in item for key in keys) for item in items)


def run_plan(path: Path, output: Path | None = None) -> RunPlan:
    """El tipo del ejemplo por su contenido (D-096): plantilla de ETABS (de zapatas, con los Excel de reacciones y de
    combinaciones en etabs_files, D-137; o de vigas, con miembros con Unique Name) con sus
    Excel en etabs_files (rutas relativas a la plantilla); diseño por tipologías (design y columns), curva costo-N si
    trae curve; diseño de zapata combinada (combined_design, D-107); diseño de cabezales (pile_cap_design, D-141); si no,
    un proyecto de verificación."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunError(f"No se pudo leer {path}: {error}") from error
    if not isinstance(data, dict):
        raise RunError(f"{path} no es un objeto JSON")
    out = output if output is not None else default_output(path)
    files = data.get("etabs_files") or {}

    def excel(key: str) -> Path | None:
        value = files.get(key)
        return None if value is None else (path.parent / value).resolve()

    members = data.get("members") or []
    if _footing_template(data):  # plantilla de zapatas de ETABS
        if not files:
            raise RunError(f"La plantilla {path.name} no declara sus Excel de ETABS en etabs_files (D-096)")
        if "combinations" not in files:
            raise RunError(f"La plantilla {path.name} no declara su Excel de combinaciones en etabs_files.combinations (D-137)")
        kinds = {"design": "etabs_design", "combined_design": "etabs_combined_design", "pile_cap_design": "etabs_pile_cap_design"}
        kind = next((value for key, value in kinds.items() if key in data), "etabs_footings")
        if kind == "etabs_design" and "curve" in data:  # la curva costo-N desde ETABS (D-165)
            kind = "etabs_curve"
        return RunPlan(kind, path, out, service=excel("service"), factored=excel("factored"), locations=excel("locations"),
                       combinations=excel("combinations"))
    if any(isinstance(member, dict) and "etabs_unique_name" in member for member in members):
        if "workbook" not in files:
            raise RunError(f"La plantilla {path.name} no declara su Excel de ETABS en etabs_files.workbook (D-096)")
        return RunPlan("etabs_beams", path, out, workbook=excel("workbook"))
    if "design" in data and "columns" in data:
        return RunPlan("curve" if "curve" in data else "design", path, out)
    if "combined_design" in data:
        return RunPlan("combined_design", path, out)
    if "pile_cap_design" in data:
        return RunPlan("pile_cap_design", path, out)
    return RunPlan("project", path, out)


def validate_file(path: Path) -> Check:
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return check_from_errors(CHECK_NAME, error.errors)
    return validate_project(project, load_engine().bars)


Analyses = dict[str, CapAnalysis]  # id del cabezal → su análisis (D-138), calculado una vez


def run_project(path: Path) -> tuple[Project | None, tuple[Check, ...]]:
    """Proyecto cargado y sus verificaciones: primero la validación; si la entrada es inválida, solo ella."""
    project, checks, _ = _run(path)
    return project, checks


def _run(path: Path) -> tuple[Project | None, tuple[Check, ...], Analyses]:
    """run_project con el análisis de cada cabezal, que el resultado y el despiece reutilizan."""
    analyses: Analyses = {}
    try:
        project = load_project(path)
    except ProjectLoadError as error:
        return None, (check_from_errors(CHECK_NAME, error.errors),), analyses
    bars = load_engine().bars
    validation = validate_project(project, bars)
    if validation.status is Status.FAIL:
        return project, (validation,), analyses
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
    if project.pile_soil is not None:
        basis = Basis(profile, project.materials, bars, project.seismic.level)
        for cap in project.pile_caps:
            analyses[cap.id] = cap_analysis(basis, cap, project.pile_soil)
            checks.extend(pile_cap_checks(basis, cap, project.pile_soil, analyses[cap.id]))
    return project, tuple(checks), analyses


def verify_file(path: Path) -> tuple[Check, ...]:
    return run_project(path)[1]


@dataclass(frozen=True)
class Report:
    status: str
    files: tuple[Path, ...]
    pdf_written: bool
    notes: tuple[str, ...] = ()  # lo que no se escribió y por qué (la cartilla DL-NET sin plantilla, D-133)


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


Draw = Callable[[Drawing, str, list[ScheduleRow], int], list[View]]


def _detailing(
    project: Project | None, results: dict[str, Any], given: tuple[str, Analyses]
) -> tuple[list[Unit], list[str], Drawing | None]:
    """Agrega la cartilla del tipo de cada zapata a su entrada del resultado (D-125, D-159) si el proyecto pide despiece y
    la entrada es válida: (los tipos con su cartilla de una unidad y sus N unidades, vacío si no se despieza; los avisos
    de los elementos que no coinciden con su tipo; el dibujo del refuerzo, una vez por tipo, si el proyecto lo pide,
    D-126)."""
    name, analyses = given
    if project is None or project.detailing is None:
        return [], [], None
    if not any(key in results for key in ("footings", "combined_footings", "pile_caps")):
        return [], [], None
    bars = load_engine().bars
    basis = Basis(PROFILES[project.profile], project.materials, bars, project.seismic.level)
    stock = project.detailing.stock_length
    drawing = None if project.drawing is None else Drawing(name, project.drawing.scale)
    entries = {entry["id"]: entry for key in ("footings", "combined_footings", "pile_caps") for entry in results.get(key, [])}
    built: list[tuple[Member, float, Draw]] = []

    def add(element: Footing | PileCap | CombinedFooting, runs: list[BarRun], concrete: float, views: Callable[..., list[View]]) -> None:
        """La cartilla del elemento con las marcas de su tipo (typology o, sin él, id) y cómo dibujar su tipo."""
        typology = element.typology or element.id
        member = Member(element.id, typology, element.quantity, tuple(schedule(typology, runs, stock)))

        def draw(target: Drawing, unit: str, rows: list[ScheduleRow], quantity: int) -> list[View]:
            return views(target, element.model_copy(update={"id": unit}), runs, (rows, stock), quantity)

        built.append((member, concrete, draw))

    pile_soil = project.pile_soil
    if pile_soil is not None:  # cabezales (D-138), con su análisis
        for cap in project.pile_caps:
            spans = (lambda direction, position, cap=cap: bar_span(cap, direction, position)) if cap.clipped_corners else None
            add(cap, footing_runs(basis, cap, moment_envelope(list(analyses[cap.id].moments)), spans),
                sum(cap.weights(pile_soil)[:2]) / pile_soil.unit_weight_concrete / 1e9, pile_cap_views)
    soil = project.soil
    for footing in project.footings if soil is not None else ():
        assert soil is not None
        add(footing, footing_runs(basis, footing, face_envelope(footing, soil)),
            sum(footing.weights(soil)[:2]) / soil.unit_weight_concrete / 1e9, footing_views)
    # La planta de localización de la trapezoidal o en T/L llega después (D-164): por ahora no se ubica.
    rectangular = [combined for combined in project.combined_footings if combined.plan is None]
    for combined in project.combined_footings if soil is not None else ():
        assert soil is not None
        add(combined, combined_runs(basis, combined, soil), sum(combined.weights(soil)[:2]) / soil.unit_weight_concrete / 1e9,
            combined_views)
    found, warnings = units([member for member, _, _ in built])
    unit_of = {member: unit for unit in found for member in unit.members}
    for member, concrete, draw in built:
        unit = unit_of[member.id]
        entries[member.id]["detailing"] = detailing_data(unit, concrete, stock)
        if drawing is not None and unit.members[0] == member.id:  # un despiece por tipo
            drawing.views[unit.name] = draw(drawing, unit.name, list(unit.rows), unit.quantity)
    if drawing is not None:
        located = location_views(drawing, [*project.footings, *project.pile_caps], rectangular,  # D-130, D-138, D-164
                                 project.min_clear_spacing)  # D-156
        if located:
            drawing.views[LOCATION] = located
    return found, warnings, drawing


def _dli_file(found: list[Unit], output: Path, start: Path) -> tuple[list[Path], list[str]]:
    """Escribe la cartilla DL-NET <caso>.dli (D-133) con la plantilla que encuentra find_template, un elemento por tipo
    con sus unidades (D-159): (archivos, avisos)."""
    template = find_template(start, dict(os.environ))
    if template is None:
        return [], [f"{output.name}.dli no se genero: falta la plantilla DL-NET ({TEMPLATE_PATH.as_posix()} o la variable "
                    f"{TEMPLATE_VARIABLE})"]
    path = output / f"{output.name}.dli"
    try:
        data = schedule_dli([(unit.name, unit.rows, unit.quantity) for unit in found], template)
    except DliError as error:  # una barra que DL-NET no representa (p. ej., gancho de 135° en una malla, D-134)
        return [], [f"{output.name}.dli no se genero: {error}"]
    path.write_bytes(data)
    return [path], []


def _drawing_files(drawing: Drawing, output: Path) -> tuple[list[Path], dict[str, list[tuple[Path, float, str]]]]:
    """Escribe el modelo de dibujo (<nombre>_drawing.json), un SVG por vista y, si ezdxf está instalado, <nombre>.dxf
    (D-126): (archivos, vistas de cada elemento para la memoria)."""
    model_path = output / f"{drawing.name}_drawing.json"
    model_path.write_text(json.dumps(drawing.to_dict(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    files: list[Path] = [model_path]
    figures: dict[str, list[tuple[Path, float, str]]] = {}
    for element, views in drawing.views.items():
        figures[element] = []
        for view in views:
            svg, aspect = view_svg(view, drawing.scale)
            path = output / f"{element}_{view.name}.svg"
            path.write_text(svg, encoding="utf-8", newline="\n")
            files.append(path)
            figures[element].append((path, aspect, view.title))
    dxf_path = output / f"{drawing.name}.dxf"
    if write_dxf(drawing, dxf_path, dxf_template()):
        files.append(dxf_path)
    return files, figures


def _clear_outputs(output: Path) -> None:
    """Borra lo que report_file escribió en una corrida anterior (D-162), para que no queden vistas o elementos que ya no
    existen: las figuras y vistas SVG, el modelo de dibujo, el DXF y el .dli del caso, la cartilla, la memoria y el
    resultado. No toca proyecto.json (el diseño lo escribe antes) ni otros archivos."""
    names = ("resultado.json", "memoria.txt", "memoria.pdf", "cartilla.csv", f"{output.name}.dxf", f"{output.name}.dli",
             f"{output.name}_drawing.json")
    for path in [*output.glob("*.svg"), *(output / name for name in names)]:
        path.unlink(missing_ok=True)


def report_file(path: Path, output: Path, *, full: bool = False) -> Report:
    """Escribe resultado.json, memoria.txt y, si fpdf2 está instalado, memoria.pdf en la carpeta de salida (D-050), con
    las figuras de presión y los diagramas de momento y cortante de las zapatas combinadas (D-095)."""
    project, checks, analyses = _run(path)
    results = build_results(project, checks, __version__, (_combined_diagrams(project, checks), analyses))
    close = _close_footings(project)  # D-156: zapatas más cercanas que la mínima o traslapadas
    if close:
        results["close_footings"] = close
    # El dibujo y el DXF llevan el nombre del caso (la carpeta de salida), como el .dli.
    found, mismatched, drawing = ([], [], None) if checks[0].status is Status.FAIL else _detailing(
        project, results, (output.name, analyses))
    output.mkdir(parents=True, exist_ok=True)
    _clear_outputs(output)
    figures = pressure_figures(results, output)
    diagram_files = diagram_figures(results, output)
    drawing_paths, drawings = ([], {}) if drawing is None else _drawing_files(drawing, output)
    documents = report_documents(results, full=full, figures=figures, diagrams=diagram_files, drawings=drawings)
    text = render_text(documents)
    result_path, memoir_path, pdf_path = output / "resultado.json", output / "memoria.txt", output / "memoria.pdf"
    result_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    memoir_path.write_text(text, encoding="utf-8", newline="\n")
    pdf_written = write_pdf(documents, pdf_path)
    files = (result_path, memoir_path, pdf_path) if pdf_written else (result_path, memoir_path)
    notes: list[str] = list(mismatched)
    if found:  # la cartilla de cada tipo (D-125, D-159) y la cartilla DL-NET (D-133)
        schedule_path = output / "cartilla.csv"
        schedule_path.write_text(detailing_csv(results), encoding="utf-8", newline="\n")
        dli_paths, dli_notes = _dli_file(found, output, path.parent)
        notes += dli_notes
        files = (*files, schedule_path, *dli_paths)
    files = (*files, *figures.values(), *(path for paths in diagram_files.values() for path in paths), *drawing_paths)
    notes += [f"Zapatas vecinas: {item['text']}" for item in close]
    return Report(results["status"], files, pdf_written, tuple(notes))


def close_footings_of(designed: dict[str, Any]) -> list[dict[str, Any]]:
    """Los pares de zapatas cercanos (D-156) de un proyecto diseñado (formato de entrada), para el resumen del diseño."""
    return _close_footings(validate_input(designed, Project))


def _close_footings(project: Project | None) -> list[dict[str, Any]]:
    """Los pares de zapatas del mismo nivel más cercanos que min_clear_spacing o traslapados (D-156), con sus nudos."""
    if project is None:
        return []
    placed = footprints([*project.footings, *project.pile_caps],  # la planta no rectangular, pendiente (D-164)
                        [combined for combined in project.combined_footings if combined.plan is None])
    minimum = project.min_clear_spacing
    return [{"first": item.first.name, "second": item.second.name, "story": item.first.story,
             "joints": [*item.first.joints, *item.second.joints], "clear [mm]": round(item.clear, 1),
             **({"minimum [mm]": minimum} if minimum is not None else {}), "text": neighbor_text(item, minimum)}
            for item in close_neighbors(placed, minimum)]


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
    service: Path | None, factored: Path | None, template_path: Path, locations: Path | None = None,
    combinations: Path | None = None,
) -> tuple[dict[str, Any] | None, FootingImportSummary | None, Check]:
    """Proyecto de zapatas a partir de las reacciones de servicio y mayoradas de ETABS y la plantilla (D-055). Un Excel
    puede omitirse (None) si la plantilla no pide cargas de su tipo (zapatas combinadas, D-084). locations es la tabla
    de coordenadas de los nudos, para la planta de localización (D-130); el diseño de una zapata combinada no la usa.
    combinations es el Excel de combinaciones (D-137); sin él, el de etabs_files.combinations de la plantilla."""
    try:
        template = load_footing_template(template_path)
        if combinations is not None:
            chosen = combinations
        elif template.etabs_files is not None:
            chosen = template_path.parent / template.etabs_files.combinations
        else:
            raise EtabsImportError((invalid_input("Falta el Excel de combinaciones: declarelo en etabs_files.combinations de la "
                                                  "plantilla (D-137)"),))
        listed = read_combinations(chosen)
        piles = isinstance(template, EtabsPileCapTemplate | EtabsPileCapDesignTemplate) and template.from_piles
        sheet = PILE_SHEET if piles else etabs_footings.SHEET
        found = tuple(None if path is None else read_table(path, sheet) for path in (service, factored))
        tables = (found[0], found[1])
        coordinates = None if locations is None else read_table(locations, etabs_footings.LOCATION_SHEET)
        if isinstance(template, EtabsFootingDesignTemplate):
            project, summary = build_footing_design_project(template, tables, listed, coordinates)
            design = validate_input(project, FootingDesignProject)
            validation = _validate_design(design)
        elif isinstance(template, EtabsPileCapDesignTemplate):  # diseño de cabezales (D-141)
            project, summary = build_pile_cap_design_project(template, tables, listed, coordinates)
            validation = _validate_design(validate_input(project, PileCapDesignProject))
        elif isinstance(template, EtabsPileCapTemplate):  # cabezales (D-138)
            project, summary = build_pile_cap_project(template, tables, listed, coordinates)
            validation = validate_project(validate_input(project, Project), load_engine().bars)
        elif isinstance(template, EtabsCombinedDesignTemplate):  # diseño de una zapata combinada (D-112)
            project, summary = build_combined_design_project(template, tables, listed)
            validation = _validate_design(validate_input(project, CombinedDesignProject))
        else:
            project, summary = build_footing_project(template, tables, listed, coordinates)
            validation = validate_project(validate_input(project, Project), load_engine().bars)
    except (ProjectLoadError, EtabsImportError) as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    except XlsxError as error:
        return None, None, check_from_errors(CHECK_NAME, [invalid_input(str(error))])
    return project, summary, validation


def _validate_design(design: FootingDesignProject | CombinedDesignProject | PileCapDesignProject) -> Check:
    """El perfil y el nivel sísmico, y que las barras del bloque de diseño estén en el catálogo."""
    errors = []
    profile = PROFILES.get(design.profile)
    if profile is None:
        errors.append(invalid_input(f"El perfil '{design.profile}' no existe; valores: {', '.join(sorted(PROFILES))}"))
    elif design.seismic.level not in profile.seismic.seismic_levels():
        errors.append(invalid_input(f"El nivel sismico '{design.seismic.level}' no existe en {profile.id}"))
    known = {bar.designation for bar in load_engine().bars}
    if isinstance(design, PileCapDesignProject):
        bars = {*design.pile_cap_design.bars, *design.pile_cap_design.dowel_bars}
    elif isinstance(design, FootingDesignProject):
        bars = {*design.design.bars, *design.design.dowel_bars}
    else:
        bars = {*design.combined_design.bars, *design.combined_design.dowel_bars, *design.combined_design.stirrup_bars}
    for designation in sorted(bars - known):
        errors.append(invalid_input(f"La barra '{designation}' del bloque de diseno no esta en el catalogo"))
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
    columns = len(ctx.project.columns)  # las aisladas: N es su número de tipologías (D-165)
    if counts:
        wanted = sorted(set(counts))
    elif ctx.project.curve is not None:  # el ejemplo de la curva declara sus N (D-096)
        wanted = sorted(ctx.project.curve.n)
    else:
        wanted = list(range(1, min(CURVE_MAX, columns) + 1))
    outside = [count for count in wanted if not 1 <= count <= columns]
    if outside:
        message = f"N debe estar entre 1 y el numero de columnas ({columns}): {', '.join(map(str, outside))}"
        return None, check_from_errors(CHECK_NAME, [invalid_input(message)])
    begin = time.perf_counter()
    part = combined_part(ctx, workers) if ctx.project.combined_footings else None  # una vez: no depende de N (D-165)
    if isinstance(part, str):
        return None, check_from_errors(CHECK_NAME, [invalid_input(part)])
    points = typology_curve(ctx, wanted, workers, None if part is None else part.costs)
    combined = None if part is None else {"pairs": len(part.pairs), "types": ctx.design.combined_typologies}
    data = curve_data(points, ctx.design.method, time.perf_counter() - begin, combined)
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
        result = design_with_pairs(ctx, workers)  # las tipologías y las combinadas de los pares, un solo f'c (D-153)
    if result.fc is None:
        failure = check_from_errors(CHECK_NAME, [invalid_input(f"Sin solucion dentro de los limites: {result.failure}")])
        return None, result, failure, measurement
    return designed_with_pairs(ctx, result), result, validation, measurement



def design_pile_caps_file(path: Path) -> tuple[dict[str, Any] | None, pile_cap_design.DesignResult | None, Check]:
    """Diseño de cabezales (D-141): el proyecto de verificación con los cabezales de menor costo, el resultado de la
    búsqueda (cada f'c, cada cabezal y sus arreglos probados) y la validación; sin solución, un Check con el motivo."""
    try:
        design = load_pile_cap_design(path)
    except ProjectLoadError as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    validation = _validate_design(design)
    if validation.status is Status.FAIL:
        return None, None, validation
    ctx = pile_cap_design.Context(design, PROFILES[design.profile], load_engine().bars)
    result = pile_cap_design.design_caps(ctx)
    if result.fc is None:
        reasons = "; ".join(item.failure for _, designs in result.options for item in designs if item.failure)
        return None, result, check_from_errors(CHECK_NAME, [invalid_input(f"Sin solucion dentro de los limites: {reasons}")])
    return pile_cap_design.designed_project(ctx, result), result, validation


def design_combined_file(
    path: Path, workers: int = 1,
) -> tuple[dict[str, Any] | None, combined_design.CombinedDesignResult | None, Check]:
    """Diseño de una zapata combinada (D-107, D-163): el proyecto de verificación con la zapata de menor costo,
    el resultado de la búsqueda (con cada f'c) y la validación; sin solución, un Check con el motivo de cada f'c. workers
    reparte los f'c entre procesos (no cambia el resultado)."""
    try:
        design = load_combined_design(path)
    except ProjectLoadError as error:
        return None, None, check_from_errors(CHECK_NAME, error.errors)
    validation = _validate_design(design)
    if validation.status is Status.FAIL:
        return None, None, validation
    ctx = combined_design.Context(design, PROFILES[design.profile], load_engine().bars)
    result = combined_design.design_combined(ctx, workers)
    if result.best is None:
        reasons = "; ".join(f"f'c = {option.fc:g} MPa: {option.failure}" for option in result.options)
        return None, result, check_from_errors(CHECK_NAME, [invalid_input(f"Sin solucion dentro de los limites: {reasons}")])
    return combined_design.designed_project(ctx, result.best), result, validation
