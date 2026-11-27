"""Vistas del muro de contención en voladizo (D-175): las dos láminas del plano de muros de referencia
(references/Despiece muros voladizo.dxf) en el formato de las zapatas y los cabezales (D-150, D-158, D-166): capas de la
plantilla, una por diámetro de barra, rótulos con la L ligada a su barra, cotas en metros y la cartilla con croquis. La
geometría de las barras sale de domain/retaining_wall/detailing.py; el dibujo en sí usa las piezas neutras de
drawing/views.py.

Ejes de las vistas: en los cortes, x a través del muro (de la puntera a la izquierda al talón a la derecha) y z desde la
cara inferior de la base; en el alzado, y a lo largo del muro y z.

- Geometría: el corte del concreto (capa MURO) con el relleno sobre el talón sombreado (capa RELLENO, patrón EARTH),
  cotas en cadena (puntera, pantalla y talón abajo; base y pantalla a la izquierda; el relleno a la derecha; el espesor
  de la pantalla arriba) y una nota con el largo, los recubrimientos y el área de concreto por metro.
- Detallado del refuerzo: el corte con cada grupo de barras (las verticales y las transversales con sus patas de la
  cartilla; las horizontales de la pantalla y las longitudinales de la base como puntos) y su rótulo con llamada.
- Barras despiezadas: cada marca dibujada aparte con sus patas, su cota y su rótulo, como la referencia.
- Alzado de la cara del relleno: un tramo del muro (hasta seis separaciones de las verticales) con quiebre, las verticales
  y las horizontales de esa cara y las longitudinales de la base, con sus rótulos y la línea de distribución.
- Cartilla con croquis.
"""

from structurelab_rc.detailing.schedule import BarRun, Piece, ScheduleRow, run_marks
from structurelab_rc.drawing.model import (
    BACKFILL,
    DIMENSIONS,
    DISTRIBUTION,
    EARTH,
    LABELS,
    WALL,
    Circle,
    Dimension,
    Drawing,
    Entity,
    Leader,
    Line,
    Point,
    Polyline,
    Text,
    View,
    metres,
)
from structurelab_rc.drawing.views import (
    CUT_DOT,
    Marked,
    cartilla_view,
    chain,
    drawn_is_cut,
    label_marks,
    label_text,
    measure,
    measured_mark,
    numbered,
    piece_legs,
    view_title,
)
from structurelab_rc.model.retaining_wall import RetainingWall

_LABEL_STEP = 1.8  # separación de los rótulos apilados, en alturas de texto
_WINDOW_BARS = 6  # separaciones de las verticales que muestra el alzado
_BREAK_STEP, _BREAK_RISE = 2.0, 4.0  # mm de papel: el quiebre del alzado
_BAR_GAP = 14.0  # mm de papel: separación entre las barras despiezadas
_ANCHOR_AT = 0.6  # altura relativa de la llamada a una vertical


def wall_title(wall: RetainingWall) -> str:
    """El título del muro en el DXF, como el plano de referencia ("MC1 H2.9M"): el id y la altura total."""
    return f"{wall.id} H={metres(wall.base_thickness + wall.stem_height)}"


def _outline(wall: RetainingWall) -> Polyline:
    """El corte del concreto: la base y la pantalla, antihorario desde el borde inferior de la puntera."""
    width, hb, top = wall.base_width, wall.base_thickness, wall.base_thickness + wall.stem_height
    front = -width / 2 + wall.toe
    back = front + wall.stem_thickness
    return Polyline(WALL, ((-width / 2, 0.0), (width / 2, 0.0), (width / 2, hb), (back, hb), (back, top), (front, top),
                           (front, hb), (-width / 2, hb)), closed=True)


def _faces(wall: RetainingWall) -> tuple[float, float]:
    front = -wall.base_width / 2 + wall.toe
    return front, front + wall.stem_thickness


def _geometry(drawing: Drawing, wall: RetainingWall) -> View:
    width, hb = wall.base_width, wall.base_thickness
    top = hb + wall.stem_height
    front, back = _faces(wall)
    fill = hb + wall.backfill_height
    soil = Polyline(BACKFILL, ((back, hb), (width / 2, hb), (width / 2, fill), (back, fill)), closed=True, pattern=EARTH)
    view = View("geometria", f"Geometria {wall.id}", [soil, _outline(wall)])
    height, gap = drawing.text_height(small=True), drawing.gap()
    left, right = -width / 2, width / 2
    view.entities += [*chain([left, front, back, right], ("x", 0.0), ((0.0, -1.0), gap), height),
                      measure(((left, 0.0), (right, 0.0)), (0.0, -1.0), 2 * gap, height),
                      *chain([0.0, hb, top], ("y", left), ((-1.0, 0.0), gap), height),
                      measure(((left, 0.0), (left, top)), (-1.0, 0.0), 2 * gap, height),
                      measure(((right, hb), (right, fill)), (1.0, 0.0), gap, height),
                      measure(((front, top), (back, top)), (0.0, 1.0), 0.6 * gap, height)]
    area = (width * hb + wall.stem_thickness * wall.stem_height) / 1e6
    length = "" if wall.length is None else f"Largo del muro L = {metres(wall.length)}; "
    note = (f"{length}recubrimientos: pantalla {metres(wall.stem_cover)}, base {metres(wall.base_cover)}; "
            f"area de concreto {area:.2f} m2 por metro")
    view.entities.append(Text(LABELS, (left, -3.4 * gap), note, height))
    view_title(drawing, view)
    return view


def _vertical(item: Marked) -> tuple[list[Entity], Point]:
    """Una vertical de la pantalla con las patas de su cartilla (pie y corona) y el punto de su llamada."""
    place = item.place
    x, (z0, z1) = place.level, place.span
    first, straight, last = piece_legs(item.pieces[0])
    if len(item.pieces) == 1:  # el tramo A de la cartilla: la barra mide su longitud de corte (D-166)
        z1 = z0 + straight
    else:  # empalmada: el tramo completo con la pata del pie y la de la corona, sin marca
        _, _, last = piece_legs(item.pieces[-1])
    points: list[Point] = [(x, z0), (x, z1)]
    if first:
        points.insert(0, (x + place.cross[0] * first, z0))
    if last:
        points.append((x + place.cross[1] * last, z1))
    shape = tuple(points)
    return [Polyline(item.layer, shape, mark=measured_mark(item, shape))], (x, z0 + _ANCHOR_AT * (z1 - z0))


def _transverse(item: Marked, middle: float) -> tuple[list[Entity], Point]:
    """Una transversal de la base con las patas de su cartilla hacia adentro y el punto de su llamada."""
    place = item.place
    z, (start, end) = place.level, place.span
    inward = 1.0 if z < middle else -1.0
    first, straight, last = piece_legs(item.pieces[0])
    if len(item.pieces) == 1:
        end = start + straight
    else:
        _, _, last = piece_legs(item.pieces[-1])
    points: list[Point] = [(start, z), (end, z)]
    if first:
        points.insert(0, (start, z + inward * first))
    if last:
        points.append((end, z + inward * last))
    shape = tuple(points)
    return [Polyline(item.layer, shape, mark=measured_mark(item, shape))], (start + 0.75 * (end - start), z)


def _dots(drawing: Drawing, item: Marked) -> tuple[list[Entity], Point]:
    """Las barras a lo largo del muro como puntos: las horizontales de la pantalla (en x = level, a sus z) o las
    longitudinales de la base (a sus x, en z = level)."""
    place = item.place
    radius = drawing.paper(CUT_DOT)
    points = [(place.level, z) for z in place.positions] if place.vertical else [(x, place.level) for x in place.positions]
    return [Circle(item.layer, point, radius) for point in points], points[len(points) // 2]


def _stacked(drawing: Drawing, view: View, anchors: list[tuple[Point, list[Marked]]], corner: Point) -> None:
    """Los rótulos con llamada, apilados a la derecha de lo dibujado (corner = esquina superior derecha), de arriba abajo
    en el orden de sus barras."""
    height = drawing.text_height(small=True)
    x, top = corner[0] + drawing.gap(), corner[1]
    grouped: dict[str, tuple[list[Point], tuple[str, ...]]] = {}  # dos caras con el mismo rótulo: uno, con dos llamadas
    for point, items in anchors:
        points, _ = grouped.setdefault(label_text(items), ([], label_marks(items)))
        points.append(point)
    ordered = sorted(grouped.items(), key=lambda pair: -max(point[1] for point in pair[1][0]))
    for index, (text, (points, marks)) in enumerate(ordered):
        view.entities.append(Leader(DIMENSIONS, (x, top - index * _LABEL_STEP * height), text, height, tuple(points), marks))


def _reinforcement(drawing: Drawing, wall: RetainingWall, marked: list[Marked]) -> View:
    view = View("refuerzo", f"Detallado del refuerzo {wall.id}", [_outline(wall)])
    middle = wall.base_thickness / 2
    anchors: list[tuple[Point, list[Marked]]] = []
    for item in marked:
        along = item.place.along
        if along == "vertical":
            entities, point = _vertical(item)
        elif along == "x":
            entities, point = _transverse(item, middle)
        else:
            entities, point = _dots(drawing, item)
        view.entities += entities
        anchors.append((point, [item]))
    x0, _, x1, y1 = view.bounds()
    height, gap = drawing.text_height(small=True), drawing.gap()
    front, back = _faces(wall)
    top = wall.base_thickness + wall.stem_height
    view.entities += [measure(((-wall.base_width / 2, 0.0), (wall.base_width / 2, 0.0)), (0.0, -1.0), gap, height),
                      measure(((front, top), (back, top)), (0.0, 1.0), 0.6 * gap, height)]
    _stacked(drawing, view, anchors, (x1, y1))
    view_title(drawing, view)
    return view


def _piece_shape(item: Marked, piece: Piece, corner: Point) -> tuple[list[Entity], Point, Point]:
    """Una pieza dibujada aparte desde corner: vertical las verticales de la pantalla (con las patas a la derecha) y
    horizontal las demás (con las patas hacia arriba); devuelve las entidades y los extremos de su tramo A."""
    first, straight, last = piece_legs(piece)
    x, y = corner
    if item.place.along == "vertical":
        start, end = (x, y), (x, y + straight)
        points = [start, end]
        if first:
            points.insert(0, (x + first, y))
        if last:
            points.append((x + last, y + straight))
    else:
        start, end = (x, y), (x + straight, y)
        points = [start, end]
        if first:
            points.insert(0, (x, y + first))
        if last:
            points.append((x + straight, y + last))
    mark = item.marks[item.pieces.index(piece)] if drawn_is_cut(piece) else ""
    return [Polyline(item.layer, tuple(points), mark=mark)], start, end


def _bars(drawing: Drawing, wall: RetainingWall, marked: list[Marked]) -> View:
    """Cada marca dibujada aparte, como la referencia: las verticales lado a lado y debajo las demás, con la cota de su
    tramo y el rótulo de su grupo."""
    view = View("barras", f"Barras despiezadas {wall.id}")
    height, step = drawing.text_height(small=True), drawing.paper(_BAR_GAP)
    seen: set[str] = set()
    column, row = 0.0, -step
    for item in marked:
        for mark, piece in zip(item.marks, item.pieces, strict=True):
            if mark in seen:
                continue
            seen.add(mark)
            vertical = item.place.along == "vertical"
            corner = (column, 0.0) if vertical else (0.0, row)
            entities, start, end = _piece_shape(item, piece, corner)
            view.entities += entities
            view.entities.append(measure((start, end), (-1.0, 0.0) if vertical else (0.0, -1.0), 0.4 * drawing.gap(), height))
            label = f"{label_text([item])}"
            if vertical:
                view.entities.append(Text(LABELS, (column + 0.8 * height + max(piece_legs(piece)[0], piece_legs(piece)[2]),
                                                   (start[1] + end[1]) / 2), label, height, align="center", rotation=90.0,
                                          marks=label_marks([item])))
                column += step + max(piece_legs(piece)[0], piece_legs(piece)[2]) + 2 * height
            else:
                view.entities.append(Text(LABELS, ((start[0] + end[0]) / 2, row + 0.6 * height + max(piece_legs(piece)[0],
                                                                                                   piece_legs(piece)[2])),
                                          label, height, align="center", marks=label_marks([item])))
                row -= step + 2 * height
    if view.entities:
        view_title(drawing, view)
    return view


def _break(drawing: Drawing, x: float, levels: tuple[float, float]) -> Polyline:
    """El quiebre del alzado en x, de levels[0] a levels[1]."""
    low, high = levels
    step, rise = drawing.paper(_BREAK_STEP), drawing.paper(_BREAK_RISE)
    middle = (low + high) / 2
    return Polyline(DIMENSIONS, ((x, low), (x, middle - step), (x + rise, middle), (x - rise, middle + step),
                                 (x, middle + 2 * step), (x, high)))


def _elevation(drawing: Drawing, wall: RetainingWall, marked: list[Marked]) -> View:
    """Alzado de la cara del relleno en un tramo del muro, con quiebre: las verticales y las horizontales de esa cara y
    las longitudinales de la base."""
    assert wall.length is not None
    hb, top = wall.base_thickness, wall.base_thickness + wall.stem_height
    start = -wall.length / 2
    window = min(wall.length, _WINDOW_BARS * wall.stem.back.spacing + 2 * wall.stem_cover)
    end = start + window
    view = View("alzado", f"Alzado cara del relleno {wall.id}",
                [Polyline(WALL, ((end, 0.0), (start, 0.0), (start, top), (end, top))), Line(WALL, (start, hb), (end, hb))])
    if window < wall.length:
        view.entities.append(_break(drawing, end, (-drawing.gap() / 4, top + drawing.gap() / 4)))
    else:
        view.entities.append(Line(WALL, (end, 0.0), (end, top)))
    _, back = _faces(wall)
    anchors: list[tuple[Point, list[Marked]]] = []
    height = drawing.text_height(small=True)
    for item in marked:
        place = item.place
        if place.along == "vertical" and place.level > (back + _faces(wall)[0]) / 2:  # las verticales de la cara del relleno
            inside = [y for y in place.positions if start <= y <= end]
            view.entities += [Line(item.layer, (y, place.span[0]), (y, place.span[1])) for y in inside]
            if inside:
                anchors.append(((inside[len(inside) // 2], top - 0.25 * (top - hb)), [item]))
                low, high = inside[0], inside[-1]
                view.entities.append(Dimension(DISTRIBUTION, (low, hb + 0.5 * (top - hb)), (high, hb + 0.5 * (top - hb)), 0.0, "",
                                               height))
        elif place.along == "y" and (not place.vertical or place.level > (back + _faces(wall)[0]) / 2):
            levels = place.positions if place.vertical else (place.level,)
            low_y, high_y = max(place.span[0], start), min(place.span[1], end)
            view.entities += [Line(item.layer, (low_y, z), (high_y, z)) for z in levels]
            anchors.append(((low_y + 0.8 * (high_y - low_y), levels[len(levels) // 2]), [item]))
    x0, _, x1, y1 = view.bounds()
    view.entities.append(measure(((start, top), (start, 0.0)), (-1.0, 0.0), drawing.gap(), height))
    _stacked(drawing, view, anchors, (x1, y1))
    view_title(drawing, view)
    return view


def wall_views(drawing: Drawing, wall: RetainingWall, runs: list[BarRun], rows: tuple[list[ScheduleRow], float],
               units: int) -> list[View]:
    """Las vistas del tipo de un muro (D-175): geometría, detallado del refuerzo, barras despiezadas, alzado de la cara
    del relleno y cartilla; rows = (cartilla, longitud comercial); units, las veces que se construye el tipo (D-159)."""
    schedule, stock = rows
    marked = numbered(runs, run_marks(wall.id, runs, stock), stock, schedule)
    drawing.titles[wall.id] = wall_title(wall)
    views = [_geometry(drawing, wall), _reinforcement(drawing, wall, marked), _bars(drawing, wall, marked),
             _elevation(drawing, wall, marked), cartilla_view(drawing, wall.id, schedule, units)]
    return [view for view in views if view.entities]
