"""Vistas neutras del refuerzo (D-126, D-132, D-150): plantas, cortes, planta de geometría y cartilla con el croquis de
cada forma, a partir de las corridas del despiece (con su ubicación, Placement), sus marcas y la longitud de corte de cada
marca en la cartilla. Sin fórmulas normativas: los ganchos y los empalmes llegan ya dimensionados.

Convenciones (D-150 y D-158, como el plano de despiece de referencia):
- Cada barra representativa y cada grupo de un corte lleva su rótulo: cantidad, barra, separación, longitud de corte de
  cada marca y las marcas de la cartilla: "22#6 C/.15 L=6.65 (ZC_m-01)". La longitud es la de la cartilla (D-147), la
  misma del .dli, del peso y del costo; las medidas van en metros (metres).
- Cada barra se dibuja con las dimensiones A, B y C de su pieza en la cartilla (tramo y patas), así que la polilínea mide
  la longitud de corte; el rótulo liga cada L a esa polilínea (Text.fields: en el DXF, un campo de AutoCAD), salvo en las
  barras que se miden por el eje (135° y estribos).
- Cada barra va en la capa de su diámetro (Borde_<designación>).
- En planta (x a la derecha, y arriba), las barras de un grupo se parten en zonas (donde el hueco entre dos barras
  vecinas supera 1.5 separaciones) y cada zona se dibuja con una barra representativa, sus patas abatidas y acotadas, una
  línea de distribución (cota sin texto con flechas) entre los límites de la zona y la marca de la barra sobre ella. Las
  zonas se dividen con líneas a trazos y se acotan en cadena; cada columna se acota con su tamaño y la distancia a los
  bordes, y la base con su ancho arriba y su largo a la izquierda.
- En un corte o alzado paralelo a X (cut "x", a la ordenada y = at) la abscisa es x y en uno paralelo a Y (cut "y", en
  x = at) es y; la vertical es z desde la base. Las barras paralelas al plano se dibujan con las patas de la cartilla si
  hay una a menos de una separación del plano; las perpendiculares como puntos, con un rótulo por zona.
- La planta de geometría acota la base, las columnas y su posición desde los bordes, con los ejes de las columnas y el
  recubrimiento.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from structurelab_rc.detailing.schedule import STIRRUP_SHAPE, BarRun, Piece, Placement, ScheduleRow, splice_spans
from structurelab_rc.detailing.units import scaled
from structurelab_rc.drawing.model import (
    AXES,
    COLUMN_FILL,
    DIMENSIONS,
    DISTRIBUTION,
    LABELS,
    PAPER_MARK,
    PAPER_SUBTITLE,
    SUBTITLE,
    TABLE,
    ZONE_COLOR,
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
_CM = 10.0  # mm: los límites entre zonas se redondean a 1 cm (D-158)
_SPLICE_SHIFT = 0.8  # mm de papel: desplazamiento entre los tramos empalmados dibujados
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
    pieces: tuple[Piece, ...] = ()  # la pieza de la cartilla de cada marca: sus dimensiones A, B y C dibujan la barra (D-158)

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
    pieces = {row.mark: row.piece for row in rows}
    numbers: dict[tuple[str, str], int] = {}
    return [Marked(run, own, numbers.setdefault((run.group, run.designation), len(numbers) + 1), stock,
                   tuple(pieces[mark].cut_length for mark in own), tuple(pieces[mark] for mark in own))
            for run, own in zip(runs, marks, strict=True) if run.placement is not None]


def piece_legs(piece: Piece) -> tuple[float, float, float]:
    """(pata del inicio, tramo A, pata del final) de una pieza de la cartilla (D-158): B es la del primer extremo con gancho
    y C la del segundo, como en el croquis de la cartilla; sin gancho, 0."""
    dimensions = dict(piece.dimensions)
    names = [name for name in ("B", "C") if name in dimensions]
    start = dimensions[names.pop(0)] if piece.angles[0] is not None and names else 0.0
    end = dimensions[names.pop(0)] if piece.angles[1] is not None and names else 0.0
    return start, dimensions["A"], end


def drawn_is_cut(piece: Piece) -> bool:
    """Si la barra dibujada con A, B y C mide la longitud de corte de la cartilla (D-147, D-158): las barras rectas y las
    de ganchos de 90° o 180° (tramo + L o U); no las de 135° ni los estribos, que se miden por el eje."""
    start, straight, end = piece_legs(piece)
    plain = all(angle in (None, 90, 180) for angle in piece.angles)
    return plain and abs(start + straight + end - piece.cut_length) < _SAME / 2


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


def _box(outline: Polyline) -> tuple[float, float, float, float]:
    """(x mínimo, y mínimo, x máximo, y máximo) de un contorno."""
    xs, ys = [p[0] for p in outline.points], [p[1] for p in outline.points]
    return min(xs), min(ys), max(xs), max(ys)


def _dim(points: tuple[Point, Point], outward: Point, offset: float, height: float) -> Dimension:
    """Cota entre dos puntos con la línea de cota corrida offset hacia outward (el lado de afuera)."""
    p, q = points
    left = (-(q[1] - p[1]), q[0] - p[0])  # la normal izquierda del sentido p -> q
    if left[0] * outward[0] + left[1] * outward[1] < 0:
        p, q = q, p
    return Dimension(DIMENSIONS, p, q, offset, metres(math.hypot(q[0] - p[0], q[1] - p[1])), height)


def _chain(stops: list[float], line: tuple[str, float], side: tuple[Point, float], height: float) -> list[Dimension]:
    """Una cadena de cotas por las posiciones stops; line = (eje "x" o "y" a lo largo del cual van, coordenada fija de la
    recta); side = (sentido hacia afuera, distancia de la línea de cota)."""
    axis, fixed = line
    outward, offset = side
    ordered = _stops(stops)

    def point(value: float) -> Point:
        return (value, fixed) if axis == "x" else (fixed, value)

    return [_dim((point(a), point(b)), outward, offset, height) for a, b in zip(ordered, ordered[1:], strict=False)]


def _dimensions(drawing: Drawing, view: View, outline: Polyline) -> None:
    """Cotas totales de la planta, como los planos de despiece (D-158): el ancho arriba y el largo a la izquierda."""
    x0, y0, x1, y1 = _box(outline)
    height, gap = drawing.text_height(small=True), drawing.gap()
    view.entities += [_dim(((x0, y1), (x1, y1)), (0.0, 1.0), gap, height), _dim(((x0, y0), (x0, y1)), (-1.0, 0.0), gap, height)]


def _title(drawing: Drawing, view: View, scaled: bool = False, text: str | None = None) -> None:
    """El título de la vista debajo de lo dibujado (por omisión, el de la vista en mayúsculas); la escala va en el título del
    elemento (D-150), salvo en las vistas sueltas (scaled: la planta de localización)."""
    x0, y0, x1, _ = view.bounds()
    shown = (text or view.title.upper()) + (f" - ESC. 1:{drawing.scale:.0f}" if scaled else "")
    view.entities.append(Text(SUBTITLE, ((x0 + x1) / 2, y0 - 2 * drawing.gap()), shown, drawing.paper(PAPER_SUBTITLE), align="center"))


def plan_view(drawing: Drawing, names: tuple[str, str], outline: tuple[list[Polyline], list[tuple[str, Polyline]]],
              marked: list[Marked], layer: tuple[float, bool]) -> View:
    """Planta (names = nombre y título) del refuerzo inferior o superior, como los planos de despiece (D-158): el concreto y
    las columnas de outline, una barra representativa por zona de los grupos horizontales con z ≤ split (layer = (split,
    False)) o z > split (layer = (split, True)), las divisiones de las zonas, las cotas y el título "REFUERZO INFERIOR" o
    "REFUERZO SUPERIOR"."""
    concrete, columns = outline
    split, upper = layer
    view = View(*names, [*concrete, *(column for _, column in columns)])
    box = _box(concrete[0])
    chosen = [item for item in marked if item.place.along in ("x", "y") and (item.place.level > split) == upper]
    for along in ("x", "y"):
        own = sorted(((item, zone) for item in chosen if item.place.along == along for zone in zones(item.place.positions)),
                     key=lambda pair: pair[1][0])
        if own:
            bounds = _zone_bounds([zone for _, zone in own], (box[1], box[3]) if along == "x" else (box[0], box[2]))
            for (item, zone), low, high in zip(own, bounds, bounds[1:], strict=False):
                _plan_bar(drawing, view, (item, zone), ((low, high), box, [_box(column) for _, column in columns]))
            _zone_divisions(drawing, view, along, bounds, box)
    _column_dimensions(drawing, view, [column for _, column in columns], box)
    _dimensions(drawing, view, concrete[0])
    _title(drawing, view, text="REFUERZO SUPERIOR" if upper else "REFUERZO INFERIOR")
    return view


def _zone_bounds(spans: list[tuple[float, ...]], edges: tuple[float, float]) -> list[float]:
    """Los límites de las zonas ordenadas (D-158): los bordes de la base y, entre dos zonas vecinas, el punto medio entre la
    última barra de una y la primera de la otra, redondeado a 1 cm (las cotas de las zonas en centímetros, como el plano
    de referencia)."""
    middles = [round((previous[-1] + following[0]) / 2 / _CM) * _CM for previous, following in zip(spans, spans[1:], strict=False)]
    return [edges[0], *(min(max(middle, edges[0]), edges[1]) for middle in middles), edges[1]]


def _zone_divisions(drawing: Drawing, view: View, along: str, bounds: list[float], box: tuple[float, float, float, float]) -> None:
    """Las divisiones entre las zonas de una dirección (líneas a trazos en gris a todo lo ancho) y, si hay más de una zona,
    su cadena de cotas: a la derecha las de las barras a lo largo de x y abajo las de las barras a lo largo de y."""
    if len(bounds) <= _PAIR:
        return
    x0, y0, x1, y1 = box
    height, gap = drawing.text_height(small=True), drawing.gap()
    for bound in bounds[1:-1]:
        points = ((x0, bound), (x1, bound)) if along == "x" else ((bound, y0), (bound, y1))
        view.entities.append(Polyline(DISTRIBUTION, points, dashed=True, color=ZONE_COLOR))
    if along == "x":
        view.entities += _chain(bounds, ("y", x1), ((1.0, 0.0), gap), height)
    else:
        view.entities += _chain(bounds, ("x", y0), ((0.0, -1.0), gap), height)


def _column_dimensions(drawing: Drawing, view: View, columns: list[Polyline], box: tuple[float, float, float, float]) -> None:
    """Cotas de cada columna en planta (D-158): su ancho y la distancia de su cara al borde +X, debajo de ella, y su alto y
    la distancia de su cara al borde más cercano en Y, a su derecha."""
    x0, y0, x1, y1 = box
    height, gap = drawing.text_height(small=True), drawing.gap()
    for column in columns:
        cx0, cy0, cx1, cy1 = _box(column)
        view.entities += _chain([cx0, cx1, x1], ("x", cy0), ((0.0, -1.0), 0.4 * gap), height)
        stops = [cy0, cy1, y1] if y1 - cy1 <= cy0 - y0 else [y0, cy0, cy1]
        view.entities += _chain(stops, ("y", cx1), ((1.0, 0.0), 0.4 * gap), height)


Box = tuple[float, float, float, float]


def _representative(zone: tuple[float, ...], horizontal: bool) -> float:
    """La barra que representa una zona, como el plano de referencia (D-158): en las barras a lo largo de x, la segunda
    desde el borde alto de la zona (su rótulo queda encima, en la zona); en las de y, la de un cuarto de la zona."""
    if horizontal:
        return zone[-2] if len(zone) > _PAIR else zone[-1]
    return zone[len(zone) // 4]


def _crossed(columns: list[Box], horizontal: bool, band: tuple[float, float]) -> list[tuple[float, float]]:
    """Los intervalos, a lo largo de una barra (horizontal: a lo largo de x), de las columnas que tocan la franja band a
    través de ella (lo que ocupa su rótulo)."""
    result = []
    for x0, y0, x1, y1 in columns:
        along, across = ((x0, x1), (y0, y1)) if horizontal else ((y0, y1), (x0, x1))
        if across[1] > band[0] and across[0] < band[1]:
            result.append(along)
    return result


def _free_middle(span: tuple[float, float], blocked: list[tuple[float, float]]) -> float:
    """El centro del tramo más largo de span que no tapan los intervalos blocked (las columnas que cruza el rótulo)."""
    free, cursor = [], span[0]
    for low, high in sorted(blocked):
        if low > cursor:
            free.append((cursor, min(low, span[1])))
        cursor = max(cursor, high)
    if cursor < span[1]:
        free.append((cursor, span[1]))
    best = max(free, key=lambda stretch: stretch[1] - stretch[0], default=span)
    return (best[0] + best[1]) / 2


def _plan_bar(drawing: Drawing, view: View, chosen: tuple[Marked, tuple[float, ...]],
              extent: tuple[tuple[float, float], Box, list[Box]]) -> None:
    """La barra representativa de una zona (en su barra central), como los planos de despiece (D-158): dibujada con las
    dimensiones A, B y C de su pieza en la cartilla (así mide la longitud de corte, la misma del .dli), con las patas
    abatidas (hacia abajo en las barras a lo largo de x, a la derecha en las de y) y su cota; los tramos empalmados
    desplazados y traslapados; la línea de distribución, una cota sin texto con flechas entre los límites de la zona; la
    marca de la barra sobre ella, y el rótulo de la zona sobre la barra (girado en las barras a lo largo de y), con cada
    L ligada a la polilínea que mide."""
    (item, zone), ((low, high), box, columns) = chosen, extent
    run, place = item.run, item.place
    height, gap = drawing.text_height(small=True), drawing.gap()
    horizontal = place.along == "x"
    leg = -1.0 if horizontal else 1.0

    def at(along: float, across: float) -> Point:
        return (along, across) if horizontal else (across, along)

    middle = _representative(zone, horizontal)
    legs, fields, centre = _bar_shape(drawing, view, item, (middle, at))
    for foot, tip, outward in legs:
        direction = (outward, 0.0) if horizontal else (0.0, outward)
        view.entities.append(_dim((foot, tip), direction, 0.4 * gap, height))
    x0, y0, x1, y1 = box
    # Las barras en y, con su línea en el centro del tramo más largo sin columnas, como el plano de referencia.
    line = x0 + _LINE_AT * (x1 - x0) if horizontal else _free_middle((y0, y1), [(c[1], c[3]) for c in columns])
    mark = drawing.paper(PAPER_MARK)
    view.entities += [Dimension(DISTRIBUTION, at(line, low), at(line, high), 0.0, "", height),
                      Circle(item.layer, at(line, middle), mark), Circle(DIMENSIONS, at(line, middle), mark, filled=False)]
    count = round(len(zone) * run.count / len(place.positions))
    text = label_text([item], count, zone)
    blocked = _crossed(columns, horizontal, (middle - 2 * height, middle + 2 * height))
    if blocked:  # el rótulo en el tramo más largo libre de columnas
        half = (place.span[1] - place.span[0]) / 2
        centre = _free_middle((centre - half, centre + half), blocked)
    view.entities.append(Text(LABELS, at(centre, middle - leg * 0.4 * height), text, height, align="center",
                              rotation=0.0 if horizontal else 90.0, fields=tuple(fields)))


Leg = tuple[Point, Point, float]  # pata dibujada: (pie, punta, sentido hacia afuera a lo largo de la barra)


def _bar_shape(drawing: Drawing, view: View, item: Marked,
               place_at: tuple[float, Callable[[float, float], Point]]) -> tuple[list[Leg], list[int], float]:
    """Dibuja la barra representativa en la abscisa transversal middle (place_at = (middle, at), con at(a lo largo, a
    través) -> punto) y devuelve sus patas, los índices de las polilíneas que miden la longitud de corte (para el rótulo)
    y el centro de la barra a lo largo. Una sola pieza: con las dimensiones de su cartilla (D-158). Empalmada: los tramos
    de la longitud comercial, desplazados y traslapados, con las patas de la primera y la última pieza."""
    middle, at = place_at
    run, place = item.run, item.place
    horizontal = place.along == "x"
    leg = -1.0 if horizontal else 1.0
    start = place.span[0]
    legs: list[Leg] = []
    if len(item.pieces) == 1:
        first, straight, last = piece_legs(item.pieces[0])
        end = start + straight
        points = [at(start, middle), at(end, middle)]
        if first:
            points.insert(0, at(start, middle + leg * first))
            legs.append((at(start, middle), at(start, middle + leg * first), -1.0))
        if last:
            points.append(at(end, middle + leg * last))
            legs.append((at(end, middle), at(end, middle + leg * last), 1.0))
        fields = [len(view.entities)] if drawn_is_cut(item.pieces[0]) else []
        view.entities.append(Polyline(item.layer, tuple(points)))
        return legs, fields, (start + end) / 2
    first, _, _ = piece_legs(item.pieces[0])
    _, _, last = piece_legs(item.pieces[-1])
    segments = [(start + a, start + b) for a, b in splice_spans(run, item.stock)]
    shift, height = _SPLICE_SHIFT * drawing.scale, drawing.text_height(small=True)
    for number, (a, b) in enumerate(segments):
        across = middle + shift * (number % 2)
        points = [at(a, across), at(b, across)]
        if number == 0 and first:
            points.insert(0, at(a, across + leg * first))
            legs.append((at(a, across), at(a, across + leg * first), -1.0))
        if number == len(segments) - 1 and last:
            points.append(at(b, across + leg * last))
            legs.append((at(b, across), at(b, across + leg * last), 1.0))
        view.entities.append(Polyline(item.layer, tuple(points)))
    for (_, end), (begin, _) in zip(segments, segments[1:], strict=False):
        view.entities.append(Text(LABELS, at((begin + end) / 2, middle + leg * 1.4 * height), f"traslapo {metres(end - begin)}",
                                  height, align="center", rotation=0.0 if horizontal else 90.0))
    return legs, [], (place.span[0] + place.span[1]) / 2


# Dónde va la línea de distribución de las barras a lo largo de x (distribuidas en y), como fracción del ancho desde −X
# (D-158), como el plano de referencia; la de las barras a lo largo de y, en el tramo más largo libre de columnas.
_LINE_AT = 0.16


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


def section_view(drawing: Drawing, names: tuple[str, str], cut: tuple[str, float], marked: list[Marked],
                 frame: tuple[list[Polyline], list[Entity], list[float], bool]) -> View:
    """Corte o alzado (names = nombre y título) paralelo a X (cut = ("x", y)) o a Y (cut = ("y", x)), como los planos de
    despiece (D-158): el concreto, las barras paralelas al plano con las patas de su cartilla y sus cotas, las barras
    cortadas por zonas con el rótulo de cada zona arriba (las superiores) o abajo (las inferiores), las divisiones de las
    zonas, los estribos y los pasadores con su rótulo a la derecha. frame = (concreto, el primero la base; arranques de
    columna con su símbolo de corte; caras de las columnas para la cadena de arriba; si lleva título). Cotas: arriba, la
    cadena de los bordes y las caras de las columnas; abajo, la de las zonas y el largo total."""
    axis, at = cut
    concrete, stubs, faces, titled_view = frame
    view = View(*names, [*concrete, *stubs])
    x0, y0, x1, y1 = _box(concrete[0])
    middle = (y0 + y1) / 2
    height, gap = drawing.text_height(small=True), drawing.gap()
    anchors: list[tuple[Point, Marked]] = []
    drawn: set[Placement] = set()
    cut_zones: list[tuple[float, ...]] = []
    levels = {True: 0, False: 0}  # rótulos ya puestos arriba (True) y abajo: cada uno a su altura
    for item in marked:
        place = item.place
        if place.along == axis:
            _parallel_bar(drawing, view, item, (at, middle))
        elif place.along in ("x", "y"):
            spans = _cut_zones(drawing, view, item, (at, middle, (y0, y1), levels))
            if place.level < middle:
                cut_zones += spans
        else:
            entities, anchor = _stirrup(item, axis, drawn) if place.along == "estribo" else _dowels(item, axis, at)
            view.entities += entities
            if anchor is not None:
                anchors.append((anchor, item))
    _labels(drawing, view, anchors, marked, (x1, y1))
    ordered = sorted(cut_zones, key=lambda zone: zone[0])
    bounds = _zone_bounds(ordered, (x0, x1)) if ordered else [x0, x1]
    for bound in bounds[1:-1]:
        view.entities.append(Polyline(DISTRIBUTION, ((bound, y0), (bound, y1)), dashed=True, color=ZONE_COLOR))
    if len(bounds) > _PAIR:
        view.entities += _chain(bounds, ("x", y0), ((0.0, -1.0), 0.5 * gap), height)
    view.entities.append(_dim(((x0, y0), (x1, y0)), (0.0, -1.0), gap if len(bounds) > _PAIR else 0.5 * gap, height))
    if faces:
        view.entities += _chain([x0, *faces, x1], ("x", y1), ((0.0, 1.0), 0.4 * gap), height)
    if titled_view:
        _title(drawing, view)
    return view


def _parallel_bar(drawing: Drawing, view: View, item: Marked, cut: tuple[float, float]) -> None:
    """Una corrida paralela al plano, si hay una barra cerca de él: la barra con las patas de su cartilla (D-158), hacia
    adentro (arriba la inferior, abajo la superior), y la cota de cada pata afuera."""
    at, middle = cut
    run, place = item.run, item.place
    if min(abs(position - at) for position in place.positions) > max(_gap(place.positions), run.diameter):
        return
    up = 1.0 if place.level < middle else -1.0
    first, _, _ = piece_legs(item.pieces[0])
    _, _, last = piece_legs(item.pieces[-1])
    (start, end), z = place.span, place.level
    points: list[Point] = [(start, z), (end, z)]
    height, gap = drawing.text_height(small=True), drawing.gap()
    if first:
        points.insert(0, (start, z + up * first))
        view.entities.append(_dim(((start, z), (start, z + up * first)), (-1.0, 0.0), 0.4 * gap, height))
    if last:
        points.append((end, z + up * last))
        view.entities.append(_dim(((end, z), (end, z + up * last)), (1.0, 0.0), 0.4 * gap, height))
    view.entities.append(Polyline(item.layer, tuple(points)))


def _cut_zones(drawing: Drawing, view: View, item: Marked,
               cut: tuple[float, float, tuple[float, float], dict[bool, int]]) -> list[tuple[float, ...]]:
    """Una corrida perpendicular al plano: un punto de tamaño fijo por barra (D-150) y, por zona, su rótulo con una
    llamada a una barra de la zona, encima de la base si son barras superiores y debajo si son inferiores (D-158), cada
    uno a su altura (levels cuenta los rótulos ya puestos de cada lado); devuelve sus zonas (ninguna si el plano no la
    corta)."""
    at, middle, (bottom, top), levels = cut
    run, place = item.run, item.place
    if not place.span[0] <= at <= place.span[1]:
        return []
    radius = drawing.paper(_DOT)
    view.entities += [Circle(item.layer, (position, place.level), radius) for position in place.positions]
    height, gap = drawing.text_height(small=True), drawing.gap()
    spans = zones(place.positions)
    upper = place.level > middle
    for zone in spans:
        target = (zone[min(1, len(zone) - 1)], place.level)
        rise = 1.6 * height * levels[upper]  # cada rótulo a su altura, para que no se monten
        levels[upper] += 1
        landing = (zone[0], top + 1.2 * gap + rise) if upper else (zone[0], bottom - 1.8 * gap - rise)
        count = round(len(zone) * run.count / len(place.positions))
        view.entities.append(Leader(DIMENSIONS, landing, label_text([item], count, zone), height, (target,)))
    return spans


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
    """Los pasadores dibujados en el corte que pasa por su columna, con el gancho del pie hacia dentro de la columna."""
    place = item.place
    centre, offset = place.positions, place.cross
    along, across = (0, 1) if axis == "x" else (1, 0)
    if abs(centre[across] - at) > offset[across] + 1e-6:
        return [], None
    leg = piece_legs(item.pieces[0])[0] if item.pieces else 0.0  # la pata de la cartilla (D-158)
    entities: list[Entity] = []
    for side in (-1.0, 1.0):
        u = centre[along] + side * offset[along]
        entities.append(Polyline(item.layer, ((u - side * leg, place.span[0]), (u, place.span[0]), (u, place.span[1]))))
    return entities, (centre[along] + offset[along], (place.span[0] + place.span[1]) / 2)


def cartilla_view(drawing: Drawing, element: str, rows: list[ScheduleRow], units: int) -> View:
    """La cartilla como tabla, con el croquis de la forma de cada marca y sus dimensiones A, B y C y la longitud de corte
    en metros (D-150), las mismas de la cartilla de la memoria (en mm) y del .dli. Es la de una unidad del tipo; si se
    construye más de una vez (units, D-159), debajo va la de las N unidades, con la cantidad y el peso por N."""
    view = View("cartilla", f"Cartilla de despiece {element}" + (f" (1 unidad de {units})" if units > 1 else ""))
    bottom = _schedule_table(drawing, view, rows, 0.0)
    if units > 1:
        small = drawing.text_height(small=True)
        top = bottom - 4 * small
        view.entities.append(Text(TABLE, (0.0, top + small), f"Cartilla de despiece {element}: {units} unidades", small))
        _schedule_table(drawing, view, scaled(rows, units), top)
    _title(drawing, view)
    return view


def _schedule_table(drawing: Drawing, view: View, rows: list[ScheduleRow], top: float) -> float:
    """Dibuja una tabla de la cartilla con su borde superior en top y devuelve la cota de su borde inferior."""
    scale, small = drawing.scale, drawing.text_height(small=True)
    width = sum(size for _, size in _COLUMNS) * scale
    lefts = [sum(size for _, size in _COLUMNS[:index]) * scale for index in range(len(_COLUMNS))]
    header, row_height = _HEADER * scale, _ROW * scale
    bottom = top - header - row_height * (len(rows) + 1)
    view.entities.append(rectangle(TABLE, (0.0, top), (width, bottom)))
    for left in lefts[1:]:
        view.entities.append(Line(TABLE, (left, top), (left, bottom)))
    for (name, size), left in zip(_COLUMNS, lefts, strict=True):
        view.entities.append(Text(TABLE, (left + size * scale / 2, top - header * 0.65), name, small, align="center"))
    view.entities.append(Line(TABLE, (0.0, top - header), (width, top - header)))
    for index, row in enumerate(rows):
        upper = top - header - index * row_height
        view.entities.append(Line(TABLE, (0.0, upper - row_height), (width, upper - row_height)))
        piece, dimensions = row.piece, dict(row.piece.dimensions)
        cells = [row.mark, piece.designation, str(piece.count), piece.shape,
                 *(metres(dimensions[name]) if name in dimensions else "" for name in ("A", "B", "C")),
                 metres(piece.cut_length), f"{row.mass:.1f}"]
        for column, (text, (_, size), left) in enumerate(zip(cells, _COLUMNS, lefts, strict=True)):
            if text and column != _SHAPE_COLUMN:
                view.entities.append(Text(TABLE, (left + size * scale / 2, upper - row_height * 0.6), text, small, align="center"))
        view.entities.append(Text(TABLE, (lefts[_SHAPE_COLUMN] + 0.5 * small, upper - 0.5 * small - small * 0.8), piece.shape,
                                  small * 0.8))
        view.entities += _shape(row, (lefts[_SHAPE_COLUMN], upper), (_COLUMNS[_SHAPE_COLUMN][1] * scale, row_height), small)
    total = sum(row.mass for row in rows)
    last = bottom + row_height
    view.entities.append(Text(TABLE, (lefts[-1] - small, last - row_height * 0.6), "Total acero", small, align="right"))
    view.entities.append(Text(TABLE, (lefts[-1] + _COLUMNS[-1][1] * scale / 2, last - row_height * 0.6), f"{total:.1f}", small,
                              align="center"))
    return bottom


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
