"""Verificaciones de un cabezal sobre pilotes (D-138), como domain/footing/checks.py: arma el análisis una vez
(domain/pile_cap/loads.py) y reúne las revisiones de cada tema.

- Geometría: empotramiento, borde y tolerancia de mala ubicación mínimos del perfil (ACI 13.4.6.3 y 13.4.1.4; NSR-10 no
  los fija).
- Geotécnicas con los casos de servicio (service.py).
- Flexión de las mallas (flexure.py), con la separación mínima de la zapata.
- Cortante y punzonamiento (shear.py).
- Desarrollo, pasadores y aplastamiento: los de la zapata (domain/footing/connection.py).
"""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.connection import column_connection_checks
from structurelab_rc.domain.footing.spacing import footing_min_spacing_checks
from structurelab_rc.domain.pile_cap.flexure import cap_rules, flexure_checks
from structurelab_rc.domain.pile_cap.loads import CapAnalysis, analyze
from structurelab_rc.domain.pile_cap.outline import edge_distance
from structurelab_rc.domain.pile_cap.service import service_checks
from structurelab_rc.domain.pile_cap.shear import shear_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil

EMBEDMENT = "Cabezal: empotramiento del pilote"
EDGE = "Cabezal: borde del pilote"
MISLOCATION = "Cabezal: tolerancia de mala ubicacion"
STRUCTURAL = "Cabezal: verificacion estructural"


def _requirement(name: str, given: tuple[float, float, str], cap: PileCap, note: str = "") -> Check:
    """Un mínimo del perfil: (mínimo, valor declarado o medido, numeral)."""
    minimum, value, clause = given
    return Check(name, Status.PASS if value >= minimum else Status.FAIL, clause=clause, member=cap.id, demand=minimum, capacity=value,
                 unit="mm", note=note)


def _geometry_checks(basis: Basis, cap: PileCap) -> list[Check]:
    """Empotramiento, borde y tolerancia mínimos del perfil; NSR-10 no los fija (D-138)."""
    rules = basis.profile.pile_cap
    clauses = rules.clauses()
    checks = []
    embedment = rules.min_embedment()
    if embedment is not None:
        checks.append(_requirement(EMBEDMENT, (embedment, cap.pile.embedment, clauses["embedment"]), cap))
    edge = rules.min_edge_distance()
    if edge is not None:
        distance, pile = min((edge_distance(cap, (item.x, item.y)) - cap.pile.size / 2, item.id) for item in cap.piles)
        checks.append(_requirement(EDGE, (edge, distance, clauses["edge"]), cap, f"Pilote {pile}"))
    tolerance = rules.min_mislocation()
    if tolerance is not None:
        checks.append(_requirement(MISLOCATION, (tolerance, cap.mislocation, clauses["mislocation"]), cap))
    return checks


def cap_analysis(basis: Basis, cap: PileCap, soil: PileCapSoil) -> CapAnalysis:
    """El análisis del cabezal con la interpolación de las reacciones del perfil."""
    return analyze(cap, soil, basis.profile.pile_cap.reaction_share)


def pile_cap_checks(basis: Basis, cap: PileCap, soil: PileCapSoil, analysis: CapAnalysis | None = None) -> list[Check]:
    """Todas las verificaciones del cabezal; analysis, si ya se calculó (el motor lo reutiliza en el resultado y el
    despiece)."""
    analysis = analysis or cap_analysis(basis, cap, soil)
    checks = [*_geometry_checks(basis, cap), *service_checks(basis, cap, analysis.cases, soil)]
    if not analysis.factored:
        error = incomplete("El cabezal no tiene casos mayorados", member=cap.id)
        return [*checks, Check(STRUCTURAL, Status.INCOMPLETE, (error,), member=cap.id)]
    loads = [(item.case.case, item.case.column) for item in analysis.factored]
    return [*checks, *flexure_checks(basis, cap, analysis), *footing_min_spacing_checks(basis, cap), *shear_checks(basis, cap, analysis),
            *column_connection_checks(basis, cap, (list(analysis.moments), cap_rules(basis, cap)), loads)]
