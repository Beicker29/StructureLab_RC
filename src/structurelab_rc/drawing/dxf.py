"""Salida DXF del modelo de dibujo (D-126, D-150) con ezdxf (extra `cad`), sobre la plantilla de los planos de despiece
(data/plantilla.dxf): sus capas, tipos de línea, estilos de texto, de cota y de multileader y el bloque de la barra
cortada.

- Unidades: el modelo está en mm y el DXF en metros, como la plantilla; la conversión ocurre solo aquí.
- Cotas: entidades DIMENSION con el estilo de la escala (DIM-50 a 1:50; si la plantilla no lo trae, uno igual a DIM-50
  escalado), que miden en metros con dos decimales (tres si la medida no es múltiplo de 1 cm).
- Rótulos de los cortes: MULTILEADER con una línea a cada barra del grupo. Barras cortadas: el bloque BARRA escalado al
  radio del punto, en la capa de su diámetro. Columnas en planta: sombreado sólido en su capa y contorno en la del
  concreto.
- Composición, como los planos de despiece: por elemento, en una fila la planta de geometría y las plantas del refuerzo y
  en otra los cortes y la cartilla, con el título del elemento ("ZC_m h=0.80") y la escala debajo; los elementos lado a
  lado y un marco alrededor. Las vistas con dxf = False (los cortes transversales de la combinada) no entran.
"""

import io
import math
from pathlib import Path
from typing import Any

from structurelab_rc.drawing.model import (
    DIMENSIONS,
    OUTLINE,
    PAPER_TEXT,
    PAPER_TITLE,
    SUBTITLE,
    TITLE,
    Circle,
    Dimension,
    Drawing,
    Entity,
    Leader,
    Line,
    Polyline,
    Text,
    View,
    dimension_line,
)

_M_PER_MM = 0.001
_PAPER_GAP = 20.0  # mm de papel: separación entre vistas, filas y elementos
_FRAME = 10.0  # mm de papel: margen del marco
_BASE_STYLE = "DIM-50"  # estilo de cota de la plantilla del que se escala el de otra escala
_BASE_SCALE = 50.0
_SCALED_DIMVARS = ("dimtxt", "dimasz", "dimexe", "dimexo", "dimgap", "dimdli", "dimfxl", "dimdle", "dimcen")
_BAR_BLOCK = "BARRA"  # punto relleno de radio 1 en la plantilla
_DASHED = "HIDDEN2"
_TEXT_STYLE = "Standard"  # Arial en la plantilla
_MLEADER_STYLE = "LEADER"  # la clave del estilo de multileader que usa la plantilla (su nombre interno es Standard)
_CM = 10.0  # mm
_ROUND_OFF = 0.05  # mm
_FIRST_ROW = ("geometria", "planta_")  # vistas de la primera fila de cada elemento


def available() -> bool:
    try:
        import ezdxf  # noqa: F401, PLC0415 - dependencia opcional
    except ImportError:
        return False
    return True


def write_dxf(drawing: Drawing, path: Path, template: str) -> bool:
    """Escribe el DXF sobre la plantilla (su texto); False si ezdxf no está instalado."""
    if not available():
        return False
    import ezdxf  # noqa: PLC0415 - dependencia opcional

    document = ezdxf.read(io.StringIO(template))
    writer = _Writer(document, drawing, _dimension_style(document, drawing.scale))
    left, frame = 0.0, [math.inf, math.inf, -math.inf, -math.inf]
    for element, views in drawing.views.items():
        shown = [view for view in views if view.dxf]
        if shown:
            box = writer.element(element, shown, left)
            frame = [min(frame[0], box[0]), min(frame[1], box[1]), max(frame[2], box[2]), max(frame[3], box[3])]
            left = box[2] + _PAPER_GAP * drawing.scale
    if math.isfinite(frame[0]):
        margin = _FRAME * drawing.scale
        x0, y0, x1, y1 = frame[0] - margin, frame[1] - margin, frame[2] + margin, frame[3] + margin
        writer.polyline(DIMENSIONS, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)
        document.set_modelspace_vport(height=(y1 - y0) * _M_PER_MM * 1.05, center=((x0 + x1) / 2 * _M_PER_MM, (y0 + y1) / 2 * _M_PER_MM))
    path.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(path, encoding="utf-8")
    return True


def _dimension_style(document: Any, scale: float) -> str:
    """El estilo de cota de la escala: el de la plantilla (DIM-50) o uno igual a DIM-50 escalado."""
    name = f"DIM-{scale:g}"
    if name not in document.dimstyles:
        base = document.dimstyles.get(_BASE_STYLE)
        style = document.dimstyles.duplicate_entry(_BASE_STYLE, name)
        for key in _SCALED_DIMVARS:
            if base.dxf.hasattr(key):
                style.dxf.set(key, base.dxf.get(key) * scale / _BASE_SCALE)
    return name


class _Writer:
    """Escribe las entidades del modelo (mm, en las coordenadas de su vista) en el espacio modelo (m), desplazadas."""

    def __init__(self, document: Any, drawing: Drawing, dimstyle: str) -> None:
        self.space = document.modelspace()
        self.drawing = drawing
        self.dimstyle = dimstyle
        self.dx, self.dy = 0.0, 0.0

    def element(self, element: str, views: list[View], left: float) -> tuple[float, float, float, float]:
        """Las vistas de un elemento desde la abscisa left (mm): la primera fila arriba, la segunda debajo, y el título;
        devuelve lo que ocupa (x0, y0, x1, y1) en mm."""
        gap = _PAPER_GAP * self.drawing.scale
        rows = [[view for view in views if view.name.startswith(_FIRST_ROW)],
                [view for view in views if not view.name.startswith(_FIRST_ROW)]]
        top, right = 0.0, left
        for row in (row for row in rows if row):
            column, tallest = left, 0.0
            for view in row:
                x0, y0, x1, y1 = view.bounds()
                self.dx, self.dy = column - x0, top - y1
                for entity in view.entities:
                    self.entity(entity)
                column += (x1 - x0) + gap
                tallest = max(tallest, y1 - y0)
            right = max(right, column - gap)
            top -= tallest + gap
        self.dx, self.dy = 0.0, 0.0
        bottom = top
        title = self.drawing.titles.get(element)
        if title is not None:
            middle = (left + right) / 2
            title_height, scale_height = self.drawing.paper(PAPER_TITLE), self.drawing.paper(PAPER_TEXT)
            self.text(Text(TITLE, (middle, top), title, title_height, align="center"))
            bottom = top - 1.6 * scale_height
            self.text(Text(SUBTITLE, (middle, bottom), f"ESC 1:{self.drawing.scale:g}", scale_height, align="center"))
        return left, bottom, right, 0.0

    def point(self, point: tuple[float, float]) -> tuple[float, float]:
        return (point[0] + self.dx) * _M_PER_MM, (point[1] + self.dy) * _M_PER_MM

    def polyline(self, layer: str, points: list[tuple[float, float]], closed: bool = False, dashed: bool = False) -> None:
        attributes = {"layer": layer, **({"linetype": _DASHED} if dashed else {})}
        self.space.add_lwpolyline([self.point(p) for p in points], close=closed, dxfattribs=attributes)

    def text(self, text: Text) -> None:
        from ezdxf.enums import TextEntityAlignment  # noqa: PLC0415 - dependencia opcional

        aligns = {"left": TextEntityAlignment.LEFT, "center": TextEntityAlignment.CENTER, "right": TextEntityAlignment.RIGHT}
        entity = self.space.add_text(text.text, height=text.height * _M_PER_MM, rotation=text.rotation,
                                     dxfattribs={"layer": text.layer, "style": _TEXT_STYLE})
        entity.set_placement(self.point(text.at), align=aligns[text.align])

    def entity(self, entity: Entity) -> None:
        layer = {"layer": entity.layer}
        if isinstance(entity, Line):
            self.space.add_line(self.point(entity.start), self.point(entity.end), dxfattribs=layer)
        elif isinstance(entity, Polyline):
            if entity.filled:  # columna: sombreado en su capa y contorno en la del concreto
                hatch = self.space.add_hatch(color=256, dxfattribs=layer)  # 256: color de la capa
                hatch.paths.add_polyline_path([self.point(p) for p in entity.points], is_closed=True)
                self.polyline(OUTLINE, list(entity.points), closed=True)
            else:
                self.polyline(entity.layer, list(entity.points), closed=entity.closed, dashed=entity.dashed)
        elif isinstance(entity, Circle):
            radius = entity.radius * _M_PER_MM
            if entity.filled:  # barra cortada: el bloque de la plantilla
                self.space.add_blockref(_BAR_BLOCK, self.point(entity.center), dxfattribs={**layer, "xscale": radius, "yscale": radius})
            else:
                self.space.add_circle(self.point(entity.center), radius, dxfattribs=layer)
        elif isinstance(entity, Text):
            self.text(entity)
        elif isinstance(entity, Leader):
            self.leader(entity)
        else:
            self.dimension(entity)

    def dimension(self, dimension: Dimension) -> None:
        start, end = dimension.start, dimension.end
        base, _ = dimension_line(dimension)
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        override = {} if abs(length - round(length / _CM) * _CM) < _ROUND_OFF else {"dimdec": 3}
        built = self.space.add_linear_dim(base=self.point(base), p1=self.point(start), p2=self.point(end), angle=angle,
                                          dimstyle=self.dimstyle, override=override, dxfattribs={"layer": dimension.layer})
        built.render()

    def leader(self, leader: Leader) -> None:
        """MULTILEADER con el estilo de la plantilla: el texto a la derecha de at y una línea a cada barra."""
        from ezdxf.math import Vec2  # noqa: PLC0415 - dependencia opcional
        from ezdxf.render import mleader  # noqa: PLC0415 - dependencia opcional

        builder = self.space.add_multileader_mtext(_MLEADER_STYLE, dxfattribs={"layer": leader.layer})
        builder.set_content(leader.text, char_height=leader.height * _M_PER_MM, alignment=mleader.TextAlignment.left)
        for target in leader.targets:
            builder.add_leader_line(mleader.ConnectionSide.left, [Vec2(self.point(target))])
        builder.build(insert=Vec2(self.point(leader.at)))
