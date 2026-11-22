"""Curva costo–N del diseño por tipologías (D-078): datos, CSV, gráfica SVG y bloques de la memoria; aquí no se calcula
nada del diseño, solo se presenta lo que devuelve typology_curve.

Cada punto lleva el f'c elegido, el costo total, el ahorro frente al punto anterior, si el costo sube, si el MILP
certificó el óptimo en su catálogo y las tipologías repetidas (con los límites de diseño en que están). Las repetidas
y un ahorro marginal pequeño indican que N está saturado (el plan no fija un umbral: la lectura es del ingeniero).
"""

from collections.abc import Sequence
from typing import Any

from structurelab_rc.design.footing.typologies import CurvePoint, DesignResult

_OPTIMAL = "optimal"
_WIDTH, _HEIGHT = 760, 420
_LEFT, _RIGHT, _TOP, _BOTTOM = 92, 24, 40, 56
_Y_TICKS = 5
_BLUE, _ORANGE, _RED, _GREY, _INK = "#1f6feb", "#d97706", "#c62828", "#c8cdd3", "#24292f"


def _status(result: DesignResult) -> str | None:
    """Estado del MILP del f'c elegido: con milp_iter el de su última iteración; con milp el del MILP; con dp no hay."""
    if result.iterations:
        return result.iterations[-1].status
    return None if result.milp is None else result.milp.status


def curve_data(points: Sequence[CurvePoint], method: str, seconds: float,
               combined: dict[str, Any] | None = None) -> dict[str, Any]:
    """Los puntos de la curva. Con combinadas (D-165), combined = {"pairs": pares, "types": tipos o None}: el costo de cada
    punto es el de la cimentación (aisladas más combinadas) y cada fila separa los dos."""
    rows = []
    reference = next((point.total for point in points if point.result.fc is not None), None)  # el menor N con solución
    for point in points:
        result = point.result
        status = _status(result)
        total = None if reference is None or result.fc is None else reference - point.total
        costs = ({"isolated_cost": None if result.fc is None else round(result.cost, 2),
                  "combined_cost": None if result.fc is None else round(point.combined_cost, 2)} if combined else {})
        rows.append({
            "N": point.count,
            "fc [MPa]": result.fc,
            "cost": None if result.fc is None else round(point.total, 2),
            **costs,
            "saving": None if point.saving is None else round(point.saving, 2),
            "saving [%]": None if point.saving is None or not point.saving + point.total else
            round(100 * point.saving / (point.saving + point.total), 3),
            "saving_from_first": None if total is None else round(total, 2),
            "saving_from_first [%]": None if total is None or reference is None or not reference else
            round(100 * total / reference, 3),
            "rises": point.rises,
            "status": status,
            "certified": None if status is None else status == _OPTIMAL,
            "distinct_count": result.distinct_count if result.fc is not None else None,
            "duplicates": [{"typologies": list(group.typologies), "at_limit": list(group.at_limit)} for group in result.duplicates],
            **({"failure": result.failure} if result.failure else {}),
        })
    return {"method": method, "seconds": round(seconds, 1), **({"combined": combined} if combined else {}), "points": rows}


def curve_csv(data: dict[str, Any]) -> str:
    split = "combined" in data  # con combinadas, el costo de las aisladas y el de las combinadas (D-165)
    header = "N;fc_MPa;costo;" + ("costo_aisladas;costo_combinadas;" if split else "") + (
        "ahorro;ahorro_pct;ahorro_desde_N1;ahorro_desde_N1_pct;sube;certificado;distintas;repetidas")
    lines = [header]
    for row in data["points"]:
        repeats = " | ".join("=".join(group["typologies"]) + (f" ({','.join(group['at_limit'])})" if group["at_limit"] else "")
                             for group in row["duplicates"])
        values = [row["N"], row["fc [MPa]"], row["cost"], *([row["isolated_cost"], row["combined_cost"]] if split else []),
                  row["saving"], row["saving [%]"], row["saving_from_first"],
                  row["saving_from_first [%]"], row["rises"], row["certified"], row["distinct_count"], repeats]
        lines.append(";".join("" if value is None else str(value) for value in values))
    return "\n".join(lines) + "\n"


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def curve_svg(data: dict[str, Any]) -> str:
    """Costo total frente a N: línea azul, puntos naranjas si tienen repetidas y rojos si el costo sube."""
    valid = [row for row in data["points"] if row["cost"] is not None]
    plot_w, plot_h = _WIDTH - _LEFT - _RIGHT, _HEIGHT - _TOP - _BOTTOM
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" viewBox="0 0 {_WIDTH} {_HEIGHT}">',
             f'<rect x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}" fill="#ffffff"/>',
             f'<text x="{_WIDTH / 2}" y="22" font-size="14" font-family="Helvetica" text-anchor="middle" fill="{_INK}">'
             f'Costo total frente al número de tipologías ({data["method"]})</text>']
    if not valid:
        parts.append(f'<text x="{_WIDTH / 2}" y="{_HEIGHT / 2}" font-size="12" font-family="Helvetica" text-anchor="middle">'
                     'Sin puntos con solución</text></svg>')
        return "\n".join(parts) + "\n"
    counts = [row["N"] for row in data["points"]]
    low, high = min(row["cost"] for row in valid), max(row["cost"] for row in valid)
    pad = (high - low) * 0.08 or high * 0.05 or 1.0
    low, high = low - pad, high + pad
    first, last = min(counts), max(counts)

    def x(count: int) -> float:
        return _LEFT + (plot_w / 2 if first == last else (count - first) / (last - first) * plot_w)

    def y(cost: float) -> float:
        return _TOP + (high - cost) / (high - low) * plot_h

    for index in range(_Y_TICKS + 1):  # rejilla y escala de costo (millones)
        value = low + (high - low) * index / _Y_TICKS
        level = f"{y(value):.1f}"
        parts.append(f'<line x1="{_LEFT}" y1="{level}" x2="{_LEFT + plot_w}" y2="{level}" stroke="{_GREY}" stroke-width="0.6"/>')
        parts.append(f'<text x="{_LEFT - 8}" y="{y(value) + 4:.1f}" font-size="11" font-family="Helvetica" text-anchor="end" '
                     f'fill="{_INK}">{value / 1e6:,.1f} M</text>')
    for count in counts:
        parts.append(f'<text x="{x(count):.1f}" y="{_TOP + plot_h + 18}" font-size="11" font-family="Helvetica" '
                     f'text-anchor="middle" fill="{_INK}">{count}</text>')
    parts.append(f'<line x1="{_LEFT}" y1="{_TOP + plot_h}" x2="{_LEFT + plot_w}" y2="{_TOP + plot_h}" stroke="{_INK}" stroke-width="1"/>')
    parts.append(f'<line x1="{_LEFT}" y1="{_TOP}" x2="{_LEFT}" y2="{_TOP + plot_h}" stroke="{_INK}" stroke-width="1"/>')
    line = " ".join(f"{x(row['N']):.1f},{y(row['cost']):.1f}" for row in valid)
    parts.append(f'<polyline points="{line}" fill="none" stroke="{_BLUE}" stroke-width="2"/>')
    for row in valid:
        color = _RED if row["rises"] else (_ORANGE if row["duplicates"] else _BLUE)
        parts.append(f'<circle cx="{x(row["N"]):.1f}" cy="{y(row["cost"]):.1f}" r="4" fill="{color}"/>')
    parts.append(f'<text x="{_LEFT + plot_w / 2}" y="{_HEIGHT - 14}" font-size="12" font-family="Helvetica" text-anchor="middle" '
                 f'fill="{_INK}">Número de tipologías N (naranja: con repetidas; rojo: el costo sube)</text>')
    parts.append(f'<text x="18" y="{_TOP + plot_h / 2}" font-size="12" font-family="Helvetica" text-anchor="middle" '
                 f'fill="{_INK}" transform="rotate(-90 18 {_TOP + plot_h / 2})">Costo total</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def curve_document(data: dict[str, Any], project: dict[str, str], svg_path: str) -> list[dict[str, Any]]:
    """Bloques de la memoria de la curva (los mismos que dibujan memoria.txt y memoria.pdf)."""
    combined = data.get("combined")
    rows = []
    for row in data["points"]:
        repeats = "; ".join(" = ".join(group["typologies"]) + (f" (límite {', '.join(group['at_limit'])})" if group["at_limit"] else "")
                            for group in row["duplicates"])
        certified = {True: "sí", False: "no", None: "–"}[row["certified"]]
        rows.append([str(row["N"]), "–" if row["fc [MPa]"] is None else f"{row['fc [MPa]']:g}",
                     "sin solución" if row["cost"] is None else _money(row["cost"]),
                     *(["–" if row["isolated_cost"] is None else _money(row["isolated_cost"]),
                        "–" if row["combined_cost"] is None else _money(row["combined_cost"])] if combined else []),
                     "–" if row["saving"] is None else _money(row["saving"]),
                     "–" if row["saving [%]"] is None else f"{row['saving [%]']:.2f} %",
                     "–" if not row["saving_from_first"] else _money(row["saving_from_first"]),
                     "–" if not row["saving_from_first [%]"] else f"{row['saving_from_first [%]']:.2f} %",
                     "sí" if row["rises"] else "no", certified,
                     "–" if row["distinct_count"] is None else str(row["distinct_count"]), repeats or "–"])
    blocks: list[dict[str, Any]] = [
        {"kind": "h1", "text": "Curva costo–N del diseño por tipologías"},
        {"kind": "kv", "items": [("Proyecto", project["description"]), ("Perfil", project["profile"]),
                                 ("Método", data["method"]), ("Tiempo total", f"{data['seconds']:.0f} s"),
                                 *([("Zapatas combinadas", _combined_text(combined))] if combined else [])]},
        {"kind": "image", "path": svg_path, "caption": "Costo total frente al número de tipologías", "aspect": _HEIGHT / _WIDTH},
        {"kind": "h2", "text": "Puntos de la curva"},
        {"kind": "table", "headers": ["N", "f'c (MPa)", "Costo total", *(["Aisladas", "Combinadas"] if combined else []),
                                      "Ahorro frente a N − 1", "Ahorro (%)",
                                      f"Ahorro frente a N = {data['points'][0]['N']}", "Ahorro acumulado (%)", "Sube",
                                      "Óptimo certificado", "Distintas", "Repetidas"], "rows": rows},
        {"kind": "h2", "text": "Lectura de la curva"},
        {"kind": "note", "text": "Cada punto conserva el catálogo de candidatos de los anteriores, así que puede resultar igual o "
                                 "más barato que el diseño suelto con ese N (D-078). El diseño de un N elegido se obtiene con "
                                 "design-footings y design.typologies = N, y se reverifica con report."},
        {"kind": "note", "text": "N está saturado cuando, al subirlo, aparecen tipologías repetidas y el ahorro marginal es "
                                 "pequeño; una repetida en plan_max o h_max indica que el límite de diseño, no la demanda, fija "
                                 "la tipología (D-074)."},
    ]
    if combined:
        blocks.append({"kind": "note", "text": "N es el número de tipologías de las zapatas aisladas; las combinadas se diseñan "
                                               "una vez, con sus pares y combined_typologies declarados, y suman su costo en el "
                                               "f'c de cada punto (decisión del usuario, D-165)."})
    rises = [str(row["N"]) for row in data["points"] if row["rises"]]
    if rises:
        blocks.append({"kind": "alert", "text": f"El costo sube respecto al punto anterior en N = {', '.join(rises)}: con N "
                                                "tipologías distintas exactas no siempre hay una más barata (D-074)."})
    uncertified = [str(row["N"]) for row in data["points"] if row["certified"] is False]
    if uncertified:
        blocks.append({"kind": "alert", "text": f"Óptimo sin certificar (límite de tiempo del MILP) en N = {', '.join(uncertified)}."})
    return blocks


def _combined_text(combined: dict[str, Any]) -> str:
    """Los pares y sus tipos, para la memoria de la curva (D-165)."""
    types = combined.get("types")
    grouped = f" en {types} tipos (combined_typologies)" if types else ", una por par"
    return f"{combined['pairs']} pares{grouped}; su costo es constante en cada f'c"
