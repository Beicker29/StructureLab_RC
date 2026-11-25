"""Dibujo del refuerzo (v3 Fase 4B, D-126, D-132, D-150): vistas de cada tipo de zapata con las barras de su despiece, las
capas de la plantilla y una por diámetro, barra representativa por zona con su rótulo (cantidad, barra, separación,
longitud de la cartilla y marcas), planta de geometría, textos a la escala declarada, medidas en metros, salidas JSON, SVG
y DXF sobre la plantilla, y figuras en la memoria."""

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.detailing.schedule import BarRun, ScheduleRow, run_marks, schedule, splice_spans
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.detailing import SKIN, combined_runs, face_envelope, footing_runs
from structurelab_rc.domain.footing.drawing import combined_views, footing_views, location_views
from structurelab_rc.drawing.model import (
    AXES,
    BAR_DESIGNATIONS,
    BAR_PREFIX,
    COLUMN_FILL,
    DISTRIBUTION,
    FOOTING,
    LABELS,
    LAYERS,
    OPTIONAL_LAYERS,
    PAPER_GAP,
    PAPER_SMALL,
    PAPER_SUBTITLE,
    PAPER_TEXT,
    PAPER_TITLE,
    PILE_CAP,
    PILES,
    Circle,
    Dimension,
    Drawing,
    Leader,
    Polyline,
    Text,
    View,
    bar_layer,
    layer_style,
    metres,
)
from structurelab_rc.drawing.svg import view_svg
from structurelab_rc.drawing.views import drawn_is_cut, label_text, numbered, zones
from structurelab_rc.engine import import_etabs_footings, report_file
from structurelab_rc.io.etabs.footings import LOCATION_SHEET, locations_by_joint
from structurelab_rc.io.etabs.importer import EtabsImportError
from structurelab_rc.io.etabs.xlsx import Table, read_table
from structurelab_rc.model.loader import ProjectLoadError, load_project, validate_input
from structurelab_rc.model.project import Project
from structurelab_rc.setup import dxf_template, load_engine

ROOT = Path(__file__).parent.parent
REACTIONS = (frozen("etabs", "zapatas", "Joint Reactions - Servicio.xlsx"),
             frozen("etabs", "zapatas", "Joint Reactions - Ultimas.xlsx"))
BARS = load_engine().bars
SCALE = 50.0


def _project(name: str, tmp_path: Path) -> Project:
    path = frozen("nsr_10", "zapatas", name)
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
    rows: list[ScheduleRow]

    def view(self, name: str) -> View:
        return next(view for view in self.views if view.name == name)


def _views(project: Project) -> _Drawn:
    assert project.detailing is not None and project.soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    drawing, stock = Drawing("prueba", SCALE), project.detailing.stock_length
    if project.footings:
        footing = project.footings[0]
        runs = footing_runs(basis, footing, face_envelope(footing, project.soil))
        rows = schedule(footing.id, runs, stock)
        views = footing_views(drawing, footing, runs, (rows, stock), 1)
        split = footing.h / 2
    else:
        combined = project.combined_footings[0]
        runs = combined_runs(basis, combined, project.soil)
        rows = schedule(combined.id, runs, stock)
        views = combined_views(drawing, combined, runs, (rows, stock), 1)
        split = (combined.h if combined.beam is None else combined.total_height) / 2
    return _Drawn(views, runs, [row.mark for row in rows], stock, split, rows)


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
    # D-132: en planta, una barra representativa por zona, con un trazo por tramo empalmado; el refuerzo superficial va en
    # las caras laterales y no sale en planta (D-158).
    bottom = [run for run in drawn.runs if run.placement is not None and run.placement.along in ("x", "y")
              and run.placement.level <= drawn.split and not run.group.startswith(SKIN)]
    expected_bars = sum(len(zones(run.placement.positions)) * len(splice_spans(run, drawn.stock)) for run in bottom
                        if run.placement is not None)
    assert len(_bars(drawn.view("planta_inferior"))) == expected_bars
    # Capas fijas y una capa por diámetro: la de cada barra.
    used = {entity.layer for view in views for entity in view.entities}
    assert {layer for layer in used if layer.startswith(BAR_PREFIX)} == {bar_layer(run.designation) for run in drawn.runs
                                                                          if run.placement is not None}
    assert {layer for layer in used if not layer.startswith(BAR_PREFIX)} <= set(LAYERS)
    texts = [entity for view in views for entity in view.entities if isinstance(entity, Text)]
    # Textos a la escala de impresión: títulos de las vistas, rótulos y cotas; las letras del croquis de la cartilla, al 80 %.
    assert {round(text.height, 6) for text in texts} <= {PAPER_TEXT * SCALE, PAPER_SUBTITLE * SCALE, PAPER_SMALL * SCALE,
                                                          0.8 * PAPER_SMALL * SCALE}
    leaders = [entity.text for view in views for entity in view.entities if isinstance(entity, Leader)]
    labels = " ".join([*(text.text for text in texts if text.layer == LABELS), *leaders])
    cartilla = {text.text for text in views[-1].entities if isinstance(text, Text)}
    for mark in drawn.marks:  # cada marca está en el rótulo de alguna vista y en la cartilla
        assert mark in labels, mark
        assert mark in cartilla, mark


def test_labels_carry_the_count_spacing_and_the_cartilla_length(tmp_path: Path) -> None:
    """D-150: cada zona de la planta lleva un rótulo con su cantidad, la barra, la separación, la longitud de corte de la
    cartilla (en m) y sus marcas; cada grupo de un corte, un rótulo con una línea de llamada a cada barra."""
    drawn = _views(_project("zapata_combinada.json", tmp_path))
    marks = run_marks("ZC1", drawn.runs, drawn.stock)
    groups = numbered(drawn.runs, marks, drawn.stock, drawn.rows)
    lengths = {row.mark: row.piece.cut_length for row in drawn.rows}
    mesh = next(item for item in groups if item.run.group == "malla inferior y")
    plan = [entity.text for entity in drawn.view("planta_inferior").entities if isinstance(entity, Text)]
    zone_list = zones(mesh.place.positions)
    assert len(zone_list) == 3  # la malla y a los lados de los dos band y entre ellos
    for zone in zone_list:  # con dos barras o menos, sin separación
        spacing = f" C/{metres(min(b - a for a, b in zip(zone, zone[1:], strict=False)))}" if len(zone) > 2 else ""
        expected = (f"{len(zone)}{mesh.run.designation}{spacing} L={metres(lengths[mesh.marks[0]])} "
                    f"({', '.join(mesh.marks)})")
        assert expected in plan
        assert label_text([mesh], len(zone), zone) == expected
    leaders = [entity for entity in drawn.view("alzado").entities if isinstance(entity, Leader)]
    assert leaders and all(entity.targets for entity in leaders)
    assert len({entity.text for entity in leaders}) == len(leaders)  # un rótulo por grupo


def test_spliced_label_lists_the_length_of_each_mark(tmp_path: Path) -> None:
    """D-150: un grupo empalmado nombra la longitud de corte de cada una de sus marcas, en su orden."""
    drawn = _views(_project("zapata_combinada.json", tmp_path))
    groups = numbered(drawn.runs, run_marks("ZC1", drawn.runs, drawn.stock), drawn.stock, drawn.rows)
    spliced = next(item for item in groups if item.run.group == "malla inferior x")
    assert len(spliced.marks) > 1
    text = label_text([spliced])
    assert "L=" + "+".join(metres(length) for length in spliced.lengths) in text
    assert text.endswith(f"({', '.join(spliced.marks)})")


def test_metres_writes_lengths_like_the_rebar_drawings() -> None:
    """D-150: dos decimales (tres si no es múltiplo de 1 cm) y sin el cero inicial."""
    assert [metres(value) for value in (3400.0, 150.0, 75.0, 125.0, 6650.0, 1270.0)] == ["3.40", ".15", ".075", ".125", "6.65", "1.27"]


def test_spliced_bar_is_drawn_in_overlapping_pieces(tmp_path: Path) -> None:
    """D-132: la barra x inferior de la combinada (6.85 m, barras de 6 m) se dibuja en dos tramos traslapados."""
    drawn = _views(_project("zapata_combinada.json", tmp_path))
    run = next(run for run in drawn.runs if run.group == "malla inferior x")
    spans = splice_spans(run, drawn.stock)
    assert len(spans) == 2
    lap = spans[0][1] - spans[1][0]
    assert run.lap is not None and lap == pytest.approx(run.lap)
    texts = [entity.text for entity in drawn.view("planta_inferior").entities if isinstance(entity, Text)]
    assert f"traslapo {metres(lap)}" in texts


def test_geometry_plan_dimensions_columns_from_the_edges(tmp_path: Path) -> None:
    """D-132: la planta de geometría acota la base, las columnas desde los bordes, sus ejes y el recubrimiento."""
    project = _project("zapata_centrica.json", tmp_path)
    footing = project.footings[0]
    view = _views(project).view("geometria")
    column = footing.column
    dimensions = [entity.text for entity in view.entities if isinstance(entity, Dimension)]
    left = footing.lx / 2 + column.offset_x - column.cx / 2
    assert {metres(left), metres(column.cx), metres(footing.lx), metres(footing.ly)} <= set(dimensions)
    assert any(isinstance(entity, Polyline) and entity.layer == COLUMN_FILL and entity.filled for entity in view.entities)
    assert sum(1 for entity in view.entities if isinstance(entity, Polyline) and entity.layer == AXES) == 2
    assert f"recubrimiento {metres(footing.cover)}" in {entity.text for entity in view.entities if isinstance(entity, Text)}
    # D-158: las plantas de refuerzo acotan la columna como el plano de referencia: su tamaño y la distancia de su cara al
    # borde +X y al borde más cercano en Y.
    plan = _views(project).view("planta_inferior")
    right = footing.lx / 2 - (column.offset_x + column.cx / 2)
    plan_dimensions = {entity.text for entity in plan.entities if isinstance(entity, Dimension)}
    assert {metres(column.cx), metres(column.cy), metres(right)} <= plan_dimensions


def test_isolated_section_cuts_every_perpendicular_bar(tmp_path: Path) -> None:
    project = _project("zapata_centrica.json", tmp_path)
    drawn = _views(project)
    across = sum(len(run.placement.positions) for run in drawn.runs if run.placement is not None and run.placement.along == "y")
    section = drawn.view("corte_x")
    dots = [entity for entity in section.entities if isinstance(entity, Circle) and entity.filled]
    assert len(dots) == across
    assert all(entity.radius == pytest.approx(0.293 * SCALE) for entity in dots)  # tamaño fijo en papel (D-150)


def test_dowel_hooks_point_into_the_column(tmp_path: Path) -> None:
    """D-158: en el corte, el gancho del pie de cada pasador se dibuja hacia dentro de la columna, con la pata de la
    cartilla."""
    drawn = _views(_project("zapata_centrica.json", tmp_path))
    dowels = [bar.points for bar in _bars(drawn.view("corte_x")) if len(bar.points) == 3  # noqa: PLR2004 - pie + fuste
              and bar.points[0][1] == bar.points[1][1] and bar.points[1][0] == bar.points[2][0]
              and bar.points[2][1] > bar.points[1][1]]
    assert len(dowels) == 2  # noqa: PLR2004 - una barra a cada lado de la columna
    centre = sum(points[1][0] for points in dowels) / 2
    for points in dowels:
        assert abs(points[0][0] - centre) < abs(points[1][0] - centre)
        assert abs(points[0][0] - points[1][0]) > 0


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
    data = json.loads((frozen("nsr_10", "zapatas", "zapata_centrica.json")).read_text(encoding="utf-8"))
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
    output = tmp_path / "zapata_centrica"  # los archivos llevan el nombre del caso (la carpeta de salida)
    report = report_file(frozen("nsr_10", "zapatas", "zapata_centrica.json"), output)
    names = {path.name for path in report.files}
    assert {"zapata_centrica_drawing.json", "Z1_geometria.svg", "Z1_planta_inferior.svg", "Z1_corte_x.svg", "Z1_cartilla.svg"} <= names
    model = json.loads((output / "zapata_centrica_drawing.json").read_text(encoding="utf-8"))
    assert model["scale"] == SCALE and set(LAYERS) <= set(model["layers"])
    assert {bar_layer("#4"), bar_layer("#5")} <= set(model["layers"])
    assert [view["name"] for view in model["elements"]["Z1"]][:2] == ["geometria", "planta_inferior"]
    assert model["titles"]["Z1"].startswith("Z1 h=")
    memoir = (output / "memoria.txt").read_text(encoding="utf-8")
    chapter = memoir[memoir.index("Despiece y cantidades"):]
    assert "Planta refuerzo inferior Z1" in chapter and "Cartilla de despiece Z1" in chapter and "Z1_corte_x.svg" in chapter


def test_dxf_uses_the_template(tmp_path: Path) -> None:
    """D-150: el DXF sale de la plantilla, en metros: sus capas y estilos, entidades solo en capas de la plantilla, cotas
    DIMENSION que miden lo del modelo, rótulos MULTILEADER, barras cortadas con el bloque BARRA, el título del elemento y
    sin los cortes transversales de la combinada."""
    ezdxf = pytest.importorskip("ezdxf")
    output = tmp_path / "zapata_combinada"
    report_file(frozen("nsr_10", "zapatas", "zapata_combinada.json"), output)
    document = ezdxf.readfile(output / "zapata_combinada.dxf")
    assert document.header["$INSUNITS"] == 6
    template = ezdxf.read(io.StringIO(dxf_template()))
    names = {layer.dxf.name for layer in template.layers}
    space = document.modelspace()
    assert {entity.dxf.layer for entity in space} <= names
    assert {style.dxf.name for style in template.dimstyles} <= {style.dxf.name for style in document.dimstyles}
    model = json.loads((output / "zapata_combinada_drawing.json").read_text(encoding="utf-8"))
    drawn = [view for view in model["elements"]["ZC1"] if view["dxf"]]
    expected = sorted(entity["text"] for view in drawn for entity in view["entities"]
                      if entity["type"] == "dimension" and entity["layer"] != DISTRIBUTION)
    dimensions = [entity for entity in space.query("DIMENSION") if entity.dxf.layer != DISTRIBUTION]
    assert {entity.dxf.dimstyle for entity in dimensions} == {"DIM-50"}
    measured = sorted(metres(entity.get_measurement() * 1000) for entity in dimensions)
    assert measured == expected
    # D-158: las líneas de distribución son cotas sin texto con el estilo DIM-75 y flechas cerradas, como la referencia.
    lines = [entity for entity in space.query("DIMENSION") if entity.dxf.layer == DISTRIBUTION]
    assert lines and {entity.dxf.dimstyle for entity in lines} == {"DIM-75"} and {entity.dxf.text for entity in lines} == {" "}
    assert all(entity.override().get("dimsah") == 1 for entity in lines)
    leaders = sum(1 for view in drawn for entity in view["entities"] if entity["type"] == "leader")
    assert len(space.query("MULTILEADER")) == leaders > 0
    # D-158: cada rótulo con la flecha cerrada (sin bloque), del mismo tamaño en la entidad y en el contexto: 0.125 m a
    # 1:50, el del estilo de la plantilla.
    style = document.mleader_styles.get("LEADER")
    for entity in space.query("MULTILEADER"):
        assert not entity.dxf.hasattr("arrow_head_handle")
        assert entity.context.arrow_head_size == entity.dxf.arrow_head_size == pytest.approx(style.dxf.arrow_head_size)
    inserts = space.query("INSERT")
    assert inserts and {entity.dxf.name for entity in inserts} == {"BARRA"}
    assert all(entity.dxf.layer.startswith(BAR_PREFIX) for entity in inserts)
    texts = {entity.dxf.text for entity in space.query("TEXT")}
    assert model["titles"]["ZC1"] in texts and "ESC 1:50" in texts
    assert not any(text.startswith("CORTE TRANSVERSAL") for text in texts)
    heights = {round(entity.dxf.height * 1000, 6) for entity in space.query("TEXT")}
    assert {PAPER_TITLE * SCALE, PAPER_SMALL * SCALE} <= heights


def _dxf_sizes(path: Path, scale: float, tmp_path: Path) -> dict[str, list[float]]:
    """Los tamaños de papel del DXF de un ejemplo dibujado a la escala dada: alturas de texto, flechas, separaciones y
    quiebres de los rótulos, tamaños de los estilos de cota usados, escala del tipo de línea y de los puntos."""
    ezdxf = pytest.importorskip("ezdxf")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["drawing"]["scale"] = scale
    source = tmp_path / f"escala_{scale:g}.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / f"escala_{scale:g}"
    report_file(source, output)
    document = ezdxf.readfile(output / f"{source.stem}.dxf")
    space = document.modelspace()
    leaders = list(space.query("MULTILEADER"))
    styles = sorted({entity.dxf.dimstyle for entity in space.query("DIMENSION")})
    dimvars = ("dimtxt", "dimasz", "dimexe", "dimexo", "dimgap", "dimdli", "dimfxl", "dimdle", "dimcen")
    return {
        "texto": sorted(entity.dxf.height for entity in space.query("TEXT")),
        "mtext": sorted(entity.dxf.char_height for entity in space.query("MTEXT")),
        "flecha": [entity.context.arrow_head_size for entity in leaders] + [entity.dxf.arrow_head_size for entity in leaders],
        "rótulo": [entity.context.char_height for entity in leaders] + [entity.context.landing_gap_size for entity in leaders]
                  + [entity.dxf.dogleg_length for entity in leaders],
        "cotas": [document.dimstyles.get(name).dxf.get(key) for name in styles for key in dimvars],
        "trazos": sorted({entity.dxf.get("ltscale", 1.0) for entity in space.query("LWPOLYLINE LINE DIMENSION")}),
        "puntos": sorted(entity.dxf.xscale for entity in space.query("INSERT")),
    }


@pytest.mark.parametrize("name", ["zapata_centrica.json", "zapata_combinada.json"])
def test_drawing_model_sizes_follow_the_scale(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-158: en el modelo de dibujo (y el SVG), a 1:100 cada altura de texto, radio de punto y separación de cota es el
    doble que a 1:50."""
    project = _project(name, tmp_path)
    base = _views(project).views
    model = Drawing
    monkeypatch.setitem(globals(), "Drawing", lambda title, _: model(title, 2 * SCALE))
    double = _views(project).views
    for first, second in zip(base, double, strict=True):
        assert len(first.entities) == len(second.entities), first.name
        for a, b in zip(first.entities, second.entities, strict=True):
            for size in ("height", "radius", "offset"):
                if hasattr(a, size):
                    assert getattr(b, size) == pytest.approx(2 * getattr(a, size)), (first.name, a)


@pytest.mark.parametrize("factor", [2.0, 0.5])
def test_dxf_sizes_follow_the_drawing_scale(factor: float, tmp_path: Path) -> None:
    """D-158: cada tamaño de papel del DXF sigue la escala: a 1:100 es el doble que a 1:50 y a 1:25 la mitad (textos,
    flechas, separaciones y quiebres de los rótulos, trazos, puntos de las barras y estilos de cota, rehechos desde DIM-50
    y DIM-75: el DIM-25 de la plantilla no es proporcional); a 1:50, los de la plantilla."""
    path = frozen("nsr_10", "zapatas", "zapata_combinada.json")
    base, scaled = _dxf_sizes(path, SCALE, tmp_path), _dxf_sizes(path, factor * SCALE, tmp_path)
    assert base["trazos"] == [1.0] and base["flecha"] and base["cotas"]
    for key, values in base.items():
        assert len(scaled[key]) == len(values), key
        assert scaled[key] == pytest.approx([factor * value for value in values]), key


@pytest.mark.parametrize(("element", "name", "layer"), [
    ("zapatas", "zapata_centrica.json", FOOTING), ("zapatas", "zapata_combinada.json", FOOTING),
    ("zapatas", "zapata_combinada_trapecio.json", FOOTING), ("cabezales", "cabezal_tres_pilotes.json", PILE_CAP),
])
def test_concrete_outline_has_its_own_layer(element: str, name: str, layer: str, tmp_path: Path) -> None:
    """D-166: el contorno del concreto va en la capa ZAPATA (aislada, combinada y T) o CABEZAL, no en la capa 0, que
    queda para las columnas y sus arranques; cada vista con concreto lo lleva."""
    output = tmp_path / "salida"
    report_file(frozen("nsr_10", element, name), output)
    model = json.loads((output / "salida_drawing.json").read_text(encoding="utf-8"))
    other = PILE_CAP if layer == FOOTING else FOOTING
    for views in model["elements"].values():
        for view in views:
            layers = {entity["layer"] for entity in view["entities"]}
            assert other not in layers, view["name"]
            if view["name"] not in ("cartilla", "cuadro_pilotes"):
                assert layer in layers, view["name"]


def test_inverted_t_outline_is_on_the_footing_layer(tmp_path: Path) -> None:
    """D-166: la T invertida (base, alma y corte en T) también va en la capa ZAPATA."""
    for view in _views(_project("zapata_t_invertida_etabs.json", tmp_path)).views:
        layers = {entity.layer for entity in view.entities}
        assert PILE_CAP not in layers and (view.name == "cartilla" or FOOTING in layers), view.name


def _cap_model(name: str, tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """El cabezal congelado de nsr_10 (su JSON) y las vistas de su dibujo por nombre."""
    path = frozen("nsr_10", "cabezales", name)
    output = tmp_path / "salida"
    report_file(path, output)
    model = json.loads((output / "salida_drawing.json").read_text(encoding="utf-8"))
    cap = json.loads(path.read_text(encoding="utf-8"))["pile_caps"][0]
    return cap, {view["name"]: view for view in next(iter(model["elements"].values()))}


def _texts(view: dict[str, Any], kind: str = "text") -> list[str]:
    return [entity["text"] for entity in view["entities"] if entity["type"] == kind]


def _top_chain(view: dict[str, Any], top: float) -> list[str]:
    return sorted(e["text"] for e in view["entities"] if e["type"] == "dimension" and e["start"][1] == e["end"][1] == top
                  and abs(e["offset"]) == pytest.approx(PAPER_GAP * SCALE))


def test_pile_cap_plans_show_the_piles_like_the_reference(tmp_path: Path) -> None:
    """D-166: los pilotes a trazos en todas las plantas, con nombre solo en las dos de geometría. La de bordes lleva la
    cota del diámetro y arriba la cadena de los bordes de los pilotes; la de ejes, arriba la de sus centros desde los
    bordes del cabezal, y abajo la de los ejes de las columnas."""
    cap, views = _cap_model("cabezal_pilotes.json", tmp_path)
    names = {pile["id"] for pile in cap["piles"]}
    size = cap["pile"]["size"]
    for name, view in views.items():
        if name.startswith(("geometria", "planta_")):
            piles = [e for e in view["entities"] if e["type"] == "circle" and e["layer"] == PILES and e["dashed"]]
            assert len(piles) == len(names), name
            assert bool(names & set(_texts(view))) == name.startswith("geometria"), name
    edges, axes = views["geometria"], views["geometria_ejes"]
    assert edges["title"].endswith("bordes") and axes["title"].endswith("ejes")
    diameters = [e for e in edges["entities"] if e["type"] == "dimension" and e["kind"] == "diameter"]
    assert [e["text"] for e in diameters] == [f"Ø{metres(size)}"]
    x0, x1, top = -cap["lx"] / 2, cap["lx"] / 2, cap["ly"] / 2
    centres = sorted({round(pile["x"], 1) for pile in cap["piles"]})
    faces = sorted(x + side * size / 2 for x in centres for side in (-1, 1))
    assert _top_chain(axes, top) == sorted(metres(b - a) for a, b in zip([x0, *centres], [*centres, x1], strict=True))
    assert _top_chain(edges, top) == sorted(metres(b - a) for a, b in zip([x0, *faces], [*faces, x1], strict=True))
    column = cap["columns"][0].get("offset_x", 0.0)
    bottom = [e["text"] for e in axes["entities"] if e["type"] == "dimension" and e["start"][1] == e["end"][1] == -top]
    assert metres(column - x0) in bottom and metres(x1 - column) in bottom


def test_clipped_pile_cap_dimensions_each_cut_corner(tmp_path: Path) -> None:
    """D-166: con esquinas recortadas, la planta de geometría acota lo que quita cada recorte en sus dos bordes, y el
    recubrimiento sigue el contorno real."""
    cap, views = _cap_model("cabezal_tres_pilotes.json", tmp_path)
    geometry = views["geometria"]
    texts = _texts(geometry, "dimension")
    for clip in cap["clipped_corners"]:
        assert metres(clip["along_x"]) in texts and metres(clip["along_y"]) in texts
    cover = [e for e in geometry["entities"] if e["type"] == "polyline" and e["layer"] == DISTRIBUTION and e["closed"]]
    assert len(cover) == 1 and len(cover[0]["points"]) == 4 + len(cap["clipped_corners"])


def test_pile_cap_sections_show_the_piles_below_the_cap(tmp_path: Path) -> None:
    """D-166: en los cortes, los pilotes bajo el cabezal (el empotramiento a trazos), con el empotramiento y el
    recubrimiento inferior acotados; las cotas de las zonas y el largo total quedan debajo de los pilotes."""
    cap, views = _cap_model("cabezal_pilotes.json", tmp_path)
    for name in ("corte_x", "corte_y"):
        entities = views[name]["entities"]
        piles = [e for e in entities if e["layer"] == PILES]
        lowest = min(point[1] for e in piles for point in (e.get("points") or [e["start"], e["end"]]))
        assert lowest < 0 and any(e.get("dashed") for e in piles)
        texts = _texts(views[name], "dimension")
        assert metres(cap["pile"]["embedment"]) in texts and metres(cap["bottom_cover"]) in texts
        total = metres(cap["lx"] if name == "corte_x" else cap["ly"])
        assert all(e["start"][1] <= lowest for e in entities if e["type"] == "dimension" and e["text"] == total)


def test_pile_cap_has_a_pile_table(tmp_path: Path) -> None:
    """D-166: el cuadro de pilotes con el nombre, el centro (x, y), la sección y el empotramiento de cada pilote."""
    cap, views = _cap_model("cabezal_pilotes.json", tmp_path)
    texts = _texts(views["cuadro_pilotes"])
    for pile in cap["piles"]:
        assert pile["id"] in texts and metres(pile["x"]) in texts and metres(pile["y"]) in texts
    assert f"Ø{metres(cap['pile']['size'])}" in texts and metres(cap["pile"]["embedment"]) in texts


def test_location_plan_draws_the_piles_of_each_pile_cap(tmp_path: Path) -> None:
    """D-166: en la planta de localización, el cabezal con su contorno real (con recortes) en la capa CABEZAL y cada
    pilote a trazos."""
    data = json.loads(frozen("nsr_10", "cabezales", "cabezal_tres_pilotes.json").read_text(encoding="utf-8"))
    cap = data["pile_caps"][0]
    cap["location"] = {"x": 10000.0, "y": 5000.0, "story": "Base", "joint": "7"}
    path = tmp_path / "ubicado.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "salida"
    report_file(path, output)
    model = json.loads((output / "salida_drawing.json").read_text(encoding="utf-8"))
    plans = [view for view in model["elements"]["localizacion"] if view["name"] != "cuadro_tipologias"]
    entities = [entity for view in plans for entity in view["entities"]]
    outlines = [entity for entity in entities if entity["layer"] == PILE_CAP]
    assert len(outlines) == 1 and len(outlines[0]["points"]) == 4 + len(cap["clipped_corners"])
    assert sum(1 for entity in entities if entity["layer"] == PILES and entity.get("dashed")) == len(cap["piles"])


@pytest.mark.parametrize(("name", "word"), [("zapata_combinada_trapecio.json", "trapecio"),
                                            ("zapata_combinada_planta_l.json", "T/L"), ("zapata_combinada_planta_i.json", "I")])
def test_location_plan_places_non_rectangular_combined_footings(name: str, word: str, tmp_path: Path) -> None:
    """D-170: la combinada trapezoidal o en planta T, L o I entra en la planta de localización con su contorno real en ejes
    globales (los mismos vértices de su planta), y el cuadro de tipologías dice la forma, el largo y los anchos."""
    data = json.loads(frozen("nsr_10", "zapatas", name).read_text(encoding="utf-8"))
    footing = data["combined_footings"][0]
    for index, column in enumerate(footing["columns"]):
        column["location"] = {"x": 20000.0 + 5000.0 * index, "y": 8000.0, "story": "Base", "joint": str(index + 1)}
    path = tmp_path / "ubicada.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    combined = load_project(path).combined_footings[0]
    output = tmp_path / "salida"
    report_file(path, output)
    model = json.loads((output / "salida_drawing.json").read_text(encoding="utf-8"))
    views = model["elements"]["localizacion"]
    outlines = [e for view in views for e in view["entities"] if e["type"] == "polyline" and e["layer"] == FOOTING]
    assert len(outlines) == 1 and len(outlines[0]["points"]) == len(combined.outline)
    table = next(view for view in views if view["name"] == "cuadro_tipologias")
    assert any(text.startswith(f"{word} ") for text in _texts(table))


def test_template_layers_match_the_drawing_model() -> None:
    """D-150: la plantilla trae cada capa del modelo de dibujo con su color ACI (drawing/model.py es la fuente)."""
    ezdxf = pytest.importorskip("ezdxf")
    template = ezdxf.read(io.StringIO(dxf_template()))
    for name in [*LAYERS, *OPTIONAL_LAYERS, *(bar_layer(designation) for designation in BAR_DESIGNATIONS)]:
        assert template.layers.get(name).color == layer_style(name)[1], name
    assert "BARRA" in template.blocks and "DIM-50" in template.dimstyles


LOCATIONS = frozen("etabs", "zapatas", "Joint Location.xlsx")


def _located(tmp_path: Path) -> Project:
    """zapata_centrica_etabs de pruebas importada con la tabla de coordenadas (D-130)."""
    data = import_etabs_footings(*REACTIONS, frozen("nsr_10", "zapatas", "zapata_centrica_etabs.json"), LOCATIONS)[0]
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
    data = import_etabs_footings(*REACTIONS, frozen("nsr_10", "zapatas", "zapata_combinada_etabs.json"), LOCATIONS)[0]
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
    output = tmp_path / "zapata_centrica_etabs"
    assert main(["run", str(frozen("nsr_10", "zapatas", "zapata_centrica_etabs.json")), "--output", str(output)]) in (0, 1)
    model = json.loads((output / "zapata_centrica_etabs_drawing.json").read_text(encoding="utf-8"))  # con el nombre del caso
    names = [view["name"] for view in model["elements"]["localizacion"]]
    assert names[-1] == "cuadro_tipologias" and len(names) >= 2
    assert all((output / f"localizacion_{name}.svg").exists() for name in names)
    assert "localizacion" not in (output / "memoria.txt").read_text(encoding="utf-8").lower()


def _length(polyline: Polyline) -> float:
    return sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(polyline.points, polyline.points[1:], strict=False))


@pytest.mark.parametrize("name", ["zapata_centrica.json", "zapata_combinada.json", "zapata_t_invertida_etabs.json"])
def test_each_bar_label_is_linked_to_a_bar_that_measures_the_cartilla_length(name: str, tmp_path: Path) -> None:
    """D-158, D-166: cada barra dibujada con A, B y C de su pieza mide la longitud de corte (la del .dli) y lleva su marca;
    cada rótulo, en planta (Text) o en un corte (Leader), lleva las marcas de sus L. Con una sola L de una pieza que se
    mide por fuera, hay una polilínea de esa marca (en la vista o, en un corte, en la planta) que mide esa L."""
    drawn = _views(_project(name, tmp_path))
    pieces = {row.mark: row.piece for row in drawn.rows}
    bars: dict[tuple[str, str], Polyline] = {}
    for view in drawn.views:
        for entity in view.entities:
            if isinstance(entity, Polyline) and entity.mark:
                assert entity.layer.startswith(BAR_PREFIX)
                assert _length(entity) == pytest.approx(pieces[entity.mark].cut_length, abs=0.5)
                bars.setdefault((view.name, entity.mark), entity)
                bars.setdefault(("", entity.mark), entity)
    linked = {"planta": 0, "corte": 0}
    for view in drawn.views:
        for entity in view.entities:
            if not isinstance(entity, (Text, Leader)) or not entity.marks:
                continue
            assert entity.marks == tuple(entity.text.rsplit("(", 1)[1].rstrip(")").split(", "))
            if len(entity.marks) != 1 or not drawn_is_cut(pieces[entity.marks[0]]):
                continue
            mark = entity.marks[0]
            bar = bars.get((view.name, mark), bars.get(("", mark)))
            assert bar is not None, (view.name, entity.text)
            assert f"L={metres(_length(bar))}" in entity.text
            linked["planta" if view.name.startswith("planta_") else "corte"] += 1
    assert linked["planta"] and linked["corte"]


def test_plans_follow_the_reference_drawing(tmp_path: Path) -> None:
    """D-158: cada zona con su línea de distribución (cota sin texto entre sus límites) y la marca de la barra; las zonas
    divididas con líneas grises y acotadas en cadena que suma el largo; el ancho total arriba y el largo a la izquierda; el
    título de la vista "REFUERZO INFERIOR"."""
    project = _project("zapata_combinada.json", tmp_path)
    footing = project.combined_footings[0]
    plan = _views(project).view("planta_inferior")
    lines = [entity for entity in plan.entities if isinstance(entity, Dimension) and entity.layer == DISTRIBUTION]
    marks = [entity for entity in plan.entities if isinstance(entity, Circle) and entity.filled]
    assert lines and len(marks) == len(lines) and all(line.text == "" for line in lines)
    divisions = [entity for entity in plan.entities if isinstance(entity, Polyline) and entity.color is not None]
    assert divisions and all(entity.dashed and entity.layer == DISTRIBUTION for entity in divisions)
    bottom = -footing.ly / 2  # la cadena de las zonas de las barras transversales va sobre el borde −Y
    chain = [entity for entity in plan.entities if isinstance(entity, Dimension) and entity.layer != DISTRIBUTION
             and abs(entity.start[1] - bottom) < 1e-6 and abs(entity.end[1] - bottom) < 1e-6]
    assert len(chain) > 1 and sum(abs(entity.end[0] - entity.start[0]) for entity in chain) == pytest.approx(footing.lx)
    texts = [entity.text for entity in plan.entities if isinstance(entity, Text)]
    assert "REFUERZO INFERIOR" in texts


def test_combined_plans_are_drawn_in_global_axes(tmp_path: Path) -> None:
    """D-158: con la viga en la Y global, las plantas van en ejes globales (la base, ly' de ancho en X y lx' de largo en Y) y
    las barras de la dirección principal quedan a lo largo de y."""
    data = json.loads(frozen("nsr_10", "zapatas", "zapata_combinada.json").read_text(encoding="utf-8"))
    footing = data["combined_footings"][0]
    footing["principal_direction"] = "y"
    footing["lx"], footing["ly"] = footing["ly"], footing["lx"]
    for column in footing["columns"]:
        column["x"], column["y"], column["cx"], column["cy"] = 0.0 - column["y"], column["x"], column["cy"], column["cx"]
    path = tmp_path / "girada.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    project = load_project(path)
    combined = project.combined_footings[0]
    plan = _views(project).view("planta_inferior")
    outline = plan.entities[0]
    assert isinstance(outline, Polyline)
    xs, ys = [p[0] for p in outline.points], [p[1] for p in outline.points]
    assert (max(xs) - min(xs), max(ys) - min(ys)) == (pytest.approx(combined.ly), pytest.approx(combined.lx))
    along_y = [bar for bar in _bars(plan) if abs(bar.points[0][0] - bar.points[-1][0]) < 1.0]
    assert any(abs(bar.points[0][1] - bar.points[-1][1]) > combined.lx / 2 for bar in along_y)


@pytest.mark.parametrize(("element", "name"), [("zapatas", "zapata_centrica.json"), ("zapatas", "zapata_combinada.json"),
                                               ("cabezales", "cabezal_pilotes.json")])
def test_dxf_writes_each_bar_length_as_an_autocad_field(element: str, name: str, tmp_path: Path) -> None:
    """D-158, D-166: en el DXF, los rótulos de las plantas (MTEXT) y de los cortes (MULTILEADER) llevan cada L como un
    campo de AutoCAD ligado a la longitud de una polilínea de barra (\\AcObjProp ... .Length), como el plano de
    referencia; el valor guardado es la longitud de la cartilla, la que mide esa polilínea."""
    ezdxf = pytest.importorskip("ezdxf")
    output = tmp_path / "salida"
    report_file(frozen("nsr_10", element, name), output)
    document = ezdxf.readfile(output / "salida.dxf")
    assert not document.audit().has_errors
    labelled = {"MTEXT": 0, "MULTILEADER": 0}
    for label in document.modelspace().query("MTEXT MULTILEADER"):
        if not label.has_extension_dict:
            continue
        field = label.get_extension_dict().dictionary["ACAD_FIELD"]["TEXT"]
        tags = {tag.code: tag.value for tag in field.xtags.get_subclass("AcDbField")}
        assert "%<\\_FldIdx 0>%" in tags[2]
        child = document.entitydb[tags[360]]
        child_tags = list(child.xtags.get_subclass("AcDbField"))
        assert any(tag.code == 2 and ".Length" in tag.value for tag in child_tags)
        bar = document.entitydb[next(tag.value for tag in child_tags if tag.code == 331)]
        assert bar.dxf.layer.startswith(BAR_PREFIX)
        points = list(bar.get_points("xy"))
        length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(points, points[1:], strict=False))
        text = label.text if label.dxftype() == "MTEXT" else label.context.mtext.default_content
        assert f"L={metres(length * 1000)}" in text
        labelled[label.dxftype()] += 1
    assert labelled["MTEXT"] and labelled["MULTILEADER"]
