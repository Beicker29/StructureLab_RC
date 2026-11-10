"""Figuras de la memoria que no son resultados nuevos: aquí no se calcula nada, solo se dibuja lo que ya trae el
resultado (D-080). Presión del suelo en planta: la zapata, sus columnas, los ejes y la presión en cada esquina del caso
de servicio que gobierna la presión admisible.
"""

from pathlib import Path
from typing import Any

PRESSURE = "Presion admisible del suelo"
CORNERS = (("-x-y", -1, -1), ("+x-y", 1, -1), ("+x+y", 1, 1), ("-x+y", -1, 1))  # nombre y signos de la esquina
_WIDTH, _HEIGHT, _MARGIN = 640, 480, 90
FIGURE_ASPECT = _HEIGHT / _WIDTH
_INK, _FILL, _COLUMN, _NONE = "#24292f", "#e8eef7", "#9aa4b2", "#c62828"


def corner_key(name: str) -> str:
    return f"p esquina {name} [kPa]"


def governing_pressure(checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La verificación de presión admisible de mayor razón que tiene las presiones en las esquinas, o None."""
    candidates = [check for check in checks if check["name"] == PRESSURE and check.get("ratio") is not None
                  and corner_key("-x-y") in check["values"]]
    return max(candidates, key=lambda check: check["ratio"], default=None)


def pressure_figures(results: dict[str, Any], folder: Path) -> dict[str, Path]:
    """Escribe presion_<zapata>.svg por cada zapata con la presión en las esquinas y devuelve sus rutas (D-080)."""
    figures = {}
    for footing in results.get("footings", []):
        governing = governing_pressure(footing["checks"])
        if governing is None:
            continue
        geometry = footing["geometry [mm]"]
        column = geometry["column"]
        columns = [{"cx": column["cx"], "cy": column["cy"], "x": column["offset_x"], "y": column["offset_y"]}]
        path = folder / f"presion_{footing['id']}.svg"
        path.write_text(pressure_svg(geometry["lx"], geometry["ly"], columns, governing), encoding="utf-8", newline="\n")
        figures[footing["id"]] = path
    return figures


def pressure_svg(lx: float, ly: float, columns: list[dict[str, float]], check: dict[str, Any]) -> str:
    """Planta de la zapata (mm) con sus columnas ({cx, cy, x, y}: sección y posición del eje respecto al centroide) y la
    presión en cada esquina (kPa) del caso; las esquinas sin contacto (presión 0) van en rojo."""
    scale = min((_WIDTH - 2 * _MARGIN) / lx, (_HEIGHT - 2 * _MARGIN) / ly)
    cx0, cy0 = _WIDTH / 2, _HEIGHT / 2

    def point(x: float, y: float) -> tuple[float, float]:
        return cx0 + x * scale, cy0 - y * scale  # Y hacia arriba en la planta

    left, top = point(-lx / 2, ly / 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" viewBox="0 0 {_WIDTH} {_HEIGHT}">',
             f'<rect x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}" fill="#ffffff"/>',
             f'<text x="{_WIDTH / 2}" y="24" font-size="14" font-family="Helvetica" text-anchor="middle" fill="{_INK}">'
             f'Presión del suelo en planta, caso {check.get("case", "")} (kPa)</text>',
             f'<rect x="{left:.1f}" y="{top:.1f}" width="{lx * scale:.1f}" height="{ly * scale:.1f}" fill="{_FILL}" '
             f'stroke="{_INK}" stroke-width="1.5"/>']
    for column in columns:
        x0, y0 = point(column["x"] - column["cx"] / 2, column["y"] + column["cy"] / 2)
        parts.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{column["cx"] * scale:.1f}" height="{column["cy"] * scale:.1f}" '
                     f'fill="{_COLUMN}" stroke="{_INK}" stroke-width="1"/>')
    for name, sx, sy in CORNERS:
        value = check["values"][corner_key(name)]
        x, y = point(sx * lx / 2, sy * ly / 2)
        color = _NONE if value == 0 else _INK
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        dx, anchor = (10, "start") if sx > 0 else (-10, "end")
        dy = -10 if sy > 0 else 20
        label = "0 (sin contacto)" if value == 0 else f"{value:.1f}"
        parts.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" font-size="13" font-family="Helvetica" text-anchor="{anchor}" '
                     f'fill="{color}">{label}</text>')
    ax, ay = point(-lx / 2, -ly / 2)
    parts += [f'<line x1="{ax:.1f}" y1="{ay + 40:.1f}" x2="{ax + 50:.1f}" y2="{ay + 40:.1f}" stroke="{_INK}" stroke-width="1"/>',
              f'<text x="{ax + 56:.1f}" y="{ay + 44:.1f}" font-size="12" font-family="Helvetica" fill="{_INK}">X</text>',
              f'<line x1="{ax - 40:.1f}" y1="{ay:.1f}" x2="{ax - 40:.1f}" y2="{ay - 50:.1f}" stroke="{_INK}" stroke-width="1"/>',
              f'<text x="{ax - 44:.1f}" y="{ay - 56:.1f}" font-size="12" font-family="Helvetica" fill="{_INK}">Y</text>',
              f'<text x="{_WIDTH / 2}" y="{_HEIGHT - 16}" font-size="12" font-family="Helvetica" text-anchor="middle" '
              f'fill="{_INK}">lx = {lx:.0f} mm, ly = {ly:.0f} mm; {check.get("note", "")}</text>',
              "</svg>"]
    return "\n".join(parts) + "\n"
