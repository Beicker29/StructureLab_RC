"""Verificaciones de una estación de viga: alcance, flexión, y cortante o torsión combinada."""

from collections.abc import Sequence
from dataclasses import replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.flexure import flexure_checks
from structurelab_rc.domain.beam.shear import interaction_check, missing_demands, shear_checks, weak_shear_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.beam.torsion import TRANSVERSE, threshold_check, torsion_checks
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station

SCOPE = "Viga: alcance"


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


def _shear_and_torsion(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    missing = missing_demands(station)
    if missing is not None:
        return (missing,)
    given = StationInput(profile, materials, member, station, bars)
    threshold = threshold_check(profile, materials, member, station)
    if threshold is None:
        checks = (*shear_checks(profile, materials, member, station, bars), *weak_shear_checks(given))
        interaction = interaction_check(profile, checks)
        return checks if interaction is None else (*checks, interaction)
    if threshold.status is not Status.PASS:
        return (threshold,)
    torsion = torsion_checks(given)
    at_s = next((dict(check.values).get("At/s", 0.0) for check in torsion if check.name == TRANSVERSE), 0.0)
    return threshold, *torsion, *weak_shear_checks(given, at_s)


def station_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    blocking = _out_of_scope(profile, materials, member, station)
    if blocking is not None:
        checks: tuple[Check, ...] = (blocking,)
    else:
        flexure = flexure_checks(profile, materials, member, station, bars)
        checks = (*flexure, *_shear_and_torsion(profile, materials, member, station, bars))
    return tuple(replace(check, member=member.id, z=station.z) for check in checks)
