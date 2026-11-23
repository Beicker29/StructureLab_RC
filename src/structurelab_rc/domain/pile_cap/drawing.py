"""Dibujo del cabezal (D-138, D-166): las vistas de la zapata aislada (domain/footing/drawing.py), con el refuerzo
presentado igual, y los pilotes como el plano de despiece de cabezales de referencia.

- Contorno del concreto en la capa CABEZAL; con esquinas recortadas, el contorno real y el recubrimiento corrido a él.
- Plantas: los pilotes a trazos. En la de geometría, además, la marca del centro, el nombre (el del cuadro), la cota del
  diámetro (o del lado) de un pilote, arriba (en x) y a la derecha (en y) la cadena de los centros de los pilotes y por
  fuera la de sus bordes, con una columna las cotas del eje de la columna a los centros, y lo que quita cada recorte.
- Cortes X-X e Y-Y por las columnas: bajo el cabezal, los pilotes de esa dirección en proyección (el empotramiento a
  trazos dentro del concreto y un tramo visible con corte ondulado), la cadena de sus bordes y la de sus centros, el
  empotramiento y el recubrimiento inferior. Sin el refuerzo de los pilotes.
- Cuadro de pilotes: nombre, centro (x, y) respecto al centroide del cabezal, sección y empotramiento.
"""

import math

from structurelab_rc.detailing.schedule import BarRun, ScheduleRow
from structurelab_rc.domain.footing.drawing import isolated_views
from structurelab_rc.drawing.model import (
    DIAMETER,
    DIMENSIONS,
    DISTRIBUTION,
    PILE_CAP,
    PILES,
    Circle,
    Dimension,
    Drawing,
    Entity,
    Line,
    Polyline,
    Text,
    View,
    metres,
)
from structurelab_rc.drawing.views import chain, measure, rectangle, table_view
from structurelab_rc.mechanics.polygon import inset
from structurelab_rc.model.pile_cap import PileCap

LAYER = PILES
PAPER_PILE = 24.0  # mm de papel: tramo visible de un pilote bajo el cabezal en un corte
_CENTRE = 0.6  # mm de papel: radio de la marca del centro de un pilote en la planta de geometría
_WAVE = 1.2  # mm de papel: amplitud del corte ondulado del pilote
_WAVE_POINTS = 12
_EDGES_AT, _CENTRES_AT = 0.35, 0.7  # fracciones del tramo visible: cadenas de bordes y de centros, como la referencia
_SAME = 1.0  # mm: dos posiciones a menos de esto son la misma
_TABLE = (("Pilote", 16.0), ("X (m)", 16.0), ("Y (m)", 16.0), ("Seccion", 18.0), ("Empotr. (m)", 20.0))
_CORNERS = {"-x-y": (-1.0, -1.0), "+x-y": (1.0, -1.0), "+x+y": (1.0, 1.0), "-x+y": (-1.0, 1.0)}


def _distinct(values: list[float]) -> list[float]:
    """Las posiciones ordenadas y sin repetir (a menos de _SAME)."""
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] > _SAME:
            result.append(value)
    return result


def _section_text(cap: PileCap) -> str:
    """La sección del pilote: Ø.50 el circular, .40x.40 el cuadrado."""
    size = metres(cap.pile.size)
    return f"{DIAMETER}{size}" if cap.pile.shape == "circular" else f"{size}x{size}"


def _plan_piles(drawing: Drawing, cap: PileCap, geometry: bool) -> list[Entity]:
    """Los pilotes en una planta, a trazos; en la de geometría, con la marca del centro y el nombre."""
    size, small = cap.pile.size, drawing.text_height(small=True)
    entities: list[Entity] = []
    for pile in cap.piles:
        if cap.pile.shape == "circular":
            entities.append(Circle(LAYER, (pile.x, pile.y), size / 2, filled=False, dashed=True))
        else:
            entities.append(rectangle(LAYER, (pile.x - size / 2, pile.y - size / 2), (pile.x + size / 2, pile.y + size / 2), dashed=True))
        if geometry:
            entities += [Circle(LAYER, (pile.x, pile.y), drawing.paper(_CENTRE), filled=False),
                         Text(LAYER, (pile.x - size / 2, pile.y + size / 2 + small / 2), pile.id, small)]
    return entities


def _pile_dimensions(drawing: Drawing, cap: PileCap) -> list[Entity]:
    """Las cotas de los pilotes en la planta de geometría, como la referencia: el diámetro (o el lado) de un pilote;
    arriba (x) y a la derecha (y), la cadena de los centros desde los bordes y por fuera la de los bordes de los
    pilotes; con una columna, las del eje de la columna al centro de cada fila de pilotes."""
    height, gap = drawing.text_height(small=True), drawing.gap()
    x0, x1, y0, y1 = -cap.lx / 2, cap.lx / 2, -cap.ly / 2, cap.ly / 2
    size = cap.pile.size
    xs, ys = _distinct([pile.x for pile in cap.piles]), _distinct([pile.y for pile in cap.piles])
    entities: list[Entity] = [
        *chain([x0, *xs, x1], ("x", y1), ((0.0, 1.0), gap), height),
        *chain([x0, *(x + side * size / 2 for x in xs for side in (-1, 1)), x1], ("x", y1), ((0.0, 1.0), 2 * gap), height),
        *chain([y0, *ys, y1], ("y", x1), ((1.0, 0.0), gap), height),
        *chain([y0, *(y + side * size / 2 for y in ys for side in (-1, 1)), y1], ("y", x1), ((1.0, 0.0), 2 * gap), height),
    ]
    first = max(cap.piles, key=lambda pile: (pile.y, pile.x))  # el de arriba a la derecha, como la referencia
    if cap.pile.shape == "circular":
        reach = size / 2 / math.sqrt(2)
        entities.append(Dimension(DIMENSIONS, (first.x - reach, first.y - reach), (first.x + reach, first.y + reach), 0.0,
                                  _section_text(cap), height, kind="diameter"))
    else:
        entities.append(measure(((first.x - size / 2, first.y + size / 2), (first.x + size / 2, first.y + size / 2)),
                                (0.0, 1.0), 0.3 * gap, height))
    if len(cap.columns) == 1:
        cx, cy = cap.columns[0].offset_x, cap.columns[0].offset_y
        entities += [measure(((cx, cy), (x, cy)), (0.0, -1.0), 0.3 * gap, height) for x in xs if abs(x - cx) > _SAME]
        entities += [measure(((cx, cy), (cx, y)), (1.0, 0.0), 0.3 * gap, height) for y in ys if abs(y - cy) > _SAME]
    return entities


def _clip_dimensions(drawing: Drawing, cap: PileCap) -> list[Entity]:
    """Lo que quita cada esquina recortada (D-141), pegado al contorno: along_x sobre el borde paralelo a X y along_y
    sobre el paralelo a Y."""
    height, gap = drawing.text_height(small=True), drawing.gap()
    entities: list[Entity] = []
    for clip in cap.clipped_corners:
        sx, sy = _CORNERS[clip.corner]
        corner = (sx * cap.lx / 2, sy * cap.ly / 2)
        entities += [measure((corner, (corner[0] - sx * clip.along_x, corner[1])), (0.0, sy), 0.5 * gap, height),
                     measure((corner, (corner[0], corner[1] - sy * clip.along_y)), (sx, 0.0), 0.5 * gap, height)]
    return entities


def _wave(left: float, right: float, level: float, amplitude: float) -> Polyline:
    """El corte ondulado de un pilote entre left y right a la altura level."""
    points = tuple((left + (right - left) * step / _WAVE_POINTS,
                    level + amplitude * math.sin(2 * math.pi * step / _WAVE_POINTS)) for step in range(_WAVE_POINTS + 1))
    return Polyline(LAYER, points)


def _section_piles(drawing: Drawing, cap: PileCap, axis: str) -> list[Entity]:
    """Los pilotes bajo el cabezal en el corte paralelo a axis, en proyección (uno por posición a lo largo del corte): el
    empotramiento a trazos dentro del concreto y un tramo visible con corte ondulado; dentro de ese tramo, la cadena de
    los bordes de los pilotes y la de sus centros desde los bordes del cabezal; el empotramiento junto a la cara interior
    del primer pilote y el recubrimiento inferior junto a la del último."""
    size, embedment = cap.pile.size, cap.pile.embedment
    visible, height, gap = drawing.paper(PAPER_PILE), drawing.text_height(small=True), drawing.gap()
    positions = _distinct([pile.x if axis == "x" else pile.y for pile in cap.piles])
    low, high = (-cap.lx / 2, cap.lx / 2) if axis == "x" else (-cap.ly / 2, cap.ly / 2)
    entities: list[Entity] = []
    for u in positions:
        left, right = u - size / 2, u + size / 2
        if embedment > 0:
            entities.append(Polyline(LAYER, ((left, 0.0), (left, embedment), (right, embedment), (right, 0.0)), dashed=True))
        entities += [Line(LAYER, (left, 0.0), (left, -visible)), Line(LAYER, (right, 0.0), (right, -visible)),
                     _wave(left, right, -visible, drawing.paper(_WAVE))]
    edges = [u + side * size / 2 for u in positions for side in (-1, 1)]
    entities += chain([low, *edges, high], ("x", -_EDGES_AT * visible), ((0.0, -1.0), 0.0), height)
    entities += chain([low, *positions, high], ("x", -_CENTRES_AT * visible), ((0.0, -1.0), 0.0), height)
    # Del lado de adentro de los pilotes de los extremos, donde no llegan las cotas de las patas de las barras.
    inner_first, inner_last = positions[0] + size / 2, positions[-1] - size / 2
    if embedment > 0:
        entities.append(measure(((inner_first, 0.0), (inner_first, embedment)), (1.0, 0.0), 0.4 * gap, height))
    entities.append(measure(((inner_last, 0.0), (inner_last, cap.bottom_cover)), (-1.0, 0.0), 0.4 * gap, height))
    return entities


def pile_table(drawing: Drawing, cap: PileCap) -> View:
    """El cuadro de pilotes (D-166): nombre, centro (x, y) respecto al centroide del cabezal, sección y empotramiento."""
    section, embedment = _section_text(cap), metres(cap.pile.embedment)
    rows = [[pile.id, metres(pile.x), metres(pile.y), section, embedment] for pile in cap.piles]
    return table_view(drawing, ("cuadro_pilotes", f"Cuadro de pilotes {cap.id}"), _TABLE, rows)


def _clipped(drawing: Drawing, cap: PileCap, views: list[View]) -> None:
    """Con esquinas recortadas (D-141): el contorno real en lugar del rectángulo y, en la planta de geometría, el
    recubrimiento corrido al contorno real y lo que quita cada recorte."""
    rectangle_outline = rectangle(PILE_CAP, (-cap.lx / 2, -cap.ly / 2), (cap.lx / 2, cap.ly / 2))
    polygon = Polyline(PILE_CAP, cap.outline, closed=True)
    cover = Polyline(DISTRIBUTION, inset(cap.outline, cap.cover), closed=True, dashed=True)
    for view in views:
        view.entities[:] = [polygon if entity == rectangle_outline else entity for entity in view.entities]
        if view.name == "geometria":
            view.entities[:] = [cover if _is_cover(entity) else entity for entity in view.entities]
            view.entities += _clip_dimensions(drawing, cap)


def _is_cover(entity: Entity) -> bool:
    return isinstance(entity, Polyline) and entity.layer == DISTRIBUTION and entity.closed and entity.dashed


def pile_cap_views(drawing: Drawing, cap: PileCap, runs: list[BarRun], rows: tuple[list[ScheduleRow], float],
                   units: int) -> list[View]:
    """Planta de geometría, plantas del refuerzo, cortes X-X e Y-Y por las columnas y cartilla, como la zapata aislada,
    con los pilotes, sus cotas y el cuadro de pilotes (D-166)."""
    below: dict[str, list[Entity]] = {axis: _section_piles(drawing, cap, axis) for axis in ("x", "y")}
    views = isolated_views(drawing, cap, (runs, rows, units), (PILE_CAP, below))
    if cap.clipped_corners:
        _clipped(drawing, cap, views)
    for view in views:
        if view.name == "geometria":
            view.entities += [*_plan_piles(drawing, cap, geometry=True), *_pile_dimensions(drawing, cap)]
        elif view.name.startswith("planta_"):
            view.entities += _plan_piles(drawing, cap, geometry=False)
    views.append(pile_table(drawing, cap))
    return views
