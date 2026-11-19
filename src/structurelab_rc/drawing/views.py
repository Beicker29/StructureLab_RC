"""Vistas neutras del refuerzo (D-126, D-132, D-150): plantas, cortes, planta de geometría y cartilla con el croquis de
cada forma, a partir de las corridas del despiece (con su ubicación, Placement), sus marcas y la longitud de corte de cada
marca en la cartilla. Sin fórmulas normativas: los ganchos y los empalmes llegan ya dimensionados.

Convenciones (D-150, sobre D-132):
- Cada barra representativa y cada grupo de un corte lleva su rótulo, como los planos de despiece: cantidad, barra,
  separación, longitud de corte de cada marca y las marcas de la cartilla: "22#6 C/.15 L=6.65 (ZC_m-01)". La longitud
  es la de la cartilla (D-147), que es la misma del .dli, del peso y del costo; las medidas van en metros (metres).
- Cada barra va en la capa de su diámetro (Borde_<designación>).
- En planta (x a la derecha, y arriba), las barras de un grupo se parten en zonas (donde el hueco entre dos barras
  vecinas supera 1.5 separaciones) y cada zona se dibuja con una barra representativa a su largo real, con los ganchos
  abatidos en el plano, los tramos empalmados desplazados y traslapados, y una línea de distribución con marcas en la
  primera y la última barra. Si una dirección tiene más de una zona, se acota cada una.
- En un corte paralelo a X (cut "x", a la ordenada y = at) la abscisa es x y en uno paralelo a Y (cut "y", en x = at) es
  y; la vertical es z desde la base. Las barras paralelas al plano se dibujan como líneas (con sus ganchos) si hay una a
  menos de una separación del plano, y las perpendiculares como puntos.
- La planta de geometría acota la base, las columnas y su posición desde los bordes, con los ejes de las columnas y el
  recubrimiento.
"""

import math
from dataclasses import dataclass

from structurelab_rc.detailing.schedule import STIRRUP_SHAPE, BarRun, Placement, ScheduleRow, hook_leg, splice_spans
from structurelab_rc.drawing.model import (
    AXES,
    COLUMN_FILL,
    DIMENSIONS,
    DISTRIBUTION,
    LABELS,
    PAPER_SUBTITLE,
    SUBTITLE,
    TABLE,
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
    bar_layer,
    metres,
)

_LABEL_STEP = 1.8  # separación de los rótulos apilados, en alturas de texto
_PAIR = 2  # con dos barras o menos (piel, caras opuestas) el rótulo no da separación
_DOT = 0.293  # mm de papel: radio del punto de una barra cortada, fijo (a 1:50, los 14.7 mm de la plantilla, D-150)
_ROW = 12.0  # mm de papel: alto de una fila de la cartilla
_HEADER = 8.0  # mm de papel: alto del encabezado de la cartilla
_COLUMNS = (("Marca", 18.0), ("Barra", 12.0), ("Cant.", 10.0), ("Forma", 46.0), ("A (m)", 14.0), ("B (m)", 14.0),
            ("C (m)", 14.0), ("L corte (m)", 20.0), ("Peso kg", 16.0))
_ZONE_GAP = 1.5  # un hueco mayor que 1.5 separaciones parte un grupo en zonas
_SPLICE_SHIFT = 0.8  # mm de papel: desplazamiento entre los tramos empalmados dibujados
_TICK = 1.0  # mm de papel: marca de los extremos de la línea de distribución
_SAME = 1.0  # mm: dos cotas a menos de esto son la misma
_HOOK_SKETCH = 0.12  # radio del gancho de 180° en el croquis de la cartilla, en anchos de la celda
_HOOK_ROOM = 0.22  # y a lo más esta fracción del alto de la fila, para que quepa en ella


@dataclass(frozen=True)
class Marked:
    """Una corrida del despiece con sus marcas de la cartilla, la longitud de corte de cada marca (mm) y el número de su
    grupo, que reúne sus rótulos en los cortes."""

    run: BarRun
    marks: tuple[str, ...]
    number: int
    stock: float  # longitud comercial: fija los tramos empalmados que se dibujan
    lengths: tuple[float, ...] = ()  # la longitud de corte de cada marca, de la cartilla (D-147)

    @property
    def place(self) -> Placement:
        assert self.run.placement is not None
        return self.run.placement

    @property
    def layer(self) -> str:
        return bar_layer(self.run.designation)


def numbered(runs: list[BarRun], marks: list[tuple[str, ...]], stock: float, rows: list[ScheduleRow]) -> list[Marked]:
    """Las corridas ubicadas con sus marcas, la longitud de corte de cada marca (de la cartilla rows) y el número de su
    grupo (grupo y designación), en el orden del despiece."""
    lengths = {row.mark: row.piece.cut_length for row in rows}
    numbers: dict[tuple[str, str], int] = {}
    return [Marked(run, own, numbers.setdefault((run.group, run.designation), len(numbers) + 1), stock,
                   tuple(lengths[mark] for mark in own))
            for run, own in zip(runs, marks, strict=True) if run.placement is not None]


def label_text(items: list[Marked], count: int | None = None, positions: tuple[float, ...] | None = None) -> str:
    """El rótulo de un grupo (D-150): cantidad, barra (E delante en los estribos), separación si tiene más de dos barras,
    "pasadores" en los pasadores, la longitud de corte de cada marca y las marcas: "22#6 C/.15 L=6.65 (ZC_m-01)". count y
    positions, los de una zona de la planta (por omisión, todo el grupo)."""
    run, place = items[0].run, items[0].place
    marks = dict.fromkeys(pair for item in items for pair in zip(item.marks, item.lengths, strict=True))
    total = sum(item.run.count for item in items) if count is None else count
    spots = place.positions if positions is None else positions
    body = f"{total}{'E' if place.along == 'estribo' else ''}{run.designation}"
    if place.along == "z":
        body += " pasadores"
    elif len(spots) > _PAIR:  # dos barras o menos: sin separación
        body += f" C/{metres(_gap(spots))}"
    lengths = "+".join(metres(length) for _, length in marks)
    return f"{body} L={lengths} ({', '.join(mark for mark, _ in marks)})"


def _gap(positions: tuple[float, ...]) -> float:
    gaps = [b - a for a, b in zip(positions, positions[1:], strict=False)]
    return min(gaps) if gaps else 0.0


def zones(positions: tuple[float, ...]) -> list[tuple[float, ...]]:
    """Las zonas de un grupo: barras seguidas, partidas donde el hueco supera _ZONE_GAP veces la separación."""
    gap = _gap(positions)
    result: list[list[float]] = [[positions[0]]]
    for previous, position in zip(positions, positions[1:], strict=False):
        if gap and position - previous > _ZONE_GAP * gap:
            result.append([])
        result[-1].append(position)
    return [tuple(zone) for zone in result]


def rectangle(layer: str, corner: Point, opposite: Point, dashed: bool = False) -> Polyline:
    (x0, y0), (x1, y1) = corner, opposite
    return Polyline(layer, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), closed=True, dashed=dashed)


def column_rectangle(corner: Point, opposite: Point) -> Polyline:
    """Una columna en planta: rellena en su capa (el DXF dibuja además el contorno en la del concreto, D-150)."""
    (x0, y0), (x1, y1) = corner, opposite
    return Polyline(COLUMN_FILL, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), closed=True, filled=True)


def _labels(drawing: Drawing, view: View, anchors: list[tuple[Point, Marked]], marked: list[Marked], corner: Point) -> None:
    """Rótulos de un corte, apilados a la derecha (corner = esquina superior derecha de lo dibujado): el rótulo de cada
    grupo con una línea de llamada a cada barra del grupo, de arriba abajo en el orden de las barras."""
    height = drawing.text_height(small=True)
    x, top = corner[0] + drawing.gap(), corner[1]
    grouped: dict[str, list[Point]] = {}  # por texto: dos grupos con el mismo rótulo (las barras x e y de una malla) van juntos
    texts: dict[int, str] = {}
    for anchor, item in anchors:
        text = texts.setdefault(item.number, label_text([other for other in marked if other.number == item.number]))
        grouped.setdefault(text, []).append(anchor)
    ordered = sorted(grouped.items(), key=lambda pair: -max(point[1] for point in pair[1]))
    for index, (text, points) in enumerate(ordered):
        view.entities.append(Leader(DIMENSIONS, (x, top - index * _LABEL_STEP * height), text, height, tuple(points)))


def _dimensions(drawing: Drawing, view: View, outline: Polyline) -> None:
    """Cotas del ancho y el alto del contorno principal, abajo y a la izquierda."""
    xs, ys = [p[0] for p in outline.points], [p[1] for p in outline.points]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    height, gap = drawing.text_height(small=True), drawing.gap()
    view.entities += [Dimension(DIMENSIONS, (x0, y0), (x1, y0), -gap, metres(x1 - x0), height),
                      Dimension(DIMENSIONS, (x0, y0), (x0, y1), gap, metres(y1 - y0), height)]


def _title(drawing: Drawing, view: View, scaled: bool = False) -> None:
    """El título de la vista debajo de lo dibujado; la escala va en el título del elemento (D-150), salvo en las vistas
    sueltas (scaled: la planta de localización)."""
    x0, y0, x1, _ = view.bounds()
    text = view.title.upper() + (f" - ESC. 1:{drawing.scale:.0f}" if scaled else "")
    view.entities.append(Text(SUBTITLE, ((x0 + x1) / 2, y0 - 2 * drawing.gap()), text, drawing.paper(PAPER_SUBTITLE), align="center"))


def _column_labels(drawing: Drawing, view: View, columns: list[tuple[str, Polyline]]) -> None:
    for column_id, column in columns:
        xs, ys = [p[0] for p in column.points], [p[1] for p in column.points]
        view.entities.append(Text(LABELS, ((min(xs) + max(xs)) / 2, max(ys) + 0.4 * drawing.text_height(small=True)), column_id,
                                  drawing.text_height(small=True), align="center"))


def plan_view(drawing: Drawing, names: tuple[str, str], outline: tuple[list[Polyline], list[tuple[str, Polyline]]],
              marked: list[Marked], layer: tuple[float, bool]) -> View:
    """Planta (names = nombre y título) del refuerzo inferior o superior: el concreto y las columnas de outline y una barra
    representativa por zona, con su rótulo, de los grupos horizontales con z ≤ split (layer = (split, False)) o z > split
    (layer = (split, True))."""
    concrete, columns = outline
    split, upper = layer
    view = View(*names, [*concrete, *(column for _, column in columns)])
    _, _, x1, y1 = view.bounds()
    _column_labels(drawing, view, columns)
    chosen = [item for item in marked if item.place.along in ("x", "y") and (item.place.level > split) == upper]
    spans: dict[str, list[tuple[float, float]]] = {"x": [], "y": []}
    for index, item in enumerate(chosen):
        for zone in zones(item.place.positions):
            view.entities += _plan_bar(drawing, item, zone, index)
            spans[item.place.along].append((zone[0], zone[-1]))
    _zone_dimensions(drawing, view, spans, (x1, y1))
    _dimensions(drawing, view, concrete[0])
    _title(drawing, view)
    return view


def _zone_dimensions(drawing: Drawing, view: View, spans: dict[str, list[tuple[float, float]]], corner: Point) -> float:
    """Cotas de las zonas de cada dirección con más de una zona: las de las barras y (zonas a lo largo de x) arriba y las de
    las barras x a la derecha; devuelve lo que ocupan a la derecha."""
    height, gap = drawing.text_height(small=True), drawing.gap()
    right = 0.0
    if len(spans["y"]) > 1:
        view.entities += [Dimension(DIMENSIONS, (low, corner[1]), (high, corner[1]), gap, metres(high - low), height)
                          for low, high in spans["y"] if high - low > _SAME]
    if len(spans["x"]) > 1:
        view.entities += [Dimension(DIMENSIONS, (corner[0], high), (corner[0], low), gap, metres(high - low), height)
                          for low, high in spans["x"] if high - low > _SAME]
        right = gap + height
    return right


def _plan_bar(drawing: Drawing, item: Marked, zone: tuple[float, ...], index: int) -> list[Entity]:
    """La barra representativa de una zona (en su barra central), con los ganchos abatidos hacia la distribución, los
    tramos empalmados desplazados y traslapados, la línea de distribución y el rótulo de la zona sobre la barra (girado en
    las barras a lo largo de y)."""
    run, place = item.run, item.place
    db, height = run.diameter, drawing.text_height(small=True)

    def at(along: float, across: float) -> Point:
        return (along, across) if place.along == "x" else (across, along)

    middle = zone[len(zone) // 2]
    start = place.span[0]
    segments = [(start + low, start + high) for low, high in splice_spans(run, item.stock)]
    shift = _SPLICE_SHIFT * drawing.scale
    entities: list[Entity] = []
    for number, (low, high) in enumerate(segments):
        across = middle + shift * (number % 2)
        points = [at(low, across), at(high, across)]
        if number == 0 and run.hooks[0] is not None:
            points.insert(0, at(low, across + hook_leg(run.hooks[0], db) - db / 2))
        if number == len(segments) - 1 and run.hooks[1] is not None:
            points.append(at(high, across + hook_leg(run.hooks[1], db) - db / 2))
        entities.append(Polyline(item.layer, tuple(points)))
    for (_, end), (begin, _) in zip(segments, segments[1:], strict=False):
        entities.append(Text(LABELS, at((begin + end) / 2, middle - 1.4 * height), f"traslapo {metres(end - begin)}",
                             height, align="center", rotation=0.0 if place.along == "x" else 90.0))
    fraction = 0.15 + 0.1 * (index % 6)  # cada grupo con su línea de distribución en otro punto del largo
    along = place.span[0] + fraction * (place.span[1] - place.span[0])
    tick = _TICK * drawing.scale
    entities.append(Line(DISTRIBUTION, at(along, zone[0]), at(along, zone[-1])))
    entities += [Line(DISTRIBUTION, at(along - tick, position - tick), at(along + tick, position + tick))
                 for position in (zone[0], zone[-1])]
    count = round(len(zone) * run.count / len(place.positions))
    text = label_text([item], count, zone)
    label_at = place.span[0] + 0.08 * (place.span[1] - place.span[0])
    if place.along == "x":
        entities.append(Text(LABELS, (label_at, middle + 0.4 * height), text, height))
    else:  # girado 90°: el texto queda a la izquierda de la barra
        entities.append(Text(LABELS, (middle - 0.4 * height, label_at), text, height, rotation=90.0))
    return entities


def titled(drawing: Drawing, view: View) -> View:
    """La vista con su título y la escala debajo de lo dibujado."""
    _title(drawing, view, scaled=True)
    return view


def table_view(drawing: Drawing, names: tuple[str, str], columns: tuple[tuple[str, float], ...], rows: list[list[str]]) -> View:
    """Una tabla (names = nombre y título) con encabezados y filas de texto; columns = (encabezado, ancho en mm de papel)."""
    scale, small = drawing.scale, drawing.text_height(small=True)
    view = View(*names)
    width = sum(size for _, size in columns) * scale
    lefts = [sum(size for _, size in columns[:index]) * scale for index in range(len(columns))]
    header, row_height = _HEADER * scale, _HEADER * scale
    bottom = -header - row_height * len(rows)
    view.entities.append(rectangle(TABLE, (0.0, 0.0), (width, bottom)))
    view.entities += [Line(TABLE, (left, 0.0), (left, bottom)) for left in lefts[1:]]
    view.entities += [Text(TABLE, (left + size * scale / 2, -header * 0.65), name, small, align="center")
                      for (name, size), left in zip(columns, lefts, strict=True)]
    for index, row in enumerate(rows):
        top = -header - index * row_height
        view.entities.append(Line(TABLE, (0.0, top), (width, top)))
        view.entities += [Text(TABLE, (left + size * scale / 2, top - row_height * 0.65), text, small, align="center")
                          for text, (_, size), left in zip(row, columns, lefts, strict=True) if text]
    _title(drawing, view)
    return view



def geometry_view(drawing: Drawing, names: tuple[str, str], shape: tuple[Polyline, list[Polyline]],
                  columns: list[tuple[str, Point, Point]], notes: tuple[float, str]) -> View:
    """Planta de geometría (names = nombre y título): el contorno de la base y sus líneas (shape = contorno, alma u otras
    líneas rectas), las columnas (nombre, centro, tamaño) con sus ejes, el recubrimiento (línea a trazos a esa distancia
    de los bordes) y una nota (notes = recubrimiento, nota). Cotas: abajo, una cadena de los bordes a las caras de todas
    las columnas en x; a la izquierda, una cadena en y por las líneas de la base (el alma) y otra por cada columna con
    posición distinta; y los totales."""
    outline, extra = shape
    cover, note = notes
    view = View(*names, [outline, *extra])
    x0, y0, x1, y1 = view.bounds()
    height, gap = drawing.text_height(small=True), drawing.gap()
    view.entities += [rectangle(DISTRIBUTION, (x0 + cover, y0 + cover), (x1 - cover, y1 - cover), dashed=True),
                      Text(LABELS, (x0 + cover + 0.5 * height, y0 + cover + 0.5 * height), f"recubrimiento {metres(cover)}", height)]
    stops_x, chains_y = [x0, x1], []
    for column_id, (cx, cy), (bx, by) in columns:
        view.entities += [column_rectangle((cx - bx / 2, cy - by / 2), (cx + bx / 2, cy + by / 2)),
                          Polyline(AXES, ((x0 - gap / 2, cy), (x1 + gap / 2, cy)), dashed=True),
                          Polyline(AXES, ((cx, y0 - gap / 2), (cx, y1 + gap / 2)), dashed=True),
                          Text(LABELS, (cx + 0.3 * height, cy + by / 2 + 0.4 * height), column_id, height)]
        stops_x += [cx - bx / 2, cx + bx / 2]
        chains_y.append(_stops([y0, cy - by / 2, cy + by / 2, y1]))
    lines = [y for line in extra if len(ys := {round(p[1], 1) for p in line.points}) == 1 for y in ys]  # el alma de la T
    if lines:
        chains_y.insert(0, _stops([y0, *lines, y1]))
    chain_x = _stops(stops_x)
    view.entities += [Dimension(DIMENSIONS, (a, y0), (b, y0), -gap, metres(b - a), height)
                      for a, b in zip(chain_x, chain_x[1:], strict=False)]
    unique = [chain for index, chain in enumerate(chains_y) if chain not in chains_y[:index]]
    for level, chain in enumerate(unique, start=1):
        view.entities += [Dimension(DIMENSIONS, (x0, a), (x0, b), level * gap, metres(b - a), height)
                          for a, b in zip(chain, chain[1:], strict=False)]
    view.entities += [Dimension(DIMENSIONS, (x0, y0), (x1, y0), -2 * gap, metres(x1 - x0), height),
                      Dimension(DIMENSIONS, (x0, y0), (x0, y1), (len(unique) + 1) * gap, metres(y1 - y0), height),
                      Text(LABELS, (x0, y0 - 3.2 * gap), note, height)]
    _title(drawing, view)
    return view


def _stops(values: list[float]) -> list[float]:
    """Las posiciones de una cadena de cotas, ordenadas y sin repetir (a menos de _SAME)."""
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] > _SAME:
            result.append(value)
    return result


def section_view(drawing: Drawing, names: tuple[str, str], cut: tuple[str, float], concrete: list[Polyline],
                 marked: list[Marked]) -> View:
    """Corte (names = nombre y título) paralelo a X (cut = ("x", y)) o a Y (cut = ("y", x)): el concreto cortado, las
    barras y los estribos, con el rótulo de cada grupo a la derecha y sus líneas de llamada."""
    axis, at = cut
    view = View(*names, list(concrete))
    _, _, x1, y1 = view.bounds()
    zs = [p[1] for p in concrete[0].points]
    middle = (min(zs) + max(zs)) / 2
    anchors: list[tuple[Point, Marked]] = []
    drawn: set[Placement] = set()
    for item in marked:
        entities, anchor = _cut_bars(drawing, item, (axis, at, middle), drawn)
        view.entities += entities
        if anchor is not None:
            anchors.append((anchor, item))
    _labels(drawing, view, anchors, marked, (x1, y1))
    _dimensions(drawing, view, concrete[0])
    _title(drawing, view)
    return view


def _cut_bars(drawing: Drawing, item: Marked, cut: tuple[str, float, float], drawn: set[Placement]) -> tuple[list[Entity], Point | None]:
    """Las entidades de una corrida en un corte y el punto al que apunta su rótulo (None si no aparece)."""
    axis, at, middle = cut
    run, place = item.run, item.place
    db = run.diameter
    if place.along == axis:  # paralelas al plano: una línea si hay una barra cerca
        gap = _gap(place.positions)
        if min(abs(position - at) for position in place.positions) > max(gap, db):
            return [], None
        up = 1.0 if place.level < middle else -1.0
        (start, end), z = place.span, place.level
        points: list[Point] = [(start, z), (end, z)]
        if run.hooks[0] is not None:
            points.insert(0, (start, z + up * (hook_leg(run.hooks[0], db) - db / 2)))
        if run.hooks[1] is not None:
            points.append((end, z + up * (hook_leg(run.hooks[1], db) - db / 2)))
        return [Polyline(item.layer, tuple(points))], (start + 0.75 * (end - start), z)
    if place.along in ("x", "y"):  # perpendiculares: un punto por barra
        if not place.span[0] <= at <= place.span[1]:
            return [], None
        radius = drawing.paper(_DOT)  # tamaño fijo en papel, como la plantilla (D-150)
        dots: list[Entity] = [Circle(item.layer, (position, place.level), radius) for position in place.positions]
        return dots, (place.positions[-1], place.level)
    if place.along == "estribo":
        return _stirrup(item, axis, drawn)
    return _dowels(item, axis, at)


def _stirrup(item: Marked, axis: str, drawn: set[Placement]) -> tuple[list[Entity], Point | None]:
    run, place = item.run, item.place
    assert run.stirrup is not None
    width, height = run.stirrup
    if axis == "x":  # a lo largo: una línea vertical por estribo (una vez por grupo de estribos anidados)
        if place in drawn:
            return [], None
        drawn.add(place)
        lines: list[Entity] = [Line(item.layer, (x, place.level), (x, place.level + height)) for x in place.positions]
        return lines, (place.positions[len(place.positions) // 2], place.level + height / 2)
    left, bottom = place.cross[1] - width / 2, place.level
    hook = min(width, height) * 0.15
    entities: list[Entity] = [rectangle(item.layer, (left, bottom), (left + width, bottom + height)),
                              Line(item.layer, (left, bottom + height), (left + hook, bottom + height - hook)),
                              Line(item.layer, (left, bottom + height), (left + hook * 0.4, bottom + height - hook * 1.2))]
    return entities, (left + width, bottom + height / 2)


def _dowels(item: Marked, axis: str, at: float) -> tuple[list[Entity], Point | None]:
    """Los pasadores dibujados en el corte que pasa por su columna, con el gancho del pie hacia afuera."""
    run, place = item.run, item.place
    centre, offset = place.positions, place.cross
    along, across = (0, 1) if axis == "x" else (1, 0)
    if abs(centre[across] - at) > offset[across] + 1e-6:
        return [], None
    leg = 0.0 if run.hooks[0] is None else hook_leg(run.hooks[0], run.diameter) - run.diameter / 2
    entities: list[Entity] = []
    for side in (-1.0, 1.0):
        u = centre[along] + side * offset[along]
        entities.append(Polyline(item.layer, ((u + side * leg, place.span[0]), (u, place.span[0]), (u, place.span[1]))))
    return entities, (centre[along] + offset[along], (place.span[0] + place.span[1]) / 2)


def cartilla_view(drawing: Drawing, element: str, rows: list[ScheduleRow]) -> View:
    """La cartilla como tabla, con el croquis de la forma de cada marca y sus dimensiones A, B y C y la longitud de corte
    en metros (D-150), las mismas de la cartilla de la memoria (en mm) y del .dli."""
    scale, small = drawing.scale, drawing.text_height(small=True)
    view = View("cartilla", f"Cartilla de despiece {element}")
    width = sum(size for _, size in _COLUMNS) * scale
    lefts = [sum(size for _, size in _COLUMNS[:index]) * scale for index in range(len(_COLUMNS))]
    header, row_height = _HEADER * scale, _ROW * scale
    bottom = -header - row_height * (len(rows) + 1)
    view.entities.append(rectangle(TABLE, (0.0, 0.0), (width, bottom)))
    for left in lefts[1:]:
        view.entities.append(Line(TABLE, (left, 0.0), (left, bottom)))
    for (name, size), left in zip(_COLUMNS, lefts, strict=True):
        view.entities.append(Text(TABLE, (left + size * scale / 2, -header * 0.65), name, small, align="center"))
    view.entities.append(Line(TABLE, (0.0, -header), (width, -header)))
    for index, row in enumerate(rows):
        top = -header - index * row_height
        view.entities.append(Line(TABLE, (0.0, top - row_height), (width, top - row_height)))
        piece, dimensions = row.piece, dict(row.piece.dimensions)
        cells = [row.mark, piece.designation, str(piece.count), piece.shape,
                 *(metres(dimensions[name]) if name in dimensions else "" for name in ("A", "B", "C")),
                 metres(piece.cut_length), f"{row.mass:.1f}"]
        for column, (text, (_, size), left) in enumerate(zip(cells, _COLUMNS, lefts, strict=True)):
            if text and column != _SHAPE_COLUMN:
                view.entities.append(Text(TABLE, (left + size * scale / 2, top - row_height * 0.6), text, small, align="center"))
        view.entities.append(Text(TABLE, (lefts[_SHAPE_COLUMN] + 0.5 * small, top - 0.5 * small - small * 0.8), piece.shape,
                                  small * 0.8))
        view.entities += _shape(row, (lefts[_SHAPE_COLUMN], top), (_COLUMNS[_SHAPE_COLUMN][1] * scale, row_height), small)
    total = sum(row.mass for row in rows)
    last = bottom + row_height
    view.entities.append(Text(TABLE, (lefts[-1] - small, last - row_height * 0.6), "Total acero", small, align="right"))
    view.entities.append(Text(TABLE, (lefts[-1] + _COLUMNS[-1][1] * scale / 2, last - row_height * 0.6), f"{total:.1f}", small,
                              align="center"))
    _title(drawing, view)
    return view


_SHAPE_COLUMN = 3  # la columna "Forma": su nombre arriba a la izquierda y el croquis


def _shape(row: ScheduleRow, corner: Point, size: Point, text: float) -> list[Entity]:
    """Croquis de una forma en una celda de la cartilla (D-150): el estribo cerrado, o el tramo A con el gancho de cada
    extremo según su ángulo (90°: pata vertical; 180°: vuelta completa; 135°: pata inclinada hacia adentro), cada uno con
    el nombre de su dimensión (B en el inicio, C en el final)."""
    piece, (x, top), (width, height) = row.piece, corner, size
    if piece.shape == STIRRUP_SHAPE:
        left, right, low, high = x + 0.3 * width, x + 0.62 * width, top - 0.78 * height, top - 0.22 * height
        hook = 0.2 * (high - low)
        return [rectangle(TABLE, (left, low), (right, high)),
                Line(TABLE, (left, high), (left + hook, high - hook)),
                Line(TABLE, (left, high), (left + 0.4 * hook, high - 1.3 * hook)),
                Text(TABLE, ((left + right) / 2, low - 0.12 * height - text * 0.5), "A", text * 0.8, align="center"),
                Text(TABLE, (right + 0.03 * width, (low + high) / 2 - text * 0.4), "B", text * 0.8),
                Text(TABLE, (left - 0.03 * width, high - text * 0.8), "C", text * 0.8, align="right")]
    x0, x1 = x + 0.2 * width, x + 0.8 * width
    base, leg = top - 0.75 * height, top - 0.3 * height
    names = [name for name in ("B", "C") if name in dict(piece.dimensions)]
    entities: list[Entity] = [Text(TABLE, ((x0 + x1) / 2, base + 0.08 * height), "A", text * 0.8, align="center")]
    ends: list[list[Point]] = [[], []]
    for side, angle in enumerate(piece.angles):
        if angle is None:
            continue
        name = names.pop(0)
        end, inward = (x0, 1.0) if side == 0 else (x1, -1.0)
        ends[side] = _hook_sketch(angle, (end, base), (inward, leg - base, min(_HOOK_SKETCH * width, _HOOK_ROOM * height)))
        tip = ends[side][-1]
        entities.append(Text(TABLE, (end - inward * 0.04 * width, (base + tip[1]) / 2 - text * 0.4), name, text * 0.8,
                             align="right" if side == 0 else "left"))
    points = [*reversed(ends[0]), (x0, base), (x1, base), *ends[1]]
    return [Polyline(TABLE, tuple(points)), *entities]


def _hook_sketch(angle: int, end: Point, sizes: tuple[float, float, float]) -> list[Point]:
    """Los puntos de un gancho en el croquis, desde el extremo del tramo A: inward es +1 si el tramo sigue hacia la derecha;
    rise, el alto de la pata de 90°; radius, el de la vuelta de 180°."""
    (x, y), (inward, rise, radius) = end, sizes
    if angle == _HALF_TURN_SKETCH:
        arc = [(x - inward * radius * math.sin(math.pi * k / 6), y + radius * (1 - math.cos(math.pi * k / 6))) for k in range(1, 7)]
        return [*arc, (x + inward * radius * 1.5, y + 2 * radius)]
    if angle == _QUARTER_TURN_SKETCH:
        return [(x, y + rise)]
    return [(x + inward * rise * 0.5, y + rise * 0.8)]  # 135°: inclinada hacia adentro


_HALF_TURN_SKETCH = 180
_QUARTER_TURN_SKETCH = 90
