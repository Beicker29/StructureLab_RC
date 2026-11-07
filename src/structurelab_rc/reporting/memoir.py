"""Memoria de verificación en texto, construida solo a partir del resultado (D-050).

Los factores φ, las capacidades y los numerales se leen del resultado; la memoria no calcula nada. El texto usa solo
caracteres de Latin-1, para que el PDF pueda escribirse con las fuentes básicas.
"""

from typing import Any

from structurelab_rc.domain.status import Status

_RULE = "=" * 100
_CONVENTIONS = (
    "Las fuerzas llegan mayoradas; la aplicacion no genera combinaciones (D-003).",
    "Ejes de ETABS: X = eje 3, Y = eje 2 (hacia arriba), Z = eje 1. Mu (M3) positivo comprime la cara superior y "
    "M2 positivo comprime la cara +3 (D-044).",
    "Flexion con Pn = Pu y momentos respecto al centroide bruto (D-024); resistencia biaxial con la seccion completa "
    "y deformacion neta de traccion en los estados M3, M2 y biaxial (D-046).",
    "d no menor que 0.8h en As,min, cortante y torsion (D-043); en el cortante V3, no menor que 0.8bw (D-047).",
    "La torsion se desprecia si Tu < phi Tth; si no, se verifica combinada con el cortante (D-037).",
    "Los factores phi, las capacidades y los numerales provienen del resultado de cada verificacion.",
)
_PRECEDENCE = {str(Status.FAIL): 3, str(Status.INCOMPLETE): 2, str(Status.BLOCKED): 1, str(Status.PASS): 0}
_DECIMALS = {"kN-m": 1, "kN": 1, "mm": 0, "mm2": 0, "mm2/mm": 3, "MPa": 2, "deg": 2, "-": 5}
_CONCRETE = {"normalweight": "concreto de peso normal", "lightweight": "concreto liviano"}
_TYPES = {"beam": "viga", "column": "columna", "footing": "zapata", "wall": "muro", "slab": "losa"}


def _number(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    text = f"{value:.{_DECIMALS.get(unit, 4)}f}"
    return text if unit == "-" else f"{text} {unit}"


def _values(values: dict[str, float | None]) -> str:
    parts = []
    for key, value in values.items():
        unit = key[key.index("[") + 1 : -1] if "[" in key else "-"
        name = key.split(" [")[0]
        parts.append(f"{name} = {_number(value, unit)}")
    return "; ".join(parts)


def _where(station: dict[str, Any]) -> str:
    case = station["case"] or "-"
    return f"z = {station['z [mm]']:.0f} mm, caso {case}"


def _section(member: dict[str, Any]) -> str:
    section = member["section"]
    text = f"{section['bw']:.0f} x {section['h']:.0f} mm, recubrimiento {section['cover']:.0f} mm"
    if "hf" in section:
        overhangs = f"{section['overhang_x_neg']:.0f} (-3) y {section['overhang_x_pos']:.0f} (+3) mm"
        text += f", ala hf = {section['hf']:.0f} mm con salientes {overhangs}"
    return text


def _governing(member: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Por verificación, la estación más exigida: primero el estado más severo, luego la mayor razón."""
    def severity(check: dict[str, Any]) -> tuple[int, float]:
        return _PRECEDENCE[check["status"]], check["ratio"] if check["ratio"] is not None else -1.0

    governing: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for station in member["stations"]:
        for check in station["checks"]:
            current = governing.get(check["name"])
            if current is None or severity(check) > severity(current[1]):
                governing[check["name"]] = (station, check)
    return governing


def _detail(lines: list[str], member_id: str, station: dict[str, Any], check: dict[str, Any]) -> None:
    lines.append(f"Miembro {member_id}, {check['name']}, {_where(station)}")
    lines.append(f"  Estado {check['status']}; numeral {check['clause'] or '-'}")
    if check["demand"] is not None or check["capacity"] is not None:
        ratio = "-" if check["ratio"] is None else f"{check['ratio']:.3f}"
        unit = check["unit"]
        lines.append(f"  Demanda {_number(check['demand'], unit)}; capacidad {_number(check['capacity'], unit)}; razon {ratio}")
    if check["values"]:
        lines.append(f"  Valores: {_values(check['values'])}")
    if check["note"]:
        lines.append(f"  Nota: {check['note']}")
    lines.extend(f"  [{error['code']}] {error['message']}" for error in check["errors"])


def _header(results: dict[str, Any]) -> list[str]:
    software, project = results["software"], results["project"]
    materials = project["materials"]
    return [
        "MEMORIA DE VERIFICACION DE VIGAS DE CONCRETO REFORZADO",
        f"{software['name']} {software['version']} - perfil {project['profile']}",
        _RULE,
        "1. DATOS DEL PROYECTO",
        f"Descripcion: {project['description']}",
        f"Perfil normativo: {project['profile']}",
        f"Nivel sismico declarado: {project['seismic']['level']}",
        f"Justificacion: {project['seismic']['justification']}",
        f"Materiales: f'c = {materials['fc [MPa]']:g} MPa; fy = {materials['fy [MPa]']:g} MPa; "
        f"fyt = {materials['fyt [MPa]']:g} MPa; {_CONCRETE.get(materials['concrete'], materials['concrete'])}",
        f"Resultado global: {results['status']}",
        "",
        "2. SUPUESTOS Y CONVENCIONES",
        *(f"- {line}" for line in _CONVENTIONS),
    ]


def render_memoir(results: dict[str, Any], *, full: bool = False) -> str:
    """Memoria: datos y supuestos, resumen por miembro, lo que no cumple y la estación crítica de cada verificación."""
    if "project" not in results:
        validation = results["validation"]
        lines = ["MEMORIA DE VERIFICACION DE VIGAS DE CONCRETO REFORZADO", _RULE, f"Resultado global: {results['status']}",
                 "La entrada no es valida:", *(f"  [{error['code']}] {error['message']}" for error in validation["errors"])]
        return "\n".join(lines) + "\n"
    lines = _header(results)
    lines += ["", "3. RESUMEN POR MIEMBRO"]
    for member in results["members"]:
        kind = _TYPES.get(member["type"], member["type"])
        lines.append(f"Miembro {member['id']}: {kind}, L = {member['length [mm]']:.0f} mm, {_section(member)}; "
                     f"{len(member['stations'])} estaciones. Estado {member['status']}")
        lines.append(f"  {'Verificacion':<50}{'Estado':<12}{'Razon':>8}  Estacion critica")
        for name, (station, check) in _governing(member).items():
            ratio = "-" if check["ratio"] is None else f"{check['ratio']:.3f}"
            lines.append(f"  {name:<50}{check['status']:<12}{ratio:>8}  {_where(station)}")
    failing = [(member["id"], station, check) for member in results["members"] for station in member["stations"]
               for check in station["checks"] if check["status"] != str(Status.PASS)]
    lines += ["", "4. VERIFICACIONES QUE NO CUMPLEN"]
    if not failing:
        lines.append("Ninguna.")
    for member_id, station, check in failing:
        _detail(lines, member_id, station, check)
    lines += ["", "5. ESTACIONES CRITICAS"]
    for member in results["members"]:
        for station, check in _governing(member).values():
            _detail(lines, member["id"], station, check)
    if full:
        lines += ["", "6. DETALLE DE TODAS LAS ESTACIONES"]
        for member in results["members"]:
            for station in member["stations"]:
                for check in station["checks"]:
                    _detail(lines, member["id"], station, check)
    return "\n".join(lines) + "\n"
