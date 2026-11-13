"""Vistas del refuerzo de cada zapata (v3 Fase 4B, D-126): el contorno del concreto de cada tipo y los cortes que se
dibujan, con las corridas del despiece (su ubicación y sus marcas). La geometría de las barras sale de domain/footing/
detailing.py y el dibujo en sí es neutro (drawing/views.py).

- Zapata aislada: planta y cortes X-X e Y-Y por el eje de la columna.
- Zapata combinada: planta, alzado longitudinal por el eje de la viga (y = 0) y un corte transversal por cada columna.
- T invertida: lo mismo, con el alma en la planta, el alzado a la altura de la viga y el corte en T.
La combinada se dibuja en los ejes de la viga (X a lo largo de la viga), en los que se calcula (D-094).

Planta de localización (D-130): una por nivel de cimentación, en ejes globales, con cada zapata a escala en su nudo, su
columna, el rótulo del tipo y el nudo de ETABS, y el cuadro de tipologías. La zapata aislada se ubica por su columna
(location menos el desplazamiento de la columna); la combinada, por sus dos columnas: el centro de la base es el promedio
de lo que da cada una, y si difieren se avisa en el plano.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from structurelab_rc.detailing.schedule import BarRun, ScheduleRow, run_marks
from structurelab_rc.drawing.model import Drawing, Entity, Polyline, Text, View
from structurelab_rc.drawing.views import Marked, cartilla_view, plan_view, rectangle, section_view, table_view, titled
from structurelab_rc.model.combined import CombinedFooting, beam_to_global
from structurelab_rc.model.footing import Footing, Mat

_STUB = 0.6  # altura del arranque de columna dibujado, en lados de la columna
_MISMATCH = 10.0  # mm: diferencia entre la base que ubica cada columna de una combinada a partir de la cual se avisa
_TABLE = (("Tipo", 24.0), ("Dimensiones lx x ly x h (mm)", 50.0), ("Malla inferior", 56.0), ("Malla superior", 56.0),
          ("Cant.", 12.0))


def _marked(element: str, runs: list[BarRun], stock: float) -> list[Marked]:
    return [Marked(run, marks) for run, marks in zip(runs, run_marks(element, runs, stock), strict=True) if run.placement is not None]


def _stub(centre: float, size: float, top: float, pedestal: float) -> list[Polyline]:
    """Pedestal (si lo hay) y arranque de la columna sobre la cara superior top, en un corte."""
    left, right = centre - size / 2, centre + size / 2
    stub = top + pedestal
    shapes = [rectangle("CONCRETO", (left, top), (right, stub))] if pedestal > 0 else []
    return [*shapes, Polyline("CONCRETO", ((left, stub), (left, stub + _STUB * size), (right, stub + _STUB * size), (right, stub)),
                              dashed=True)]


def footing_views(drawing: Drawing, footing: Footing, runs: list[BarRun], rows: tuple[list[ScheduleRow], float]) -> list[View]:
    """Zapata aislada: planta, cortes X-X e Y-Y por la columna y cartilla; rows = (cartilla, longitud comercial)."""
    schedule, stock = rows
    marked = _marked(footing.id, runs, stock)
    column, h, pedestal = footing.column, footing.h, footing.pedestal_height
    lx, ly = footing.lx, footing.ly
    outline = rectangle("CONCRETO", (-lx / 2, -ly / 2), (lx / 2, ly / 2))
    columns = [(footing.id, rectangle("CONCRETO", (column.offset_x - column.cx / 2, column.offset_y - column.cy / 2),
                                      (column.offset_x + column.cx / 2, column.offset_y + column.cy / 2)))]
    return [
        *_plans(drawing, (footing.id, ""), ([outline], columns), marked, h / 2),
        section_view(drawing, ("corte_x", "Corte X-X"), ("x", column.offset_y),
                     [rectangle("CONCRETO", (-lx / 2, 0.0), (lx / 2, h)), *_stub(column.offset_x, column.cx, h, pedestal)], marked),
        section_view(drawing, ("corte_y", "Corte Y-Y"), ("y", column.offset_x),
                     [rectangle("CONCRETO", (-ly / 2, 0.0), (ly / 2, h)), *_stub(column.offset_y, column.cy, h, pedestal)], marked),
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
    schedule, stock = rows
    marked = _marked(footing.id, runs, stock)
    lx, ly, h, top, pedestal = footing.lx, footing.ly, footing.h, footing.total_height, footing.pedestal_height
    beam = footing.beam
    concrete = [rectangle("CONCRETO", (-lx / 2, -ly / 2), (lx / 2, ly / 2))]
    if beam is not None:
        concrete += [Polyline("CONCRETO", ((-lx / 2, side * beam.width / 2), (lx / 2, side * beam.width / 2))) for side in (-1, 1)]
    columns = [(column.id, rectangle("CONCRETO", (column.x - column.cx / 2, column.y - column.cy / 2),
                                     (column.x + column.cx / 2, column.y + column.cy / 2))) for column in footing.columns]
    if beam is None:
        cross = rectangle("CONCRETO", (-ly / 2, 0.0), (ly / 2, h))
    else:
        half = beam.width / 2
        cross = Polyline("CONCRETO", ((-ly / 2, 0.0), (ly / 2, 0.0), (ly / 2, h), (half, h), (half, top), (-half, top),
                                      (-half, h), (-ly / 2, h)), closed=True)
    elevation = [rectangle("CONCRETO", (-lx / 2, 0.0), (lx / 2, top))]
    elevation += [shape for column in footing.columns for shape in _stub(column.x, column.cx, top, pedestal)]
    views = [
        *_plans(drawing, (footing.id, " (ejes de la viga)"), (concrete, columns), marked, h / 2 if beam is None else top / 2),
        section_view(drawing, ("alzado", "Alzado longitudinal A-A"), ("x", 0.0), elevation, marked),
    ]
    for column in footing.columns:
        views.append(section_view(drawing, (f"corte_{column.id}", f"Corte transversal por {column.id}"), ("y", column.x),
                                  [cross, *_stub(column.y, column.cy, top, pedestal)], marked))
    views.append(cartilla_view(drawing, footing.id, schedule))
    return views


@dataclass
class _Placed:
    """Una zapata ubicada en el proyecto: su nivel, su tipo, la fila del cuadro y lo que se dibuja de ella."""

    story: str
    typology: str
    row: list[str]
    entities: list[Entity] = field(default_factory=list)


def _mat_text(mat: Mat | None, swap: bool = False) -> str:
    """Una malla en el cuadro de tipologías, con x e y globales (swap: la combinada con la viga en la Y global)."""
    if mat is None:
        return "-"
    sets = {"x": mat.y, "y": mat.x} if swap else {"x": mat.x, "y": mat.y}
    return "; ".join(f"{axis} {bar_set.designation} c/{bar_set.spacing:.0f}" for axis, bar_set in sets.items())


def _outline(drawing: Drawing, centre: tuple[float, float], size: tuple[float, float],
             columns: list[tuple[tuple[float, float], tuple[float, float], str]], label: str) -> list[Entity]:
    """Contorno de la base de tamaño size centrada en centre, las columnas (centro, tamaño, nudo) y el rótulo del tipo."""
    (x, y), (width, depth) = centre, size
    entities: list[Entity] = [rectangle("CONCRETO", (x - width / 2, y - depth / 2), (x + width / 2, y + depth / 2))]
    small = drawing.text_height(small=True)
    for (cx, cy), (bx, by), joint in columns:
        entities.append(rectangle("CONCRETO", (cx - bx / 2, cy - by / 2), (cx + bx / 2, cy + by / 2)))
        entities.append(Text("TEXTOS", (cx, cy - by / 2 - 1.5 * small), joint, small, align="center"))
    entities.append(Text("TEXTOS", (x, y + depth / 2 + 0.5 * small), label, drawing.text_height(), align="center"))
    return entities


def _isolated_place(drawing: Drawing, footing: Footing) -> _Placed:
    location, column = footing.location, footing.column
    assert location is not None
    centre = (location.x - column.offset_x, location.y - column.offset_y)
    typology = footing.typology or footing.id
    entities = _outline(drawing, centre, (footing.lx, footing.ly), [((location.x, location.y), (column.cx, column.cy), location.joint)],
                        typology)
    row = [typology, f"{footing.lx:.0f} x {footing.ly:.0f} x {footing.h:.0f}", _mat_text(footing.bottom), _mat_text(footing.top)]
    return _Placed(location.story, typology, row, entities)


def _combined_place(drawing: Drawing, footing: CombinedFooting) -> _Placed:
    """La combinada en ejes globales: con la viga en la Y global, las dimensiones, las columnas y las barras vuelven de
    los ejes de la viga a los declarados (D-094, D-101)."""
    rotated = footing.principal_direction == "y"
    size = (footing.ly, footing.lx) if rotated else (footing.lx, footing.ly)
    estimates, columns = [], []
    for column in footing.columns:
        location = column.location
        assert location is not None
        offset = beam_to_global(column.x, column.y) if rotated else (column.x, column.y)
        estimates.append((location.x - offset[0], location.y - offset[1]))
        columns.append(((location.x, location.y), (column.cy, column.cx) if rotated else (column.cx, column.cy), location.joint))
    centre = (sum(x for x, _ in estimates) / len(estimates), sum(y for _, y in estimates) / len(estimates))
    entities = _outline(drawing, centre, size, columns, footing.id)
    (x0, y0), (x1, y1) = estimates
    mismatch = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if mismatch > _MISMATCH:
        small = drawing.text_height(small=True)
        entities.append(Text("TEXTOS", (centre[0], centre[1] - size[1] / 2 - 3 * small),
                             f"ADVERTENCIA: las columnas de ETABS ubican la base a {mismatch:.0f} mm entre si", small, align="center"))
    first = footing.columns[0].location
    assert first is not None
    row = [footing.id, f"{size[0]:.0f} x {size[1]:.0f} x {footing.total_height:.0f}", _mat_text(footing.bottom, rotated),
           "ver despiece"]
    return _Placed(first.story, footing.id, row, entities)


def _natural(name: str) -> list[tuple[int, str]]:
    """Orden natural de los tipos: Z2 antes que Z10."""
    return [(int(part), "") if part.isdigit() else (0, part) for part in re.split(r"(\d+)", name)]


def _file_name(story: str) -> str:
    """El nivel en el nombre de la vista (y de su SVG): solo letras, números, punto, guion y guion bajo."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", story).strip("_")


def location_views(drawing: Drawing, footings: Sequence[Footing], combined: Sequence[CombinedFooting]) -> list[View]:
    """Plantas de localización por nivel y cuadro de tipologías (D-130), con las zapatas que tienen ubicación; [] si
    ninguna la tiene. Una combinada entra si sus dos columnas la tienen."""
    placed = [_isolated_place(drawing, footing) for footing in footings if footing.location is not None]
    placed += [_combined_place(drawing, footing) for footing in combined if all(column.location is not None for column in footing.columns)]
    if not placed:
        return []
    views = []
    for story in sorted({item.story for item in placed}):
        view = View(_file_name(story), f"Planta de localizacion {story}",
                    [entity for item in placed if item.story == story for entity in item.entities])
        views.append(titled(drawing, view))
    counts: dict[str, int] = {}
    rows: dict[str, list[str]] = {}
    for item in placed:
        counts[item.typology] = counts.get(item.typology, 0) + 1
        rows.setdefault(item.typology, item.row)
    table = [[*rows[name], str(counts[name])] for name in sorted(rows, key=_natural)]
    views.append(table_view(drawing, ("cuadro_tipologias", "Cuadro de tipologias"), _TABLE, table))
    return views
