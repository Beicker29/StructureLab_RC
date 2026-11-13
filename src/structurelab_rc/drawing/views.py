"""Vistas neutras del refuerzo (D-126): planta, corte y cartilla con el croquis de cada forma, a partir de las corridas
del despiece (con su ubicación, Placement) y sus marcas. Sin fórmulas normativas: los ganchos llegan ya dimensionados.

Convenciones: en planta, x hacia la derecha e y hacia arriba; las barras inferiores con línea continua y las superiores
(sobre la mitad del espesor) a trazos. En un corte paralelo a X (cut "x", a la ordenada y = at) la abscisa es x y en
uno paralelo a Y (cut "y", en x = at) es y; la vertical es z desde la base. En un corte, las barras paralelas al plano se
dibujan como líneas (con sus ganchos) si hay una a menos de una separación del plano, y las perpendiculares como puntos.
"""

from dataclasses import dataclass

from structurelab_rc.detailing.schedule import BarRun, Placement, ScheduleRow, hook_leg
from structurelab_rc.drawing.model import Circle, Dimension, Drawing, Entity, Line, Point, Polyline, Text, View

_LABEL_STEP = 1.8  # separación de los rótulos apilados, en alturas de texto
_PAIR = 2  # con dos barras o menos (piel, caras opuestas) el rótulo no da separación
_DOT = 0.4  # mm de papel: radio mínimo del punto de una barra cortada
_ROW = 12.0  # mm de papel: alto de una fila de la cartilla
_HEADER = 8.0  # mm de papel: alto del encabezado de la cartilla
_COLUMNS = (("Marca", 18.0), ("Barra", 12.0), ("Cant.", 10.0), ("Forma", 46.0), ("A", 14.0), ("B", 14.0), ("C", 14.0),
            ("L corte", 18.0), ("Peso kg", 16.0))


@dataclass(frozen=True)
class Marked:
    """Una corrida del despiece con sus marcas de la cartilla."""

    run: BarRun
    marks: tuple[str, ...]

    @property
    def place(self) -> Placement:
        assert self.run.placement is not None
        return self.run.placement

    def label(self) -> str:
        run, marks = self.run, ", ".join(self.marks)
        if self.place.along == "estribo":
            return f"{marks} E{run.designation} {run.note}"
        if self.place.along == "z":
            return f"{marks} {run.count} {run.designation} pasadores"
        gap = _gap(self.place.positions) if len(self.place.positions) > _PAIR else 0.0  # dos barras: sin separación
        return f"{marks} {run.count} {run.designation}" + (f" c/{gap:.0f}" if gap else "")


def _gap(positions: tuple[float, ...]) -> float:
    gaps = [b - a for a, b in zip(positions, positions[1:], strict=False)]
    return min(gaps) if gaps else 0.0


def rectangle(layer: str, corner: Point, opposite: Point, dashed: bool = False) -> Polyline:
    (x0, y0), (x1, y1) = corner, opposite
    return Polyline(layer, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), closed=True, dashed=dashed)


def _labels(drawing: Drawing, view: View, anchors: list[tuple[Point, str]], right: float, top: float) -> None:
    """Rótulos apilados a la derecha de la vista, de arriba abajo en el orden de sus barras; un rótulo repetido se escribe
    una vez, con una línea a cada barra."""
    height = drawing.text_height(small=True)
    x = right + drawing.gap()
    grouped: dict[str, list[Point]] = {}
    for anchor, text in anchors:
        grouped.setdefault(text, []).append(anchor)
    ordered = sorted(grouped.items(), key=lambda item: -max(point[1] for point in item[1]))
    for index, (text, points) in enumerate(ordered):
        y = top - index * _LABEL_STEP * height
        view.entities += [Line("TEXTOS", anchor, (x - height * 0.3, y + height * 0.3)) for anchor in points]
        view.entities.append(Text("TEXTOS", (x, y), text, height))


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


def plan_view(drawing: Drawing, names: tuple[str, str], outline: tuple[list[Polyline], list[tuple[str, Polyline]]],
              marked: list[Marked], layer: tuple[float, bool]) -> View:
    """Planta (names = nombre y título) del refuerzo inferior o superior: el concreto y las columnas de outline y las
    barras horizontales con z ≤ split (layer = (split, False)) o z > split (layer = (split, True))."""
    concrete, columns = outline
    split, upper = layer
    view = View(*names, [*concrete, *(column for _, column in columns)])
    _, _, x1, y1 = view.bounds()
    for column_id, column in columns:
        xs, ys = [p[0] for p in column.points], [p[1] for p in column.points]
        view.entities.append(Text("TEXTOS", ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), column_id,
                                  drawing.text_height(small=True), align="center"))
    anchors: list[tuple[Point, str]] = []
    for item in marked:
        place = item.place
        if place.along not in ("x", "y") or (place.level > split) != upper:
            continue
        for position in place.positions:
            start, end = ((place.span[0], position), (place.span[1], position)) if place.along == "x" else \
                ((position, place.span[0]), (position, place.span[1]))
            view.entities.append(Line("REFUERZO", start, end))
        middle = place.positions[len(place.positions) // 2]
        anchors.append(((place.span[1] * 0.8, middle) if place.along == "x" else (middle, place.span[1] * 0.8), item.label()))
    _labels(drawing, view, anchors, x1, y1)
    _dimensions(drawing, view, concrete[0])
    _title(drawing, view)
    return view


def section_view(drawing: Drawing, names: tuple[str, str], cut: tuple[str, float], concrete: list[Polyline],
                 marked: list[Marked]) -> View:
    """Corte (names = nombre y título) paralelo a X (cut = ("x", y)) o a Y (cut = ("y", x)): el concreto cortado, las
    barras y los estribos."""
    axis, at = cut
    view = View(*names, list(concrete))
    _, _, x1, y1 = view.bounds()
    zs = [p[1] for p in concrete[0].points]
    middle = (min(zs) + max(zs)) / 2
    anchors: list[tuple[Point, str]] = []
    drawn: set[Placement] = set()
    for item in marked:
        entities, anchor = _cut_bars(drawing, item, (axis, at, middle), drawn)
        view.entities += entities
        if anchor is not None:
            anchors.append((anchor, item.label()))
    _labels(drawing, view, anchors, x1, y1)
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
        return [Polyline("REFUERZO", tuple(points))], (start + 0.75 * (end - start), z)
    if place.along in ("x", "y"):  # perpendiculares: un punto por barra
        if not place.span[0] <= at <= place.span[1]:
            return [], None
        radius = max(db / 2, _DOT * drawing.scale)
        dots: list[Entity] = [Circle("REFUERZO_CORTE", (position, place.level), radius) for position in place.positions]
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
        lines: list[Entity] = [Line("REFUERZO", (x, place.level), (x, place.level + height)) for x in place.positions]
        return lines, (place.positions[len(place.positions) // 2], place.level + height / 2)
    left, bottom = place.cross[1] - width / 2, place.level
    hook = min(width, height) * 0.15
    entities: list[Entity] = [rectangle("REFUERZO", (left, bottom), (left + width, bottom + height)),
                              Line("REFUERZO", (left, bottom + height), (left + hook, bottom + height - hook)),
                              Line("REFUERZO", (left, bottom + height), (left + hook * 0.4, bottom + height - hook * 1.2))]
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
        entities.append(Polyline("REFUERZO", ((u + side * leg, place.span[0]), (u, place.span[0]), (u, place.span[1]))))
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
