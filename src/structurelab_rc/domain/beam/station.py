"""Verificaciones de una estación de viga: alcance, flexión, y cortante o torsión combinada."""

from collections.abc import Sequence
from dataclasses import replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.deep import deep_beam_checks
from structurelab_rc.domain.beam.flexure import (
    MIN_REINFORCEMENT_M2,
    NET_TENSILE_STRAIN_BIAXIAL,
    NET_TENSILE_STRAIN_M2,
    flexure_checks,
    skin_check,
)
from structurelab_rc.domain.beam.shear import interaction_check, missing_demands, shear_checks, weak_shear_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.beam.torsion import TRANSVERSE, threshold_check, torsion_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station

SCOPE = "Viga: alcance"
_WEAK_AXIS = frozenset({NET_TENSILE_STRAIN_M2, NET_TENSILE_STRAIN_BIAXIAL, MIN_REINFORCEMENT_M2})


def _out_of_scope(profile: Profile, materials: Materials, member: Member, station: Station) -> Check | None:
    """El miembro debe ser viga y, si se conoce Pu, Pu < 0.10 f'c·Ag (D-024)."""
    if member.type != "beam":
        return check_from_errors(SCOPE, [blocked(f"El tipo de miembro '{member.type}' no esta implementado")])
    pu = station.demands.pu
    limit = profile.flexure.beam_axial_limit(materials.fc, member.section.area)
    if pu is not None and pu >= limit:
        error = blocked("Pu >= 0.10 f'c Ag: el miembro no puede tratarse como viga")
        clause = profile.flexure.clauses()["axial_limit"]
        return Check(SCOPE, Status.BLOCKED, (error,), clause, demand=pu, capacity=limit, unit="N")
    return None


def shear_and_torsion_checks(given: StationInput) -> tuple[Check, ...]:
    """Cortante y torsión de una estación (D-088: común a las vigas y a la viga larga de la zapata combinada). Si Tu es
    despreciable, el cortante solo; si no, el umbral y la verificación combinada de torsión y cortante. En modo
    cimentación no hay eje débil ni interacción (D-083)."""
    profile, materials, member, station = given.profile, given.materials, given.member, given.station
    missing = missing_demands(station)
    if missing is not None:
        return (missing,)
    threshold = threshold_check(profile, materials, member, station)
    if threshold is None:
        if given.foundation:  # la zapata no tiene cortante V3: sin eje débil ni interacción (D-083)
            return shear_checks(given)
        checks = (*shear_checks(given), *weak_shear_checks(given))
        interaction = interaction_check(profile, checks)
        return checks if interaction is None else (*checks, interaction)
    if threshold.status is not Status.PASS:
        return (threshold,)
    torsion = torsion_checks(given)
    at_s = next((dict(check.values).get("At/s", 0.0) for check in torsion if check.name == TRANSVERSE), 0.0)
    if given.foundation:
        return threshold, *torsion
    return threshold, *torsion, *weak_shear_checks(given, at_s)


def checks_for(given: StationInput) -> tuple[Check, ...]:
    """Verificaciones de una estación; given.foundation marca la dirección larga de una zapata combinada (D-081)."""
    profile, materials, member, station = given.profile, given.materials, given.member, given.station
    blocking = _out_of_scope(profile, materials, member, station)
    if blocking is not None:
        checks: tuple[Check, ...] = (blocking,)
    else:
        skin = skin_check(given)
        # La excepción de 4/3 del As,min la declara cada elemento (min_steel_exception, D-123).
        flexure = flexure_checks(given)
        if given.foundation:  # la zapata no tiene M2: las verificaciones del eje débil no aplican (D-083)
            flexure = tuple(check for check in flexure if check.name not in _WEAK_AXIS)
        deep = deep_beam_checks(given) if member.deep_beam else ()
        checks = (*flexure, *(() if skin is None else (skin,)), *shear_and_torsion_checks(given), *deep)
    return tuple(replace(check, member=member.id, z=station.z, case=station.case) for check in checks)


def flexure_station_checks(given: StationInput) -> tuple[Check, ...]:
    """Solo la flexión de una estación en modo cimentación (con el refuerzo superficial, que depende de la cara en
    tracción), sin el eje débil: la segunda cara de una sección de la combinada rectangular con momentos de Wood-Armer en
    las dos (D-118), cuyo cortante ya se revisó con la primera."""
    member, station = given.member, given.station
    skin = skin_check(given)
    checks = (*(check for check in flexure_checks(given) if check.name not in _WEAK_AXIS), *(() if skin is None else (skin,)))
    return tuple(replace(check, member=member.id, z=station.z, case=station.case) for check in checks)


def station_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    return checks_for(StationInput(profile, materials, member, station, bars))
