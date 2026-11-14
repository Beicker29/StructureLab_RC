"""Vistas neutras del refuerzo (D-126, D-132): plantas, cortes, planta de geometría y cartilla con el croquis de cada
forma, a partir de las corridas del despiece (con su ubicación, Placement) y sus marcas. Sin fórmulas normativas: los
ganchos y los empalmes llegan ya dimensionados.

Convenciones (D-132):
- Cada grupo de barras (grupo y designación del despiece) lleva un número en un círculo, el mismo en todas las vistas del
  elemento; la leyenda de cada vista dice, por número, la cantidad, la barra, la separación y sus marcas de la cartilla.
- Cada barra va en la capa de su diámetro (REFUERZO_<designación>).
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

from dataclasses import dataclass

from structurelab_rc.detailing.schedule import BarRun, Placement, ScheduleRow, hook_leg, splice_spans
from structurelab_rc.drawing.model import Circle, Dimension, Drawing, Entity, Line, Point, Polyline, Text, View, bar_layer

_LABEL_STEP = 1.8  # separación de los rótulos apilados, en alturas de texto
_PAIR = 2  # con dos barras o menos (piel, caras opuestas) el rótulo no da separación
_DOT = 0.4  # mm de papel: radio mínimo del punto de una barra cortada
_ROW = 12.0  # mm de papel: alto de una fila de la cartilla
_HEADER = 8.0  # mm de papel: alto del encabezado de la cartilla
_COLUMNS = (("Marca", 18.0), ("Barra", 12.0), ("Cant.", 10.0), ("Forma", 46.0), ("A", 14.0), ("B", 14.0), ("C", 14.0),
            ("L corte", 18.0), ("Peso kg", 16.0))
_ZONE_GAP = 1.5  # un hueco mayor que 1.5 separaciones parte un grupo en zonas
_SPLICE_SHIFT = 0.8  # mm de papel: desplazamiento entre los tramos empalmados dibujados
_TICK = 1.0  # mm de papel: marca de los extremos de la línea de distribución
_BUBBLE = 0.9  # radio del círculo del número, en alturas de texto
_SAME = 1.0  # mm: dos cotas a menos de esto son la misma


@dataclass(frozen=True)
class Marked:
    """Una corrida del despiece con sus marcas de la cartilla y el número de su grupo en el dibujo."""

    run: BarRun
    marks: tuple[str, ...]
    number: int
    stock: float  # longitud comercial: fija los tramos empalmados que se dibujan

    @property
    def place(self) -> Placement:
        assert self.run.placement is not None
        return self.run.placement

    @property
    def layer(self) -> str:
        return bar_layer(self.run.designation)


def numbered(runs: list[BarRun], marks: list[tuple[str, ...]], stock: float) -> list[Marked]:
    """Las corridas ubicadas con sus marcas y el número de su grupo (grupo y designación), en el orden del despiece."""
    numbers: dict[tuple[str, str], int] = {}
    return [Marked(run, own, numbers.setdefault((run.group, run.designation), len(numbers) + 1), stock)
            for run, own in zip(runs, marks, strict=True) if run.placement is not None]


def legend_text(items: list[Marked]) -> str:
    """El texto de la leyenda de un número: cantidad, barra, separación (o lo propio de estribos y pasadores) y marcas."""
    run, place = items[0].run, items[0].place
    marks = ", ".join(dict.fromkeys(mark for item in items for mark in item.marks))
    if place.along == "estribo":
        body = f"E{run.designation} {run.note}"
    elif place.along == "z":
        body = f"{sum(item.run.count for item in items)} {run.designation} pasadores"
    else:
        gap = _gap(place.positions) if len(place.positions) > _PAIR else 0.0  # dos barras: sin separación
        body = f"{sum(item.run.count for item in items)} {run.designation}" + (f" c/{gap:.0f}" if gap else "")
    return f"{body} ({marks})"


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


def _bubble(drawing: Drawing, centre: Point, number: int) -> list[Entity]:
    """El número de un grupo en un círculo."""
    height = drawing.text_height(small=True)
    return [Circle("TEXTOS", centre, _BUBBLE * height, filled=False),
            Text("TEXTOS", (centre[0], centre[1] - 0.35 * height), str(number), height, align="center")]


def _legend_line(drawing: Drawing, at: Point, number: int, text: str) -> list[Entity]:
    height = drawing.text_height(small=True)
    return [*_bubble(drawing, (at[0] + _BUBBLE * height, at[1]), number),
            Text("TEXTOS", (at[0] + 2.4 * height, at[1] - 0.35 * height), text, height)]


def _legend(drawing: Drawing, view: View, marked: list[Marked], shown: list[int], at: Point) -> None:
    """La leyenda de los números que aparecen en la vista, de arriba abajo, desde at."""
    height = drawing.text_height(small=True)
    for index, number in enumerate(sorted(set(shown))):
        items = [item for item in marked if item.number == number]
        view.entities += _legend_line(drawing, (at[0], at[1] - index * _LABEL_STEP * height), number, legend_text(items))


def _labels(drawing: Drawing, view: View, anchors: list[tuple[Point, Marked]], marked: list[Marked], corner: Point) -> None:
    """Rótulos de un corte, apilados a la derecha (corner = esquina superior derecha de lo dibujado): el número y su
    leyenda, con una línea a cada barra del grupo, de arriba abajo en el orden de las barras."""
    height = drawing.text_height(small=True)
    x, top = corner[0] + drawing.gap(), corner[1]
    grouped: dict[int, list[Point]] = {}
    for anchor, item in anchors:
        grouped.setdefault(item.number, []).append(anchor)
    ordered = sorted(grouped.items(), key=lambda pair: -max(point[1] for point in pair[1]))
    for index, (number, points) in enumerate(ordered):
        y = top - index * _LABEL_STEP * height
        view.entities += [Line("TEXTOS", anchor, (x, y)) for anchor in points]
        view.entities += _legend_line(drawing, (x, y), number, legend_text([item for item in marked if item.number == number]))


def _dimensions(drawing: Drawing, view: View, outline: Polyline) -> None:
    """Cotas del ancho y el alto del contorno principal, abajo y a la izquierda."""
    xs, ys = [p[0] for p in outline.points], [p[1] for p in outline.points]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    height, gap = drawing.text_height(small=True), drawing.gap()
    view.entities += [Dimension("COTAS", (x0, y0), (x1, y0), -gap, f"{x1 - x0:.0f}", height),
                      Dimension("COTAS", (x0, y0), (x0, y1), gap, f"{y1 - y0:.0f}", height)]


def _title(drawing: Drawing, view: View, scaled: bool = True) -> None:
    x0, y0, x1, _ = view.bounds()
    text = view.title.upper() + (f" - ESC. 1:{drawing.scale:.0f}" if scaled else "")
    view.entities.append(Text("TEXTOS", ((x0 + x1) / 2, y0 - 2 * drawing.gap()), text, drawing.text_height(), align="center"))


def _column_labels(drawing: Drawing, view: View, columns: list[tuple[str, Polyline]]) -> None:
    for column_id, column in columns:
        xs, ys = [p[0] for p in column.points], [p[1] for p in column.points]
        view.entities.append(Text("TEXTOS", ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), column_id,
                                  drawing.text_height(small=True), align="center"))


def plan_view(drawing: Drawing, names: tuple[str, str], outline: tuple[list[Polyline], list[tuple[str, Polyline]]],
              marked: list[Marked], layer: tuple[float, bool]) -> View:
    """Planta (names = nombre y título) del refuerzo inferior o superior: el concreto y las columnas de outline y una barra
    representativa por zona de los grupos horizontales con z ≤ split (layer = (split, False)) o z > split (layer =
    (split, True)), con la leyenda a la derecha."""
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
    right = x1 + _zone_dimensions(drawing, view, spans, (x1, y1))
    _legend(drawing, view, marked, [item.number for item in chosen], (right + drawing.gap(), y1))
    _dimensions(drawing, view, concrete[0])
    _title(drawing, view)
    return view


def _zone_dimensions(drawing: Drawing, view: View, spans: dict[str, list[tuple[float, float]]], corner: Point) -> float:
    """Cotas de las zonas de cada dirección con más de una zona: las de las barras y (zonas a lo largo de x) arriba y las de
    las barras x a la derecha; devuelve lo que ocupan a la derecha."""
    height, gap = drawing.text_height(small=True), drawing.gap()
    right = 0.0
    if len(spans["y"]) > 1:
        view.entities += [Dimension("COTAS", (low, corner[1]), (high, corner[1]), gap, f"{high - low:.0f}", height)
                          for low, high in spans["y"] if high - low > _SAME]
    if len(spans["x"]) > 1:
        view.entities += [Dimension("COTAS", (corner[0], high), (corner[0], low), gap, f"{high - low:.0f}", height)
                          for low, high in spans["x"] if high - low > _SAME]
        right = gap + height
    return right


def _plan_bar(drawing: Drawing, item: Marked, zone: tuple[float, ...], index: int) -> list[Entity]:
    """La barra representativa de una zona (en su barra central), con los ganchos abatidos hacia la distribución, los
    tramos empalmados desplazados y traslapados, la línea de distribución y el número del grupo."""
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
        entities.append(Text("TEXTOS", at((begin + end) / 2, middle - 1.4 * height), f"traslapo {end - begin:.0f}",
                             height, align="center"))
    fraction = 0.15 + 0.1 * (index % 6)  # cada grupo con su línea de distribución en otro punto del largo
    along = place.span[0] + fraction * (place.span[1] - place.span[0])
    tick = _TICK * drawing.scale
    entities.append(Line("COTAS", at(along, zone[0]), at(along, zone[-1])))
    entities += [Line("COTAS", at(along - tick, position - tick), at(along + tick, position + tick)) for position in (zone[0], zone[-1])]
    entities += _bubble(drawing, at(place.span[1] - 2 * height, middle + 1.4 * height), item.number)  # cerca del extremo
    return entities

def titled(drawing: Drawing, view: View) -> View:
    """La vista con su título y la escala debajo de lo dibujado."""
    _title(drawing, view)
    return view


def table_view(drawing: Drawing, names: tuple[str, str], columns: tuple[tuple[str, float], ...], rows: list[list[str]]) -> View:
    """Una tabla (names = nombre y título) con encabezados y filas de texto; columns = (encabezado, ancho en mm de papel)."""
    scale, small = drawing.scale, drawing.text_height(small=True)
    view = View(*names)
    width = sum(size for _, size in columns) * scale
    lefts = [sum(size for _, size in columns[:index]) * scale for index in range(len(columns))]
    header, row_height = _HEADER * scale, _HEADER * scale
    bottom = -header - row_height * len(rows)
    view.entities.append(rectangle("CARTILLA", (0.0, 0.0), (width, bottom)))
    view.entities += [Line("CARTILLA", (left, 0.0), (left, bottom)) for left in lefts[1:]]
    view.entities += [Text("CARTILLA", (left + size * scale / 2, -header * 0.65), name, small, align="center")
                      for (name, size), left in zip(columns, lefts, strict=True)]
    for index, row in enumerate(rows):
        top = -header - index * row_height
        view.entities.append(Line("CARTILLA", (0.0, top), (width, top)))
        view.entities += [Text("CARTILLA", (left + size * scale / 2, top - row_height * 0.65), text, small, align="center")
                          for text, (_, size), left in zip(row, columns, lefts, strict=True) if text]
    _title(drawing, view, scaled=False)
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
    view.entities += [rectangle("COTAS", (x0 + cover, y0 + cover), (x1 - cover, y1 - cover), dashed=True),
                      Text("COTAS", (x0 + cover + 0.5 * height, y0 + cover + 0.5 * height), f"recubrimiento {cover:.0f} mm", height)]
    stops_x, chains_y = [x0, x1], []
    for column_id, (cx, cy), (bx, by) in columns:
        view.entities += [rectangle("COLUMNAS", (cx - bx / 2, cy - by / 2), (cx + bx / 2, cy + by / 2)),
                          Polyline("EJES", ((x0 - gap / 2, cy), (x1 + gap / 2, cy)), dashed=True),
                          Polyline("EJES", ((cx, y0 - gap / 2), (cx, y1 + gap / 2)), dashed=True),
                          Text("TEXTOS", (cx + 0.3 * height, cy + by / 2 + 0.4 * height), column_id, height)]
        stops_x += [cx - bx / 2, cx + bx / 2]
        chains_y.append(_stops([y0, cy - by / 2, cy + by / 2, y1]))
    lines = [y for line in extra if len(ys := {round(p[1], 1) for p in line.points}) == 1 for y in ys]  # el alma de la T
    if lines:
        chains_y.insert(0, _stops([y0, *lines, y1]))
    chain_x = _stops(stops_x)
    view.entities += [Dimension("COTAS", (a, y0), (b, y0), -gap, f"{b - a:.0f}", height)
                      for a, b in zip(chain_x, chain_x[1:], strict=False)]
    unique = [chain for index, chain in enumerate(chains_y) if chain not in chains_y[:index]]
    for level, chain in enumerate(unique, start=1):
        view.entities += [Dimension("COTAS", (x0, a), (x0, b), level * gap, f"{b - a:.0f}", height)
                          for a, b in zip(chain, chain[1:], strict=False)]
    view.entities += [Dimension("COTAS", (x0, y0), (x1, y0), -2 * gap, f"{x1 - x0:.0f}", height),
                      Dimension("COTAS", (x0, y0), (x0, y1), (len(unique) + 1) * gap, f"{y1 - y0:.0f}", height),
                      Text("TEXTOS", (x0, y0 - 3.2 * gap), note, height)]
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
    barras y los estribos, con el número y la leyenda de cada grupo a la derecha."""
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
        radius = max(db / 2, _DOT * drawing.scale)
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
    """La cartilla como tabla, con el croquis de la forma de cada marca y sus dimensiones A, B y C."""
    scale, small = drawing.scale, drawing.text_height(small=True)
    view = View("cartilla", f"Cartilla de despiece {element}")
    width = sum(size for _, size in _COLUMNS) * scale
    lefts = [sum(size for _, size in _COLUMNS[:index]) * scale for index in range(len(_COLUMNS))]
    header, row_height = _HEADER * scale, _ROW * scale
    bottom = -header - row_height * (len(rows) + 1)
    view.entities.append(rectangle("CARTILLA", (0.0, 0.0), (width, bottom)))
    for left in lefts[1:]:
        view.entities.append(Line("CARTILLA", (left, 0.0), (left, bottom)))
    for (name, size), left in zip(_COLUMNS, lefts, strict=True):
        view.entities.append(Text("CARTILLA", (left + size * scale / 2, -header * 0.65), name, small, align="center"))
    view.entities.append(Line("CARTILLA", (0.0, -header), (width, -header)))
    for index, row in enumerate(rows):
        top = -header - index * row_height
        view.entities.append(Line("CARTILLA", (0.0, top - row_height), (width, top - row_height)))
        piece, dimensions = row.piece, dict(row.piece.dimensions)
        cells = [row.mark, piece.designation, str(piece.count), "",
                 *(f"{dimensions[name]:.0f}" if name in dimensions else "" for name in ("A", "B", "C")),
                 f"{piece.cut_length:.0f}", f"{row.mass:.1f}"]
        for text, (_, size), left in zip(cells, _COLUMNS, lefts, strict=True):
            if text:
                view.entities.append(Text("CARTILLA", (left + size * scale / 2, top - row_height * 0.6), text, small, align="center"))
        view.entities += _shape((piece.shape, tuple(dimensions)), (lefts[3], top), (_COLUMNS[3][1] * scale, row_height), small)
    total = sum(row.mass for row in rows)
    last = bottom + row_height
    view.entities.append(Text("CARTILLA", (lefts[-1] - small, last - row_height * 0.6), "Total acero", small, align="right"))
    view.entities.append(Text("CARTILLA", (lefts[-1] + _COLUMNS[-1][1] * scale / 2, last - row_height * 0.6), f"{total:.1f}", small,
                              align="center"))
    _title(drawing, view, scaled=False)
    return view


def _shape(form: tuple[str, tuple[str, ...]], corner: Point, size: Point, text: float) -> list[Entity]:
    """Croquis de una forma (recta, L, U o estribo, con los nombres de sus dimensiones) en una celda de la cartilla."""
    (shape, names), (x, top), (width, height) = form, corner, size
    x0, x1 = x + 0.15 * width, x + 0.85 * width
    base, leg = top - 0.75 * height, top - 0.25 * height
    if shape == "estribo":
        left, right, low, high = x + 0.3 * width, x + 0.62 * width, top - 0.78 * height, top - 0.22 * height
        hook = 0.2 * (high - low)
        return [rectangle("CARTILLA", (left, low), (right, high)),
                Line("CARTILLA", (left, high), (left + hook, high - hook)),
                Line("CARTILLA", (left, high), (left + 0.4 * hook, high - 1.3 * hook)),
                Text("CARTILLA", ((left + right) / 2, low - 0.12 * height - text * 0.5), "A", text * 0.8, align="center"),
                Text("CARTILLA", (right + 0.03 * width, (low + high) / 2 - text * 0.4), "B", text * 0.8),
                Text("CARTILLA", (left - 0.03 * width, high - text * 0.8), "C", text * 0.8, align="right")]
    points: list[Point] = [(x0, base), (x1, base)]
    letters: list[Entity] = [Text("CARTILLA", ((x0 + x1) / 2, base + 0.08 * height), "A", text * 0.8, align="center")]
    if shape in ("L", "U"):
        points.append((x1, leg))
        letters.append(Text("CARTILLA", (x1 + 0.03 * width, (base + leg) / 2 - text * 0.4), names[-1], text * 0.8))
    if shape == "U":
        points.insert(0, (x0, leg))
        letters.append(Text("CARTILLA", (x0 - 0.03 * width, (base + leg) / 2 - text * 0.4), "B", text * 0.8, align="right"))
    return [Polyline("CARTILLA", tuple(points)), *letters]
