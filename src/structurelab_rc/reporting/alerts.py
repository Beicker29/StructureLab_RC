"""Alertas de tipologías atípicas (D-172): datos, las dos tablas CSV y la sección de la memoria. Aquí no se calcula
nada: solo se presenta lo que devuelve design/footing/alerts.typology_alerts.
"""

from collections import Counter
from typing import Any

from structurelab_rc.design.footing.alerts import METRICS, AlertsResult
from structurelab_rc.reporting.units import kN

_M2 = 1e6  # mm² por m²
_M3 = 1e9  # mm³ por m³
_METRIC_NAMES = {"area": "área", "volume": "volumen"}
NOTES = (
    "Este análisis es una alerta para revisión del ingeniero, no una decisión de diseño.",
    "Los momentos en la base provienen del modelo estructural. Si se modeló con base empotrada y sin vigas de amarre, "
    "pueden estar sobreestimados. Verifique antes de decidir.",
    "Cuando el momento es reversible, evalúe si la viga centradora se requiere en una o en ambas direcciones.",
)
ACTION = ("La solución la decide el analista en el proyecto: declarar las columnas en zapata combinada (combined_pairs, "
          "D-153) o quitarlas del diseño por tipologías (exclude_unique_names, D-111) y tratarlas aparte. Este análisis no "
          "cambia el diseño.")


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def alerts_data(result: AlertsResult) -> dict[str, Any]:
    """Las alertas en datos (el canal hacia la memoria y alertas_tipologias.json): parámetros, estadística de cada
    métrica, concentración, cada tipología y cada columna candidata."""
    settings = result.settings
    candidates = [signal for signal in result.columns if signal.candidate]
    statistics = {}
    for metric in METRICS:
        stat = result.statistics[metric]
        scale = _M2 if metric == "area" else _M3
        statistics[metric] = {
            "q1": _round(None if stat.q1 is None else stat.q1 / scale, 3),
            "q3": _round(None if stat.q3 is None else stat.q3 / scale, 3),
            "tukey_limit": _round(None if stat.tukey_limit is None else stat.tukey_limit / scale, 3),
            "median": _round(None if stat.median is None else stat.median / scale, 3),
            "mad": _round(None if stat.mad is None else stat.mad / scale, 3),
            **({"tukey_note": stat.tukey_note} if stat.tukey_note else {}),
            **({"z_note": stat.z_note} if stat.z_note else {})}
    concentration = result.concentration
    return {
        "fc [MPa]": result.fc,
        "settings": settings.model_dump(),
        "columns_count": len(result.columns),
        "candidates_by_reason": dict(sorted(Counter(reason for signal in candidates for reason in signal.reasons).items())),
        "statistics": statistics,
        "concentration": {"fraction": concentration.fraction, "columns": concentration.count, "of": concentration.total,
                          "concrete [%]": round(concentration.concrete_share, 1),
                          "cost [%]": round(concentration.cost_share, 1)},
        "typologies": [
            {"name": item.name, "lx [mm]": item.lx, "ly [mm]": item.ly, "h [mm]": item.h,
             "area [m2]": round(item.area / _M2, 3), "volume [m3]": round(item.volume / _M3, 3),
             "columns": len(item.columns), "cost": round(item.cost, 2), "singles_cost": round(item.singles_cost, 2),
             "grouping_overcost": round(item.grouping_overcost, 2), "candidates": item.candidates,
             "z_area": _round(item.z["area"], 2), "z_volume": _round(item.z["volume"], 2),
             "atypical_by": list(item.atypical_by), "small": item.small, "flagged": item.flagged}
            for item in result.typologies],
        "candidates": [
            {"column": signal.column, "joint": signal.joint, "typology": signal.typology,
             "P_max [kN]": round(kN(signal.p_max), 1), "P_min [kN]": round(kN(signal.p_min), 1),
             "FA": _round(signal.fa, 3), "ex/lx": _round(signal.ex_ratio, 3), "ex_case": signal.ex_case,
             "ey/ly": _round(signal.ey_ratio, 3), "ey_case": signal.ey_case, "contact": _round(signal.contact, 3),
             "contact_case": signal.contact_case, "reasons": list(signal.reasons)}
            for signal in candidates],
    }


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " | ".join(str(item) for item in value)
        return str(value)

    return "\n".join([";".join(header), *(";".join(cell(value) for value in row) for row in rows)]) + "\n"


def typologies_csv(data: dict[str, Any]) -> str:
    """tipologias_estadistica.csv: una fila por tipología con sus métricas y señales."""
    limits = {metric: data["statistics"][metric]["tukey_limit"] for metric in METRICS}
    header = ["tipologia", "lx_mm", "ly_mm", "h_mm", "area_m2", "volumen_m3", "columnas", "costo_total", "candidatas",
              "limite_tukey_area_m2", "atipica_tukey_area", "z_area", "atipica_z_area",
              "limite_tukey_volumen_m3", "atipica_tukey_volumen", "z_volumen", "atipica_z_volumen",
              "pequena", "suma_individuales", "sobrecosto_agrupacion", "senalada"]
    rows = [[row["name"], row["lx [mm]"], row["ly [mm]"], row["h [mm]"], row["area [m2]"], row["volume [m3]"], row["columns"],
             row["cost"], row["candidates"],
             limits["area"], "tukey area" in row["atypical_by"], row["z_area"], "z area" in row["atypical_by"],
             limits["volume"], "tukey volume" in row["atypical_by"], row["z_volume"], "z volume" in row["atypical_by"],
             row["small"], row["singles_cost"], row["grouping_overcost"], row["flagged"]] for row in data["typologies"]]
    return _csv(header, rows)


def columns_csv(data: dict[str, Any]) -> str:
    """alertas_columnas.csv: una fila por columna candidata con sus señales y el motivo."""
    header = ["columna", "nudo", "tipologia", "P_max_kN", "P_min_kN", "FA", "ex_B_max", "caso_ex", "ey_L_max", "caso_ey",
              "contacto_min", "caso_contacto", "motivos"]
    rows = [[row["column"], row["joint"], row["typology"], row["P_max [kN]"], row["P_min [kN]"], row["FA"], row["ex/lx"],
             row["ex_case"], row["ey/ly"], row["ey_case"], row["contact"], row["contact_case"], row["reasons"]]
            for row in data["candidates"]]
    return _csv(header, rows)


def _value(value: float | None, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def alerts_document(data: dict[str, Any]) -> list[dict[str, Any]]:
    """La sección de la memoria (los mismos bloques en memoria.txt y memoria.pdf)."""
    settings = data["settings"]
    typologies = data["typologies"]
    flagged = [row for row in typologies if row["flagged"]]
    atypical = [row["name"] for row in typologies if row["atypical_by"]]
    small = [row["name"] for row in typologies if row["small"]]
    concentration = data["concentration"]
    reasons = data["candidates_by_reason"]
    blocks: list[dict[str, Any]] = [
        {"kind": "h1", "text": "Alertas de tipologías atípicas (D-172)"},
        *({"kind": "note", "text": text} for text in NOTES),
        {"kind": "p", "text": f"Métricas sobre el resultado del diseño por tipologías (f'c = {data['fc [MPa]']:g} MPa). Una "
                              "columna es candidata si su zapata individual crece por el momento (FA), si su excentricidad "
                              "de servicio supera el umbral en alguna dirección o si su carga axial de servicio es baja o "
                              "nula. Una tipología queda señalada si es atípica por área o por volumen y tiene al menos una "
                              "candidata."},
        {"kind": "h2", "text": "Parámetros"},
        {"kind": "kv", "items": [
            ("Umbral de FA = A(P, M)/A(P, 0)", f"{settings['fa_threshold']:g}"),
            ("Umbral de e/B", f"{settings['eccentricity_threshold']:g}"),
            ("P mínima relativa (P_min/P_max de servicio)", f"{settings['min_relative_p']:g}"),
            ("k de Tukey (Q3 + k·IQR)", f"{settings['tukey_k']:g}"),
            ("Umbral del z robusto", f"{settings['z_threshold']:g}"),
            ("Columnas de una tipología pequeña", f"≤ {settings['small_typology_max_columns']}"),
            ("Tipologías mínimas para la estadística", str(settings["min_typologies_for_statistics"])),
            ("Fracción de las columnas que más consumen", f"{settings['pareto_fraction']:g}")]},
        {"kind": "h2", "text": "Resumen"},
        {"kind": "kv", "items": [
            ("Columnas aisladas", str(data["columns_count"])),
            ("Columnas candidatas", str(len(data["candidates"]))),
            *((f"  por {reason}", str(count)) for reason, count in reasons.items()),
            ("Tipologías atípicas", ", ".join(atypical) or "ninguna"),
            ("Tipologías atípicas pequeñas", ", ".join(small) or "ninguna"),
            ("Tipologías señaladas", ", ".join(row["name"] for row in flagged) or "ninguna"),
            ("Concentración", f"{concentration['columns']} de {concentration['of']} columnas consumen el "
                              f"{concentration['concrete [%]']:.1f} % del concreto y el {concentration['cost [%]']:.1f} % "
                              "del costo de las aisladas"),
            *((f"Límite de Tukey del {_METRIC_NAMES[metric]}",
               f"{data['statistics'][metric]['tukey_limit']:.3f} {'m²' if metric == 'area' else 'm³'}")
              for metric in METRICS if data["statistics"][metric]["tukey_limit"] is not None)]},
    ]
    for metric in METRICS:
        stat = data["statistics"][metric]
        for key, method in (("tukey_note", "Tukey"), ("z_note", "z robusto")):
            if key in stat:
                blocks.append({"kind": "note", "text": f"{method} del {_METRIC_NAMES[metric]} no calculado: {stat[key]}."})
    blocks.append({"kind": "h2", "text": "Tipologías señaladas"})
    if flagged:
        blocks.append({"kind": "table", "headers": ["Tipología", "lx × ly × h (mm)", "Área (m²)", "Volumen (m³)", "Columnas",
                                                    "Candidatas", "Atípica por", "Sobrecosto por agrupación", "Pequeña"],
                       "rows": [[row["name"], f"{row['lx [mm]']:g} × {row['ly [mm]']:g} × {row['h [mm]']:g}",
                                 f"{row['area [m2]']:.2f}", f"{row['volume [m3]']:.2f}", str(row["columns"]),
                                 str(row["candidates"]), ", ".join(row["atypical_by"]), _money(row["grouping_overcost"]),
                                 "sí" if row["small"] else "no"] for row in flagged]})
        blocks.append({"kind": "alert", "text": ACTION})
    else:
        blocks.append({"kind": "p", "text": "Ninguna tipología queda señalada."})
    blocks.append({"kind": "h2", "text": "Columnas candidatas"})
    if data["candidates"]:
        blocks.append({"kind": "table", "headers": ["Columna", "Nudo", "Tipología", "FA", "ex/lx", "ey/ly", "Contacto mín.",
                                                    "Motivos"],
                       "rows": [[row["column"], row["joint"] or "–", row["typology"], _value(row["FA"]),
                                 _value(row["ex/lx"], 3), _value(row["ey/ly"], 3), _value(row["contact"]),
                                 ", ".join(row["reasons"])] for row in data["candidates"]]})
    else:
        blocks.append({"kind": "p", "text": "Ninguna columna es candidata."})
    blocks.append({"kind": "note", "text": "El detalle de cada tipología y de cada candidata está en tipologias_estadistica.csv "
                                           "y alertas_columnas.csv."})
    return blocks
