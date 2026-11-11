"""Modelo neutro de la memoria de cálculo (D-068): bloques por elemento, construidos solo a partir del resultado.

Cada elemento (viga o zapata) tiene capítulos fijos; lo que no corresponde dice "No aplica" y lo que el programa no
calcula dice "Falta implementación". El texto (text.py) y el PDF (pdf.py) dibujan los mismos bloques. Vigas y zapatas
comparten la verificación gobernante, el detalle de cada verificación, la tabla de requisitos y los índices DCR; solo
cambia cómo se ubica una verificación (estación de la viga o caso de carga de la zapata).

Bloques: title, summary, h1, h2, table, kv, p, note y alert (diccionarios con "kind").
"""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from structurelab_rc.domain.status import Status
from structurelab_rc.reporting.figures import CORNERS, FIGURE_ASPECT, PRESSURE, corner_key, governing_pressure
from structurelab_rc.reporting.glossary import PROFILE_NAMES, STATUS_TEXT, classify, describe, display, number, unit_of

Block = dict[str, Any]
# Una verificación ubicada: (ubicación en palabras, verificación del resultado).
Located = tuple[str, dict[str, Any]]

_PRECEDENCE = {str(Status.FAIL): 3, str(Status.INCOMPLETE): 2, str(Status.BLOCKED): 1, str(Status.PASS): 0}
_CONCRETE = {"normalweight": "concreto de peso normal", "lightweight": "concreto liviano"}
_COATING = {"uncoated": "sin recubrimiento", "galvanized": "galvanizado (zinc)", "epoxy": "epóxico",
            "zinc_epoxy": "recubrimiento dual de zinc y epóxico"}
_ENDS = {"straight": "rectas", "hook": "con gancho estándar"}
_CHAPTER_TITLES = {
    "requirements": "Revisión de requerimientos técnicos",
    "flexure": "Revisión de capacidad a momento flector",
    "shear": "Revisión de capacidad a fuerza cortante",
    "torsion": "Revisión de capacidad a torsión",
    "geotechnical": "Revisión geotécnica: presión, contacto y estabilidad",
    "one_way": "Revisión de cortante en una dirección",
    "punching": "Revisión de cortante en dos direcciones (punzonamiento)",
    "development": "Revisión de desarrollo y anclaje del refuerzo",
    "bearing": "Revisión de aplastamiento y pasadores",
    "other": "Otras revisiones",
}
_BEAM_CONVENTIONS = (
    "Las fuerzas llegan mayoradas; la aplicación no genera combinaciones (D-003).",
    "Ejes de ETABS: X = eje 3, Y = eje 2 (hacia arriba), Z = eje 1. Mu (M3) positivo comprime la cara superior y M2 "
    "positivo comprime la cara +3 (D-044).",
    "Flexión con Pn = Pu y momentos respecto al centroide bruto (D-024); resistencia biaxial con la sección completa y "
    "deformación neta de tracción en los estados M3, M2 y biaxial (D-046).",
    "d no menor que 0.8h en As,min, cortante y torsión (D-043); en el cortante V3, no menor que 0.8bw (D-047).",
    "La torsión se desprecia si Tu < φTth; si no, se verifica combinada con el cortante (D-037).",
)
_BEAM_LIMITATIONS = (
    "Servicio: la separación por fisuración se verifica (D-081); espesor mínimo y deflexiones, falta implementación "
    "(subfase 2D, D-017, D-039).",
    "Vigas de gran altura (ACI 9.9, NSR-10 C.11.7): falta implementación.",
    "Torsión de compatibilidad (Tu reducido a φTcr) y reducción de Aℓ en la zona comprimida: falta implementación.",
    "Secciones huecas a torsión: no cubiertas.",
    "Requisitos sísmicos de vigas (Fase 3): falta implementación.",
)
_FOOTING_CONVENTIONS = (
    "Las fuerzas de la columna llegan como casos de servicio y mayorados, cada uno con los factores de carga muerta y "
    "viva de su combinación; la aplicación no genera combinaciones (D-052, D-057).",
    "Ejes globales de ETABS con origen en el centroide de la base: X a lo largo de lx, Y a lo largo de ly, Z hacia "
    "arriba. Las fuerzas son las de la columna sobre la zapata, en la base de la columna (D-052, D-055).",
    "Presión del suelo lineal y sin tracción bajo zapata rígida según Bellos y Bakas (2017) (D-053). qa es la presión "
    "admisible bruta: incluye los pesos propios y las sobrecargas (D-056, D-057).",
    "El contacto con el suelo se verifica con los casos de servicio; un caso sin equilibrio es NO CUMPLE (D-052, D-054).",
    "Verificación estructural con la carga neta de cada caso mayorado: flexión en las caras de la columna, cortante a d "
    "de la cara y punzonamiento a d/2 con transferencia de momento en los dos ejes (D-061, D-063).",
    "Desarrollo con ψe según el recubrimiento declarado, ψcc en ganchos y el factor As requerido/As suministrado solo "
    "donde el perfil lo permite con el nivel sísmico declarado; ψr = 1.0 (D-071).",
    "Deslizamiento (fricción, adherencia sobre el área en contacto y pasiva afectada por su factor) y volcamiento con los "
    "casos de servicio y los factores de seguridad declarados por el usuario, sísmicos en los casos marcados (D-070).",
)
_COMBINED_CONVENTIONS = (
    "Zapata combinada rectangular de dos columnas, rígida, con la presión lineal y sin tracción de Bellos y Bakas (2017) "
    "de la resultante de las dos columnas; X es la dirección larga y el origen es el centroide de la base (D-080).",
    "Las fuerzas de cada columna actúan en su eje a la altura h + pedestal: el cortante horizontal produce un momento en "
    "la base, que entra en la presión, en la viga larga y en el punzonamiento.",
    "Viga en la dirección larga revisada con el código de vigas en sus secciones críticas (mayores momentos y a d de las "
    "caras), con Vc y Av,min de cimentación; en una cara de columna el cortante es el de la sección a d (D-081, D-082).",
    "Franja transversal bajo cada columna de ancho columna + d/2 a cada lado, con la carga de la columna repartida en el "
    "ancho con la forma de la presión, revisada también con el código de vigas (D-080, D-082).",
    "Punzonamiento por columna con la carga neta de Bellos dentro del perímetro crítico; el esfuerzo se evalúa en cada "
    "esquina con el cortante directo y el del momento transferido en los dos ejes, y gobierna la mayor (D-083).",
)
_COMBINED_LIMITATIONS = (
    "Torsión por Vy y por columnas desplazadas en Y: falta implementación; en las franjas solo entran por la forma de la "
    "presión (D-080).",
    "Punzonamiento de dos columnas cuyos perímetros críticos se traslapan y franja de una columna con presión nula: falta "
    "implementación (D-082).",
    "Vigas de gran altura (ACI 9.9, NSR-10 C.11.7), otras formas de zapata combinada y más de dos columnas: no cubiertas.",
)
_FOOTING_LIMITATIONS = (
    "Empuje pasivo sobre el pedestal y deslizamiento con suelo bajo nivel freático: no cubiertos (D-070).",
    "Momento negativo sin malla superior como concreto simple solo donde el perfil lo permite con el nivel sísmico; la "
    "excepción de viviendas de una o dos familias de hasta tres pisos no está implementada (D-072).",
    "Aplastamiento del lado de la columna, empalme de los pasadores y tracción en la interfaz: se verificarán con las "
    "columnas (D-059).",
    "Medianeras con viga de amarre, rotadas, escalonadas, losas de cimentación y pilotes: no cubiertas.",
)
_SOURCES = "Los factores φ, las capacidades y los numerales provienen del resultado de cada verificación."


def _severity(check: dict[str, Any]) -> tuple[int, float]:
    return _PRECEDENCE[check["status"]], check["ratio"] if check["ratio"] is not None else -1.0


def governing(items: Iterable[Located]) -> dict[str, Located]:
    """Por verificación, la ubicación más exigida: primero el estado más severo, luego la mayor razón."""
    result: dict[str, Located] = {}
    for where, check in items:
        current = result.get(check["name"])
        if current is None or _severity(check) > _severity(current[1]):
            result[check["name"]] = (where, check)
    return result


def _status_text(status: str) -> str:
    return STATUS_TEXT.get(status, status)


def _quantity(value: float | None, unit: str) -> str:
    shown = unit_of(f"x [{unit}]")[1]
    return f"{number(value, shown)} {shown}".rstrip(" –") if value is not None else "–"


def _title(element: str, results: dict[str, Any], meta: list[tuple[str, str]], items: list[Located], status: str) -> Block:
    project = results["project"]
    ratios = [check["ratio"] for _, check in items if check["ratio"] is not None]
    meta = [("Proyecto", project["description"]), ("Norma", PROFILE_NAMES.get(project["profile"], project["profile"])),
            ("Nivel sísmico declarado", project["seismic"]["level"]), *meta,
            ("Programa", f"{results['software']['name']} {results['software']['version']}")]
    return {"kind": "title", "element": element, "meta": meta, "status": status, "status_text": _status_text(status),
            "ratio": max(ratios) if ratios else None}


def _summary(items: list[Located]) -> Block:
    """La verificación de mayor DCR de cada capítulo de resistencia."""
    lines = []
    by_chapter: dict[str, Located] = {}
    for where, check in items:
        chapter = classify(check["name"])[0]
        if chapter == "requirements" or check["ratio"] is None:
            continue
        current = by_chapter.get(chapter)
        if current is None or _severity(check) > _severity(current[1]):
            by_chapter[chapter] = (where, check)
    for chapter, (where, check) in by_chapter.items():
        lines.append(f"{_CHAPTER_TITLES[chapter].split(': ')[0].replace('Revisión de ', '').capitalize()}: "
                     f"DCR = {check['ratio']:.3f} ({display(check['name'])}, {where})")
    return {"kind": "summary", "items": lines}


def _materials(results: dict[str, Any]) -> list[Block]:
    project = results["project"]
    materials, used = project["materials"], project.get("materials_used", {})
    profile = PROFILE_NAMES.get(project["profile"], project["profile"])
    rows = [["Resistencia especificada del concreto (f'c)", number(materials["fc [MPa]"], "MPa"), "MPa", "Dato del usuario"],
            ["Esfuerzo de fluencia del refuerzo longitudinal (fy)", number(materials["fy [MPa]"], "MPa"), "MPa", "Dato del usuario"],
            ["Esfuerzo de fluencia del refuerzo transversal (fyt)", number(materials["fyt [MPa]"], "MPa"), "MPa", "Dato del usuario"],
            ["Tipo de concreto", _CONCRETE.get(materials["concrete"], materials["concrete"]), "–", "Dato del usuario"],
            ["Recubrimiento de las barras", _COATING.get(materials["coating"], materials["coating"]), "–", "Dato del usuario"]]
    for key, value in used.items():
        name, unit = unit_of(key)
        description, symbol = describe(name)
        rows.append([f"{description} ({symbol})", "–" if value is None else number(value, unit if unit != "–" else "–"),
                     unit, f"Perfil {profile}"])
    return [{"kind": "table", "headers": ["Propiedad", "Valor", "Unidad", "Referencia literal"], "rows": rows}]


def _values_table(check: dict[str, Any]) -> Block | None:
    if not check["values"]:
        return None
    rows = []
    for key, value in check["values"].items():
        name, unit = unit_of(key)
        description, symbol = describe(name)
        rows.append([description, symbol, number(value, unit), unit])
    return {"kind": "table", "headers": ["Parámetro", "Símbolo", "Valor", "Unidad"], "rows": rows}


def _check_detail(number_text: str, where: str, check: dict[str, Any], locations: list[Located] | None) -> list[Block]:
    """Detalle de una verificación en su ubicación gobernante; con locations, la tabla de todas las ubicaciones."""
    _, demand_symbol, capacity_symbol = classify(check["name"])
    blocks: list[Block] = [{"kind": "h2", "text": f"{number_text} {display(check['name'])}; ubicación gobernante: {where}"}]
    table = _values_table(check)
    if table is not None:
        blocks.append(table)
    lines: list[tuple[str, str]] = [("Referencia literal", check["clause"] or "–")]
    unit = check["unit"]
    if check["demand"] is not None or check["capacity"] is not None:
        lines.append((f"Demanda{f' ({demand_symbol})' if demand_symbol else ''}", _quantity(check["demand"], unit)))
        lines.append((f"Capacidad{f' ({capacity_symbol})' if capacity_symbol else ''}", _quantity(check["capacity"], unit)))
    if check["ratio"] is not None:
        shown = unit_of(f"x [{unit}]")[1]
        lines.append(("Verificación", f"{demand_symbol or 'Demanda'} / {capacity_symbol or 'capacidad'} = "
                      f"{number(check['demand'], shown)} / {number(check['capacity'], shown)} = {check['ratio']:.3f}"))
    lines.append(("Resultado", _status_text(check["status"])))
    blocks.append({"kind": "kv", "items": lines})
    if check["note"]:
        blocks.append({"kind": "note", "text": check["note"]})
    blocks.extend({"kind": "alert", "text": f"[{error['code']}] {error['message']}"} for error in check["errors"])
    if locations:
        rows = [[place, _status_text(item["status"]), _quantity(item["demand"], item["unit"]),
                 _quantity(item["capacity"], item["unit"]), "–" if item["ratio"] is None else f"{item['ratio']:.3f}"]
                for place, item in locations]
        blocks.append({"kind": "table", "headers": ["Ubicación", "Resultado", "Demanda", "Capacidad", "DCR"], "rows": rows})
    return blocks


def _requirements(items: list[Located]) -> list[Block]:
    rows = []
    for name, (where, check) in governing(items).items():
        if classify(name)[0] != "requirements":
            continue
        rows.append([display(name), where, _quantity(check["demand"], check["unit"]), _quantity(check["capacity"], check["unit"]),
                     check["clause"] or "–", _status_text(check["status"])])
    if not rows:
        return [{"kind": "p", "text": "No aplica: ningún requisito para este elemento."}]
    blocks: list[Block] = [{"kind": "table", "headers": ["Requisito", "Ubicación gobernante", "Exigido", "Suministrado",
                                                          "Referencia literal", "Resultado"], "rows": rows}]
    for name, (_, check) in governing(items).items():
        if classify(name)[0] == "requirements":
            blocks.extend({"kind": "alert", "text": f"{display(name)}: [{error['code']}] {error['message']}"}
                          for error in check["errors"])
    return blocks


def _chapter(chapter: str, number_text: str, items: list[Located], full: bool) -> list[Block]:
    selected = {name: located for name, located in governing(items).items() if classify(name)[0] == chapter}
    if not selected:
        return [{"kind": "p", "text": "No aplica: ninguna verificación de este tipo en el elemento."}]
    blocks: list[Block] = []
    for index, (name, (where, check)) in enumerate(selected.items(), start=1):
        locations = [item for item in items if item[1]["name"] == name] if full else None
        blocks.extend(_check_detail(f"{number_text}.{index}", where, check, locations))
    return blocks


def _dcr(items: list[Located]) -> list[Block]:
    rows = [[display(name), _CHAPTER_TITLES[classify(name)[0]].replace("Revisión de ", "").capitalize(), where,
             _quantity(check["demand"], check["unit"]), _quantity(check["capacity"], check["unit"]),
             "–" if check["ratio"] is None else f"{check['ratio']:.3f}", _status_text(check["status"])]
            for name, (where, check) in governing(items).items()]
    return [{"kind": "table", "headers": ["Revisión", "Capítulo", "Ubicación gobernante", "Demanda", "Capacidad", "DCR",
                                          "Resultado"], "rows": rows}]


def _notes(results: dict[str, Any], conventions: tuple[str, ...], limitations: tuple[str, ...]) -> list[Block]:
    project = results["project"]
    return [{"kind": "p", "text": f"Justificación del nivel sísmico: {project['seismic']['justification']}"},
            *({"kind": "note", "text": text} for text in (*conventions, _SOURCES)),
            {"kind": "p", "text": "Limitaciones:"},
            *({"kind": "note", "text": text} for text in limitations)]


def _assemble(head: list[Block], chapters: list[tuple[str, Callable[[str], list[Block]]]]) -> list[Block]:
    blocks = list(head)
    for index, (title, build) in enumerate(chapters, start=1):
        blocks.append({"kind": "h1", "text": f"{index}. {title}"})
        blocks.extend(build(str(index)))
    return blocks


def _layers(layout: dict[str, Any]) -> str:
    parts = []
    for layer in layout["layers"]:
        bars = layer["bars"]
        if isinstance(bars, dict):
            text = f"{bars['designation']} c/{bars['spacing']:.0f} mm"
        else:
            text = " ".join(bar if isinstance(bar, str) else bar["designation"] for bar in bars)
        role = "torsión" if layer["role"] == "torsion" else "flexión"
        parts.append(f"{layer['depth']:.0f} mm: {text} ({role})")
    return "; ".join(parts)


def _stirrups(layout: dict[str, Any]) -> str:
    stirrups = layout["stirrups"]
    if stirrups is None:
        return "sin estribos"
    closed = "cerrados" if stirrups["closed"] else "abiertos"
    return f"{stirrups['designation']} de {stirrups['legs']} ramas c/{stirrups['spacing']:.0f} mm, {closed}"


def _beam_geometry(member: dict[str, Any]) -> list[Block]:
    section = member["section"]
    names = {"bw": "Ancho del alma (bw)", "h": "Altura total (h)", "cover": "Recubrimiento libre a los estribos",
             "hf": "Espesor del ala (hf)", "overhang_x_neg": "Saliente del ala hacia −3", "overhang_x_pos": "Saliente del ala hacia +3"}
    rows = [["Longitud del miembro (L)", number(member["length [mm]"], "mm"), "mm", "Dato del usuario"]]
    rows += [[label, number(section[key], "mm"), "mm", "Dato del usuario"] for key, label in names.items() if key in section]
    reinforcement = [[f"{station['z [mm]']:.0f}", station["case"] or "–", _layers(station["layout"]), _stirrups(station["layout"])]
                     for station in member["stations"]]
    return [{"kind": "table", "headers": ["Propiedad", "Valor", "Unidad", "Fuente"], "rows": rows},
            {"kind": "p", "text": "Armado por estación (profundidad de cada capa desde la fibra superior):"},
            {"kind": "table", "headers": ["z (mm)", "Caso", "Capas longitudinales", "Estribos"], "rows": reinforcement}]


def _beam_demands(member: dict[str, Any]) -> list[Block]:
    keys = ("Pu [kN]", "Mu [kN-m]", "M2 [kN-m]", "Vu [kN]", "V3 [kN]", "Tu [kN-m]")
    rows = [[f"{station['z [mm]']:.0f}", station["case"] or "–",
             *(number(station["demands"].get(key), unit_of(key)[1]) for key in keys)] for station in member["stations"]]
    headers = ["z (mm)", "Caso", *(f"{unit_of(key)[0]} ({unit_of(key)[1]})" for key in keys)]
    return [{"kind": "p", "text": "Fuerzas mayoradas; Pu > 0 en compresión."}, {"kind": "table", "headers": headers, "rows": rows}]


def beam_document(results: dict[str, Any], member: dict[str, Any], full: bool) -> list[Block]:
    items: list[Located] = [(f"z = {station['z [mm]']:.0f} mm, caso {station['case'] or '–'}", check)
                            for station in member["stations"] for check in station["checks"]]
    head = [_title(f"Viga {member['id']}", results, [("Estaciones", str(len(member["stations"])))], items, member["status"]),
            _summary(items)]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda _: _materials(results)),
        ("Propiedades geométricas y armado", lambda _: _beam_geometry(member)),
        ("Solicitaciones", lambda _: _beam_demands(member)),
        (_CHAPTER_TITLES["requirements"], lambda _: _requirements(items)),
        ("Revisión de condiciones de servicio",
         lambda _: [{"kind": "p", "text": "Falta implementación: fisuración, espesor mínimo y deflexiones (subfase 2D)."}]),
        (_CHAPTER_TITLES["flexure"], lambda n: _chapter("flexure", n, items, full)),
        (_CHAPTER_TITLES["shear"], lambda n: _chapter("shear", n, items, full)),
        (_CHAPTER_TITLES["torsion"], lambda n: _chapter("torsion", n, items, full)),
        ("Índices DCR", lambda _: _dcr(items)),
        ("Notas y limitaciones", lambda _: _notes(results, _BEAM_CONVENTIONS, _BEAM_LIMITATIONS)),
    ]
    return _assemble(head, chapters)


def _mat_text(mat: dict[str, Any] | None) -> str:
    if mat is None:
        return "no hay"
    sets = "; ".join(
        f"barras {direction} {mat[direction]['designation']} c/{mat[direction]['spacing']:.0f} mm"
        + (f" (franja central c/{mat[direction]['band_spacing']:.0f} mm)" if mat[direction].get("band_spacing") else "")
        for direction in ("x", "y"))
    return f"{sets}; primero {mat['first']}; barras {_ENDS[mat['end']]}"


def _soil_rows(results: dict[str, Any]) -> list[list[str]]:
    soil = results["soil"]
    return [["Presión admisible bruta (qa)", number(soil["qa [kPa]"], "kPa"), "kPa"],
            ["Factor de aumento de qa en combinaciones con sismo", number(soil["factor sismo qa [-]"], "–"), "–"],
            ["Fracción mínima de contacto", number(soil["contacto minimo [-]"], "–"), "–"],
            ["Peso unitario del concreto (γc)", number(soil["gamma concreto [kN/m3]"], "kN/m³"), "kN/m³"],
            ["Peso unitario del relleno (γf)", number(soil["gamma relleno [kN/m3]"], "kN/m³"), "kN/m³"],
            ["Coeficiente de fricción suelo–zapata (μ)", number(soil["mu [-]"], "–"), "–"],
            ["Adherencia suelo–zapata (ca)", number(soil["ca [kPa]"], "kPa"), "kPa"],
            ["Coeficiente de empuje pasivo (Kp)", number(soil["Kp [-]"], "–"), "–"],
            ["Cohesión del suelo (c)", number(soil["c [kPa]"], "kPa"), "kPa"],
            ["Factor del empuje pasivo (fp)", number(soil["fp [-]"], "–"), "–"],
            ["FS mínimo al deslizamiento: sin sismo / con sismo",
             f"{number(soil['FS deslizamiento [-]'], '–')} / {number(soil['FS deslizamiento sismo [-]'], '–')}", "–"],
            ["FS mínimo al volcamiento: sin sismo / con sismo",
             f"{number(soil['FS volcamiento [-]'], '–')} / {number(soil['FS volcamiento sismo [-]'], '–')}", "–"]]


def _properties_rows(footing: dict[str, Any]) -> list[list[str]]:
    rows = []
    for key, value in footing["properties"].items():
        name, unit = unit_of(key)
        description, symbol = describe(name)
        rows.append([f"{description} ({symbol})", number(value, unit), unit])
    return rows


def _footing_geometry(results: dict[str, Any], footing: dict[str, Any]) -> list[Block]:
    g = footing["geometry [mm]"]
    column = g["column"]
    rows = [["Largo a lo largo de X (lx)", number(g["lx"], "mm"), "mm"], ["Ancho a lo largo de Y (ly)", number(g["ly"], "mm"), "mm"],
            ["Espesor (h)", number(g["h"], "mm"), "mm"], ["Recubrimiento libre de las mallas", number(g["cover"], "mm"), "mm"],
            ["Columna a lo largo de X (cx)", number(column["cx"], "mm"), "mm"],
            ["Columna a lo largo de Y (cy)", number(column["cy"], "mm"), "mm"],
            ["Desplazamiento de la columna en X", number(column["offset_x"], "mm"), "mm"],
            ["Desplazamiento de la columna en Y", number(column["offset_y"], "mm"), "mm"],
            ["Altura del pedestal", number(g["pedestal_height"], "mm"), "mm"], ["Altura del relleno", number(g["fill_height"], "mm"), "mm"],
            ["Sobrecarga muerta (qD)", number(g["surcharge_dead [kN/m2]"], "kN/m²"), "kN/m²"],
            ["Sobrecarga viva (qL)", number(g["surcharge_live [kN/m2]"], "kN/m²"), "kN/m²"]]
    soil_rows = _soil_rows(results)
    properties = _properties_rows(footing)
    dowels = column.get("dowels")
    reinforcement = [["Malla inferior", _mat_text(footing["reinforcement"]["bottom"])],
                     ["Malla superior", _mat_text(footing["reinforcement"]["top"])],
                     ["Pasadores", f"{dowels['count']} {dowels['designation']}" if dowels else "no declarados"]]
    return [{"kind": "table", "headers": ["Dimensión (dato del usuario)", "Valor", "Unidad"], "rows": rows},
            {"kind": "table", "headers": ["Suelo y pesos (dato del usuario)", "Valor", "Unidad"], "rows": soil_rows},
            {"kind": "p", "text": "Propiedades calculadas a partir de las dimensiones (nunca declaradas):"},
            {"kind": "table", "headers": ["Propiedad", "Valor", "Unidad"], "rows": properties},
            {"kind": "table", "headers": ["Refuerzo", "Descripción"], "rows": reinforcement}]


def _soil_pressures(footing: dict[str, Any], figure: Path | None) -> list[Block]:
    """Presión del suelo en las esquinas (D-080): la planta del caso de servicio que gobierna la presión admisible y la
    tabla de las esquinas de todos los casos de servicio."""
    checks = [check for check in footing["checks"] if check["name"] == PRESSURE and corner_key("-x-y") in check["values"]]
    if not checks:
        return []
    blocks: list[Block] = [{"kind": "h2", "text": "Presión del suelo en las esquinas (casos de servicio)"}]
    governing = governing_pressure(footing["checks"])
    if figure is not None and governing is not None:
        blocks.append({"kind": "image", "path": str(figure), "aspect": FIGURE_ASPECT,
                       "caption": f"Presión del suelo en planta, caso que gobierna {governing['case']}"})
    rows = [[check["case"], *(number(check["values"][corner_key(name)], "kPa") for name, _, _ in CORNERS)] for check in checks]
    blocks.append({"kind": "table", "headers": ["Caso", "p (−x, −y) kPa", "p (+x, −y) kPa", "p (+x, +y) kPa", "p (−x, +y) kPa"],
                   "rows": rows})
    blocks.append({"kind": "note", "text": "Presión bruta de Bellos y Bakas (2017) con los factores del caso; 0 indica una esquina "
                                           "sin contacto con el suelo."})
    return blocks


_LOAD_KEYS = ("P [kN]", "Vx [kN]", "Vy [kN]", "Mx [kN-m]", "My [kN-m]")


def _loads_table(loads: list[dict[str, Any]], column: str | None = None) -> Block:
    rows = [[*([column] if column else []), load["case"], f"{load['dead_factor']:.2f}", f"{load['live_factor']:.2f}",
             "sí" if load["seismic"] else "no", *(number(load[key], unit_of(key)[1]) for key in _LOAD_KEYS)] for load in loads]
    headers = [*(["Columna"] if column else []), "Caso", "Factor D", "Factor L", "Sismo",
               *(f"{unit_of(key)[0]} ({unit_of(key)[1]})" for key in _LOAD_KEYS)]
    return {"kind": "table", "headers": headers, "rows": rows}


def _footing_demands(footing: dict[str, Any], figure: Path | None = None) -> list[Block]:
    blocks: list[Block] = [{"kind": "p", "text": "Fuerzas de la columna sobre la zapata, en la base de la columna; P > 0 en compresión."}]
    for kind, title in (("service", "Casos de servicio"), ("factored", "Casos mayorados")):
        loads = [load for load in footing["loads"] if load["kind"] == kind]
        blocks.append({"kind": "h2", "text": title})
        if not loads:
            blocks.append({"kind": "p", "text": "No aplica: ningún caso de este tipo."})
            continue
        blocks.append(_loads_table(loads))
    return blocks + _soil_pressures(footing, figure)


def _punching_corners(items: list[Located]) -> list[Block]:
    """Esfuerzo de punzonamiento en cada esquina del perímetro crítico, por caso (y columna): cortante directo más el del
    momento transferido en los dos ejes; gobierna la mayor (D-083)."""
    rows = []
    for where, check in items:
        if check["name"] != "Punzonamiento":
            continue
        values = check["values"]
        stresses = [values[key] for key in values if key.startswith("esquina ") and key.split(" ")[2] == "v"]
        if not stresses:
            continue
        top = max(stresses)
        index = 1
        while f"esquina {index} v [MPa]" in values:
            stress = values[f"esquina {index} v [MPa]"]
            x, y = values[f"esquina {index} x [mm]"], values[f"esquina {index} y [mm]"]
            rows.append([where, str(index), number(x, "mm"), number(y, "mm"),
                         f"{stress:.3f}", "gobierna" if stress == top else ""])
            index += 1
    if not rows:
        return []
    return [{"kind": "h2", "text": "Esfuerzos de punzonamiento en las esquinas del perímetro crítico"},
            {"kind": "table", "headers": ["Ubicación", "Esquina", "x (mm)", "y (mm)", "vu (MPa)", ""], "rows": rows},
            {"kind": "note", "text": "Coordenadas respecto al centroide de la base. vu = Vu/(b0·d) + γv,x·Msc,x·(x − xc)/Jc,x + "
                                     "γv,y·Msc,y·(y − yc)/Jc,y, con la carga neta de Bellos dentro del área crítica."}]


def footing_document(results: dict[str, Any], footing: dict[str, Any], full: bool, figure: Path | None = None) -> list[Block]:
    items: list[Located] = [(f"caso {check['case']}" if check.get("case") else "toda la zapata", check) for check in footing["checks"]]
    counts = {kind: sum(1 for load in footing["loads"] if load["kind"] == kind) for kind in ("service", "factored")}
    meta = [("Casos de carga", f"{counts['service']} de servicio y {counts['factored']} mayorados")]
    head = [_title(f"Zapata {footing['id']}", results, meta, items, footing["status"]), _summary(items)]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda _: _materials(results)),
        ("Propiedades geométricas, suelo y armado", lambda _: _footing_geometry(results, footing)),
        ("Solicitaciones", lambda _: _footing_demands(footing, figure)),
        (_CHAPTER_TITLES["geotechnical"], lambda n: _chapter("geotechnical", n, items, full)),
        (_CHAPTER_TITLES["requirements"], lambda _: _requirements(items)),
        (_CHAPTER_TITLES["flexure"], lambda n: _chapter("flexure", n, items, full)),
        (_CHAPTER_TITLES["one_way"], lambda n: _chapter("one_way", n, items, full)),
        (_CHAPTER_TITLES["punching"], lambda n: [*_chapter("punching", n, items, full), *_punching_corners(items)]),
        (_CHAPTER_TITLES["development"], lambda n: _chapter("development", n, items, full)),
        (_CHAPTER_TITLES["bearing"], lambda n: _chapter("bearing", n, items, full)),
        ("Índices DCR", lambda _: _dcr(items)),
        ("Notas y limitaciones", lambda _: _notes(results, _FOOTING_CONVENTIONS, _FOOTING_LIMITATIONS)),
    ]
    return _assemble(head, chapters)


def _combined_where(check: dict[str, Any]) -> str:
    """Ubicación de una verificación de la zapata combinada: el caso y la viga larga (z y sección), la franja o la columna."""
    case = f"caso {check['case']}" if check.get("case") else "toda la zapata"
    note = check["note"].split(":")[0].split(";")[0]
    z = check.get("z [mm]")
    if note.startswith("Franja"):
        return f"{case}, {note}" + (f" (z = {z:.0f} mm desde −Y)" if z is not None else "")
    if note.startswith("Columna"):
        return f"{case}, {note}"
    if z is not None:
        return f"{case}, viga larga en z = {z:.0f} mm desde −X ({note[:1].lower() + note[1:]})"
    return case


def _bar_text(bars: dict[str, Any] | None, extra: str = "") -> str:
    if bars is None:
        return "no hay"
    return f"{bars['designation']} c/{bars['spacing']:.0f} mm{extra}"


def _combined_geometry(results: dict[str, Any], footing: dict[str, Any]) -> list[Block]:
    g = footing["geometry [mm]"]
    rows = [["Largo a lo largo de X (lx)", number(g["lx"], "mm"), "mm"], ["Ancho a lo largo de Y (ly)", number(g["ly"], "mm"), "mm"],
            ["Espesor (h)", number(g["h"], "mm"), "mm"], ["Recubrimiento libre", number(g["cover"], "mm"), "mm"],
            ["Altura de los pedestales", number(g["pedestal_height"], "mm"), "mm"],
            ["Altura del relleno", number(g["fill_height"], "mm"), "mm"],
            ["Sobrecarga muerta (qD)", number(g["surcharge_dead [kN/m2]"], "kN/m²"), "kN/m²"],
            ["Sobrecarga viva (qL)", number(g["surcharge_live [kN/m2]"], "kN/m²"), "kN/m²"]]
    columns = [[column["id"], number(column["cx"], "mm"), number(column["cy"], "mm"), number(column["x"], "mm"), number(column["y"], "mm"),
                f"{column['dowels']['count']} {column['dowels']['designation']}" if column.get("dowels") else "no declarados",
                _bar_text(column.get("band"))] for column in footing["columns"]]
    reinforcement = footing["reinforcement"]
    top = reinforcement.get("top")
    stirrups = reinforcement.get("stirrups")
    skin = reinforcement.get("skin")
    bars = [["Malla inferior", _mat_text(reinforcement["bottom"])],
            ["Barras superiores x", _bar_text(top, f"; barras {_ENDS[top['end']]}" if top else "")],
            ["Estribos de la viga larga", "no hay" if stirrups is None else
             f"{stirrups['legs']} ramas {stirrups['designation']} c/{stirrups['spacing']:.0f} mm"],
            ["Refuerzo superficial (caras largas)", _bar_text(skin, " en vertical" if skin else "")]]
    return [{"kind": "table", "headers": ["Dimensión (dato del usuario)", "Valor", "Unidad"], "rows": rows},
            {"kind": "table",
             "headers": ["Columna", "cx (mm)", "cy (mm)", "x (mm)", "y (mm)", "Pasadores", "Refuerzo bajo la columna (band)"],
             "rows": columns},
            {"kind": "note", "text": "x e y ubican el eje de cada columna respecto al centroide de la base."},
            {"kind": "table", "headers": ["Suelo y pesos (dato del usuario)", "Valor", "Unidad"], "rows": _soil_rows(results)},
            {"kind": "p", "text": "Propiedades calculadas a partir de las dimensiones (nunca declaradas):"},
            {"kind": "table", "headers": ["Propiedad", "Valor", "Unidad"], "rows": _properties_rows(footing)},
            {"kind": "table", "headers": ["Refuerzo", "Descripción"], "rows": bars}]


def _combined_demands(footing: dict[str, Any], figure: Path | None) -> list[Block]:
    blocks: list[Block] = [{"kind": "p", "text": "Fuerzas de cada columna sobre la zapata, en la base de la columna; P > 0 en compresión."}]
    for kind, title in (("service", "Casos de servicio"), ("factored", "Casos mayorados")):
        blocks.append({"kind": "h2", "text": title})
        tables = [_loads_table([load for load in column["loads"] if load["kind"] == kind], column["id"]) for column in footing["columns"]]
        rows = [row for table in tables for row in table["rows"]]
        if not rows:
            blocks.append({"kind": "p", "text": "No aplica: ningún caso de este tipo."})
            continue
        blocks.append({**tables[0], "rows": rows})
    return blocks + _soil_pressures(footing, figure)


def combined_document(results: dict[str, Any], footing: dict[str, Any], full: bool, figure: Path | None = None) -> list[Block]:
    """Memoria de una zapata combinada (D-080 a D-083): la viga larga y las franjas transversales con las verificaciones de
    vigas, el punzonamiento con los esfuerzos de cada esquina, el desarrollo, el aplastamiento y los pasadores."""
    items: list[Located] = [(_combined_where(check), check) for check in footing["checks"]]
    strips = [item for item in items if item[1]["note"].startswith("Franja")]
    beam = [item for item in items if item[1].get("z [mm]") is not None and not item[1]["note"].startswith("Franja")]
    others = [item for item in items if item not in strips and item not in beam]
    counts = {kind: sum(1 for load in footing["columns"][0]["loads"] if load["kind"] == kind) for kind in ("service", "factored")}
    meta = [("Columnas", " y ".join(column["id"] for column in footing["columns"])),
            ("Casos de carga", f"{counts['service']} de servicio y {counts['factored']} mayorados")]
    head = [_title(f"Zapata combinada {footing['id']}", results, meta, items, footing["status"]), _summary(items)]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda _: _materials(results)),
        ("Propiedades geométricas, columnas, suelo y armado", lambda _: _combined_geometry(results, footing)),
        ("Solicitaciones", lambda _: _combined_demands(footing, figure)),
        (_CHAPTER_TITLES["geotechnical"], lambda n: _chapter("geotechnical", n, others, full)),
        (_CHAPTER_TITLES["requirements"], lambda _: _requirements(items)),
        ("Viga en la dirección larga: momento flector", lambda n: _chapter("flexure", n, beam, full)),
        ("Viga en la dirección larga: fuerza cortante", lambda n: _chapter("shear", n, beam, full)),
        ("Franjas transversales: momento flector", lambda n: _chapter("flexure", n, strips, full)),
        ("Franjas transversales: fuerza cortante", lambda n: _chapter("shear", n, strips, full)),
        (_CHAPTER_TITLES["punching"], lambda n: [*_chapter("punching", n, others, full), *_punching_corners(others)]),
        (_CHAPTER_TITLES["development"], lambda n: _chapter("development", n, others, full)),
        (_CHAPTER_TITLES["bearing"], lambda n: _chapter("bearing", n, others, full)),
        ("Índices DCR", lambda _: _dcr(items)),
        ("Notas y limitaciones", lambda _: _notes(results, _COMBINED_CONVENTIONS, _COMBINED_LIMITATIONS)),
    ]
    return _assemble(head, chapters)


def report_documents(results: dict[str, Any], *, full: bool = False, figures: dict[str, Path] | None = None) -> list[list[Block]]:
    """Una memoria por elemento (vigas y luego zapatas); con la entrada inválida, una memoria corta de validación."""
    if "project" not in results:
        validation = results["validation"]
        return [[{"kind": "title", "element": "Validación de entrada", "meta": [], "status": results["status"],
                  "status_text": _status_text(results["status"]), "ratio": None},
                 {"kind": "p", "text": "La entrada no es válida:"},
                 *({"kind": "alert", "text": f"[{error['code']}] {error['message']}"} for error in validation["errors"])]]
    documents = [beam_document(results, member, full) for member in results["members"]]
    documents += [footing_document(results, footing, full, (figures or {}).get(footing["id"]))
                  for footing in results.get("footings", [])]
    documents += [combined_document(results, footing, full, (figures or {}).get(footing["id"]))
                  for footing in results.get("combined_footings", [])]
    return documents
