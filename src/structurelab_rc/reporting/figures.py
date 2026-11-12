"""Figuras de la memoria que no son resultados nuevos: aquí no se calcula nada, solo se dibuja lo que ya trae el
resultado (D-080). Presión del suelo en planta: la zapata (aislada o combinada), sus columnas, los ejes y la presión en
cada esquina del caso de servicio que gobierna la presión admisible. Diagramas de momento y cortante de las zapatas
combinadas (D-095): la envolvente de los casos mayorados, en la dirección larga y en la transversal.
"""

from pathlib import Path
from typing import Any

PRESSURE = "Presion admisible del suelo"
CORNERS = (("-x-y", -1, -1), ("+x-y", 1, -1), ("+x+y", 1, 1), ("-x+y", -1, 1))  # nombre y signos de la esquina
_WIDTH, _PLAN, _MARGIN = 640, 480, 90  # ancho de las figuras; alto máximo de la planta y margen lateral
_ABOVE, _BELOW, _LEGEND = 60, 70, 60  # sobre la zapata (título y rótulos), bajo ella (rótulos y ejes), leyenda y nota


def _plan_scale(lx: float, ly: float) -> float:
    """Escala de la planta: llena el ancho o el alto máximo, lo que limite primero."""
    return min((_WIDTH - 2 * _MARGIN) / lx, (_PLAN - _ABOVE - _BELOW) / ly)


def _plan_height(lx: float, ly: float) -> float:
    """Alto de la figura de presiones: sigue la proporción de la zapata, sin franjas en blanco (D-105)."""
    return _ABOVE + ly * _plan_scale(lx, ly) + _BELOW + _LEGEND


def pressure_aspect(lx: float, ly: float) -> float:
    """Alto / ancho de la figura de presiones de una zapata lx × ly (para la memoria)."""
    return _plan_height(lx, ly) / _WIDTH
_INK, _FILL, _COLUMN, _NONE = "#24292f", "#e8eef7", "#9aa4b2", "#c62828"
_ACCENT, _FONT = "#1f3864", "Segoe UI, Helvetica, Arial, sans-serif"  # azul de los títulos de la memoria (D-105)


def _legend(y: float, items: list[tuple[str, str]]) -> list[str]:
    """Leyenda en una fila centrada a la altura y, fuera del área del dibujo, en un recuadro: cada elemento es (muestra
    SVG de 24 × 12 con origen en su esquina, texto)."""
    widths = [40 + 5.6 * len(text) for _, text in items]
    total = sum(widths) + 16
    x = (_WIDTH - total) / 2
    parts = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{total:.1f}" height="24" fill="#ffffff" stroke="#c8ced8" stroke-width="1" '
             'rx="3"/>']
    left = x + 8
    for (sample, text), width in zip(items, widths, strict=True):
        parts.append(f'<g transform="translate({left:.1f},{y + 6:.1f})">{sample}</g>')
        parts.append(f'<text x="{left + 30:.1f}" y="{y + 16:.1f}" font-size="11" font-family="{_FONT}" fill="{_INK}">{text}</text>')
        left += width
    return parts


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
    footings = [(footing, [{"cx": footing["geometry [mm]"]["column"]["cx"], "cy": footing["geometry [mm]"]["column"]["cy"],
                            "x": footing["geometry [mm]"]["column"]["offset_x"], "y": footing["geometry [mm]"]["column"]["offset_y"]}])
                for footing in results.get("footings", [])]
    footings += [(footing, [{key: column[key] for key in ("cx", "cy", "x", "y")} for column in footing["columns"]])
                 for footing in results.get("combined_footings", [])]
    for footing, columns in footings:
        governing = governing_pressure(footing["checks"])
        if governing is None:
            continue
        geometry = footing["geometry [mm]"]
        path = folder / f"presion_{footing['id']}.svg"
        path.write_text(pressure_svg(geometry["lx"], geometry["ly"], columns, governing), encoding="utf-8", newline="\n")
        figures[footing["id"]] = path
    return figures


def pressure_svg(lx: float, ly: float, columns: list[dict[str, float]], check: dict[str, Any]) -> str:
    """Planta de la zapata (mm) con sus columnas ({cx, cy, x, y}: sección y posición del eje respecto al centroide) y la
    presión en cada esquina (kPa) del caso; las esquinas sin contacto (presión 0) van en rojo."""
    scale = _plan_scale(lx, ly)
    height = _plan_height(lx, ly)
    cx0, cy0 = _WIDTH / 2, _ABOVE + ly * scale / 2

    def point(x: float, y: float) -> tuple[float, float]:
        return cx0 + x * scale, cy0 - y * scale  # Y hacia arriba en la planta

    left, top = point(-lx / 2, ly / 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height:.0f}" viewBox="0 0 {_WIDTH} {height:.0f}">',
             f'<rect x="0" y="0" width="{_WIDTH}" height="{height:.0f}" fill="#ffffff"/>',
             f'<text x="{_WIDTH / 2}" y="24" font-size="14" font-family="{_FONT}" text-anchor="middle" fill="{_ACCENT}" '
             f'font-weight="bold">Presión del suelo en planta, caso {check.get("case", "")} (kPa)</text>',
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
              f'<text x="{_WIDTH / 2}" y="{height - 16:.0f}" font-size="12" font-family="{_FONT}" text-anchor="middle" '
              f'fill="{_INK}">lx = {lx:.0f} mm, ly = {ly:.0f} mm; {check.get("note", "")}</text>']
    parts += _legend(height - _LEGEND + 2, [
        (f'<rect x="0" y="0" width="22" height="12" fill="{_FILL}" stroke="{_INK}" stroke-width="1"/>', "Zapata"),
        (f'<rect x="0" y="0" width="22" height="12" fill="{_COLUMN}" stroke="{_INK}" stroke-width="1"/>', "Columna"),
        (f'<circle cx="11" cy="6" r="4" fill="{_INK}"/>', "Presión en la esquina (kPa)"),
        (f'<circle cx="11" cy="6" r="4" fill="{_NONE}"/>', "Esquina sin contacto")])
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


_PANEL = 220  # alto de cada panel de un diagrama
_MAX_INK, _MIN_INK, _MARK = "#1f4e9c", "#c62828", "#8a94a3"


_LEGEND_BAND = 80  # alto debajo del panel para la leyenda y la nota
DIAGRAM_ASPECT = (_PANEL + _LEGEND_BAND) / _WIDTH  # alto / ancho de una figura de diagrama (un panel)
QUANTITIES = (("V", "Fuerza cortante", "kN", "cortante"), ("M", "Momento flector", "kN·m", "momento"))


def _slug(envelope: dict[str, Any], index: int) -> str:
    """Nombre de archivo de un diagrama: principal, franja_<columna> o aletas."""
    title = envelope["title"]
    if index == 0:
        return "principal"
    if title.startswith("Franja transversal de la columna "):
        return f"franja_{title.removeprefix('Franja transversal de la columna ')}"
    return "aletas"


def diagram_figures(results: dict[str, Any], folder: Path) -> dict[str, list[Path]]:
    """Un SVG por magnitud y elemento de cada zapata combinada con diagramas (D-104): diagrama_<zapata>_<elemento>_cortante
    y _momento, con el elemento principal, franja_<columna> o aletas; en el orden de la memoria (dirección principal,
    luego cada franja o las aletas; en cada uno, cortante y momento)."""
    figures = {}
    for footing in results.get("combined_footings", []):
        diagrams = footing.get("diagrams")
        if not diagrams:
            continue
        paths = []
        for index, envelope in enumerate([diagrams["principal"], *diagrams["secondary"]]):
            for key, name, unit, word in QUANTITIES:
                path = folder / f"diagrama_{footing['id']}_{_slug(envelope, index)}_{word}.svg"
                path.write_text(diagram_svg(envelope, key, f"{name} ({unit}{' por metro' if envelope['per_metre'] else ''})"),
                                encoding="utf-8", newline="\n")
                paths.append(path)
        figures[footing["id"]] = paths
    return figures


def diagram_svg(envelope: dict[str, Any], key: str, title: str) -> str:
    """Un panel: la curva del máximo (azul) y la del mínimo (rojo) de los casos mayorados en cada posición, el eje cero y
    las marcas (columnas o caras)."""
    height = _PANEL + _LEGEND_BAND
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}">',
             f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>']
    parts += _panel(envelope, key, 20, f"{title}, envolvente de los casos mayorados")
    parts += _legend(_PANEL + 20, [
        (f'<line x1="0" y1="6" x2="24" y2="6" stroke="{_MAX_INK}" stroke-width="2"/>', "Máximo de los casos mayorados"),
        (f'<line x1="0" y1="6" x2="24" y2="6" stroke="{_MIN_INK}" stroke-width="2"/>', "Mínimo de los casos mayorados")])
    parts.append(f'<text x="{_WIDTH / 2}" y="{height - 10}" font-size="11" font-family="{_FONT}" text-anchor="middle" '
                 f'fill="{_INK}">M &gt; 0 tracciona la cara inferior; V del cuerpo libre a la izquierda.</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _panel(envelope: dict[str, Any], key: str, top: float, title: str) -> list[str]:
    positions = envelope["positions [mm]"]
    upper = envelope[f"{key} max [{'kN-m' if key == 'M' else 'kN'}]"]
    lower = envelope[f"{key} min [{'kN-m' if key == 'M' else 'kN'}]"]
    left, right = 70.0, _WIDTH - 30.0
    plot_top, plot_bottom = top + 34, top + _PANEL - 36
    start, end = min(positions), max(positions)
    low, high = min(0.0, *lower), max(0.0, *upper)
    span = (high - low) or 1.0

    def point(position: float, value: float) -> tuple[float, float]:
        x = left + (position - start) / ((end - start) or 1.0) * (right - left)
        return x, plot_bottom - (value - low) / span * (plot_bottom - plot_top)

    zero = point(start, 0.0)[1]
    parts = [f'<text x="{_WIDTH / 2}" y="{top + 16}" font-size="12" font-family="{_FONT}" text-anchor="middle" '
             f'fill="{_ACCENT}" font-weight="bold">{title}</text>',
             f'<line x1="{left:.1f}" y1="{zero:.1f}" x2="{right:.1f}" y2="{zero:.1f}" stroke="{_INK}" stroke-width="1"/>']
    for mark in envelope["marks"]:
        x = point(mark["position [mm]"], 0.0)[0]
        parts += [f'<line x1="{x:.1f}" y1="{plot_top:.1f}" x2="{x:.1f}" y2="{plot_bottom:.1f}" stroke="{_MARK}" '
                  f'stroke-dasharray="4 3" stroke-width="1"/>',
                  f'<text x="{x:.1f}" y="{plot_bottom + 14:.1f}" font-size="10" font-family="Helvetica" text-anchor="middle" '
                  f'fill="{_MARK}">{mark["label"]}</text>']
    for first, last in envelope["segments"]:
        for values, color in ((upper, _MAX_INK), (lower, _MIN_INK)):
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(positions[i], values[i]) for i in range(first, last + 1)))
            parts.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.6"/>')
    for label, value in ((f"{high:.1f}", high), (f"{low:.1f}", low)):
        parts.append(f'<text x="{left - 6:.1f}" y="{point(start, value)[1] + 4:.1f}" font-size="10" font-family="Helvetica" '
                     f'text-anchor="end" fill="{_INK}">{label}</text>')
    parts.append(f'<text x="{left:.1f}" y="{plot_bottom + 28:.1f}" font-size="10" font-family="Helvetica" fill="{_INK}">'
                 f'{start:.0f} mm</text>')
    parts.append(f'<text x="{right:.1f}" y="{plot_bottom + 28:.1f}" font-size="10" font-family="Helvetica" text-anchor="end" '
                 f'fill="{_INK}">{end:.0f} mm</text>')
    return parts
