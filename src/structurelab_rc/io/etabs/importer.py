"""Construcción del proyecto JSON a partir de la tabla "Element Forces - Beams" de ETABS (D-042).

Convierte el formato de ETABS al formato de entrada del proyecto: m a mm y P con la compresión positiva.
Las unidades internas (N, mm) solo se aplican después, al cargar el proyecto (model/).
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.template import EtabsTemplate, TemplateMember

SHEET = "Element Forces - Beams"
REQUIRED_UNITS = {"Station": "m", "P": "kN", "V2": "kN", "V3": "kN", "T": "kN-m", "M2": "kN-m", "M3": "kN-m"}
REQUIRED_COLUMNS = ("Unique Name", "Output Case", "Case Type", "Step Type", *REQUIRED_UNITS)
_MM_PER_M = 1000.0


class EtabsImportError(Exception):
    def __init__(self, errors: tuple[StructuredError, ...]) -> None:
        super().__init__("; ".join(error.message for error in errors))
        self.errors = errors


@dataclass(frozen=True)
class ImportSummary:
    members: int
    stations: int
    cases: tuple[str, ...]
    skipped_rows: int


def _check_table(table: Table) -> list[StructuredError]:
    missing = [column for column in REQUIRED_COLUMNS if column not in table.headers]
    errors = [invalid_input(f"Falta la columna '{column}' en la tabla de ETABS") for column in missing]
    for column, unit in REQUIRED_UNITS.items():
        if column in table.headers and table.units.get(column) != unit:
            errors.append(invalid_input(f"La columna '{column}' debe venir en {unit}; viene en '{table.units.get(column)}'"))
    return errors


def case_label(row: dict[str, str]) -> str:
    """Las filas Max y Min de una combinación con envolvente son dos estados de carga distintos."""
    step = row["Step Type"].strip()
    return f"{row['Output Case']} ({step})" if step else row["Output Case"]


def _segment_layout(member: TemplateMember, z: float) -> dict[str, Any] | None:
    for segment in member.segments:
        if segment.start - 1e-6 <= z <= segment.end + 1e-6:
            return segment.layout.model_dump(mode="json", exclude_none=False)
    return None


def _member_rows(template: EtabsTemplate, table: Table) -> tuple[dict[str, list[dict[str, str]]], int]:
    wanted = set(template.combinations) if template.combinations is not None else None
    by_member: dict[str, list[dict[str, str]]] = defaultdict(list)
    skipped = 0
    for row in table.rows:
        if row["Case Type"] != "Combination" or (wanted is not None and row["Output Case"] not in wanted):
            skipped += 1
            continue
        by_member[row["Unique Name"]].append(row)
    return by_member, skipped


def _stations(member: TemplateMember, rows: list[dict[str, str]], errors: list[StructuredError]) -> list[dict[str, Any]]:
    stations = []
    for row in rows:
        z = float(row["Station"]) * _MM_PER_M
        layout = _segment_layout(member, z)
        if layout is None:
            errors.append(invalid_input("La estacion de ETABS no cae en ningun tramo de armado", member=member.id, z=z))
            continue
        if z > member.length + 1e-6:
            errors.append(invalid_input("La estacion de ETABS supera la longitud del miembro", member=member.id, z=z))
            continue
        # Los ejes de la sección son los de ETABS (D-044): solo P cambia de signo, para que la compresión sea positiva.
        demands = {
            "Pu_kN": -float(row["P"]),
            "Mu_kNm": float(row["M3"]),
            "M2_kNm": float(row["M2"]),
            "Vu_kN": float(row["V2"]),
            "V3_kN": float(row["V3"]),
            "Tu_kNm": float(row["T"]),
        }
        stations.append({"z": z, "case": case_label(row), "layout": layout, "demands": demands})
    return stations


def build_project(template: EtabsTemplate, table: Table) -> tuple[dict[str, Any], ImportSummary]:
    """Proyecto en el formato de entrada JSON; lanza EtabsImportError con todos los problemas encontrados."""
    errors = _check_table(table)
    if errors:
        raise EtabsImportError(tuple(errors))
    by_member, skipped = _member_rows(template, table)
    present = {row["Output Case"] for rows in by_member.values() for row in rows}
    for name in sorted(set(template.combinations or ()) - present):
        errors.append(invalid_input(f"La combinacion '{name}' no aparece en la tabla de ETABS"))
    members = []
    for member in template.members:
        rows = by_member.get(member.etabs_unique_name, [])
        if not rows:
            message = f"El Unique Name '{member.etabs_unique_name}' no tiene combinaciones en la tabla"
            errors.append(invalid_input(message, member=member.id))
            continue
        data = member.model_dump(mode="json", by_alias=True, exclude={"etabs_unique_name", "segments"}, exclude_none=True)
        data["stations"] = _stations(member, rows, errors)
        members.append(data)
    if errors:
        raise EtabsImportError(tuple(errors))
    project = template.model_dump(mode="json", by_alias=True, exclude={"combinations", "members", "etabs_files"}, exclude_none=True)
    project["members"] = members
    cases = tuple(sorted({station["case"] for member in members for station in member["stations"]}))
    summary = ImportSummary(len(members), sum(len(member["stations"]) for member in members), cases, skipped)
    return project, summary
