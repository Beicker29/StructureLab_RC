"""Dibujo del refuerzo (v3 Fase 4B, D-126): vistas de cada tipo de zapata con las barras de su despiece, capas fijas,
textos a la escala declarada, marcas de la cartilla, salidas JSON, SVG y DXF, y figuras en la memoria."""

import json
from pathlib import Path

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.detailing.schedule import run_marks, schedule
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.detailing import combined_runs, footing_runs
from structurelab_rc.domain.footing.drawing import combined_views, footing_views
from structurelab_rc.drawing.model import LAYERS, PAPER_SMALL, PAPER_TEXT, Circle, Drawing, Line, Text, View
from structurelab_rc.drawing.svg import view_svg
from structurelab_rc.engine import import_etabs_footings, report_file
from structurelab_rc.model.loader import ProjectLoadError, load_project, validate_input
from structurelab_rc.model.project import Project
from structurelab_rc.setup import load_engine

ROOT = Path(__file__).parent.parent
PRUEBAS = ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas"
REACTIONS = (ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Servicio.xlsx",
             ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Ultimas.xlsx")
BARS = load_engine().bars
SCALE = 50.0


def _project(name: str, tmp_path: Path) -> Project:
    path = PRUEBAS / name
    if name.endswith("_etabs.json"):
        data = import_etabs_footings(*REACTIONS, path)[0]
        assert data is not None
        path = tmp_path / "etabs.json"
        path.write_text(json.dumps(data), encoding="utf-8")
    return load_project(path)


def _views(project: Project) -> tuple[list[View], list[str], int]:
    """Vistas de la primera zapata, las marcas de su cartilla y el número de barras horizontales de la malla inferior."""
    assert project.detailing is not None and project.soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    drawing, stock = Drawing("prueba", SCALE), project.detailing.stock_length
    if project.footings:
        footing = project.footings[0]
        runs = footing_runs(basis, footing)
        rows = schedule(footing.id, runs, stock)
        views = footing_views(drawing, footing, runs, (rows, stock))
        split = footing.h / 2
    else:
        combined = project.combined_footings[0]
        runs = combined_runs(basis, combined, project.soil)
        rows = schedule(combined.id, runs, stock)
        views = combined_views(drawing, combined, runs, (rows, stock))
        split = (combined.h if combined.beam is None else combined.total_height) / 2
    bottom = sum(len(run.placement.positions) for run in runs
                 if run.placement is not None and run.placement.along in ("x", "y") and run.placement.level <= split)
    return views, [row.mark for row in rows], bottom


@pytest.mark.parametrize(("name", "expected"), [
    ("zapata_centrica.json", ["planta_inferior", "planta_superior", "corte_x", "corte_y", "cartilla"]),
    ("zapata_combinada.json", ["planta_inferior", "planta_superior", "alzado", "corte_C1", "corte_C2", "cartilla"]),
    ("zapata_t_invertida_etabs.json", ["planta_inferior", "planta_superior", "alzado", "corte_C15", "corte_C1659", "cartilla"]),
])
def test_views_of_each_footing_type(name: str, expected: list[str], tmp_path: Path) -> None:
    views, marks, bottom = _views(_project(name, tmp_path))
    assert [view.name for view in views] == expected
    plan = views[0]
    assert sum(1 for entity in plan.entities if isinstance(entity, Line) and entity.layer == "REFUERZO") == bottom
    texts = [entity for view in views for entity in view.entities if isinstance(entity, Text)]
    assert {entity.layer for view in views for entity in view.entities} <= set(LAYERS)
    # Textos a la escala de impresión: títulos, rótulos y cotas; las letras del croquis de la cartilla, al 80 %.
    assert {round(text.height, 6) for text in texts} <= {PAPER_TEXT * SCALE, PAPER_SMALL * SCALE, 0.8 * PAPER_SMALL * SCALE}
    labels = " ".join(text.text for text in texts if text.layer == "TEXTOS")
    cartilla = {text.text for text in views[-1].entities if isinstance(text, Text)}
    for mark in marks:  # cada marca se rotula en alguna vista y está en la cartilla
        assert mark in labels, mark
        assert mark in cartilla, mark


def test_isolated_section_cuts_every_perpendicular_bar(tmp_path: Path) -> None:
    project = _project("zapata_centrica.json", tmp_path)
    views, _, _ = _views(project)
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    runs = footing_runs(basis, project.footings[0])
    across = sum(len(run.placement.positions) for run in runs if run.placement is not None and run.placement.along == "y")
    section = next(view for view in views if view.name == "corte_x")
    assert sum(1 for entity in section.entities if isinstance(entity, Circle)) == across


def test_run_marks_match_the_schedule(tmp_path: Path) -> None:
    project = _project("zapata_combinada.json", tmp_path)
    assert project.detailing is not None and project.soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    combined = project.combined_footings[0]
    runs = combined_runs(basis, combined, project.soil)
    rows = schedule(combined.id, runs, project.detailing.stock_length)
    marks = run_marks(combined.id, runs, project.detailing.stock_length)
    for row in rows:  # cada marca la llevan las corridas de los grupos que nombra
        owners = dict.fromkeys(run.group for run, own in zip(runs, marks, strict=True) if row.mark in own)
        assert ", ".join(owners) == row.piece.group, row.mark
    assert all(marks), "toda corrida tiene marca"


def test_drawing_requires_detailing() -> None:
    data = json.loads((PRUEBAS / "zapata_centrica.json").read_text(encoding="utf-8"))
    del data["detailing"]
    with pytest.raises(ProjectLoadError, match="drawing requiere detailing"):
        validate_input(data, Project)


def test_svg_keeps_the_model_scale(tmp_path: Path) -> None:
    views, _, _ = _views(_project("zapata_centrica.json", tmp_path))
    svg, aspect = view_svg(views[1], SCALE)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert aspect > 0
    assert f'stroke-width="{LAYERS["REFUERZO"][2] * SCALE:.1f}"' in svg


def test_report_writes_the_drawing(tmp_path: Path) -> None:
    report = report_file(PRUEBAS / "zapata_centrica.json", tmp_path)
    names = {path.name for path in report.files}
    assert {"zapata_centrica_drawing.json", "Z1_planta_inferior.svg", "Z1_corte_x.svg", "Z1_cartilla.svg"} <= names
    model = json.loads((tmp_path / "zapata_centrica_drawing.json").read_text(encoding="utf-8"))
    assert model["scale"] == SCALE and set(model["layers"]) == set(LAYERS)
    assert [view["name"] for view in model["elements"]["Z1"]][0] == "planta_inferior"
    memoir = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    chapter = memoir[memoir.index("Despiece y cantidades"):]
    assert "Planta refuerzo inferior Z1" in chapter and "Cartilla de despiece Z1" in chapter and "Z1_corte_x.svg" in chapter


def test_dxf_has_the_layers_and_views(tmp_path: Path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    report_file(PRUEBAS / "zapata_combinada.json", tmp_path)
    document = ezdxf.readfile(tmp_path / "zapata_combinada.dxf")
    assert set(LAYERS) <= {layer.dxf.name for layer in document.layers}
    space = document.modelspace()
    layers = {entity.dxf.layer for entity in space}
    assert {"CONCRETO", "REFUERZO", "REFUERZO_CORTE", "COTAS", "TEXTOS", "CARTILLA"} <= layers
    heights = {round(entity.dxf.height, 6) for entity in space.query("TEXT")}
    assert PAPER_TEXT * SCALE in heights and PAPER_SMALL * SCALE in heights
