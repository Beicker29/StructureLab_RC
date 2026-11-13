"""Proyecto de zapatas a partir de dos tablas "Joint Reactions" de ETABS: servicio y mayoradas (D-052, D-055).

Las zapatas combinadas (D-084) toman de los Excel solo los tipos de carga que su plantilla pide (loads_source); los
demás vienen escritos en la plantilla. Si ningún grupo pide un tipo, su Excel puede omitirse.

ETABS reporta la fuerza que el apoyo ejerce sobre la estructura; sobre la zapata actúa la opuesta. Por eso
P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY, en la base de la columna y en ejes globales. El traslado al
centroide de la base (altura y desplazamiento de la columna) lo hace el dominio. Las unidades internas (N, mm) solo
se aplican después, al cargar el proyecto (model/).
"""

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.io.etabs.importer import EtabsImportError, case_label
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.template import EtabsCombinedDesignTemplate, EtabsFootingDesignTemplate, EtabsFootingTemplate, LoadFactors

KINDS = {"service": "servicio", "factored": "cargas mayoradas"}
BOTH = ("service", "factored")
# Un grupo de nudos: nombre, Unique Names y los tipos de carga que salen de ETABS.
Group = tuple[str, tuple[str, ...], tuple[str, ...]]

SHEET = "Joint Reactions"
REQUIRED_UNITS = {"FX": "kN", "FY": "kN", "FZ": "kN", "MX": "kN-m", "MY": "kN-m"}
REQUIRED_COLUMNS = ("Label", "Unique Name", "Output Case", "Case Type", "Step Type", *REQUIRED_UNITS)


LOCATION_SHEET = "Point Object Connectivity"  # tabla de coordenadas de los nudos de ETABS (D-130)
LOCATION_UNITS = {"X": "m", "Y": "m"}
LOCATION_COLUMNS = ("UniqueName", "Story", *LOCATION_UNITS)
MM_PER_M = 1000.0


def locations_by_joint(table: Table | None, names: list[str]) -> dict[str, dict[str, Any]]:
    """La ubicación (formato de entrada, en mm) de cada Unique Name de names en la tabla de coordenadas de ETABS (D-130);
    {} sin tabla. Lanza EtabsImportError si faltan columnas, unidades o nudos."""
    if table is None:
        return {}
    errors = [invalid_input(f"Falta la columna '{column}' en la tabla de coordenadas") for column in LOCATION_COLUMNS
              if column not in table.headers]
    errors += [invalid_input(f"La columna '{column}' de la tabla de coordenadas debe venir en {unit}; viene en "
                             f"'{table.units.get(column)}'") for column, unit in LOCATION_UNITS.items()
               if column in table.headers and table.units.get(column) != unit]
    if errors:
        raise EtabsImportError(tuple(errors))
    rows = {row["UniqueName"]: row for row in table.rows}
    missing = [name for name in names if name not in rows]
    if missing:
        raise EtabsImportError((invalid_input(f"La tabla de coordenadas no tiene los Unique Name {', '.join(missing)}"),))
    return {name: {"x": float(rows[name]["X"]) * MM_PER_M, "y": float(rows[name]["Y"]) * MM_PER_M,
                   "story": rows[name]["Story"], "joint": name} for name in names}


@dataclass(frozen=True)
class FootingImportSummary:
    footings: int
    service_cases: tuple[str, ...]
    factored_cases: tuple[str, ...]
    skipped_rows: int
    omitted: tuple[str, ...] = ()  # Unique Name de los Excel que no entran (no listados o excluidos, D-111)


def _check_table(table: Table, which: str) -> list[StructuredError]:
    errors = [invalid_input(f"Falta la columna '{column}' en la tabla de {which}")
              for column in REQUIRED_COLUMNS if column not in table.headers]
    for column, unit in REQUIRED_UNITS.items():
        if column in table.headers and table.units.get(column) != unit:
            errors.append(invalid_input(f"La columna '{column}' de {which} debe venir en {unit}; viene en '{table.units.get(column)}'"))
    return errors


def _rows_by_joint(table: Table) -> tuple[dict[str, list[dict[str, str]]], int]:
    by_joint: dict[str, list[dict[str, str]]] = defaultdict(list)
    skipped = 0
    for row in table.rows:
        if row["Case Type"] != "Combination":
            skipped += 1
            continue
        by_joint[row["Unique Name"]].append(row)
    return by_joint, skipped


def _load(row: dict[str, str], kind: str, factors: LoadFactors) -> dict[str, Any]:
    return {"case": case_label(row), "kind": kind, "dead_factor": factors.dead, "live_factor": factors.live,
            "seismic": factors.seismic, "P_kN": float(row["FZ"]), "Vx_kN": -float(row["FX"]), "Vy_kN": -float(row["FY"]),
            "Mx_kNm": -float(row["MX"]), "My_kNm": -float(row["MY"])}


@dataclass(frozen=True)
class _Joint:
    group: str
    unique_name: str
    label: str
    loads: list[dict[str, Any]]


def _joint_loads(
    load_factors: dict[str, LoadFactors], tables: dict[str, Table | None], groups: list[Group]
) -> tuple[list[_Joint], int]:
    """Casos de cada nudo de los grupos, de los tipos que cada grupo toma de ETABS; lanza EtabsImportError con todos los
    problemas. tables: la tabla de cada tipo, o None si se omitió su Excel."""
    needed = {kind for _, _, kinds in groups for kind in kinds}
    errors = [invalid_input(f"Falta el Excel de {KINDS[kind]}: la plantilla toma de ETABS cargas de ese tipo")
              for kind in BOTH if kind in needed and tables[kind] is None]
    present_tables = {kind: table for kind, table in tables.items() if table is not None}
    for kind, table in present_tables.items():
        errors += _check_table(table, KINDS[kind])
    if errors:
        raise EtabsImportError(tuple(errors))
    rows_by_kind, skipped = {}, 0
    for kind, table in present_tables.items():
        rows_by_kind[kind], omitted = _rows_by_joint(table)
        skipped += omitted
    present = {row["Output Case"] for rows in rows_by_kind.values() for joint in rows.values() for row in joint}
    for name in sorted(present - set(load_factors)):
        errors.append(invalid_input(f"La combinacion '{name}' no tiene factores de carga en la plantilla"))
    if len(present_tables) == len(BOTH):  # con un solo Excel, las combinaciones del otro no pueden aparecer
        for name in sorted(set(load_factors) - present):
            errors.append(invalid_input(f"La combinacion '{name}' de la plantilla no aparece en las tablas de ETABS"))
    joints = []
    for group, unique_names, kinds in groups:
        for unique_name in unique_names:
            own = {kind: rows_by_kind[kind].get(unique_name, []) for kind in kinds}
            for kind, rows in own.items():
                if not rows:
                    errors.append(invalid_input(f"El Unique Name '{unique_name}' no tiene combinaciones en la tabla de {KINDS[kind]}",
                                                member=group))
            if not all(own.values()) or any(row["Output Case"] not in load_factors for rows in own.values() for row in rows):
                continue
            loads = [_load(row, kind, load_factors[row["Output Case"]]) for kind, rows in own.items() for row in rows]
            label = next(rows[0]["Label"] for rows in own.values()) if own else unique_name
            joints.append(_Joint(group, unique_name, label, loads))
    if errors:
        raise EtabsImportError(tuple(errors))
    return joints, skipped


def _summary(items: list[dict[str, Any]], skipped: int) -> FootingImportSummary:
    loads = [load for item in items for load in item["loads"]]
    return FootingImportSummary(len(items), tuple(sorted({load["case"] for load in loads if load["kind"] == "service"})),
                                tuple(sorted({load["case"] for load in loads if load["kind"] == "factored"})), skipped)


def _located(locations: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    """{"location": ...} del nudo si hay tabla de coordenadas (D-130); {} si no."""
    return {"location": locations[name]} if name in locations else {}


def _combined_footings(template: EtabsFootingTemplate, joints: list[_Joint],
                       locations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Zapatas combinadas del proyecto (D-084): cada columna con las cargas de su nudo de los tipos que vienen de ETABS y
    las de la plantilla de los demás, y su ubicación si hay tabla de coordenadas (D-130)."""
    loads = {(joint.group, joint.unique_name): joint.loads for joint in joints}
    footings = []
    for footing in template.combined_footings:
        data = footing.model_dump(mode="json", exclude={"loads_source", "columns"}, exclude_none=True)
        columns = []
        for column in footing.columns:
            own = column.model_dump(mode="json", exclude={"etabs_unique_name", "loads"}, exclude_none=True)
            columns.append({**own, **_located(locations, column.etabs_unique_name),
                            "loads": [*loads.get((footing.id, column.etabs_unique_name), []), *column.loads]})
        footings.append({**data, "columns": columns})
    return footings


def build_footing_project(
    template: EtabsFootingTemplate, service: Table | None, factored: Table | None, coordinates: Table | None = None
) -> tuple[dict[str, Any], FootingImportSummary]:
    """Proyecto de verificación en el formato de entrada JSON: una zapata aislada por nudo con la tipología de su grupo y
    las zapatas combinadas con las cargas de sus dos nudos (D-084). Un Excel puede omitirse (None) si ningún grupo pide
    cargas de su tipo. Con la tabla de coordenadas (D-130), cada zapata aislada lleva la ubicación de su nudo y el tipo
    (su grupo), y cada columna de las combinadas la suya."""
    groups: list[Group] = [(footing.id, footing.etabs_unique_names, BOTH) for footing in template.footings]
    groups += [(footing.id, tuple(column.etabs_unique_name for column in footing.columns), footing.etabs_kinds())
               for footing in template.combined_footings]
    joints, skipped = _joint_loads(template.load_factors, {"service": service, "factored": factored}, groups)
    locations = locations_by_joint(coordinates, [name for _, names, _ in groups for name in names])
    isolated = {footing.id for footing in template.footings}
    bases = {footing.id: footing.model_dump(mode="json", exclude={"id", "etabs_unique_names"}) for footing in template.footings}
    footings = [{"id": f"{joint.group}-{joint.label}", **bases[joint.group], "loads": joint.loads,
                 **({"typology": joint.group, **_located(locations, joint.unique_name)} if locations else {})}
                for joint in joints if joint.group in isolated]
    combined = _combined_footings(template, [joint for joint in joints if joint.group not in isolated], locations)
    project = template.model_dump(mode="json", exclude={"load_factors", "footings", "combined_footings", "etabs_files"})
    if footings:
        project["footings"] = footings
    if combined:
        project["combined_footings"] = combined
    items = footings + [{"loads": [load for column in footing["columns"] for load in column["loads"]]} for footing in combined]
    return project, _summary(items, skipped)


def build_footing_design_project(
    template: EtabsFootingDesignTemplate, service: Table | None, factored: Table | None, coordinates: Table | None = None
) -> tuple[dict[str, Any], FootingImportSummary]:
    """Proyecto de diseño por tipologías (D-069): una columna por nudo listado y no excluido, con su sección, sus casos
    de carga y, con la tabla de coordenadas, su ubicación (D-130). Los Unique Name de los Excel que no entran se avisan
    en el resumen y en la descripción (D-111)."""
    excluded = set(template.exclude_unique_names)
    groups: list[Group] = [(str(index), tuple(name for name in group.etabs_unique_names if name not in excluded), BOTH)
                           for index, group in enumerate(template.columns)]
    joints, skipped = _joint_loads(template.load_factors, {"service": service, "factored": factored}, groups)
    locations = locations_by_joint(coordinates, [joint.unique_name for joint in joints])
    sections = {str(index): group for index, group in enumerate(template.columns)}
    columns = [{"id": joint.label, "cx": sections[joint.group].cx, "cy": sections[joint.group].cy,
                **_located(locations, joint.unique_name), "loads": joint.loads} for joint in joints]
    project = template.model_dump(mode="json", exclude={"load_factors", "columns", "etabs_files", "exclude_unique_names"})
    project["columns"] = columns
    used = {joint.unique_name for joint in joints}
    present = {row["Unique Name"] for table in (service, factored) if table is not None for row in table.rows
               if row.get("Case Type") == "Combination"}
    omitted = tuple(sorted(present - used, key=_natural))
    if omitted:
        project["description"] = (f"{project['description']} Unique Name de ETABS que no entran al diseño (no listados o "
                                  f"excluidos): {', '.join(omitted)}.")
    return project, replace(_summary(columns, skipped), omitted=omitted)


def _natural(name: str) -> tuple[int, str]:
    """Orden de los Unique Name: los numéricos por su valor y luego los demás."""
    return (int(name), "") if name.isdigit() else (2**63, name)


def build_combined_design_project(
    template: EtabsCombinedDesignTemplate, service: Table | None, factored: Table | None
) -> tuple[dict[str, Any], FootingImportSummary]:
    """Proyecto de diseño de la zapata combinada (D-112): cada columna con las cargas de su nudo de los tipos que vienen
    de ETABS y las de la plantilla de los demás. Un Excel puede omitirse (None) si ningún tipo sale de él."""
    group: Group = ("diseno", tuple(column.etabs_unique_name for column in template.columns), template.etabs_kinds())
    joints, skipped = _joint_loads(template.load_factors, {"service": service, "factored": factored}, [group])
    loads = {joint.unique_name: joint.loads for joint in joints}
    columns = [{**column.model_dump(mode="json", exclude={"etabs_unique_name", "loads", "dowels", "band", "band_top"}, exclude_none=True),
                "loads": [*loads.get(column.etabs_unique_name, []), *column.loads]} for column in template.columns]
    project = template.model_dump(mode="json", exclude={"load_factors", "loads_source", "columns", "etabs_files"})
    project["columns"] = columns
    return project, _summary([{"loads": [load for column in columns for load in column["loads"]]}], skipped)
