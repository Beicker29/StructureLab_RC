"""Vista previa en SVG de una vista del modelo de dibujo (D-126), sin dependencias: el eje y del modelo hacia arriba se
invierte para el SVG y el grosor de línea es el de la capa en papel, por la escala."""

from html import escape

from structurelab_rc.drawing.model import LAYERS, Circle, Dimension, Line, Polyline, Text, View, dimension_line

_WIDTH = 800.0  # px de ancho del SVG
_MARGIN = 0.04  # fracción del tamaño de la vista


def view_svg(view: View, scale: float) -> tuple[str, float]:
    """(SVG, alto/ancho) de una vista."""
    x0, y0, x1, y1 = view.bounds()
    pad = _MARGIN * max(x1 - x0, y1 - y0)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    width, height = x1 - x0, y1 - y0
    aspect = height / width
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH:.0f}" height="{_WIDTH * aspect:.0f}" '
             f'viewBox="{x0:.1f} {-y1:.1f} {width:.1f} {height:.1f}" font-family="Helvetica, Arial, sans-serif">',
             f'<rect x="{x0:.1f}" y="{-y1:.1f}" width="{width:.1f}" height="{height:.1f}" fill="white"/>']
    for entity in view.entities:
        color, _, weight = LAYERS[entity.layer]
        stroke = f'stroke="{color}" stroke-width="{weight * scale:.1f}" fill="none"'
        if isinstance(entity, Line):
            parts.append(f'<line x1="{entity.start[0]:.1f}" y1="{-entity.start[1]:.1f}" x2="{entity.end[0]:.1f}" '
                         f'y2="{-entity.end[1]:.1f}" {stroke}/>')
        elif isinstance(entity, Polyline):
            points = " ".join(f"{x:.1f},{-y:.1f}" for x, y in entity.points)
            tag = "polygon" if entity.closed else "polyline"
            dash = f' stroke-dasharray="{6 * scale:.0f} {3 * scale:.0f}"' if entity.dashed else ""
            parts.append(f'<{tag} points="{points}" {stroke}{dash}/>')
        elif isinstance(entity, Circle):
            parts.append(f'<circle cx="{entity.center[0]:.1f}" cy="{-entity.center[1]:.1f}" r="{entity.radius:.1f}" fill="{color}"/>')
        elif isinstance(entity, Text):
            anchor = {"left": "start", "center": "middle", "right": "end"}[entity.align]
            parts.append(f'<text x="{entity.at[0]:.1f}" y="{-entity.at[1]:.1f}" font-size="{entity.height:.1f}" fill="{color}" '
                         f'text-anchor="{anchor}">{escape(entity.text)}</text>')
        elif isinstance(entity, Dimension):
            parts += _dimension_svg(entity, stroke, color)
    parts.append("</svg>")
    return "\n".join(parts) + "\n", aspect


def _dimension_svg(dimension: Dimension, stroke: str, color: str) -> list[str]:
    (a, b) = dimension_line(dimension)
    (sx, sy), (ex, ey) = dimension.start, dimension.end
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
    rotate = f' transform="rotate(-90 {mid[0]:.1f} {-mid[1]:.1f})"' if vertical else ""
    return [f'<line x1="{sx:.1f}" y1="{-sy:.1f}" x2="{a[0]:.1f}" y2="{-a[1]:.1f}" {stroke}/>',
            f'<line x1="{ex:.1f}" y1="{-ey:.1f}" x2="{b[0]:.1f}" y2="{-b[1]:.1f}" {stroke}/>',
            f'<line x1="{a[0]:.1f}" y1="{-a[1]:.1f}" x2="{b[0]:.1f}" y2="{-b[1]:.1f}" {stroke}/>',
            f'<text x="{mid[0]:.1f}" y="{-mid[1] - dimension.height * 0.3:.1f}" font-size="{dimension.height:.1f}" fill="{color}" '
            f'text-anchor="middle"{rotate}>{escape(dimension.text)}</text>']
