"""Modelo de dibujo neutro (v3 Fase 4B, D-126, D-132, D-150): vistas con entidades en mm reales (modelo 1:1), en las capas
de la plantilla DXF (data/dxf/plantilla.dxf): la capa dice el papel de cada entidad (contorno, relleno de columnas, cotas,
textos, títulos, líneas de distribución) y hay una por diámetro de barra (Borde_<designación>). Los textos, las cotas y
los símbolos se dimensionan para la escala de impresión declarada (un texto de PAPER_TEXT mm en papel mide PAPER_TEXT ×
escala en el modelo). Los rótulos y las cotas van en metros (metres, D-150). Sin fórmulas normativas: solo geometría y
rótulos.

Se guarda como JSON (`<nombre>_drawing.json`, que entra en la huella) y se escribe como SVG (drawing/svg.py) y DXF
(drawing/dxf.py, extra `cad`).
"""

from dataclasses import asdict, dataclass, field
from typing import Any

Point = tuple[float, float]

# Capas de la plantilla (D-150): (color RGB para SVG, color ACI para DXF, grosor de línea en mm de papel). El ACI es el de
# la plantilla (una prueba lo compara); el RGB es el del SVG, legible sobre fondo blanco.
OUTLINE = "0"  # contornos de las columnas y de sus arranques
FOOTING = "ZAPATA"  # contorno del concreto de las zapatas aisladas, combinadas y T invertidas (D-166)
PILE_CAP = "CABEZAL"  # contorno del concreto de los cabezales (D-166)
COLUMN_FILL = "ACH ESTRUCTURA"  # relleno sólido de las columnas en planta
DIMENSIONS = "DIM"  # cotas y llamadas de los cortes
LABELS = "TEXTO"  # rótulos de las barras, nombres de las columnas y notas
TITLE = "TXT TITULO"  # título de cada elemento
SUBTITLE = "TXT ESCALA"  # título de cada vista y escala del elemento
DISTRIBUTION = "PROYECCIONES"  # líneas de distribución de las barras y arranques de columna
AXES = "EJES"
TABLE = "CARTILLA"
LAYERS: dict[str, tuple[str, int, float]] = {
    OUTLINE: ("#000000", 7, 0.35),
    FOOTING: ("#000000", 7, 0.35),
    PILE_CAP: ("#000000", 7, 0.35),
    COLUMN_FILL: ("#666666", 252, 0.18),
    DIMENSIONS: ("#cc0000", 1, 0.18),
    LABELS: ("#7d6608", 2, 0.18),
    TITLE: ("#1f4e9c", 161, 0.35),
    SUBTITLE: ("#cc0000", 1, 0.25),
    DISTRIBUTION: ("#cc0000", 1, 0.18),
    AXES: ("#7f8c8d", 9, 0.13),
    TABLE: ("#000000", 7, 0.18),
}
# Capas que solo aparecen si el dibujo las usa: los pilotes de los cabezales (D-138); el concreto del muro de contención y
# el relleno detrás de él (D-175).
PILES = "PILOTES"
WALL = "MURO"
BACKFILL = "RELLENO"
OPTIONAL_LAYERS: dict[str, tuple[str, int, float]] = {PILES: ("#5d4037", 34, 0.25), WALL: ("#000000", 7, 0.35),
                                                      BACKFILL: ("#8d6e63", 34, 0.13)}
EARTH = "EARTH"  # patrón de sombreado del relleno (el de AutoCAD), como el plano de muros de referencia (D-175)
BAR_PREFIX = "Borde_"
# Colores de las capas de barras, por el número de la designación (#5 -> 5): (RGB, ACI), uno distinto por barra. De #4 a #8,
# los de la plantilla (D-150); las demás conservan los de D-132. Una barra fuera de la tabla, gris.
_BAR_COLORS: dict[int, tuple[str, int]] = {
    3: ("#2471a3", 4), 4: ("#a55200", 32), 5: ("#0000ff", 170), 6: ("#7f0000", 14), 7: ("#7f00ff", 190), 8: ("#ff00bf", 220),
    9: ("#117a65", 130), 10: ("#1a5276", 150), 11: ("#7d6608", 50), 14: ("#8e44ad", 6), 18: ("#16a085", 3),
}
BAR_DESIGNATIONS = tuple(f"#{number}" for number in _BAR_COLORS)
_OTHER_BAR = ("#616a6b", 251)
_BAR_WEIGHT = 0.35


def bar_layer(designation: str) -> str:
    """La capa de las barras de una designación: Borde_#5."""
    return f"{BAR_PREFIX}{designation}"


def layer_style(name: str) -> tuple[str, int, float]:
    """(color RGB, color ACI, grosor en mm de papel) de una capa fija o de barras."""
    if name in LAYERS:
        return LAYERS[name]
    if name in OPTIONAL_LAYERS:
        return OPTIONAL_LAYERS[name]
    digits = "".join(character for character in name.removeprefix(BAR_PREFIX) if character.isdigit())
    color, aci = _BAR_COLORS.get(int(digits or 0), _OTHER_BAR)
    return color, aci, _BAR_WEIGHT
PAPER_TEXT = 2.5  # mm de papel: altura de los textos (la escala del elemento)
PAPER_SMALL = 2.0  # mm de papel: textos de cotas, rótulos y tablas
PAPER_SUBTITLE = 3.0  # mm de papel: título de cada vista
PAPER_TITLE = 6.0  # mm de papel: título de cada elemento
PAPER_GAP = 8.0  # mm de papel: separación de cotas y llamadas
PAPER_MARK = 1.25  # mm de papel: radio de la marca de una barra sobre su línea de distribución (D-158)
PAPER_STUB = 18.0  # mm de papel: alto del arranque de columna en un alzado (D-158)
PAPER_ARROW = 2.5  # mm de papel: flecha de los rótulos con llamada, como el MULTILEADER de la referencia (D-158)
DIAMETER = "Ø"  # prefijo del texto de una cota de diámetro (D-166); Latin-1, para las fuentes base de la memoria PDF
BASE_SCALE = 50.0  # la escala de la plantilla DXF: sus estilos y tipos de línea se multiplican por escala/BASE_SCALE
ZONE_COLOR = 252  # ACI de las divisiones de zona (D-158)
_CM = 10.0  # mm: una longitud múltiplo de 1 cm se escribe con dos decimales; si no, con tres
_ROUND_OFF = 0.05  # mm: diferencia con el múltiplo de 1 cm que se toma como redondeo


def metres(length: float) -> str:
    """Una longitud en mm como texto en metros, como los planos de despiece (D-150): dos decimales (tres si no es múltiplo
    de 1 cm) y sin el cero inicial: 3400 -> "3.40", 150 -> ".15", 75 -> ".075"."""
    value = length / 1000.0
    text = f"{value:.2f}" if abs(length - round(length / _CM) * _CM) < _ROUND_OFF else f"{value:.3f}"
    return text[1:] if text.startswith("0.") else text.replace("-0.", "-.")


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
    filled: bool = False  # cerrada y rellena (las columnas en planta): el DXF la sombrea y dibuja el contorno en OUTLINE
    color: int | None = None  # color ACI propio (el gris 252 de las divisiones de zona, D-158); None: el de la capa
    # Una barra dibujada que mide la longitud de corte de su marca de la cartilla (D-158, D-166): la marca; si no, "".
    mark: str = ""
    pattern: str = ""  # cerrada y sombreada con ese patrón (el relleno del muro, EARTH, D-175): el DXF agrega el sombreado


@dataclass(frozen=True)
class Circle:
    layer: str
    center: Point
    radius: float
    filled: bool = True  # sin relleno: el círculo del número de un grupo de barras
    dashed: bool = False  # a trazos: los pilotes bajo el cabezal en planta (D-166)


@dataclass(frozen=True)
class Text:
    layer: str
    at: Point
    text: str
    height: float
    align: str = "left"  # left, center o right
    rotation: float = 0.0  # grados, antihorario: 90 en los rótulos de las barras a lo largo de y
    # Rótulo de una barra (D-158, D-166): la marca de cada L del texto ("L=3.95" o "L=6.00+3.25"); el DXF escribe cada L
    # como un campo de AutoCAD ligado a la longitud de la polilínea de esa marca (Polyline.mark) en el mismo elemento.
    marks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Leader:
    """Rótulo con líneas de llamada a varios puntos (las barras de un grupo en un corte): el texto empieza en at y cada
    línea va del comienzo del texto a un punto de targets. marks, como en Text: cada L ligada a la polilínea de su marca."""

    layer: str
    at: Point
    text: str
    height: float
    targets: tuple[Point, ...]
    marks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dimension:
    """Cota lineal entre dos puntos, con la línea de cota corrida offset en la normal (izquierda del sentido); o, con
    kind "diameter", la cota del diámetro de un círculo entre dos puntos opuestos de él (el pilote, D-166)."""

    layer: str
    start: Point
    end: Point
    offset: float
    text: str
    height: float
    kind: str = "linear"  # linear o diameter


Entity = Line | Polyline | Circle | Text | Leader | Dimension


@dataclass
class View:
    """Una vista (planta, corte, alzado o cartilla) con su título."""

    name: str
    title: str
    entities: list[Entity] = field(default_factory=list)
    dxf: bool = True  # False: solo en el SVG y la memoria (los cortes transversales de la combinada, D-150)

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
                points = _text_box(entity)
            elif isinstance(entity, Leader):
                width = 0.6 * entity.height * len(entity.text)
                points = [*entity.targets, entity.at, (entity.at[0] + width, entity.at[1] + entity.height)]
            else:
                points = [entity.start, entity.end, *_dimension_points(entity)]
            xs += [p[0] for p in points]
            ys += [p[1] for p in points]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 1.0, 1.0)


def _text_box(text: Text) -> list[Point]:
    """Las esquinas aproximadas de un texto (ancho 0.6 de la altura por carácter), girado si lo está."""
    width = 0.6 * text.height * len(text.text)
    shift = {"left": 0.0, "center": width / 2, "right": width}[text.align]
    corners = [(-shift, 0.0), (width - shift, text.height)]
    if text.rotation % 180:  # vertical: 90 o 270
        corners = [(-y, x) for x, y in corners]
    return [(text.at[0] + x, text.at[1] + y) for x, y in corners]


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
    titles: dict[str, str] = field(default_factory=dict)  # título de cada elemento en el DXF ("ZC_m h=0.80", D-150)

    def layers(self) -> list[str]:
        """Las capas fijas y las de barras que usa el dibujo, estas en orden de diámetro."""
        used = {entity.layer for views in self.views.values() for view in views for entity in view.entities}
        bars = sorted((name for name in used if name.startswith(BAR_PREFIX)),
                      key=lambda name: int("".join(c for c in name if c.isdigit()) or 0))
        return [*LAYERS, *(name for name in OPTIONAL_LAYERS if name in used), *bars]

    def text_height(self, small: bool = False) -> float:
        return (PAPER_SMALL if small else PAPER_TEXT) * self.scale

    def paper(self, size: float) -> float:
        """Una medida en mm de papel, en mm del modelo."""
        return size * self.scale

    def gap(self) -> float:
        return PAPER_GAP * self.scale

    def to_dict(self) -> dict[str, Any]:
        """El modelo en JSON: capas, escala y las entidades de cada vista con su tipo, en mm redondeados a 0.1."""
        def entity(item: Entity) -> dict[str, Any]:
            data = asdict(item)
            if isinstance(item, Polyline) and not item.pattern:  # solo el relleno del muro lo lleva (D-175)
                del data["pattern"]
            return {"type": type(item).__name__.lower(), **_rounded(data)}
        return {"name": self.name, "scale": self.scale, "units": "mm",
                "layers": {name: dict(zip(("color", "aci", "lineweight [mm]"), layer_style(name), strict=True)) for name in self.layers()},
                "titles": self.titles,
                "elements": {element: [{"name": view.name, "title": view.title, "dxf": view.dxf,
                                        "entities": [entity(item) for item in view.entities]}
                                       for view in views] for element, views in self.views.items()}}


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 1) + 0.0
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    return value
