"""Proyecto de cabezales a partir de las tablas de ETABS (D-138).

Con las cargas de la columna, las tablas "Joint Reactions" como en las zapatas (io/etabs/footings.py): P = FZ,
Vx = −FX, Vy = −FY, Mx = −MX y My = −MY. Con las de los pilotes, las tablas "Element Forces - Columns" del elemento que
modela cada pilote, en la estación declarada (etabs_station, en m): ETABS da las fuerzas internas en la cara positiva
de la sección (la del tramo inferior, el pilote), en ejes locales; sobre el cabezal actúan las opuestas. Con el eje 2 a
un ángulo θ de X global (0 por omisión: eje 2 = X, eje 3 = Y, eje 1 hacia arriba):

    P = −P_etabs (compresión positiva)
    Vx = −V2·cos θ + V3·sen θ        Vy = −V2·sen θ − V3·cos θ
    Mx = −M2·cos θ + M3·sen θ        My = −M2·sen θ − M3·cos θ

La torsión T no carga el cabezal. Las combinaciones que entran salen del Excel de combinaciones (D-137).
"""

import math
from typing import Any

from structurelab_rc.errors import invalid_input
from structurelab_rc.io.etabs.combinations import Combination
from structurelab_rc.io.etabs.footings import BOTH, FootingImportSummary, Group, TableSpec, joint_loads, locations_by_joint
from structurelab_rc.io.etabs.importer import EtabsImportError, case_label
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.layout import public
from structurelab_rc.model.template import EtabsPileCapTemplate, LoadFactors

PILE_SHEET = "Element Forces - Columns"
PILE_UNITS = {"Station": "m", "P": "kN", "V2": "kN", "V3": "kN", "M2": "kN-m", "M3": "kN-m"}
PILE_COLUMNS = ("Unique Name", "Output Case", "Case Type", "Step Type", *PILE_UNITS)
_STATION_TOLERANCE = 1e-6  # m


def _pile_spec(angles: dict[str, float]) -> TableSpec:
    """Las filas de un pilote pasan a la acción sobre el cabezal en ejes globales, con el ángulo de su eje local 2."""

    def convert(row: dict[str, str], kind: str, factors: LoadFactors) -> dict[str, Any]:
        theta = math.radians(angles[row["Unique Name"]])
        cos, sin = math.cos(theta), math.sin(theta)
        v2, v3, m2, m3 = (float(row[key]) for key in ("V2", "V3", "M2", "M3"))
        return {"case": case_label(row), "kind": kind, "dead_factor": factors.dead, "live_factor": factors.live,
                "seismic": factors.seismic, "P_kN": -float(row["P"]), "Vx_kN": -v2 * cos + v3 * sin, "Vy_kN": -v2 * sin - v3 * cos,
                "Mx_kNm": -m2 * cos + m3 * sin, "My_kNm": -m2 * sin - m3 * cos}

    return TableSpec(PILE_COLUMNS, PILE_UNITS, convert)


def _at_station(table: Table | None, stations: dict[str, float]) -> Table | None:
    """La tabla con solo la estación declarada de cada pilote (las filas de otros elementos quedan, y se ignoran después);
    lanza EtabsImportError si un pilote no tiene esa estación."""
    if table is None or "Station" not in table.headers or "Unique Name" not in table.headers:
        return table
    found: dict[str, set[float]] = {name: set() for name in stations}
    rows = []
    for row in table.rows:
        name = row["Unique Name"]
        if name not in stations:
            rows.append(row)
            continue
        station = float(row["Station"])
        found[name].add(station)
        if abs(station - stations[name]) <= _STATION_TOLERANCE:
            rows.append(row)
    errors = [invalid_input(f"El Unique Name '{name}' no tiene la estacion {stations[name]:g} m; tiene "
                            f"{', '.join(f'{value:g}' for value in sorted(values)) or 'ninguna'}")
              for name, values in found.items() if not any(abs(value - stations[name]) <= _STATION_TOLERANCE for value in values)]
    if errors:
        raise EtabsImportError(tuple(errors))
    return Table(table.headers, table.units, tuple(rows))


def build_pile_cap_project(
    template: EtabsPileCapTemplate, tables: tuple[Table | None, Table | None], combinations: dict[str, Combination],
    coordinates: Table | None = None,
) -> tuple[dict[str, Any], FootingImportSummary]:
    """Proyecto de cabezales en el formato de entrada JSON: cada cabezal de la plantilla con las cargas de su columna o
    las de cada uno de sus pilotes y, con la tabla de coordenadas (Joint Location), la ubicación de su columna y su tipo
    (su id) para la planta de localización (D-130)."""
    if coordinates is not None:
        missing = [cap.id for cap in template.pile_caps if cap.column_joint is None]
        if missing:
            raise EtabsImportError(tuple(invalid_input(f"El cabezal '{name}' necesita column_unique_name: la plantilla declara la "
                                                       "tabla de coordenadas") for name in missing))
    locations = locations_by_joint(coordinates, [joint for cap in template.pile_caps if (joint := cap.column_joint)])
    service, factored = tables
    if template.from_piles:
        stations = {pile.etabs_unique_name: cap.etabs_station for cap in template.pile_caps for pile in cap.piles
                    if pile.etabs_unique_name is not None and cap.etabs_station is not None}
        angles = {pile.etabs_unique_name: pile.angle for cap in template.pile_caps for pile in cap.piles if pile.etabs_unique_name}
        groups: list[Group] = [(cap.id, tuple(name for pile in cap.piles if (name := pile.etabs_unique_name)), BOTH)
                               for cap in template.pile_caps]
        given = {"service": _at_station(service, stations), "factored": _at_station(factored, stations)}
        joints, skipped, ignored = joint_loads(combinations, given, groups, _pile_spec(angles))
    else:
        groups = [(cap.id, (cap.etabs_unique_name,), BOTH) for cap in template.pile_caps if cap.etabs_unique_name]
        joints, skipped, ignored = joint_loads(combinations, {"service": service, "factored": factored}, groups)
    loads = {(joint.group, joint.unique_name): joint.loads for joint in joints}
    caps = []
    for cap in template.pile_caps:
        body = cap.model_dump(mode="json", exclude={"etabs_unique_name", "etabs_station", "column_unique_name", "piles"},
                              exclude_none=True)
        if cap.column_joint in locations:
            body.update(location=locations[cap.column_joint], typology=cap.id)
        piles = [{"id": pile.id, "x": pile.x, "y": pile.y,
                  **({"loads": loads[(cap.id, pile.etabs_unique_name)]} if pile.etabs_unique_name else {})} for pile in cap.piles]
        column = {"loads": loads[(cap.id, cap.etabs_unique_name)]} if cap.etabs_unique_name else {}
        caps.append({**body, "piles": piles, **column})
    project = template.model_dump(mode="json", exclude={"pile_caps", "etabs_files"}, exclude_none=True)
    project["pile_caps"] = caps
    every = [load for cap in caps for load in [*cap.get("loads", []), *(load for pile in cap["piles"] for load in pile.get("loads", []))]]
    summary = FootingImportSummary(len(caps), tuple(sorted({load["case"] for load in every if load["kind"] == "service"})),
                                   tuple(sorted({load["case"] for load in every if load["kind"] == "factored"})), skipped,
                                   ignored_combinations=ignored)
    return public(project), summary
