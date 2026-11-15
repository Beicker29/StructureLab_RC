"""Revisiones geotécnicas del cabezal con los casos de servicio (D-138), como las de las zapatas (domain/footing/service.py).

Presión admisible de cada pilote a compresión (la mayor reacción, con +ΔR de la mala ubicación y, en ACI, la capacidad
aumentada 10 %, 13.4.1.4) y a tracción (con −ΔR); deslizamiento (la carga lateral de cada pilote); capacidad del grupo
(η·n·Qa) y, en los casos sin sismo (D+L), la excentricidad de la resultante de las reacciones respecto al centroide del
grupo. Las capacidades del suelo suben en los casos con sismo. Con pilotes alineados, el momento que no resisten queda
INCOMPLETE.
"""

import math
from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.pile_cap.loads import CapCase, group_centre, spread_on_cap
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete, invalid_input
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil

PILE_COMPRESSION = "Presion admisible del pilote: compresion"
PILE_TENSION = "Presion admisible del pilote: traccion"
PILE_LATERAL = "Deslizamiento del pilote"
GROUP = "Capacidad del grupo de pilotes"
ECCENTRICITY = "Excentricidad en servicio"
UNRESISTED = "Pilotes: momento no resistido"
_NEGLIGIBLE_FORCE = 1.0  # N
_NEGLIGIBLE_MOMENT = 1e3  # N·mm


@dataclass(frozen=True)
class _Where:
    """Dónde va una revisión: el cabezal, el caso y la nota (el pilote)."""

    member: str
    case: str
    note: str = ""


@dataclass(frozen=True)
class _Demand:
    """Una demanda frente a una capacidad opcional del suelo (None si no se declaró) y el campo que la declara."""

    value: float
    capacity: float | None
    field: str


def _optional_capacity(name: str, demand: _Demand, clause: str, where: _Where) -> Check:
    """Sin la capacidad, INCOMPLETE (no se supone)."""
    if demand.capacity is None:
        error = incomplete(f"Falta soil.{demand.field}: un pilote la necesita en este caso (no se supone)", member=where.member,
                           case=where.case)
        return Check(name, Status.INCOMPLETE, (error,), clause, member=where.member, case=where.case, demand=demand.value, unit="N",
                     note=where.note)
    return Check(name, Status.PASS if demand.value <= demand.capacity else Status.FAIL, clause=clause, member=where.member,
                 case=where.case, demand=demand.value, capacity=demand.capacity, unit="N", note=where.note)


def _scaled(capacity: float | None, factor: float) -> float | None:
    return None if capacity is None else factor * capacity


def _case_checks(basis: Basis, cap: PileCap, case: CapCase, soil: PileCapSoil) -> list[Check]:
    rules = basis.profile.pile_cap
    spread = 1.0 if spread_on_cap(cap) else 0.0
    seismic = soil.factor(case.load.seismic)
    mislocation = rules.mislocation_capacity_factor() if spread and cap.mislocation > 0 else 1.0
    clause = rules.clauses()["pile_capacity"]
    count, forces = range(len(cap.piles)), case.forces

    def where(index: int) -> _Where:
        return _Where(cap.id, case.case, f"Pilote {cap.piles[index].id}")

    reaction, index = max((case.reaction(index, spread), index) for index in count)
    capacity = mislocation * seismic * soil.pile_capacity_compression
    values = (("R pilote", forces.reactions[index]), ("delta R", spread * forces.spread[index]),
              ("Qa", soil.pile_capacity_compression), ("factor mala ubicacion", mislocation), ("factor sismo", seismic))
    checks = [Check(PILE_COMPRESSION, Status.PASS if reaction <= capacity else Status.FAIL, clause=clause, member=cap.id, case=case.case,
                    demand=max(reaction, 0.0), capacity=capacity, unit="N", values=values, note=where(index).note)]
    pull, index = min((case.reaction(index, -spread), index) for index in count)
    if pull < -_NEGLIGIBLE_FORCE:
        demand = _Demand(-pull, _scaled(soil.pile_capacity_tension, seismic), "pile_capacity_tension_kN")
        checks.append(_optional_capacity(PILE_TENSION, demand, clause, where(index)))
    lateral, index = max((math.hypot(*forces.shears[index]), index) for index in count)
    if lateral > _NEGLIGIBLE_FORCE:
        demand = _Demand(lateral, _scaled(soil.pile_capacity_lateral, seismic), "pile_capacity_lateral_kN")
        checks.append(_optional_capacity(PILE_LATERAL, demand, clause, where(index)))
    group = soil.group_efficiency * len(cap.piles) * seismic * soil.pile_capacity_compression
    checks.append(Check(GROUP, Status.PASS if case.total <= group else Status.FAIL, clause=clause, member=cap.id, case=case.case,
                        demand=max(case.total, 0.0), capacity=group, unit="N",
                        values=(("eficiencia", soil.group_efficiency), ("pilotes", float(len(cap.piles))), ("factor sismo", seismic))))
    if not case.load.seismic:
        checks.append(_eccentricity(cap, case, soil))
    return checks


def _eccentricity(cap: PileCap, case: CapCase, soil: PileCapSoil) -> Check:
    """La resultante vertical de las reacciones respecto al centroide del grupo no pasa de la excentricidad máxima
    declarada (decisión del usuario, D-138)."""
    reactions = case.forces.reactions
    total = sum(reactions)
    if total <= 0:
        error = invalid_input("La resultante de servicio no comprime el grupo de pilotes", member=cap.id, case=case.case)
        return Check(ECCENTRICITY, Status.FAIL, (error,), "D-138", member=cap.id, case=case.case, unit="mm")
    xc, yc = group_centre(cap)
    ex = sum(r * pile.x for r, pile in zip(reactions, cap.piles, strict=True)) / total - xc
    ey = sum(r * pile.y for r, pile in zip(reactions, cap.piles, strict=True)) / total - yc
    e = math.hypot(ex, ey)
    return Check(ECCENTRICITY, Status.PASS if e <= soil.max_eccentricity else Status.FAIL, clause="D-138", member=cap.id,
                 case=case.case, demand=e, capacity=soil.max_eccentricity, unit="mm", values=(("ex", ex), ("ey", ey)),
                 note="Resultante vertical respecto al centroide del grupo de pilotes")


def _unresisted(cap: PileCap, case: CapCase) -> list[Check]:
    if case.unresisted <= _NEGLIGIBLE_MOMENT:
        return []
    error = incomplete("Los pilotes estan alineados y no resisten el momento de la columna en la direccion normal a su eje: "
                       "requiere vigas de amarre o pilotes que tomen momento (no se suponen)", member=cap.id, case=case.case)
    return [Check(UNRESISTED, Status.INCOMPLETE, (error,), "D-138", member=cap.id, case=case.case, demand=case.unresisted, unit="N*mm")]


def service_checks(basis: Basis, cap: PileCap, cases: tuple[CapCase, ...], soil: PileCapSoil) -> list[Check]:
    """Las revisiones geotécnicas de los casos de servicio y el momento no resistido de todos los casos."""
    service = [check for case in cases if case.load.kind == "service" for check in _case_checks(basis, cap, case, soil)]
    return [*service, *(check for case in cases for check in _unresisted(cap, case))]
