"""Salida DXF del modelo de dibujo (D-126) con ezdxf (extra `cad`): las capas con su color y grosor, y las vistas de cada
elemento en fila, separadas, en el espacio modelo a escala 1:1 en mm."""

from pathlib import Path

from structurelab_rc.drawing.model import LAYERS, Circle, Dimension, Drawing, Line, Polyline, Text, dimension_line

_GAP_FACTOR = 0.15  # separación entre vistas, fracción del ancho de la vista


def available() -> bool:
    try:
        import ezdxf  # noqa: F401, PLC0415 - dependencia opcional
    except ImportError:
        return False
    return True


def write_dxf(drawing: Drawing, path: Path) -> bool:
    """Escribe el DXF; False si ezdxf no está instalado."""
    if not available():
        return False
    import ezdxf  # noqa: PLC0415 - dependencia opcional
    from ezdxf.enums import TextEntityAlignment  # noqa: PLC0415 - dependencia opcional

    aligns = {"left": TextEntityAlignment.LEFT, "center": TextEntityAlignment.CENTER, "right": TextEntityAlignment.RIGHT}
    document = ezdxf.new("R2010", setup=True)
    document.units = ezdxf.units.MM
    for name, (_, aci, weight) in LAYERS.items():
        document.layers.add(name, color=aci, lineweight=int(round(weight * 100)))
    space = document.modelspace()
    row = 0.0
    for views in drawing.views.values():
        column, tallest = 0.0, 0.0
        for view in views:
            x0, y0, x1, y1 = view.bounds()
            dx, dy = column - x0, row - y1
            for entity in view.entities:
                attributes = {"layer": entity.layer}
                if isinstance(entity, Line):
                    space.add_line(_shift(entity.start, dx, dy), _shift(entity.end, dx, dy), dxfattribs=attributes)
                elif isinstance(entity, Polyline):
                    space.add_lwpolyline([_shift(p, dx, dy) for p in entity.points], close=entity.closed,
                                         dxfattribs={**attributes, **({"linetype": "DASHED"} if entity.dashed else {})})
                elif isinstance(entity, Circle):
                    space.add_circle(_shift(entity.center, dx, dy), entity.radius, dxfattribs=attributes)
                elif isinstance(entity, Text):
                    text = space.add_text(entity.text, height=entity.height, dxfattribs=attributes)
                    text.set_placement(_shift(entity.at, dx, dy), align=aligns[entity.align])
                elif isinstance(entity, Dimension):
                    a, b = dimension_line(entity)
                    for start, end in ((entity.start, a), (entity.end, b), (a, b)):
                        space.add_line(_shift(start, dx, dy), _shift(end, dx, dy), dxfattribs=attributes)
                    vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
                    mid = ((a[0] + b[0]) / 2 - entity.height * 0.3 * vertical, (a[1] + b[1]) / 2 + entity.height * 0.3 * (not vertical))
                    label = space.add_text(entity.text, height=entity.height, rotation=90.0 * vertical, dxfattribs=attributes)
                    label.set_placement(_shift(mid, dx, dy), align=aligns["center"])
            column += (x1 - x0) * (1 + _GAP_FACTOR)
            tallest = max(tallest, y1 - y0)
        row -= tallest * (1 + _GAP_FACTOR)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(path)
    return True


def _shift(point: tuple[float, float], dx: float, dy: float) -> tuple[float, float]:
    return point[0] + dx, point[1] + dy
