"""Proyecto de zapatas a partir de dos tablas "Joint Reactions" de ETABS: servicio y mayoradas (D-052, D-055).

ETABS reporta la fuerza que el apoyo ejerce sobre la estructura; sobre la zapata actúa la opuesta. Por eso
P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY, en la base de la columna y en ejes globales. El traslado al
centroide de la base (altura y desplazamiento de la columna) lo hace el dominio. Las unidades internas (N, mm) solo
se aplican después, al cargar el proyecto (model/).
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.io.etabs.importer import EtabsImportError, case_label
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.template import EtabsFootingTemplate, LoadFactors

SHEET = "Joint Reactions"
REQUIRED_UNITS = {"FX": "kN", "FY": "kN", "FZ": "kN", "MX": "kN-m", "MY": "kN-m"}
REQUIRED_COLUMNS = ("Label", "Unique Name", "Output Case", "Case Type", "Step Type", *REQUIRED_UNITS)


@dataclass(frozen=True)
class FootingImportSummary:
    footings: int
    service_cases: tuple[str, ...]
    factored_cases: tuple[str, ...]
    skipped_rows: int


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
            "P_kN": float(row["FZ"]), "Vx_kN": -float(row["FX"]), "Vy_kN": -float(row["FY"]),
            "Mx_kNm": -float(row["MX"]), "My_kNm": -float(row["MY"])}


def build_footing_project(
    template: EtabsFootingTemplate, service: Table, factored: Table
) -> tuple[dict[str, Any], FootingImportSummary]:
    """Proyecto en el formato de entrada JSON, una zapata por nudo; lanza EtabsImportError con todos los problemas."""
    errors = _check_table(service, "servicio") + _check_table(factored, "cargas mayoradas")
    if errors:
        raise EtabsImportError(tuple(errors))
    service_rows, skipped_service = _rows_by_joint(service)
    factored_rows, skipped_factored = _rows_by_joint(factored)
    present = {row["Output Case"] for rows in (*service_rows.values(), *factored_rows.values()) for row in rows}
    for name in sorted(present - set(template.load_factors)):
        errors.append(invalid_input(f"La combinacion '{name}' no tiene factores de carga en la plantilla"))
    for name in sorted(set(template.load_factors) - present):
        errors.append(invalid_input(f"La combinacion '{name}' de la plantilla no aparece en las tablas de ETABS"))
    footings = []
    for footing_type in template.footings:
        base = footing_type.model_dump(mode="json", exclude={"id", "etabs_unique_names"})
        for unique_name in footing_type.etabs_unique_names:
            own_service, own_factored = service_rows.get(unique_name, []), factored_rows.get(unique_name, [])
            for rows, which in ((own_service, "servicio"), (own_factored, "cargas mayoradas")):
                if not rows:
                    errors.append(invalid_input(f"El Unique Name '{unique_name}' no tiene combinaciones en la tabla de {which}",
                                                member=footing_type.id))
            if not own_service or not own_factored:
                continue
            if any(row["Output Case"] not in template.load_factors for row in (*own_service, *own_factored)):
                continue
            loads = [_load(row, "service", template.load_factors[row["Output Case"]]) for row in own_service]
            loads += [_load(row, "factored", template.load_factors[row["Output Case"]]) for row in own_factored]
            footings.append({"id": f"{footing_type.id}-{own_service[0]['Label']}", **base, "loads": loads})
    if errors:
        raise EtabsImportError(tuple(errors))
    project = template.model_dump(mode="json", exclude={"load_factors", "footings"})
    project["footings"] = footings
    summary = FootingImportSummary(
        len(footings),
        tuple(sorted({load["case"] for footing in footings for load in footing["loads"] if load["kind"] == "service"})),
        tuple(sorted({load["case"] for footing in footings for load in footing["loads"] if load["kind"] == "factored"})),
        skipped_service + skipped_factored,
    )
    return project, summary
