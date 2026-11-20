"""Vistas del refuerzo de cada zapata (v3 Fase 4B, D-126): el contorno del concreto de cada tipo y los cortes que se
dibujan, con las corridas del despiece (su ubicación y sus marcas). La geometría de las barras sale de domain/footing/
detailing.py y el dibujo en sí es neutro (drawing/views.py).

- Zapata aislada: planta de geometría, plantas del refuerzo inferior y superior y cortes X-X e Y-Y por el eje de la
  columna.
- Zapata combinada: planta de geometría, plantas del refuerzo, alzado longitudinal por el eje de la viga (y = 0) y un
  corte transversal por cada columna (este solo en el SVG y la memoria, no en el DXF, D-150).
- T invertida: lo mismo, con el alma en las plantas, el alzado a la altura de la viga y el corte en T.
Las plantas de la combinada van en los ejes globales del proyecto (D-158): con la viga en la Y global, se giran desde los
ejes de la viga en los que se calcula (D-094); el alzado y los cortes, a lo largo y a través de la viga. Cada elemento deja su
título para el DXF en drawing.titles ("ZC_m h=0.80", D-150).

Planta de localización (D-130): una por nivel de cimentación, en ejes globales, con cada zapata a escala en su nudo, su
columna, el rótulo del tipo y el nudo de ETABS, y el cuadro de tipologías. La zapata aislada se ubica por su columna
(location menos el desplazamiento de la columna); la combinada, por sus dos columnas: el centro de la base es el promedio
de lo que da cada una, y si difieren se avisa en el plano.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from structurelab_rc.detailing.schedule import BarRun, Piece, ScheduleRow, run_marks
from structurelab_rc.domain.footing.detailing import SKIN
from structurelab_rc.domain.footing.neighbors import (
    Footprint,
    close_neighbors,
    combined_footprint,
    isolated_footprint,
    neighbor_text,
)
from structurelab_rc.drawing.model import (
    DIMENSIONS,
    LABELS,
    OUTLINE,
    PAPER_STUB,
    Drawing,
    Entity,
    Line,
    Point,
    Polyline,
    Text,
    View,
    metres,
)
from structurelab_rc.drawing.views import (
    Marked,
    cartilla_view,
    column_rectangle,
    geometry_view,
    numbered,
    plan_view,
    rectangle,
    section_view,
    table_view,
    titled,
)
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import FootingBody, Mat

# Símbolo de corte del arranque de columna (D-158), como el plano de referencia: sale de la columna 0.25 de su lado, el
# quiebre va a 0.15 del lado desde el eje, con pasos de 2 mm y alturas de 4 mm de papel.
_BREAK_MARGIN = 0.25
_BREAK_AT = 0.15
_BREAK_STEP = 2.0
_BREAK_RISE = 4.0
_MISMATCH = 10.0  # mm: diferencia entre la base que ubica cada columna de una combinada a partir de la cual se avisa
_TABLE = (("Tipo", 24.0), ("Dimensiones lx x ly x h (m)", 50.0), ("Malla inferior", 56.0), ("Malla superior", 56.0),
          ("Cant.", 12.0))


def _marked(element: str, runs: list[BarRun], rows: tuple[list[ScheduleRow], float]) -> list[Marked]:
    schedule, stock = rows
    return numbered(runs, run_marks(element, runs, stock), stock, schedule)


def _metres_text(length: float) -> str:
    """Una medida en metros para una nota: 800 -> "0.80 m"."""
    return f"{length / 1000:.2f} m"


def element_title(element: str, thickness: float) -> str:
    """El título de un elemento en el DXF, como los planos de despiece (D-150): "ZC_m h=0.80"."""
    return f"{element} h={thickness / 1000:.2f}"


def _stub(drawing: Drawing, centre: float, size: float, levels: tuple[float, float]) -> list[Entity]:
    """Pedestal (si lo hay) y arranque de la columna sobre la cara superior, en un corte, como los planos de despiece
    (D-158): las dos caras de la columna hasta un alto fijo en papel y el símbolo de corte encima. levels = (cara
    superior de la base, alto del pedestal)."""
    top, pedestal = levels
    left, right = centre - size / 2, centre + size / 2
    stub = top + pedestal
    high = stub + drawing.paper(PAPER_STUB)
    entities: list[Entity] = [rectangle(OUTLINE, (left, top), (right, stub))] if pedestal > 0 else []
    entities += [Line(OUTLINE, (left, stub), (left, high)), Line(OUTLINE, (right, stub), (right, high))]
    step, rise = drawing.paper(_BREAK_STEP), drawing.paper(_BREAK_RISE)
    kink = centre + _BREAK_AT * size
    entities.append(Polyline(DIMENSIONS, ((left - _BREAK_MARGIN * size, high), (kink - step, high), (kink, high - rise),
                                          (kink, high + rise), (kink + step, high), (right + _BREAK_MARGIN * size, high))))
    return entities


def _rotated(point: Point) -> Point:
    """Un punto de los ejes de una viga en la Y global, en los ejes globales (D-094, D-158): x = −y', y = x'."""
    return 0.0 - point[1], point[0]


def _rotated_polyline(polyline: Polyline) -> Polyline:
    return replace(polyline, points=tuple(_rotated(point) for point in polyline.points))


def _rotated_marked(item: Marked) -> Marked:
    """Una corrida horizontal de la combinada con la viga en la Y global, en los ejes globales (D-158), para las plantas:
    las barras a lo largo de la viga (x') van a lo largo de y en las posiciones −y'; las transversales (y') van a lo largo
    de x con el largo invertido, así que sus extremos (ganchos y patas B y C de la cartilla) se intercambian."""
    run, place = item.run, item.place
    if place.along == "x":
        moved = replace(place, along="y", positions=tuple(sorted(0.0 - position for position in place.positions)))
        return replace(item, run=replace(run, placement=moved))
    if place.along != "y":
        return item
    moved = replace(place, along="x", span=(0.0 - place.span[1], 0.0 - place.span[0]))
    pieces = tuple(_reversed_piece(piece) for piece in item.pieces)
    return replace(item, run=replace(run, placement=moved, hooks=(run.hooks[1], run.hooks[0])), pieces=pieces)


def _reversed_piece(piece: Piece) -> Piece:
    """La pieza vista desde el otro extremo: los ganchos y, si hay dos patas, B y C intercambiadas."""
    dimensions = dict(piece.dimensions)
    if "B" in dimensions and "C" in dimensions:
        dimensions["B"], dimensions["C"] = dimensions["C"], dimensions["B"]
    return replace(piece, dimensions=tuple(dimensions.items()), angles=(piece.angles[1], piece.angles[0]))


def footing_views(drawing: Drawing, footing: FootingBody, runs: list[BarRun], rows: tuple[list[ScheduleRow], float]) -> list[View]:
    """Zapata aislada o cabezal: planta, cortes X-X e Y-Y por las columnas (por el eje medio si hay varias, D-143) y
    cartilla; rows = (cartilla, longitud comercial)."""
    schedule, _ = rows
    marked = _marked(footing.id, runs, rows)
    drawing.titles[footing.id] = element_title(footing.id, footing.h)
    h, pedestal = footing.h, footing.pedestal_height
    all_columns = footing.all_columns
    names = [footing.id] if len(all_columns) == 1 else [str(getattr(column, "id", footing.id)) for column in all_columns]
    lx, ly = footing.lx, footing.ly
    outline = rectangle(OUTLINE, (-lx / 2, -ly / 2), (lx / 2, ly / 2))
    columns = [(name, column_rectangle((column.offset_x - column.cx / 2, column.offset_y - column.cy / 2),
                                       (column.offset_x + column.cx / 2, column.offset_y + column.cy / 2)))
               for name, column in zip(names, all_columns, strict=True)]
    cut_y = sum(column.offset_y for column in all_columns) / len(all_columns)
    cut_x = sum(column.offset_x for column in all_columns) / len(all_columns)
    on_x = [column for column in all_columns if abs(column.offset_y - cut_y) <= column.cy / 2]
    on_y = [column for column in all_columns if abs(column.offset_x - cut_x) <= column.cx / 2]
    stubs_x = [shape for column in on_x for shape in _stub(drawing, column.offset_x, column.cx, (h, pedestal))]
    stubs_y = [shape for column in on_y for shape in _stub(drawing, column.offset_y, column.cy, (h, pedestal))]
    faces_x = [face for column in on_x for face in (column.offset_x - column.cx / 2, column.offset_x + column.cx / 2)]
    faces_y = [face for column in on_y for face in (column.offset_y - column.cy / 2, column.offset_y + column.cy / 2)]
    labels = [(name, (column.offset_x, column.offset_y), (column.cx, column.cy)) for name, column in zip(names, all_columns, strict=True)]
    return [
        geometry_view(drawing, ("geometria", f"Planta de geometria {footing.id}"), (outline, []), labels,
                      (footing.cover, f"Espesor h = {_metres_text(h)}; pedestal {_metres_text(pedestal)}.")),
        *_plans(drawing, (footing.id, ""), ([outline], columns), marked, h / 2),
        section_view(drawing, ("corte_x", "Corte X-X"), ("x", cut_y), marked,
                     ([rectangle(OUTLINE, (-lx / 2, 0.0), (lx / 2, h))], stubs_x, faces_x, True)),
        section_view(drawing, ("corte_y", "Corte Y-Y"), ("y", cut_x), marked,
                     ([rectangle(OUTLINE, (-ly / 2, 0.0), (ly / 2, h))], stubs_y, faces_y, True)),
        cartilla_view(drawing, footing.id, schedule),
    ]


def _plans(drawing: Drawing, names: tuple[str, str], outline: tuple[list[Polyline], list[tuple[str, Polyline]]],
           marked: list[Marked], split: float) -> list[View]:
    """Planta del refuerzo inferior y, si lo hay, del superior (las barras horizontales sobre split); names = (elemento,
    sufijo del título)."""
    element, suffix = names
    views = [plan_view(drawing, ("planta_inferior", f"Planta refuerzo inferior {element}{suffix}"), outline, marked, (split, False))]
    if any(item.place.along in ("x", "y") and item.place.level > split for item in marked):
        views.append(plan_view(drawing, ("planta_superior", f"Planta refuerzo superior {element}{suffix}"), outline, marked,
                               (split, True)))
    return views


def combined_views(drawing: Drawing, footing: CombinedFooting, runs: list[BarRun],
                   rows: tuple[list[ScheduleRow], float]) -> list[View]:
    """Zapata combinada o T invertida: planta, alzado longitudinal, un corte transversal por columna y cartilla."""
    schedule, _ = rows
    marked = _marked(footing.id, runs, rows)
    drawing.titles[footing.id] = element_title(footing.id, footing.h)
    lx, ly, h, top, pedestal = footing.lx, footing.ly, footing.h, footing.total_height, footing.pedestal_height
    beam = footing.beam
    concrete = [rectangle(OUTLINE, (-lx / 2, -ly / 2), (lx / 2, ly / 2))]
    if beam is not None:
        concrete += [Polyline(OUTLINE, ((-lx / 2, side * beam.width / 2), (lx / 2, side * beam.width / 2))) for side in (-1, 1)]
    columns = [(column.id, column_rectangle((column.x - column.cx / 2, column.y - column.cy / 2),
                                            (column.x + column.cx / 2, column.y + column.cy / 2))) for column in footing.columns]
    if beam is None:
        cross = rectangle(OUTLINE, (-ly / 2, 0.0), (ly / 2, h))
    else:
        half = beam.width / 2
        cross = Polyline(OUTLINE, ((-ly / 2, 0.0), (ly / 2, 0.0), (ly / 2, h), (half, h), (half, top), (-half, top),
                                   (-half, h), (-ly / 2, h)), closed=True)
    elevation = [rectangle(OUTLINE, (-lx / 2, 0.0), (lx / 2, top))]
    stubs = [shape for column in footing.columns for shape in _stub(drawing, column.x, column.cx, (top, pedestal))]
    faces = [face for column in footing.columns for face in (column.x - column.cx / 2, column.x + column.cx / 2)]
    note = f"Espesor h = {_metres_text(h)}; pedestal {_metres_text(pedestal)}" + (
        "." if beam is None else f"; viga {metres(beam.width)} x {metres(beam.height)} m (alto desde la base).")
    shapes = [(column.id, (column.x, column.y), (column.cx, column.cy)) for column in footing.columns]
    # El refuerzo superficial va en las caras laterales: se ve en el alzado, no en las plantas (D-158).
    plan_marked = [item for item in marked if not item.run.group.startswith(SKIN)]
    plan_concrete, plan_columns = concrete, columns
    if footing.principal_direction == "y":  # las plantas en los ejes globales del proyecto (D-158)
        plan_marked = [_rotated_marked(item) for item in plan_marked]
        plan_concrete = [_rotated_polyline(polyline) for polyline in concrete]
        plan_columns = [(name, _rotated_polyline(polyline)) for name, polyline in columns]
        shapes = [(name, _rotated(centre), (size[1], size[0])) for name, centre, size in shapes]
    views = [
        geometry_view(drawing, ("geometria", f"Planta de geometria {footing.id}"), (plan_concrete[0], plan_concrete[1:]), shapes,
                      (footing.cover, note)),
        *_plans(drawing, (footing.id, ""), (plan_concrete, plan_columns), plan_marked, h / 2 if beam is None else top / 2),
        section_view(drawing, ("alzado", "Alzado longitudinal A-A"), ("x", 0.0), marked, (elevation, stubs, faces, False)),
    ]
    for column in footing.columns:  # solo en el SVG y la memoria (D-150)
        stub = _stub(drawing, column.y, column.cy, (top, pedestal))
        section = section_view(drawing, (f"corte_{column.id}", f"Corte transversal por {column.id}"), ("y", column.x), marked,
                               ([cross], stub, [column.y - column.cy / 2, column.y + column.cy / 2], True))
        section.dxf = False
        views.append(section)
    views.append(cartilla_view(drawing, footing.id, schedule))
    return views


@dataclass
class _Placed:
    """Una zapata ubicada en el proyecto: su nivel, su tipo, la fila del cuadro y lo que se dibuja de ella."""

    story: str
    typology: str
    row: list[str]
    entities: list[Entity] = field(default_factory=list)
    footprint: Footprint | None = None  # la planta de la zapata en ejes globales (D-156)


def _mat_text(mat: Mat | None, swap: bool = False) -> str:
    """Una malla en el cuadro de tipologías, con x e y globales (swap: la combinada con la viga en la Y global)."""
    if mat is None:
        return "-"
    sets = {"x": mat.y, "y": mat.x} if swap else {"x": mat.x, "y": mat.y}
    return "; ".join(f"{axis} {bar_set.designation} C/{metres(bar_set.spacing)}" for axis, bar_set in sets.items())


def _outline(drawing: Drawing, centre: tuple[float, float], size: tuple[float, float],
             columns: list[tuple[tuple[float, float], tuple[float, float], str]], label: str) -> list[Entity]:
    """Contorno de la base de tamaño size centrada en centre, las columnas (centro, tamaño, nudo) y el rótulo del tipo."""
    (x, y), (width, depth) = centre, size
    entities: list[Entity] = [rectangle(OUTLINE, (x - width / 2, y - depth / 2), (x + width / 2, y + depth / 2))]
    small = drawing.text_height(small=True)
    for (cx, cy), (bx, by), joint in columns:
        entities.append(column_rectangle((cx - bx / 2, cy - by / 2), (cx + bx / 2, cy + by / 2)))
        entities.append(Text(LABELS, (cx, cy - by / 2 - 1.5 * small), joint, small, align="center"))
    entities.append(Text(LABELS, (x, y + depth / 2 + 0.5 * small), label, drawing.text_height(), align="center"))
    return entities


def _isolated_place(drawing: Drawing, footing: FootingBody) -> _Placed:
    """Zapata aislada o cabezal: location es la de su (primera) columna; las demás columnas de un cabezal se dibujan con
    sus desplazamientos (D-143)."""
    location, first = footing.location, footing.all_columns[0]
    footprint = isolated_footprint(footing)
    assert location is not None and footprint is not None
    centre = footprint.centre
    typology = footing.typology or footing.id
    columns = [((centre[0] + column.offset_x, centre[1] + column.offset_y), (column.cx, column.cy),
                location.joint if column is first else str(getattr(column, "id", "")))
               for column in footing.all_columns]
    entities = _outline(drawing, centre, (footing.lx, footing.ly), columns, typology)
    row = [typology, f"{metres(footing.lx)} x {metres(footing.ly)} x {metres(footing.h)}", _mat_text(footing.bottom),
           _mat_text(footing.top)]
    return _Placed(location.story, typology, row, entities, footprint)


def _combined_place(drawing: Drawing, footing: CombinedFooting) -> _Placed:
    """La combinada en ejes globales: con la viga en la Y global, las dimensiones, las columnas y las barras vuelven de
    los ejes de la viga a los declarados (D-094, D-101)."""
    rotated = footing.principal_direction == "y"
    footprint = combined_footprint(footing)
    assert footprint is not None
    centre, size, mismatch = footprint.centre, footprint.size, footprint.mismatch
    columns = []
    for column in footing.columns:
        location = column.location
        assert location is not None
        columns.append(((location.x, location.y), (column.cy, column.cx) if rotated else (column.cx, column.cy), location.joint))
    typology = footing.typology or footing.id  # el tipo de combinada (D-157)
    entities = _outline(drawing, centre, size, columns, typology)
    if mismatch > _MISMATCH:
        small = drawing.text_height(small=True)
        entities.append(Text(LABELS, (centre[0], centre[1] - size[1] / 2 - 3 * small),
                             f"ADVERTENCIA: las columnas de ETABS ubican la base a {_metres_text(mismatch)} entre si", small,
                             align="center"))
    row = [typology, f"{metres(size[0])} x {metres(size[1])} x {metres(footing.total_height)}", _mat_text(footing.bottom, rotated),
           "ver despiece"]
    return _Placed(footprint.story, typology, row, entities, footprint)


def _warnings(drawing: Drawing, placed: list[_Placed], minimum: float | None) -> list[Entity]:
    """Aviso en el plano de cada par de zapatas del mismo nivel más cercanas que la separación mínima o traslapadas
    (D-153, D-156), entre las dos: el diseño no revisa la interacción entre zapatas vecinas."""
    small = drawing.text_height(small=True)
    warnings: list[Entity] = []
    for item in close_neighbors([own.footprint for own in placed if own.footprint is not None], minimum):
        a, b = item.first.box, item.second.box
        x, y = (max(a[0], b[0]) + min(a[2], b[2])) / 2, (max(a[1], b[1]) + min(a[3], b[3])) / 2
        warnings.append(Text(LABELS, (x, y), f"ADVERTENCIA: {neighbor_text(item, minimum)}", small, align="center"))
    return warnings


def _natural(name: str) -> list[tuple[int, str]]:
    """Orden natural de los tipos: Z2 antes que Z10."""
    return [(int(part), "") if part.isdigit() else (0, part) for part in re.split(r"(\d+)", name)]


def _file_name(story: str) -> str:
    """El nivel en el nombre de la vista (y de su SVG): solo letras, números, punto, guion y guion bajo."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", story).strip("_")


def location_views(drawing: Drawing, footings: Sequence[FootingBody], combined: Sequence[CombinedFooting],
                   minimum: float | None = None) -> list[View]:
    """Plantas de localización por nivel y cuadro de tipologías (D-130), con las zapatas que tienen ubicación; [] si
    ninguna la tiene. Una combinada entra si sus dos columnas la tienen. minimum: la separación libre mínima entre
    zapatas (min_clear_spacing, D-156); el plano avisa los pares más cercanos y los traslapados."""
    placed = [_isolated_place(drawing, footing) for footing in footings if footing.location is not None]
    placed += [_combined_place(drawing, footing) for footing in combined if all(column.location is not None for column in footing.columns)]
    if not placed:
        return []
    views = []
    for story in sorted({item.story for item in placed}):
        own = [item for item in placed if item.story == story]
        view = View(_file_name(story), f"Planta de localizacion {story}",
                    [*(entity for item in own for entity in item.entities), *_warnings(drawing, own, minimum)])
        views.append(titled(drawing, view))
    counts: dict[str, int] = {}
    rows: dict[str, list[str]] = {}
    for item in placed:
        counts[item.typology] = counts.get(item.typology, 0) + 1
        rows.setdefault(item.typology, item.row)
    table = [[*rows[name], str(counts[name])] for name in sorted(rows, key=_natural)]
    views.append(table_view(drawing, ("cuadro_tipologias", "Cuadro de tipologias"), _TABLE, table))
    return views
