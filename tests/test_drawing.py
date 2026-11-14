"""Dibujo del refuerzo (v3 Fase 4B, D-126, D-132): vistas de cada tipo de zapata con las barras de su despiece, capas fijas
y una por diámetro, barra representativa por zona con su número y la leyenda, planta de geometría, textos a la escala
declarada, marcas de la cartilla, salidas JSON, SVG y DXF, y figuras en la memoria."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.detailing.schedule import BarRun, run_marks, schedule, splice_spans
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.detailing import combined_runs, footing_runs
from structurelab_rc.domain.footing.drawing import combined_views, footing_views, location_views
from structurelab_rc.drawing.model import (
    BAR_PREFIX,
    LAYERS,
    PAPER_SMALL,
    PAPER_TEXT,
    Circle,
    Dimension,
    Drawing,
    Polyline,
    Text,
    View,
    bar_layer,
    layer_style,
)
from structurelab_rc.drawing.svg import view_svg
from structurelab_rc.drawing.views import legend_text, numbered, zones
from structurelab_rc.engine import import_etabs_footings, report_file
from structurelab_rc.io.etabs.footings import LOCATION_SHEET, locations_by_joint
from structurelab_rc.io.etabs.importer import EtabsImportError
from structurelab_rc.io.etabs.xlsx import Table, read_table
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


@dataclass
class _Drawn:
    """Las vistas de la primera zapata de un proyecto, con sus corridas, sus marcas, la longitud comercial y la altura que
    separa las plantas inferior y superior."""

    views: list[View]
    runs: list[BarRun]
    marks: list[str]
    stock: float
    split: float

    def view(self, name: str) -> View:
        return next(view for view in self.views if view.name == name)


def _views(project: Project) -> _Drawn:
    assert project.detailing is not None and project.soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    drawing, stock = Drawing("prueba", SCALE), project.detailing.stock_length
    if project.footings:
        footing = project.footings[0]
        runs = footing_runs(basis, footing, project.soil)
        rows = schedule(footing.id, runs, stock)
        views = footing_views(drawing, footing, runs, (rows, stock))
        split = footing.h / 2
    else:
        combined = project.combined_footings[0]
        runs = combined_runs(basis, combined, project.soil)
        rows = schedule(combined.id, runs, stock)
        views = combined_views(drawing, combined, runs, (rows, stock))
        split = (combined.h if combined.beam is None else combined.total_height) / 2
    return _Drawn(views, runs, [row.mark for row in rows], stock, split)


def _bars(view: View) -> list[Polyline]:
    return [entity for entity in view.entities if isinstance(entity, Polyline) and entity.layer.startswith(BAR_PREFIX)]


@pytest.mark.parametrize(("name", "expected"), [
    ("zapata_centrica.json", ["geometria", "planta_inferior", "planta_superior", "corte_x", "corte_y", "cartilla"]),
    ("zapata_combinada.json", ["geometria", "planta_inferior", "planta_superior", "alzado", "corte_C1", "corte_C2", "cartilla"]),
    ("zapata_t_invertida_etabs.json",
     ["geometria", "planta_inferior", "planta_superior", "alzado", "corte_C15", "corte_C1659", "cartilla"]),
])
def test_views_of_each_footing_type(name: str, expected: list[str], tmp_path: Path) -> None:
    drawn = _views(_project(name, tmp_path))
    views = drawn.views
    assert [view.name for view in views] == expected
    # D-132: en planta, una barra representativa por zona, con un trazo por tramo empalmado.
    bottom = [run for run in drawn.runs if run.placement is not None and run.placement.along in ("x", "y")
              and run.placement.level <= drawn.split]
    expected_bars = sum(len(zones(run.placement.positions)) * len(splice_spans(run, drawn.stock)) for run in bottom
                        if run.placement is not None)
    assert len(_bars(drawn.view("planta_inferior"))) == expected_bars
    # Capas fijas y una capa por diámetro: la de cada barra.
    used = {entity.layer for view in views for entity in view.entities}
    assert {layer for layer in used if layer.startswith(BAR_PREFIX)} == {bar_layer(run.designation) for run in drawn.runs
                                                                          if run.placement is not None}
    assert {layer for layer in used if not layer.startswith(BAR_PREFIX)} <= set(LAYERS)
    texts = [entity for view in views for entity in view.entities if isinstance(entity, Text)]
    # Textos a la escala de impresión: títulos, rótulos y cotas; las letras del croquis de la cartilla, al 80 %.
    assert {round(text.height, 6) for text in texts} <= {PAPER_TEXT * SCALE, PAPER_SMALL * SCALE, 0.8 * PAPER_SMALL * SCALE}
    labels = " ".join(text.text for text in texts if text.layer == "TEXTOS")
    cartilla = {text.text for text in views[-1].entities if isinstance(text, Text)}
    for mark in drawn.marks:  # cada marca está en la leyenda de alguna vista y en la cartilla
        assert mark in labels, mark
        assert mark in cartilla, mark


def test_each_group_has_one_number_and_a_legend_line(tmp_path: Path) -> None:
    """D-132: el número de un grupo es el mismo en todas sus zonas y vistas; la leyenda de la planta tiene una línea por
    número, con la cantidad total del grupo, la barra, la separación y sus marcas."""
    drawn = _views(_project("zapata_combinada.json", tmp_path))
    marks = run_marks("ZC1", drawn.runs, drawn.stock)
    groups = numbered(drawn.runs, marks, drawn.stock)
    mesh = [item for item in groups if item.run.group == "malla inferior y"]
    assert len({item.number for item in mesh}) == 1
    plan = drawn.view("planta_inferior")
    texts = [entity.text for entity in plan.entities if isinstance(entity, Text)]
    bottom = {item.number for item in groups if item.place.along in ("x", "y") and item.place.level <= drawn.split}
    for number in bottom:
        line = legend_text([item for item in groups if item.number == number])
        assert line in texts, line
    # Un círculo por zona en la planta, con su número.
    circles = [entity for entity in plan.entities if isinstance(entity, Circle) and not entity.filled]
    zone_count = sum(len(zones(item.place.positions)) for item in groups
                     if item.place.along in ("x", "y") and item.place.level <= drawn.split)
    assert len(circles) == zone_count + len(bottom)  # los de las barras y los de la leyenda
    assert len(zones(mesh[0].place.positions)) == 3  # la malla y a los lados de los dos band y entre ellos


def test_spliced_bar_is_drawn_in_overlapping_pieces(tmp_path: Path) -> None:
    """D-132: la barra x inferior de la combinada (6.85 m, barras de 6 m) se dibuja en dos tramos traslapados."""
    drawn = _views(_project("zapata_combinada.json", tmp_path))
    run = next(run for run in drawn.runs if run.group == "malla inferior x")
    spans = splice_spans(run, drawn.stock)
    assert len(spans) == 2
    lap = spans[0][1] - spans[1][0]
    assert run.lap is not None and lap == pytest.approx(run.lap)
    texts = [entity.text for entity in drawn.view("planta_inferior").entities if isinstance(entity, Text)]
    assert f"traslapo {lap:.0f}" in texts


def test_geometry_plan_dimensions_columns_from_the_edges(tmp_path: Path) -> None:
    """D-132: la planta de geometría acota la base, las columnas desde los bordes, sus ejes y el recubrimiento."""
    project = _project("zapata_centrica.json", tmp_path)
    footing = project.footings[0]
    view = _views(project).view("geometria")
    column = footing.column
    dimensions = [entity.text for entity in view.entities if isinstance(entity, Dimension)]
    left = footing.lx / 2 + column.offset_x - column.cx / 2
    assert {f"{left:.0f}", f"{column.cx:.0f}", f"{footing.lx:.0f}", f"{footing.ly:.0f}"} <= set(dimensions)
    assert any(isinstance(entity, Polyline) and entity.layer == "COLUMNAS" for entity in view.entities)
    assert sum(1 for entity in view.entities if isinstance(entity, Polyline) and entity.layer == "EJES") == 2
    assert f"recubrimiento {footing.cover:.0f} mm" in {entity.text for entity in view.entities if isinstance(entity, Text)}
    # Las plantas de refuerzo no acotan la posición de la columna.
    plan = _views(project).view("planta_inferior")
    assert f"{left:.0f}" not in {entity.text for entity in plan.entities if isinstance(entity, Dimension)}


def test_isolated_section_cuts_every_perpendicular_bar(tmp_path: Path) -> None:
    project = _project("zapata_centrica.json", tmp_path)
    drawn = _views(project)
    across = sum(len(run.placement.positions) for run in drawn.runs if run.placement is not None and run.placement.along == "y")
    section = drawn.view("corte_x")
    assert sum(1 for entity in section.entities if isinstance(entity, Circle) and entity.filled) == across


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
    drawn = _views(_project("zapata_centrica.json", tmp_path))
    svg, aspect = view_svg(drawn.view("planta_inferior"), SCALE)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert aspect > 0
    color, _, weight = layer_style(bar_layer("#5"))
    assert f'stroke="{color}" stroke-width="{weight * SCALE:.1f}"' in svg


def test_report_writes_the_drawing(tmp_path: Path) -> None:
    report = report_file(PRUEBAS / "zapata_centrica.json", tmp_path)
    names = {path.name for path in report.files}
    assert {"zapata_centrica_drawing.json", "Z1_geometria.svg", "Z1_planta_inferior.svg", "Z1_corte_x.svg", "Z1_cartilla.svg"} <= names
    model = json.loads((tmp_path / "zapata_centrica_drawing.json").read_text(encoding="utf-8"))
    assert model["scale"] == SCALE and set(LAYERS) <= set(model["layers"])
    assert {bar_layer("#4"), bar_layer("#5")} <= set(model["layers"])
    assert [view["name"] for view in model["elements"]["Z1"]][:2] == ["geometria", "planta_inferior"]
    memoir = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    chapter = memoir[memoir.index("Despiece y cantidades"):]
    assert "Planta refuerzo inferior Z1" in chapter and "Cartilla de despiece Z1" in chapter and "Z1_corte_x.svg" in chapter


def test_dxf_has_the_layers_and_views(tmp_path: Path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    report_file(PRUEBAS / "zapata_combinada.json", tmp_path)
    document = ezdxf.readfile(tmp_path / "zapata_combinada.dxf")
    names = {layer.dxf.name for layer in document.layers}
    assert set(LAYERS) <= names
    space = document.modelspace()
    layers = {entity.dxf.layer for entity in space}
    assert {"CONCRETO", "COLUMNAS", "COTAS", "TEXTOS", "CARTILLA", "EJES"} <= layers
    bars = {layer for layer in layers if layer.startswith(BAR_PREFIX)}
    assert len(bars) >= 2 and bars <= names  # una capa por diámetro, cada una con su color
    assert len({document.layers.get(name).dxf.color for name in bars}) == len(bars)
    assert space.query("HATCH")  # barras cortadas rellenas
    heights = {round(entity.dxf.height, 6) for entity in space.query("TEXT")}
    assert PAPER_TEXT * SCALE in heights and PAPER_SMALL * SCALE in heights


LOCATIONS = ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Location.xlsx"


def _located(tmp_path: Path) -> Project:
    """zapata_centrica_etabs de pruebas importada con la tabla de coordenadas (D-130)."""
    data = import_etabs_footings(*REACTIONS, PRUEBAS / "zapata_centrica_etabs.json", LOCATIONS)[0]
    assert data is not None
    path = tmp_path / "etabs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_project(path)


def test_import_locates_each_footing_at_its_etabs_joint(tmp_path: Path) -> None:
    """D-130: cada zapata aislada lleva el nudo, el nivel y la posición en mm de la tabla de coordenadas, y su tipo."""
    project = _located(tmp_path)
    table = read_table(LOCATIONS, LOCATION_SHEET)
    rows = {row["UniqueName"]: row for row in table.rows}
    for footing in project.footings:
        assert footing.location is not None and footing.typology == footing.id.split("-")[0]
        row = rows[footing.location.joint]
        assert (footing.location.x, footing.location.y) == (pytest.approx(float(row["X"]) * 1000), pytest.approx(float(row["Y"]) * 1000))
        assert footing.location.story == row["Story"]


def test_missing_joint_or_units_in_the_location_table_are_errors() -> None:
    table = read_table(LOCATIONS, LOCATION_SHEET)
    with pytest.raises(EtabsImportError, match="no tiene los Unique Name no-existe"):
        locations_by_joint(table, ["15", "no-existe"])
    wrong = Table(table.headers, {**table.units, "X": "mm"}, table.rows)
    with pytest.raises(EtabsImportError, match="debe venir en m"):
        locations_by_joint(wrong, ["15"])


def test_location_plan_draws_every_footing_at_its_joint_by_story(tmp_path: Path) -> None:
    """D-130: una planta por nivel con el contorno de cada zapata centrado en su nudo (columna centrada), la columna, el
    tipo y el nudo, y el cuadro de tipologías con la cantidad de cada tipo."""
    project = _located(tmp_path)
    drawing = Drawing("prueba", SCALE)
    views = location_views(drawing, project.footings, project.combined_footings)
    stories = sorted({footing.location.story for footing in project.footings if footing.location is not None})
    assert [view.name for view in views] == [*(story.replace("'", "_").strip("_") for story in stories), "cuadro_tipologias"]
    plan = views[0]
    outlines = {(round(entity.points[0][0], 1), round(entity.points[0][1], 1), round(entity.points[2][0], 1))
                for entity in plan.entities if isinstance(entity, Polyline)}
    texts = [entity.text for entity in plan.entities if isinstance(entity, Text)]
    for footing in project.footings:
        location = footing.location
        assert location is not None
        corner = (round(location.x - footing.lx / 2, 1), round(location.y - footing.ly / 2, 1), round(location.x + footing.lx / 2, 1))
        assert corner in outlines, footing.id
        assert location.joint in texts
    table = [entity.text for entity in views[-1].entities if isinstance(entity, Text)]
    counts = {name: sum(1 for footing in project.footings if footing.typology == name) for name in ("Z1", "Z2", "Z3")}
    for name, count in counts.items():
        index = table.index(name)
        assert table[index + 4] == str(count)


def test_combined_footing_is_placed_by_its_columns_and_warns_if_they_disagree(tmp_path: Path) -> None:
    """D-130: la combinada se ubica por sus dos columnas; si la distancia de ETABS no cuadra con la declarada, avisa."""
    data = import_etabs_footings(*REACTIONS, PRUEBAS / "zapata_combinada_etabs.json", LOCATIONS)[0]
    assert data is not None
    footing = data["combined_footings"][0]
    first, second = footing["columns"]
    second["location"] = {**first["location"], "x": first["location"]["x"] + second["x"] - first["x"],
                          "y": first["location"]["y"] + second["y"] - first["y"]}
    data["combined_footings"] = [footing]
    path = tmp_path / "combinada.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    combined = load_project(path).combined_footings[0]
    views = location_views(Drawing("prueba", SCALE), [], [combined])
    texts = [entity.text for entity in views[0].entities if isinstance(entity, Text)]
    assert combined.id in texts and not any(text.startswith("ADVERTENCIA") for text in texts)
    outline = next(entity for entity in views[0].entities if isinstance(entity, Polyline))
    centre_x = first["location"]["x"] - first["x"]
    assert (outline.points[0][0] + outline.points[2][0]) / 2 == pytest.approx(centre_x)
    second["location"]["x"] += 500.0
    path.write_text(json.dumps(data), encoding="utf-8")
    views = location_views(Drawing("prueba", SCALE), [], [load_project(path).combined_footings[0]])
    assert any(entity.text.startswith("ADVERTENCIA") for entity in views[0].entities if isinstance(entity, Text))


def test_run_writes_the_location_plan_outside_the_memoir(tmp_path: Path) -> None:
    """D-130: run con etabs_files.locations escribe la planta por nivel y el cuadro (SVG y modelo de dibujo); la memoria
    no la lleva."""
    assert main(["run", str(PRUEBAS / "zapata_centrica_etabs.json"), "--output", str(tmp_path)]) in (0, 1)
    model = json.loads((tmp_path / "proyecto_drawing.json").read_text(encoding="utf-8"))
    names = [view["name"] for view in model["elements"]["localizacion"]]
    assert names[-1] == "cuadro_tipologias" and len(names) >= 2
    assert all((tmp_path / f"localizacion_{name}.svg").exists() for name in names)
    assert "localizacion" not in (tmp_path / "memoria.txt").read_text(encoding="utf-8").lower()
