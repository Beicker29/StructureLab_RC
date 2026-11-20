"""Vista previa en SVG de una vista del modelo de dibujo (D-126), sin dependencias: el eje y del modelo hacia arriba se
invierte para el SVG y el grosor de línea es el de la capa en papel, por la escala."""

import math
from html import escape

from structurelab_rc.drawing.model import (
    DISTRIBUTION,
    PAPER_ARROW,
    ZONE_COLOR,
    Circle,
    Dimension,
    Leader,
    Line,
    Polyline,
    Text,
    View,
    dimension_line,
    layer_style,
)

_WIDTH = 800.0  # px de ancho del SVG
_MARGIN = 0.04  # fracción del tamaño de la vista
_GRAY = "#a6a6a6"  # el ACI 252 de las divisiones de zona
_ARROW = 3.75  # mm de papel: largo de la flecha de las líneas de distribución (el dimasz de DIM-75 a su escala)


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
        color, _, weight = layer_style(entity.layer)
        stroke = f'stroke="{color}" stroke-width="{weight * scale:.1f}" fill="none"'
        if isinstance(entity, Line):
            parts.append(f'<line x1="{entity.start[0]:.1f}" y1="{-entity.start[1]:.1f}" x2="{entity.end[0]:.1f}" '
                         f'y2="{-entity.end[1]:.1f}" {stroke}/>')
        elif isinstance(entity, Polyline):
            points = " ".join(f"{x:.1f},{-y:.1f}" for x, y in entity.points)
            tag = "polygon" if entity.closed else "polyline"
            dash = f' stroke-dasharray="{6 * scale:.0f} {3 * scale:.0f}"' if entity.dashed else ""
            if entity.color == ZONE_COLOR:  # las divisiones de zona, en gris (D-158)
                stroke = stroke.replace(f'stroke="{color}"', f'stroke="{_GRAY}"')
            paint = f'fill="{color}" stroke="none"' if entity.filled else stroke
            parts.append(f'<{tag} points="{points}" {paint}{dash}/>')
        elif isinstance(entity, Circle):
            paint = f'fill="{color}"' if entity.filled else stroke
            parts.append(f'<circle cx="{entity.center[0]:.1f}" cy="{-entity.center[1]:.1f}" r="{entity.radius:.1f}" {paint}/>')
        elif isinstance(entity, Text):
            anchor = {"left": "start", "center": "middle", "right": "end"}[entity.align]
            (x, y), rotate = entity.at, ""
            if entity.rotation:  # SVG gira en sentido horario con y hacia abajo
                rotate = f' transform="rotate({-entity.rotation:.1f} {x:.1f} {-y:.1f})"'
            parts.append(f'<text x="{x:.1f}" y="{-y:.1f}" font-size="{entity.height:.1f}" fill="{color}" '
                         f'text-anchor="{anchor}"{rotate}>{escape(entity.text)}</text>')
        elif isinstance(entity, Leader):
            (x, y) = entity.at
            for target in entity.targets:
                parts.append(f'<line x1="{target[0]:.1f}" y1="{-target[1]:.1f}" x2="{x:.1f}" y2="{-y:.1f}" {stroke}/>')
                parts.append(_arrow(target, (x, y), color, PAPER_ARROW * scale))
            parts.append(f'<text x="{x + entity.height * 0.3:.1f}" y="{-y + entity.height * 0.35:.1f}" font-size="{entity.height:.1f}" '
                         f'fill="{color}">{escape(entity.text)}</text>')
        elif isinstance(entity, Dimension):
            distribution = entity.layer == DISTRIBUTION
            parts += _distribution_svg(entity, stroke, color, scale) if distribution else _dimension_svg(entity, stroke, color)
    parts.append("</svg>")
    return "\n".join(parts) + "\n", aspect


def _distribution_svg(dimension: Dimension, stroke: str, color: str, scale: float) -> list[str]:
    """Una línea de distribución (D-158): a trazos, con una flecha cerrada en cada extremo y sin texto."""
    (sx, sy), (ex, ey) = dimension.start, dimension.end
    dash = f'stroke-dasharray="{6 * scale:.0f} {3 * scale:.0f}"'
    parts = [f'<line x1="{sx:.1f}" y1="{-sy:.1f}" x2="{ex:.1f}" y2="{-ey:.1f}" {stroke} {dash}/>']
    parts += [_arrow((sx, sy), (ex, ey), color, _ARROW * scale), _arrow((ex, ey), (sx, sy), color, _ARROW * scale)]
    return parts


def _arrow(tip: tuple[float, float], toward: tuple[float, float], color: str, size: float) -> str:
    """Una flecha cerrada de largo size con la punta en tip, mirando desde toward (distribución y rótulos, D-158)."""
    (px, py), half = tip, size / 3
    length = math.hypot(toward[0] - px, toward[1] - py) or 1.0
    dx, dy = (toward[0] - px) / length, (toward[1] - py) / length
    wing = [(px + dx * size - dy * half, py + dy * size + dx * half), (px + dx * size + dy * half, py + dy * size - dx * half)]
    points = " ".join(f"{x:.1f},{-y:.1f}" for x, y in [(px, py), *wing])
    return f'<polygon points="{points}" fill="{color}" stroke="none"/>'


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
