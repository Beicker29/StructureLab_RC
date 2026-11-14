"""Modelo de dibujo neutro (v3 Fase 4B, D-126, D-132): vistas con entidades en mm reales (modelo 1:1), en capas fijas por
tipo de objeto y una capa por diámetro de barra (REFUERZO_<designación>, con un color fijo por diámetro). Los textos, las
cotas y los símbolos se dimensionan para la escala de impresión declarada (un texto de PAPER_TEXT mm en papel mide
PAPER_TEXT × escala en el modelo). Sin fórmulas normativas: solo geometría y rótulos.

Se guarda como JSON (`<nombre>_drawing.json`, que entra en la huella) y se escribe como SVG (drawing/svg.py) y DXF
(drawing/dxf.py, extra `cad`).
"""

from dataclasses import asdict, dataclass, field
from typing import Any

Point = tuple[float, float]

# Capa: (color RGB para SVG, color ACI para DXF, grosor de línea en mm de papel).
LAYERS: dict[str, tuple[str, int, float]] = {
    "CONCRETO": ("#1f3864", 5, 0.35),
    "COLUMNAS": ("#d4a017", 2, 0.35),
    "COTAS": ("#555555", 8, 0.18),
    "TEXTOS": ("#000000", 7, 0.18),
    "EJES": ("#7f8c8d", 9, 0.13),
    "CARTILLA": ("#000000", 7, 0.18),
}
BAR_PREFIX = "REFUERZO_"
# Colores de las capas de barras (D-132), por el número de la designación (#5 -> 5): (RGB, ACI), uno distinto por barra
# del catálogo y sin el amarillo de las columnas; una barra fuera de la tabla, gris.
_BAR_COLORS: dict[int, tuple[str, int]] = {
    3: ("#2471a3", 4), 4: ("#c0392b", 1), 5: ("#d35400", 30), 6: ("#1e8449", 94), 7: ("#b03a2e", 14), 8: ("#6c3483", 200),
    9: ("#117a65", 130), 10: ("#1a5276", 150), 11: ("#7d6608", 50), 14: ("#8e44ad", 6), 18: ("#16a085", 3),
}
_OTHER_BAR = ("#616a6b", 251)
_BAR_WEIGHT = 0.35


def bar_layer(designation: str) -> str:
    """La capa de las barras de una designación: REFUERZO_#5."""
    return f"{BAR_PREFIX}{designation}"


def layer_style(name: str) -> tuple[str, int, float]:
    """(color RGB, color ACI, grosor en mm de papel) de una capa fija o de barras."""
    if name in LAYERS:
        return LAYERS[name]
    digits = "".join(character for character in name.removeprefix(BAR_PREFIX) if character.isdigit())
    color, aci = _BAR_COLORS.get(int(digits or 0), _OTHER_BAR)
    return color, aci, _BAR_WEIGHT
PAPER_TEXT = 2.5  # mm de papel: altura de los textos
PAPER_SMALL = 2.0  # mm de papel: textos de cotas y tablas
PAPER_GAP = 8.0  # mm de papel: separación de cotas y llamadas


@dataclass(frozen=True)
class Line:
    layer: str
    start: Point
    end: Point


@dataclass(frozen=True)
class Polyline:
    layer: str
    points: tuple[Point, ...]
    closed: bool = False
    dashed: bool = False


@dataclass(frozen=True)
class Circle:
    layer: str
    center: Point
    radius: float
    filled: bool = True  # sin relleno: el círculo del número de un grupo de barras


@dataclass(frozen=True)
class Text:
    layer: str
    at: Point
    text: str
    height: float
    align: str = "left"  # left, center o right


@dataclass(frozen=True)
class Dimension:
    """Cota lineal entre dos puntos, con la línea de cota corrida offset en la normal (izquierda del sentido)."""

    layer: str
    start: Point
    end: Point
    offset: float
    text: str
    height: float


Entity = Line | Polyline | Circle | Text | Dimension


@dataclass
class View:
    """Una vista (planta, corte, alzado o cartilla) con su título."""

    name: str
    title: str
    entities: list[Entity] = field(default_factory=list)

    def bounds(self) -> tuple[float, float, float, float]:
        """(x mínimo, y mínimo, x máximo, y máximo) de las entidades."""
        xs: list[float] = []
        ys: list[float] = []
        for entity in self.entities:
            points: list[Point]
            if isinstance(entity, Line):
                points = [entity.start, entity.end]
            elif isinstance(entity, Polyline):
                points = list(entity.points)
            elif isinstance(entity, Circle):
                (x, y), r = entity.center, entity.radius
                points = [(x - r, y - r), (x + r, y + r)]
            elif isinstance(entity, Text):
                width = 0.6 * entity.height * len(entity.text)
                shift = {"left": 0.0, "center": width / 2, "right": width}[entity.align]
                points = [(entity.at[0] - shift, entity.at[1]), (entity.at[0] - shift + width, entity.at[1] + entity.height)]
            else:
                points = [entity.start, entity.end, *_dimension_points(entity)]
            xs += [p[0] for p in points]
            ys += [p[1] for p in points]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 1.0, 1.0)


def _dimension_points(dimension: Dimension) -> list[Point]:
    (x0, y0), (x1, y1) = dimension.start, dimension.end
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1.0
    nx, ny = -(y1 - y0) / length * dimension.offset, (x1 - x0) / length * dimension.offset
    return [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny)]


def dimension_line(dimension: Dimension) -> tuple[Point, Point]:
    """Los extremos de la línea de cota (corrida offset)."""
    first, second = _dimension_points(dimension)
    return first, second


@dataclass
class Drawing:
    """El dibujo de un proyecto: una lista de vistas por elemento, a la escala de impresión declarada."""

    name: str
    scale: float
    views: dict[str, list[View]] = field(default_factory=dict)

    def layers(self) -> list[str]:
        """Las capas fijas y las de barras que usa el dibujo, estas en orden de diámetro."""
        used = {entity.layer for views in self.views.values() for view in views for entity in view.entities}
        bars = sorted((name for name in used if name.startswith(BAR_PREFIX)),
                      key=lambda name: int("".join(c for c in name if c.isdigit()) or 0))
        return [*LAYERS, *bars]

    def text_height(self, small: bool = False) -> float:
        return (PAPER_SMALL if small else PAPER_TEXT) * self.scale

    def gap(self) -> float:
        return PAPER_GAP * self.scale

    def to_dict(self) -> dict[str, Any]:
        """El modelo en JSON: capas, escala y las entidades de cada vista con su tipo, en mm redondeados a 0.1."""
        def entity(item: Entity) -> dict[str, Any]:
            data = asdict(item)
            return {"type": type(item).__name__.lower(), **_rounded(data)}
        return {"name": self.name, "scale": self.scale, "units": "mm",
                "layers": {name: dict(zip(("color", "aci", "lineweight [mm]"), layer_style(name), strict=True)) for name in self.layers()},
                "elements": {element: [{"name": view.name, "title": view.title, "entities": [entity(item) for item in view.entities]}
                                       for view in views] for element, views in self.views.items()}}


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 1) + 0.0
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    return value
