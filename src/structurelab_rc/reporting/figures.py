"""Figuras de la memoria que no son resultados nuevos: aquí no se calcula nada, solo se dibuja lo que ya trae el
resultado (D-080). Presión del suelo en planta: la zapata (aislada o combinada), sus columnas, los ejes y la presión en
cada esquina del caso de servicio que gobierna la presión admisible. Diagramas de momento y cortante de las zapatas
combinadas (D-095): la envolvente de los casos mayorados, en la dirección larga y en la transversal.
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


_PANEL = 220  # alto de cada panel de un diagrama
_MAX_INK, _MIN_INK, _MARK = "#1f4e9c", "#c62828", "#8a94a3"


def diagram_aspect(panels: int) -> float:
    """Alto / ancho de una figura de diagramas con `panels` paneles (para la memoria)."""
    return (_PANEL * panels + 40) / _WIDTH


def diagram_figures(results: dict[str, Any], folder: Path) -> dict[str, tuple[Path, Path]]:
    """Escribe diagrama_<zapata>_principal.svg y diagrama_<zapata>_secundaria.svg por cada zapata combinada con
    diagramas (D-095, D-101) y devuelve sus rutas."""
    figures = {}
    for footing in results.get("combined_footings", []):
        diagrams = footing.get("diagrams")
        if not diagrams:
            continue
        principal = folder / f"diagrama_{footing['id']}_principal.svg"
        secondary = folder / f"diagrama_{footing['id']}_secundaria.svg"
        principal.write_text(diagrams_svg([diagrams["principal"]]), encoding="utf-8", newline="\n")
        secondary.write_text(diagrams_svg(diagrams["secondary"]), encoding="utf-8", newline="\n")
        figures[footing["id"]] = (principal, secondary)
    return figures


def diagrams_svg(envelopes: list[dict[str, Any]]) -> str:
    """Un par de paneles (M arriba, V abajo) por envolvente: la curva del máximo (azul) y la del mínimo (rojo) de los casos
    mayorados en cada posición, el eje cero, las marcas (columnas o caras) y los extremos con su caso."""
    height = _PANEL * 2 * len(envelopes) + 40
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}">',
             f'<rect x="0" y="0" width="{_WIDTH}" height="{height}" fill="#ffffff"/>']
    for index, envelope in enumerate(envelopes):
        unit = " por metro" if envelope["per_metre"] else ""
        for row, (key, name, unit_text) in enumerate((("M", "Momento flector", "kN·m"), ("V", "Fuerza cortante", "kN"))):
            top = 20 + _PANEL * (2 * index + row)
            title = f"{envelope['title']}: {name.lower()} ({unit_text}{unit}), envolvente de los casos mayorados"
            parts += _panel(envelope, key, top, title)
    parts.append(f'<text x="{_WIDTH / 2}" y="{height - 10}" font-size="11" font-family="Helvetica" text-anchor="middle" '
                 f'fill="{_INK}">Azul: máximo; rojo: mínimo. M &gt; 0 tracciona la cara inferior; V del cuerpo libre a la '
                 f'izquierda.</text>')
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
    parts = [f'<text x="{_WIDTH / 2}" y="{top + 16}" font-size="12" font-family="Helvetica" text-anchor="middle" '
             f'fill="{_INK}">{title}</text>',
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
