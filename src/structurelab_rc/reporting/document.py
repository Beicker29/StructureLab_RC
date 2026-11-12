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

from structurelab_rc.domain.footing.service import CONTACT
from structurelab_rc.domain.status import Status
from structurelab_rc.reporting.figures import (
    CORNERS,
    DIAGRAM_ASPECT,
    PRESSURE,
    QUANTITIES,
    corner_key,
    governing_pressure,
    pressure_aspect,
)
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
    "La torsión se desprecia si Tu < φTth; si no, se verifica combinada con el cortante (D-037). Las barras de piel "
    "cuentan como Aℓ y las de torsión en las caras laterales como piel (D-090).",
    "Viga de gran altura: la declara el usuario (deep_beam); se verifican el límite de sección, el refuerzo distribuido "
    "transversal y longitudinal, su separación y las cortinas donde el perfil las pide (D-089).",
)
_BEAM_LIMITATIONS = (
    "Servicio: la separación por fisuración se verifica (D-081); espesor mínimo y deflexiones, falta implementación "
    "(subfase 2D, D-017, D-039).",
    "Vigas de gran altura: la resistencia por análisis no lineal o puntal-tensor (ACI 9.9.1.2 y capítulo 23, NSR-10 "
    "C.11.7.2 y Apéndice C-A), el desarrollo en los apoyos simples (ACI 9.9.4.5 y 9.9.4.6, NSR-10 C.12.10.6) y el pandeo "
    "lateral (NSR-10 C.10.7.2) no se verifican (D-089).",
    "Torsión de compatibilidad (Tu reducido a φTcr) y reducción de Aℓ en la zona comprimida: falta implementación.",
    "Torsión: la prolongación (bt + d) del refuerzo, el desarrollo de Aℓ en los extremos y el gancho de 135° de los "
    "estribos cerrados no se verifican (D-088).",
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
    "Transferencia de momento por flexión (ACI 8.4.2.2, NSR-10 C.11.11.7.1 y C.13.5.3): γf·Msc frente a la malla inferior "
    "dentro de bslab; no se suma al momento de la zapata y su parte negativa la debe tomar la viga de cimentación (D-087).",
    "Desarrollo con ψe según el recubrimiento declarado, ψcc en ganchos y el factor As requerido/As suministrado solo "
    "donde el perfil lo permite con el nivel sísmico declarado; ψr = 1.0 (D-071).",
    "Deslizamiento (fricción, adherencia sobre el área en contacto y pasiva afectada por su factor) y volcamiento con los "
    "casos de servicio y los factores de seguridad declarados por el usuario, sísmicos en los casos marcados (D-070).",
)
_COMBINED_CONVENTIONS = (
    "Zapata combinada rectangular de dos columnas, rígida, con la presión lineal y sin tracción de Bellos y Bakas (2017) "
    "de la resultante de las dos columnas (D-080). Dirección principal: la de la viga que une las columnas; secundaria: "
    "la transversal. Ejes globales declarados, con el origen en el centroide de la base (D-094, D-101).",
    "Las fuerzas de cada columna actúan en su eje a la altura h + pedestal: el cortante horizontal produce un momento en "
    "la base, que entra en la presión, en la viga de la dirección principal y en el punzonamiento.",
    "Viga de la dirección principal revisada con el código de vigas en sus secciones críticas (mayores momentos y a d de "
    "las caras), con Vc y Av,min de cimentación; en una cara de columna el cortante es el de la sección a d (D-081, D-082).",
    "Torsión T(x) por equilibrio: el momento estático de cada columna respecto al eje de la viga (F·y − Mx + H·Vy) menos "
    "el de la carga neta del suelo (D-088). En la combinada rectangular es torsión de placa (Wood-Armer, decisión del "
    "usuario, D-118): mxy = T/B uniforme en el ancho; las barras x se revisan con máx(M + |T|, 0) abajo y mín(M − |T|, 0) "
    "arriba; las franjas con su momento ± b·|mxy|, y las barras y fuera de las franjas con ±|mxy| por metro. En la T "
    "invertida, el alma se revisa con la torsión de vigas (Tu a d de la cara, combinada con el cortante).",
    "T invertida (beam): la viga es una T volteada con el ala de viga aislada (≤ 4bw y solo si h ≥ 0.5bw, ACI "
    "6.3.2.2, NSR-10 C.8.12.4), las barras inferiores de la dirección principal dentro del ala y As,min con el ala a "
    "tracción por ser isostática; "
    "las aletas son voladizos por metro desde la cara de la viga; sin punzonamiento, franjas ni transferencia γf·Msc: la "
    "carga de la columna la toma la viga (D-093).",
    "Franja transversal (dirección secundaria) bajo cada columna de ancho columna + d/2 a cada lado, con la carga neta de "
    "la columna repartida en el ancho con la forma de la presión, revisada también con el código de vigas (D-080, D-082, "
    "D-095); el par de la columna que la franja no equilibra lo lleva la zapata como torsión (de placa en la combinada "
    "rectangular, D-118) y la fuerza horizontal transversal como fuerza axial de la franja se desprecia (D-088).",
    "Punzonamiento por columna con la carga neta de Bellos dentro del perímetro crítico; el esfuerzo se evalúa en cada "
    "esquina con el cortante directo y el del momento transferido en los dos ejes, y gobierna la mayor (D-083).",
    "Acero mínimo por punzonamiento (ACI 8.6.1.2) aplicado a la zapata combinada por criterio del usuario, aunque 13.3.2.1 "
    "la remite a los capítulos 7 y 9 (D-087).",
    "Transferencia de momento por flexión (ACI 8.4.2.2, NSR-10 C.11.11.7.1 y C.13.5.3): γf·Msc frente a la malla inferior "
    "dentro de bslab; no se suma al momento de la zapata y su parte negativa la debe tomar la viga de cimentación (D-087).",
)
_COMBINED_LIMITATIONS = (
    "El pedestal no aporta empuje pasivo: el pasivo solo actúa sobre el espesor de la zapata (decisión del usuario, "
    "D-092).",
    "Nivel freático: falta implementación; la presión, el contacto, el deslizamiento y el volcamiento se calculan sin agua "
    "(sin subpresión ni pesos sumergidos) (D-092).",
    "Torsión de placa con mxy = T/B uniforme en el ancho (conservador: no cuenta con el cortante de borde de Kirchhoff) "
    "y Wood-Armer desacoplado (my = 0 para las barras x, mx = 0 para las y), que cumple su criterio (D-118).",
    "T invertida, torsión del alma: la de compatibilidad (Tu reducido a φTcr), la reducción de Aℓ en la zona comprimida, "
    "la prolongación (bt + d) del refuerzo, el desarrollo de Aℓ en los extremos y el gancho de 135° de los estribos "
    "cerrados no se verifican (D-088).",
    "Si los perímetros de punzonamiento de las dos columnas se traslapan, se revisa además el perímetro común (D-086). Si "
    "la presión es nula en la línea de una columna, su franja usa la presión integrada en su ancho o, sin ella, la carga "
    "uniforme (D-085).",
    "Revisión en una dirección (ACI 13.3.2); el comportamiento en dos direcciones (13.3.4) no está implementado y se avisa "
    "cuando B ≥ ℓn, la luz libre entre las caras de las columnas (D-091).",
    "Viga de la dirección principal de gran altura (deep_beam): la resistencia por análisis no lineal o puntal-tensor no "
    "se verifica (D-089). Otras formas de zapata combinada y más de dos columnas: no cubiertas.",
)
_FOOTING_LIMITATIONS = (
    "El pedestal no aporta empuje pasivo: el pasivo solo actúa sobre el espesor de la zapata (decisión del usuario, "
    "D-092).",
    "Nivel freático: falta implementación; la presión, el contacto, el deslizamiento y el volcamiento se calculan sin agua "
    "(sin subpresión ni pesos sumergidos) (D-092).",
    "Momento negativo sin malla superior como concreto simple solo donde el perfil lo permite con el nivel sísmico; la "
    "excepción de viviendas de una o dos familias de hasta tres pisos no se aplica en este repositorio (D-072, D-092).",
    "Aplastamiento del lado de la columna, empalme de los pasadores y tracción en la interfaz: se verificarán con las "
    "columnas (D-059).",
    "Medianeras con viga de amarre, rotadas, escalonadas, losas de cimentación y pilotes: no cubiertas.",
)
_SOURCES = "Los factores φ, las capacidades y los numerales provienen del resultado de cada verificación."


def _severity(check: dict[str, Any]) -> tuple[int, float, float]:
    """Estado, razón y, entre las que no tienen razón (por ejemplo un concreto simple no permitido), la mayor demanda."""
    return (_PRECEDENCE[check["status"]], check["ratio"] if check["ratio"] is not None else -1.0,
            abs(check["demand"]) if check["ratio"] is None and check.get("demand") is not None else 0.0)


def governing(items: Iterable[Located]) -> dict[str, Located]:
    """Por verificación, la ubicación más exigida: primero el estado más severo, luego la mayor razón."""
    return _governing_by(items, lambda item: item[1]["name"])


def _governing_by(items: Iterable[Located], key: Callable[[Located], str]) -> dict[str, Located]:
    """Por clave, la ubicación más exigida: primero el estado más severo, luego la mayor razón."""
    result: dict[str, Located] = {}
    for item in items:
        name = key(item)
        current = result.get(name)
        if current is None or _severity(item[1]) > _severity(current[1]):
            result[name] = item
    return result


def _combined_label(item: Located) -> str:
    """Fila del índice DCR de la zapata combinada (D-119): la verificación, su dirección (principal; secundaria en las
    franjas, fuera de ellas o en las aletas) y el signo del momento de su sección, si lo tiene."""
    check = item[1]
    note = check["note"] or ""
    named = display(check["name"])
    if classify(check["name"])[0] in ("development", "bearing", "punching", "geotechnical"):
        return named  # su nombre ya dice la barra, la columna o el caso
    if note.startswith("Franja"):
        where = " dirección secundaria (franjas)"
    elif note.startswith("Fuera de las franjas"):
        where = " dirección secundaria (fuera de las franjas)"
    elif note.startswith("Aleta"):
        where = " dirección secundaria (aletas)"
    elif check.get("z [mm]") is not None:
        where = " dirección principal"
    else:
        where = ""
    sign = next((f" {text}" for text in ("momento positivo", "momento negativo") if text in note), "")
    if not sign and "concreto simple" in check["name"]:
        sign = " momento negativo"
    # Si el nombre ya trae la dirección (p. ej. "Dirección secundaria: …"), no se repite.
    repeated = bool(where) and where.strip().split(" (")[0].lower() in named.lower()
    return named + ("" if repeated else where) + sign


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


_CONCRETE_KEYS = ("beta1", "ecu", "alpha1", "lambda")  # valores del perfil propios del concreto; el resto, del acero


def _material_rows(results: dict[str, Any]) -> tuple[list[list[str]], list[list[str]]]:
    """Filas del concreto y del acero de refuerzo: los datos del usuario y los valores del perfil que usa el cálculo."""
    project = results["project"]
    materials, used = project["materials"], project.get("materials_used", {})
    profile = PROFILE_NAMES.get(project["profile"], project["profile"])
    concrete = [["Resistencia especificada del concreto (f'c)", number(materials["fc [MPa]"], "MPa"), "MPa", "Dato del usuario"],
                ["Tipo de concreto", _CONCRETE.get(materials["concrete"], materials["concrete"]), "–", "Dato del usuario"]]
    if "max_aggregate [mm]" in materials:
        concrete.append(["Tamaño máximo nominal del agregado grueso (dagg)", number(materials["max_aggregate [mm]"], "mm"), "mm",
                         "Dato del usuario"])
    steel = [["Esfuerzo de fluencia del refuerzo longitudinal (fy)", number(materials["fy [MPa]"], "MPa"), "MPa", "Dato del usuario"],
             ["Esfuerzo de fluencia del refuerzo transversal (fyt)", number(materials["fyt [MPa]"], "MPa"), "MPa", "Dato del usuario"],
             ["Recubrimiento de las barras", _COATING.get(materials["coating"], materials["coating"]), "–", "Dato del usuario"]]
    for key, value in used.items():
        name, unit = unit_of(key)
        description, symbol = describe(name)
        row = [f"{description} ({symbol})", "–" if value is None else number(value, unit if unit != "–" else "–"), unit,
               f"Perfil {profile}"]
        (concrete if name in _CONCRETE_KEYS else steel).append(row)
    return concrete, steel


_MATERIAL_HEADERS = ["Propiedad", "Valor", "Unidad", "Referencia literal"]


def _materials(results: dict[str, Any]) -> list[Block]:
    concrete, steel = _material_rows(results)
    return [{"kind": "table", "headers": _MATERIAL_HEADERS, "rows": [*concrete, *steel]}]


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
    lines += _contact_lines(check)
    lines.append(("Resultado", _status_text(check["status"])))
    blocks.append({"kind": "kv", "items": lines})
    if check["note"]:
        blocks.append({"kind": "note", "text": check["note"]})
    excess = next((value for key, value in check["values"].items() if key.startswith("excedente para la viga")), None)
    if excess is not None:
        # Cortante de la franja que excede φVc (D-103, D-114): en rojo y negrilla, en la propia revisión.
        blocks.append({"kind": "alert", "tone": "danger",
                       "text": f"Vu > φVc: el cortante excedente ({number(excess, 'kN')} kN) debe ser asumido por el refuerzo "
                               "transversal de la viga de cimentación; esta revisión se reporta con DCR = 0.99 (D-103, D-114)."})
    blocks.extend({"kind": "alert", "text": f"[{error['code']}] {error['message']}"} for error in check["errors"])
    if locations:
        rows = [[place, _status_text(item["status"]), _quantity(item["demand"], item["unit"]),
                 _quantity(item["capacity"], item["unit"]), "–" if item["ratio"] is None else f"{item['ratio']:.3f}"]
                for place, item in locations]
        blocks.append({"kind": "table", "headers": ["Ubicación", "Resultado", "Demanda", "Capacidad", "DCR"], "rows": rows})
    return blocks


def _contact_lines(check: dict[str, Any]) -> list[tuple[str, str]]:
    """Contacto con el suelo (D-103): la ubicación gobernante es la combinación con la menor área en contacto, que se
    compara con el área mínima (la fracción mínima declarada por el área de la base)."""
    values = check["values"]
    if check["name"] != CONTACT or "A contacto [m2]" not in values:
        return []
    area, minimum = values["A contacto [m2]"], values["A minima [m2]"]
    sign = "≥" if area >= minimum else "<"
    return [("Combinación con la menor área en contacto", check.get("case") or "–"),
            ("Área en contacto frente al área mínima", f"Ac = {number(area, 'm²')} m² {sign} Ac,mín = {number(minimum, 'm²')} m²")]


# Subcapítulos de los requisitos técnicos (D-100, D-102): por palabras del nombre de la verificación (sin tilde), en
# orden; la separación mínima va antes que las demás separaciones. El resto va en "Otros requisitos".
_MINIMUM_WORDS = ("acero minimo", "refuerzo minimo", "refuerzo transversal minimo", "area minima", "cuantia",
                  "refuerzo distribuido")
_SPACING_WORDS = ("separacion", "cortinas", "refuerzo superficial")
_REQUIREMENT_SECTIONS = (
    ("Refuerzo mínimo", ()),
    ("Separación del refuerzo", ("Separación máxima del refuerzo", "Separación mínima del refuerzo")),
    ("Deformación neta de tracción", ()),
    ("Otros requisitos", ()),
)
_NBSP = " "
_REQUIREMENT_HEADERS = ["Requisito", "Exigido", "Suministrado", "Referencia normativa", "Resultado"]
# La cara en tracción de una revisión de flexión, de su nota: nombra el refuerzo que se revisa (D-102).
_TENSION_FACES = (("Cara inferior en traccion", "barras inferiores"), ("Cara superior en traccion", "barras superiores"))


def _requirement_group(name: str) -> tuple[str, str]:
    """(subcapítulo, apartado) de un requisito: el apartado solo en la separación (máxima o mínima)."""
    lowered = name.lower()
    if "separacion minima" in lowered:
        return "Separación del refuerzo", "Separación mínima del refuerzo"
    if any(word in lowered for word in _SPACING_WORDS):
        return "Separación del refuerzo", "Separación máxima del refuerzo"
    if any(word in lowered for word in _MINIMUM_WORDS):
        return "Refuerzo mínimo", ""
    if "deformacion neta" in lowered:
        return "Deformación neta de tracción", ""
    return "Otros requisitos", ""


def _requirement_label(check: dict[str, Any], axes: tuple[str, str] | None) -> str:
    """El requisito y el refuerzo que revisa (D-102): en las revisiones de flexión, la cara en tracción y, en la zapata
    combinada, la dirección; en la combinada, cada dirección con su eje global (D-101)."""
    name, note = check["name"], check["note"] or ""
    parts = []
    if name.startswith("Flexion:"):
        faces = [text for key, text in _TENSION_FACES if key in note]
        if not faces:  # sin la cara en la nota, el signo del momento de la sección (D-095) dice cuál tracciona
            faces = [text for key, text in (("momento positivo", "barras inferiores"), ("momento negativo", "barras superiores"))
                     if key in note]
        parts += faces
        if axes is not None:
            parts.append("direccion secundaria" if note.startswith(("Franja", "Aleta")) else "direccion principal")
    label = display(name if not parts else f"{name} ({', '.join(parts)})")
    if axes is not None:
        for word in ("dirección", "Dirección"):
            label = label.replace(f"{word} principal", f"{word} principal ({axes[0]})")
            label = label.replace(f"{word} secundaria", f"{word} secundaria ({axes[1]})")
    return label


def _limits(name: str, check: dict[str, Any]) -> tuple[str, str]:
    """(Exigido, Suministrado). En las separaciones máximas la demanda es la separación dispuesta y la capacidad el
    máximo: lo exigido es "≤ máximo"; en los demás requisitos lo exigido es la demanda ("≥ mínimo") y lo suministrado la
    capacidad."""
    unit = check["unit"]

    def text(value: float | None, sign: str = "") -> str:
        # Espacios de no separación: el signo, el número y la unidad no se parten en dos renglones.
        return "–" if value is None else f"{sign}{_quantity(value, unit)}".replace(" ", _NBSP)

    if classify(name)[2].endswith("máx"):
        return text(check["capacity"], "≤ "), text(check["demand"])
    return text(check["demand"], "≥ "), text(check["capacity"])


def _requirements(items: list[Located], number_text: str, axes: tuple[str, str] | None = None) -> list[Block]:
    """Requisitos técnicos en subcapítulos (D-100, D-102): refuerzo mínimo; separación del refuerzo, con la máxima y la
    mínima por separado; deformación neta de tracción y otros. Cada fila es un requisito para un tipo de refuerzo (las
    revisiones de flexión, por cara en tracción y, en la zapata combinada, por dirección), en su ubicación más exigida;
    columnas: requisito, exigido, suministrado, referencia normativa y resultado. axes: los ejes globales de la
    dirección principal y la secundaria de la zapata combinada."""
    rows: dict[str, Located] = {}
    for where, check in items:
        if classify(check["name"])[0] != "requirements":
            continue
        label = _requirement_label(check, axes)
        current = rows.get(label)
        if current is None or _severity(check) > _severity(current[1]):
            rows[label] = (where, check)
    if not rows:
        return [{"kind": "p", "text": "No aplica: ningún requisito para este elemento."}]
    blocks: list[Block] = []
    index = 0
    for title, parts in _REQUIREMENT_SECTIONS:
        own = {label: located for label, located in rows.items() if _requirement_group(located[1]["name"])[0] == title}
        if not own:
            continue
        index += 1
        blocks.append({"kind": "h2", "text": f"{number_text}.{index} {title}"})
        for position, part in enumerate(parts or ("",), start=1):
            selected = {label: located for label, located in own.items() if _requirement_group(located[1]["name"])[1] == part}
            if part:
                blocks.append({"kind": "h3", "text": f"{number_text}.{index}.{position} Revisión de {part[0].lower()}{part[1:]}"})
            if not selected:
                blocks.append({"kind": "p", "text": "No aplica: ninguna revisión de este tipo en el elemento."})
                continue
            table = []
            for label, (_, check) in sorted(selected.items()):
                required, provided = _limits(check["name"], check)
                table.append([label, required, provided, check["clause"] or "–", _status_text(check["status"])])
            blocks.append({"kind": "table", "headers": _REQUIREMENT_HEADERS, "rows": table})
    for label, (_, check) in rows.items():
        blocks.extend({"kind": "alert", "text": f"{label}: [{error['code']}] {error['message']}"} for error in check["errors"])
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


def _dcr(items: list[Located], label: Callable[[Located], str] | None = None) -> list[Block]:
    """Índices demanda/capacidad de las revisiones de resistencia (D-102): los requisitos técnicos (cuantías,
    separaciones, deformación neta…) se revisan en su capítulo y no van aquí. label da el nombre de cada fila: por
    omisión, el de la verificación; en la zapata combinada, además la dirección y el signo del momento (D-119)."""
    named = label or (lambda item: display(item[1]["name"]))
    rows = [[title, _CHAPTER_TITLES[classify(check["name"])[0]].replace("Revisión de ", "").capitalize(), where,
             _quantity(check["demand"], check["unit"]), _quantity(check["capacity"], check["unit"]),
             "–" if check["ratio"] is None else f"{check['ratio']:.3f}", _status_text(check["status"])]
            for title, (where, check) in _governing_by(items, named).items() if classify(check["name"])[0] != "requirements"]
    if not rows:
        return [{"kind": "p", "text": "No aplica: ninguna revisión de resistencia en el elemento."}]
    return [{"kind": "table", "headers": ["Revisión", "Capítulo", "Ubicación gobernante", "Demanda", "Capacidad", "DCR",
                                          "Resultado"], "rows": rows}]


def _notes(results: dict[str, Any], conventions: tuple[str, ...], limitations: tuple[str, ...]) -> list[Block]:
    project = results["project"]
    return [{"kind": "p", "text": f"Justificación del nivel sísmico: {project['seismic']['justification']}"},
            *({"kind": "note", "text": text} for text in (*conventions, _SOURCES)),
            {"kind": "p", "text": "Limitaciones:"},
            *({"kind": "note", "text": text} for text in limitations)]


def _assemble(head: list[Block], chapters: list[tuple[str, Callable[[str], list[Block]]]]) -> list[Block]:
    """Encabezado y capítulos numerados; las figuras se numeran por capítulo ("Figura 3.2", D-105)."""
    blocks = list(head)
    for index, (title, build) in enumerate(chapters, start=1):
        blocks.append({"kind": "h1", "text": f"{index}. {title}"})
        figures = 0
        for block in build(str(index)):
            if block["kind"] == "image":
                figures += 1
                block = {**block, "number": f"{index}.{figures}"}
            blocks.append(block)
    return blocks


def _layers(layout: dict[str, Any]) -> str:
    parts = []
    for layer in layout["layers"]:
        bars = layer["bars"]
        if isinstance(bars, dict):
            text = f"{bars['designation']} c/{bars['spacing']:.0f} mm"
        else:
            names = [bar if isinstance(bar, str) else bar["designation"] for bar in bars]
            # Cantidad y designación de cada tipo de barra, en el orden de la capa ("9 #8", "2 #6 + 2 #5").
            text = " + ".join(f"{names.count(name)} {name}" for name in dict.fromkeys(names))
        role = {"torsion": "torsión", "skin": "piel"}.get(layer["role"], "flexión")
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
            _summary(items), *_deep_alert(member.get("deep_beam", False), "La viga")]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda _: _materials(results)),
        ("Propiedades geométricas y armado", lambda _: _beam_geometry(member)),
        ("Solicitaciones", lambda _: _beam_demands(member)),
        (_CHAPTER_TITLES["requirements"], lambda n: _requirements(items, n)),
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


def _soil_pressures(footing: dict[str, Any], figure: Path | None,
                    heading: str = "Presión del suelo en las esquinas (casos de servicio)") -> list[Block]:
    """Presión del suelo en las esquinas (D-080): la planta del caso de servicio que gobierna la presión admisible y la
    tabla de las esquinas de todos los casos de servicio."""
    checks = [check for check in footing["checks"] if check["name"] == PRESSURE and corner_key("-x-y") in check["values"]]
    if not checks:
        return []
    blocks: list[Block] = [{"kind": "h2", "text": heading}]
    governing = governing_pressure(footing["checks"])
    if figure is not None and governing is not None:
        geometry = footing["geometry [mm]"]
        blocks.append({"kind": "image", "path": str(figure), "aspect": pressure_aspect(geometry["lx"], geometry["ly"]),
                       "caption": f"Presión del suelo en planta, caso que gobierna {governing['case']}"})
    geometry = footing["geometry [mm]"]
    rows = [[check["case"], *(number(check["values"][corner_key(name)], "kPa") for name, _, _ in CORNERS),
             f"{check['values']['ex [mm]'] / geometry['lx']:.3f}", f"{check['values']['ey [mm]'] / geometry['ly']:.3f}",
             _region(check)] for check in checks]
    blocks.append({"kind": "table", "headers": ["Caso", "p (−x, −y) kPa", "p (+x, −y) kPa", "p (+x, +y) kPa", "p (−x, +y) kPa",
                                                "ex/lx", "ey/ly", "Región"], "rows": rows})
    blocks.append({"kind": "note", "text": "Presión bruta de Bellos y Bakas (2017) con los factores del caso; 0 indica una esquina "
                                           "sin contacto con el suelo. ex/lx y ey/ly son las excentricidades de la resultante "
                                           "respecto al centroide de la base, como fracción de su dimensión; la región es la "
                                           "de Bellos y Bakas (A: contacto total; B a E: contacto parcial)."})
    return blocks


def _region(check: dict[str, Any]) -> str:
    """Letra de la región de Bellos y Bakas (2017) de un caso de servicio, que la nota de la verificación trae."""
    note = check.get("note") or ""
    return note[len("Region "):].split(" ", 1)[0] if note.startswith("Region ") else "–"


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


def _beam_moments(footing: dict[str, Any]) -> list[Block]:
    """Momentos γf·Msc negativos que la zapata no resiste con malla superior ni concreto simple: los debe tomar la viga de
    cimentación (D-087); se listan para que el analista los lleve al diseño de la viga."""
    moments = footing.get("foundation_beam_moments", [])
    if not moments:
        return [{"kind": "p", "text": "La parte negativa de γf·Msc la resiste la zapata en todos los casos (malla superior o "
                                      "concreto simple)."}]
    rows = [[item["case"], item["column"] or "–", item["beam_direction"], number(item["M [kN-m]"], "kN·m")] for item in moments]
    return [{"kind": "h2", "text": "Momentos para la viga de cimentación"},
            {"kind": "table", "headers": ["Caso", "Columna", "Dirección de la viga", "M para la viga (kN·m)"], "rows": rows},
            {"kind": "note", "text": "Parte negativa del momento transferido por flexión que la zapata no resiste con la malla superior "
                                     "ni con el concreto simple: la debe tomar la viga de cimentación; no se suma al momento de la "
                                     "zapata ni se verifica aquí (ACI 8.4.2.2, NSR-10 C.13.5.3; D-087)."}]


def _two_way_alert(footing: dict[str, Any]) -> list[Block]:
    """Aviso de zapata ancha (D-091): B ≥ ℓn; se revisa en una dirección, pero puede trabajar en dos."""
    warning = footing.get("two_way_warning")
    if not warning:
        return []
    return [{"kind": "alert", "text": f"El ancho B = {number(warning['B [mm]'], 'mm')} mm alcanza la luz libre entre columnas "
                                      f"ℓn = {number(warning['ln [mm]'], 'mm')} mm (B/ℓn = {warning['B/ln']:.2f}): la zapata "
                                      "puede trabajar en dos direcciones (ACI 13.3.4). Se revisa en una dirección (ACI "
                                      "13.3.2); la revisión en dos direcciones no está implementada (D-091)."}]


def _deep_alert(deep: bool, subject: str) -> list[Block]:
    """Aviso de viga de gran altura declarada (D-089): se verifican sus criterios, pero la resistencia es seccional."""
    if not deep:
        return []
    return [{"kind": "alert", "text": f"{subject} está declarada de gran altura (ACI 9.9.1.1, NSR-10 C.11.7.1): se verifican "
                                      "el límite de sección y el refuerzo distribuido; la flexión y el cortante son del cálculo "
                                      "seccional, que no considera la distribución no lineal de deformaciones (ACI 9.9.1.2, "
                                      "NSR-10 C.11.7.2). El análisis no lineal o el puntal-tensor quedan a cargo del analista "
                                      "(D-089)."}]


def _beam_alert(footing: dict[str, Any]) -> list[Block]:
    """Aviso al comienzo de la memoria si hay momentos que debe tomar la viga de cimentación (D-087)."""
    moments = footing.get("foundation_beam_moments", [])
    if not moments:
        return []
    largest = max(item["M [kN-m]"] for item in moments)
    return [{"kind": "alert", "tone": "danger",
             "text": f"La viga de cimentación debe tomar momentos transferidos por la columna (hasta "
                     f"{number(largest, 'kN·m')} kN·m): ver la tabla \"Momentos para la viga de cimentación\" "
                     "en el capítulo de punzonamiento (D-087)."}]


def _beam_shear_alert(footing: dict[str, Any]) -> list[Block]:
    """Aviso al comienzo de la memoria si el refuerzo transversal de la viga de cimentación debe tomar cortante de las
    franjas que excede φVc (D-103)."""
    shears = footing.get("foundation_beam_shears", [])
    if not shears:
        return []
    largest = max(item["V [kN]"] for item in shears)
    return [{"kind": "alert", "tone": "danger",
             "text": f"El cortante de las franjas de la dirección secundaria excede φVc (hasta {number(largest, 'kN')} kN): "
                     "el excedente lo debe asumir el refuerzo transversal de la viga de cimentación; esas verificaciones se "
                     "reportan con DCR = 0.99. Ver la tabla \"Cortante para el refuerzo transversal de la viga de cimentación\" "
                     "(D-103)."}]


def _beam_shears(footing: dict[str, Any]) -> list[Block]:
    """Tabla de los cortantes de franja que debe tomar la viga de cimentación (D-103)."""
    shears = footing.get("foundation_beam_shears", [])
    if not shears:
        return []
    rows = [[item["case"], item["column"], item["section"], number(item["V [kN]"], "kN")] for item in shears]
    return [{"kind": "h2", "text": "Cortante para el refuerzo transversal de la viga de cimentación"},
            {"kind": "alert", "tone": "danger",
             "text": "Vu > φVc en estas secciones de las franjas: el cortante excedente debe ser asumido por el refuerzo "
                     "transversal de la viga de cimentación (no se verifica aquí; DCR = 0.99 en la revisión de la franja, D-114)."},
            {"kind": "table", "headers": ["Caso", "Columna", "Sección de la franja", "Vu − φVc (kN)"], "rows": rows}]


def _punching_corners(items: list[Located]) -> list[Block]:
    """Esfuerzo de punzonamiento en cada esquina del perímetro crítico (D-083), como una matriz por columna o grupo
    (D-103): una fila por combinación, una columna por esquina con sus coordenadas en el encabezado, vu,máx y la esquina
    crítica; el máximo de cada fila va resaltado."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for _, check in items:
        if check["name"] == "Punzonamiento" and "esquina 1 v [MPa]" in check["values"]:
            label = check["note"].split(":")[0] if (check["note"] or "").startswith("Columna") else ""
            groups.setdefault(label, []).append(check)
    if not groups:
        return []
    blocks: list[Block] = [{"kind": "h2", "text": "Esfuerzos de punzonamiento en las esquinas del perímetro crítico"}]
    for label, checks in groups.items():
        values = checks[0]["values"]
        count = sum(1 for key in values if key.startswith("esquina ") and key.endswith(" v [MPa]"))
        headers = ["Combinación", *(f"Esquina {i} ({number(values[f'esquina {i} x [mm]'], 'mm')}, "
                                    f"{number(values[f'esquina {i} y [mm]'], 'mm')}) mm" for i in range(1, count + 1)),
                   "vu,máx (MPa)", "Esquina crítica"]
        rows, bold = [], []
        for row_index, check in enumerate(checks):
            stresses = [check["values"][f"esquina {i} v [MPa]"] for i in range(1, count + 1)]
            critical = max(range(count), key=lambda i: stresses[i])
            rows.append([check.get("case") or "–", *(f"{stress:.3f}" for stress in stresses), f"{stresses[critical]:.3f}",
                         str(critical + 1)])
            bold.append([row_index, critical + 1])
        if label:
            blocks.append({"kind": "p", "text": label})
        blocks.append({"kind": "table", "headers": headers, "rows": rows, "bold": bold})
    blocks.append({"kind": "note", "text": "Coordenadas respecto al centroide de la base. vu = Vu/(b0·d) + γv,x·Msc,x·(x − xc)/Jc,x + "
                                           "γv,y·Msc,y·(y − yc)/Jc,y, con la carga neta de Bellos dentro del área crítica; "
                                           "en negrilla, el máximo de cada combinación."})
    return blocks


def footing_document(results: dict[str, Any], footing: dict[str, Any], full: bool, figure: Path | None = None) -> list[Block]:
    items: list[Located] = [(f"caso {check['case']}" if check.get("case") else "toda la zapata", check) for check in footing["checks"]]
    counts = {kind: sum(1 for load in footing["loads"] if load["kind"] == kind) for kind in ("service", "factored")}
    meta = [("Casos de carga", f"{counts['service']} de servicio y {counts['factored']} mayorados")]
    head = [_title(f"Zapata {footing['id']}", results, meta, items, footing["status"]), _summary(items), *_beam_alert(footing)]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda _: _materials(results)),
        ("Propiedades geométricas, suelo y armado", lambda _: _footing_geometry(results, footing)),
        ("Solicitaciones", lambda _: _footing_demands(footing, figure)),
        (_CHAPTER_TITLES["geotechnical"], lambda n: _chapter("geotechnical", n, items, full)),
        (_CHAPTER_TITLES["requirements"], lambda n: _requirements(items, n)),
        (_CHAPTER_TITLES["flexure"], lambda n: _chapter("flexure", n, items, full)),
        (_CHAPTER_TITLES["one_way"], lambda n: _chapter("one_way", n, items, full)),
        (_CHAPTER_TITLES["punching"], lambda n: [*_chapter("punching", n, items, full), *_punching_corners(items),
                                                 *_beam_moments(footing)]),
        (_CHAPTER_TITLES["development"], lambda n: _chapter("development", n, items, full)),
        (_CHAPTER_TITLES["bearing"], lambda n: _chapter("bearing", n, items, full)),
        ("Índices DCR", lambda _: _dcr(items)),
        ("Notas y limitaciones", lambda _: _notes(results, _FOOTING_CONVENTIONS, _FOOTING_LIMITATIONS)),
    ]
    return _assemble(head, chapters)


def _combined_axes(footing: dict[str, Any]) -> tuple[str, str]:
    """Ejes globales de la dirección principal y de la secundaria de la zapata combinada (D-094, D-101)."""
    principal = (footing["geometry [mm]"].get("principal_direction") or "x").upper()
    return principal, "Y" if principal == "X" else "X"


def _combined_where(check: dict[str, Any], axes: tuple[str, str]) -> str:
    """Ubicación de una verificación de la zapata combinada, en los ejes declarados (D-101): el caso y la dirección
    principal (z a lo largo de la viga y sección), la franja (z desde el borde −secundario) o la columna."""
    principal, secondary = axes
    case = f"caso {check['case']}" if check.get("case") else "toda la zapata"
    note = check["note"].split(":")[0].split(";")[0]
    z = check.get("z [mm]")
    if note.startswith("Franja"):
        return f"{case}, {note}" + (f" (z = {z:.0f} mm desde −{secondary})" if z is not None else "")
    if note.startswith("Aleta"):
        return f"{case}, {note}"
    if note.startswith("Columna"):
        return f"{case}, {note}"
    if z is not None:
        return f"{case}, dirección principal en z = {z:.0f} mm desde −{principal} ({note[:1].lower() + note[1:]})"
    return case


def _bar_text(bars: dict[str, Any] | None, extra: str = "") -> str:
    if bars is None:
        return "no hay"
    return f"{bars['designation']} c/{bars['spacing']:.0f} mm{extra}"


def _top_text(top: dict[str, Any] | None) -> str:
    """Las barras superiores de la zapata combinada (D-099): cada dirección declarada (y en todo el largo), la primera
    y cómo terminan."""
    if top is None:
        return "no hay"
    sets = [f"barras {direction} {top[direction]['designation']} c/{top[direction]['spacing']:.0f} mm"
            + (" (todo el largo)" if direction == "y" else "") for direction in ("x", "y") if top.get(direction)]
    first = f"; primero {top['first']}" if top.get("first") else ""
    return f"{'; '.join(sets)}{first}; barras {_ENDS[top['end']]}"


def _combined_materials(results: dict[str, Any], number_text: str) -> list[Block]:
    """1.1 Concreto estructural, 1.2 Acero de refuerzo y 1.3 Suelo (D-104)."""
    concrete, steel = _material_rows(results)
    soil = _soil_rows(results)
    weight = [row for row in soil if row[0].startswith("Peso unitario del concreto")]
    concrete += [[*row, "Dato del usuario"] for row in weight]
    ground = [row for row in soil if not row[0].startswith("Peso unitario del concreto")]
    return [{"kind": "h2", "text": f"{number_text}.1 Concreto estructural"},
            {"kind": "table", "headers": _MATERIAL_HEADERS, "rows": concrete},
            {"kind": "h2", "text": f"{number_text}.2 Acero de refuerzo"},
            {"kind": "table", "headers": _MATERIAL_HEADERS, "rows": steel},
            {"kind": "h2", "text": f"{number_text}.3 Suelo"},
            {"kind": "table", "headers": ["Propiedad (dato del usuario)", "Valor", "Unidad"], "rows": ground}]


def _combined_geometry(results: dict[str, Any], footing: dict[str, Any], number_text: str) -> list[Block]:
    """2.1 Zapata combinada, 2.2 Acero de refuerzo, 2.3 Suelo y 2.4 Columnas (D-104)."""
    g = footing["geometry [mm]"]
    principal, secondary = _combined_axes(footing)
    rows = [["Dirección principal (la de la viga que une las columnas)", f"{principal} global", "–"],
            ["Dimensión a lo largo de X (lx)", number(g["lx"], "mm"), "mm"],
            ["Dimensión a lo largo de Y (ly)", number(g["ly"], "mm"), "mm"],
            ["Espesor (h)" if not g.get("beam") else "Espesor de la zarpa (h)", number(g["h"], "mm"), "mm"],
            *([["Ancho de la viga (bw, T invertida)", number(g["beam"]["width"], "mm"), "mm"],
               ["Altura total de la viga (H)", number(g["beam"]["height"], "mm"), "mm"]] if g.get("beam") else []),
            ["Recubrimiento libre", number(g["cover"], "mm"), "mm"]]
    columns = [[column["id"], number(column["cx"], "mm"), number(column["cy"], "mm"), number(column["x"], "mm"), number(column["y"], "mm"),
                f"{column['dowels']['count']} {column['dowels']['designation']}" if column.get("dowels") else "no declarados",
                _bar_text(column.get("band")), _bar_text(column.get("band_top"))] for column in footing["columns"]]
    reinforcement = footing["reinforcement"]
    stirrups = reinforcement.get("stirrups")
    skin = reinforcement.get("skin")
    bars = [["Malla inferior", _mat_text(reinforcement["bottom"])],
            ["Barras superiores", _top_text(reinforcement.get("top"))],
            ["Estribos de la viga (dirección principal)", "no hay" if stirrups is None else
             f"{stirrups['legs']} ramas {stirrups['designation']} c/{stirrups['spacing']:.0f} mm"],
            ["Refuerzo superficial (caras largas)", _bar_text(skin, " en vertical" if skin else "")]]
    if g.get("beam"):
        # T invertida (D-106): el refuerzo de la viga va en sus capas; la malla es la de la zarpa.
        beam = g["beam"]
        covered = "el ala efectiva" if beam.get("bottom_width") is None else f"{beam['bottom_width']:.0f} mm"
        bars = [["Viga: capas (profundidad desde la cara superior)", _layers(beam)],
                ["Viga: estribos", _stirrups(beam)],
                ["Viga: extremos de las barras", _ENDS[beam["end"]]],
                ["Ancho que cubre la capa inferior de la viga", covered],
                ["Malla inferior de la zarpa (barras x fuera de ese ancho; barras y de las aletas)",
                 _mat_text(reinforcement["bottom"])]]
    return [{"kind": "h2", "text": f"{number_text}.1 Zapata combinada"},
            {"kind": "table", "headers": ["Dimensión (dato del usuario)", "Valor", "Unidad"], "rows": rows},
            _axes_note(principal, secondary),
            {"kind": "p", "text": "Propiedades calculadas a partir de las dimensiones (nunca declaradas):"},
            {"kind": "table", "headers": ["Propiedad", "Valor", "Unidad"], "rows": _properties_rows(footing)},
            {"kind": "h2", "text": f"{number_text}.2 Acero de refuerzo"},
            {"kind": "table", "headers": ["Refuerzo", "Descripción"], "rows": bars},
            {"kind": "h2", "text": f"{number_text}.3 Suelo"},
            {"kind": "table", "headers": ["Dimensión (dato del usuario)", "Valor", "Unidad"],
             "rows": [["Altura del relleno sobre la zapata", number(g["fill_height"], "mm"), "mm"]]},
            {"kind": "h2", "text": f"{number_text}.4 Columnas"},
            {"kind": "table",
             "headers": ["Columna", "cx (mm)", "cy (mm)", "x (mm)", "y (mm)", "Pasadores", "Refuerzo bajo la columna (band)",
                         "Band superior"],
             "rows": columns},
            {"kind": "table", "headers": ["Dimensión (dato del usuario)", "Valor", "Unidad"],
             "rows": [["Altura de los pedestales", number(g["pedestal_height"], "mm"), "mm"]]},
            {"kind": "note", "text": "x e y ubican el eje de cada columna respecto al centroide de la base."}]


def _axes_note(principal: str, secondary: str) -> Block:
    """Los ejes de la memoria (D-101): los globales declarados; la dirección principal y la secundaria."""
    return {"kind": "note", "text": f"Ejes globales declarados en toda la memoria. Dirección principal: {principal} global, la de "
                                    f"la viga que une las columnas; dirección secundaria: {secondary} global, la de las franjas "
                                    "transversales o las aletas. El cálculo trabaja en ejes de la viga y sus resultados se "
                                    "devuelven a los ejes declarados (D-094, D-101)."}


def _combined_actions(footing: dict[str, Any], figure: Path | None, diagrams: list[Path] | None, number_text: str) -> list[Block]:
    """3.1 Sobrecargas, 3.2 combinaciones de servicio (ASD), 3.3 combinaciones mayoradas (LRFD), 3.4 presión sobre el suelo
    y 3.5 solicitaciones internas (D-104)."""
    g = footing["geometry [mm]"]
    blocks: list[Block] = [
        {"kind": "h2", "text": f"{number_text}.1 Sobrecargas"},
        {"kind": "table", "headers": ["Sobrecarga (dato del usuario)", "Valor", "Unidad"],
         "rows": [["Sobrecarga muerta (qD)", number(g["surcharge_dead [kN/m2]"], "kN/m²"), "kN/m²"],
                  ["Sobrecarga viva (qL)", number(g["surcharge_live [kN/m2]"], "kN/m²"), "kN/m²"]]}]
    titles = (("service", f"{number_text}.2 Combinaciones de esfuerzos admisibles (ASD)"),
              ("factored", f"{number_text}.3 Combinaciones de resistencia última (LRFD)"))
    for kind, title in titles:
        blocks.append({"kind": "h2", "text": title})
        tables = [_loads_table([load for load in column["loads"] if load["kind"] == kind], column["id"]) for column in footing["columns"]]
        rows = [row for table in tables for row in table["rows"]]
        if not rows:
            blocks.append({"kind": "p", "text": "No aplica: ningún caso de este tipo."})
            continue
        blocks += [{"kind": "p", "text": "Fuerzas de cada columna sobre la zapata, en la base de la columna; P > 0 en compresión."},
                   {**tables[0], "rows": rows}]
    blocks += _soil_pressures(footing, figure, f"{number_text}.4 Presión sobre el suelo")
    return blocks + _internal_forces(footing, diagrams, f"{number_text}.5")


_SECTION_HEADERS = {"V": ("V máx (kN)", "V mín (kN)"), "M": ("M máx (kN·m)", "M mín (kN·m)")}


def _internal_forces(footing: dict[str, Any], files: list[Path] | None, number_text: str) -> list[Block]:
    """Solicitaciones internas (D-095, D-104): por elemento (dirección principal, cada franja o las aletas), el diagrama
    envolvente de cortante y el de momento, cada uno con la tabla de sus secciones críticas."""
    blocks: list[Block] = [{"kind": "h2", "text": f"{number_text} Solicitaciones internas"}]
    diagrams = footing.get("diagrams")
    if not diagrams:
        return [*blocks, {"kind": "p", "text": "No aplica: la zapata no tiene casos mayorados en equilibrio."}]
    principal, secondary = _combined_axes(footing)
    blocks.append({"kind": "p", "text": "Envolvente de los casos mayorados: en cada posición, el mayor y el menor valor entre todos "
                                        "los casos. M > 0 tracciona la cara inferior; V es el del cuerpo libre a la izquierda "
                                        f"(desde −{principal} en la dirección principal y desde −{secondary} en la secundaria). "
                                        "Posiciones desde el centroide de la base. Las tablas dan, en cada sección crítica, el "
                                        "máximo y el mínimo de la envolvente y su caso."})
    paths = iter(files or [])
    index = 1
    for envelope in [diagrams["principal"], *diagrams["secondary"]]:
        title = envelope["title"]
        where = f"en la dirección principal ({principal} global)" if title == "Dirección principal" else \
            f"en la dirección secundaria ({secondary} global), {title[:1].lower() + title[1:]}"
        per_metre = " por metro" if envelope["per_metre"] else ""
        for key, name, _, _ in QUANTITIES:
            heading = f"{number_text}.{index} {name} {where}"
            index += 1
            blocks.append({"kind": "h3", "text": heading})
            figure = next(paths, None)
            if figure is not None:
                blocks.append({"kind": "image", "path": str(figure), "aspect": DIAGRAM_ASPECT, "caption": f"{name} {where}"})
            unit = "kN" if key == "V" else "kN·m"
            high, low = _SECTION_HEADERS[key]
            rows = [[section["label"], number(section["position [mm]"], "mm"),
                     number(section[f"{key} max [{'kN' if key == 'V' else 'kN-m'}]"], unit), section[f"{key} max case"],
                     number(section[f"{key} min [{'kN' if key == 'V' else 'kN-m'}]"], unit), section[f"{key} min case"]]
                    for section in envelope.get("sections", [])]
            if rows:
                blocks.append({"kind": "table", "headers": ["Sección crítica", "Posición (mm)", f"{high}{per_metre}", "Caso",
                                                            f"{low}{per_metre}", "Caso"], "rows": rows})
    return blocks


def _negative(item: Located) -> bool:
    """Verificación del momento negativo (D-095): su sección lo dice en la nota, o es de concreto simple (cara superior)."""
    check = item[1]
    return "momento negativo" in (check["note"] or "") or "concreto simple" in check["name"]


def _flexure_by_sign(number_text: str, items: list[Located], negative: bool, full: bool) -> list[Block]:
    """La revisión del momento de un signo; si ningún caso lo produce, lo dice (D-095)."""
    own = [item for item in items if _negative(item) == negative]
    if not any(classify(check["name"])[0] == "flexure" for _, check in own):
        sign = "negativo (tracción en la cara superior)" if negative else "positivo (tracción en la cara inferior)"
        return [{"kind": "p", "text": f"No aplica: ningún caso mayorado produce momento {sign} en las secciones revisadas."}]
    return _chapter("flexure", number_text, own, full)


def _outside_chapter(kind: str, number_text: str, items: list[Located], negative: bool | None, full: bool) -> list[Block]:
    """Un capítulo de la dirección secundaria fuera de las franjas band (D-119): la flexión de un signo o el cortante de
    la torsión de placa; sin torsión, no hay nada que revisar allí (solo retracción y temperatura, D-116)."""
    own = [item for item in items if classify(item[1]["name"])[0] == kind and (negative is None or _negative(item) == negative)]
    if not own:
        return [{"kind": "p", "text": "No aplica: sin torsión de placa fuera de las franjas band, my = 0 y solo rige el mínimo "
                                      "de retracción y temperatura (D-116, D-118)."}]
    return _chapter(kind, number_text, own, full)


def combined_document(results: dict[str, Any], footing: dict[str, Any], full: bool, figure: Path | None = None,
                      diagrams: list[Path] | None = None) -> list[Block]:
    """Memoria de una zapata combinada (D-080 a D-083): la viga larga y las franjas transversales con las verificaciones de
    vigas, el momento positivo y el negativo por separado y sus diagramas envolventes (D-095), el punzonamiento con los
    esfuerzos de cada esquina, el desarrollo, el aplastamiento y los pasadores."""
    axes = _combined_axes(footing)
    principal, secondary = axes
    items: list[Located] = [(_combined_where(check, axes), check) for check in footing["checks"]]
    # La dirección secundaria: franjas o aletas y, aparte, la torsión de placa fuera de las franjas band (D-118, D-119).
    strips = [item for item in items if item[1]["note"].startswith(("Franja", "Aleta"))]
    outside = [item for item in items if item[1]["note"].startswith("Fuera de las franjas")]
    inverted = bool(footing["geometry [mm]"].get("beam"))
    along = f"Dirección principal ({principal} global)"
    across = f"Dirección secundaria ({secondary} global), {'aletas de la zarpa' if inverted else 'franjas transversales'}"
    beyond = f"Dirección secundaria ({secondary} global), fuera de las franjas band"
    beam = [item for item in items if item[1].get("z [mm]") is not None and not item[1]["note"].startswith("Franja")]
    others = [item for item in items if item not in strips and item not in beam and item not in outside]
    counts = {kind: sum(1 for load in footing["columns"][0]["loads"] if load["kind"] == kind) for kind in ("service", "factored")}
    meta = [("Columnas", " y ".join(column["id"] for column in footing["columns"])),
            ("Casos de carga", f"{counts['service']} de servicio y {counts['factored']} mayorados")]
    head = [_title(f"Zapata combinada {footing['id']}", results, meta, items, footing["status"]), _summary(items),
            *_beam_alert(footing), *_beam_shear_alert(footing),
            *_deep_alert(footing.get("deep_beam", False), "La viga de la dirección principal"),
            *_two_way_alert(footing)]
    chapters: list[tuple[str, Callable[[str], list[Block]]]] = [
        ("Propiedades mecánicas de los materiales", lambda n: _combined_materials(results, n)),
        ("Propiedades geométricas, armado, suelo y columnas", lambda n: _combined_geometry(results, footing, n)),
        ("Solicitaciones", lambda n: _combined_actions(footing, figure, diagrams, n)),
        (_CHAPTER_TITLES["geotechnical"], lambda n: _chapter("geotechnical", n, others, full)),
        (_CHAPTER_TITLES["requirements"], lambda n: _requirements(items, n, axes)),
        (f"{along}: momento positivo", lambda n: _flexure_by_sign(n, beam, False, full)),
        (f"{along}: momento negativo", lambda n: _flexure_by_sign(n, beam, True, full)),
        (f"{along}: fuerza cortante", lambda n: _chapter("shear", n, beam, full)),
        # La torsión de vigas solo en el alma de la T; en la rectangular es de placa y va en la flexión (D-118).
        *([(f"{along}: torsión", lambda n: _chapter("torsion", n, beam, full))] if inverted else []),
        (f"{across}: momento positivo", lambda n: _flexure_by_sign(n, strips, False, full)),
        (f"{across}: momento negativo", lambda n: _flexure_by_sign(n, strips, True, full)),
        (f"{across}: fuerza cortante", lambda n: [*_chapter("shear", n, strips, full), *_beam_shears(footing)]),
        # Fuera de las franjas band: la torsión de placa (Wood-Armer, D-118) y su cortante ∂mxy/∂x (D-119).
        *([] if inverted else [(f"{beyond}: momento positivo", lambda n: _outside_chapter("flexure", n, outside, False, full)),
                               (f"{beyond}: momento negativo", lambda n: _outside_chapter("flexure", n, outside, True, full)),
                               (f"{beyond}: fuerza cortante", lambda n: _outside_chapter("shear", n, outside, None, full))]),
        *([] if inverted else [(_CHAPTER_TITLES["punching"], lambda n: [*_chapter("punching", n, others, full),
                                                                        *_punching_corners(others), *_beam_moments(footing)])]),
        (_CHAPTER_TITLES["development"], lambda n: _chapter("development", n, others, full)),
        (_CHAPTER_TITLES["bearing"], lambda n: _chapter("bearing", n, others, full)),
        ("Índices DCR", lambda _: _dcr(items, _combined_label)),
        ("Notas y limitaciones", lambda _: _notes(results, _COMBINED_CONVENTIONS, _COMBINED_LIMITATIONS)),
    ]
    return _assemble(head, chapters)


def report_documents(results: dict[str, Any], *, full: bool = False, figures: dict[str, Path] | None = None,
                     diagrams: dict[str, list[Path]] | None = None) -> list[list[Block]]:
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
    documents += [combined_document(results, footing, full, (figures or {}).get(footing["id"]), (diagrams or {}).get(footing["id"]))
                  for footing in results.get("combined_footings", [])]
    return documents
