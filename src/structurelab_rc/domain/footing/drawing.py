"""Vistas del refuerzo de cada zapata (v3 Fase 4B, D-126): el contorno del concreto de cada tipo y los cortes que se
dibujan, con las corridas del despiece (su ubicación y sus marcas). La geometría de las barras sale de domain/footing/
detailing.py y el dibujo en sí es neutro (drawing/views.py).

- Zapata aislada: planta y cortes X-X e Y-Y por el eje de la columna.
- Zapata combinada: planta, alzado longitudinal por el eje de la viga (y = 0) y un corte transversal por cada columna.
- T invertida: lo mismo, con el alma en la planta, el alzado a la altura de la viga y el corte en T.
La combinada se dibuja en los ejes de la viga (X a lo largo de la viga), en los que se calcula (D-094).
"""

from structurelab_rc.detailing.schedule import BarRun, ScheduleRow, run_marks
from structurelab_rc.drawing.model import Drawing, Polyline, View
from structurelab_rc.drawing.views import Marked, cartilla_view, plan_view, rectangle, section_view
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing

_STUB = 0.6  # altura del arranque de columna dibujado, en lados de la columna


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
