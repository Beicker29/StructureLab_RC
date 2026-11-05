"""Verificación a cortante de vigas por estación, con torsión despreciable (Tu < φTth)."""

from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.flexure import nominal_flexure, steel_layers
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete
from structurelab_rc.mechanics.flexure import NoEquilibrium
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station

STRENGTH = "Cortante: resistencia"
SECTION = "Cortante: dimensiones de la seccion"
MIN_REINFORCEMENT = "Cortante: refuerzo minimo"
SPACING = "Cortante: separacion maxima"
TORSION = "Cortante: torsion despreciable"


def _not_evaluable(profile: Profile, materials: Materials, member: Member, station: Station) -> Check | None:
    """Verificación que impide evaluar el cortante de la estación, si la hay."""
    demands = station.demands
    if demands.vu is None or demands.pu is None or demands.mu is None or demands.tu is None:
        return check_from_errors(STRENGTH, [incomplete("El cortante requiere Vu, Pu, Mu y Tu")])
    lam = profile.strength_assumptions.concrete_lambda(materials.concrete)
    if lam is None:
        return check_from_errors(STRENGTH, [blocked("El concreto liviano no esta implementado (D-028)")])
    section = member.section
    # Umbral con la sección del alma: sin alas el umbral nunca es mayor que el de la norma (D-032).
    acp, pcp = section.bw * section.h, 2 * (section.bw + section.h)
    threshold = profile.torsion.threshold_torsion(materials.fc, lam, acp, pcp, demands.pu, section.area)
    limit = profile.torsion.strength_reduction() * threshold
    if abs(demands.tu) >= limit:
        error = blocked("Tu >= phi Tth: la torsion no es despreciable y su verificacion llega en 2C")
        clause = profile.torsion.clauses()["threshold"]
        return Check(TORSION, Status.BLOCKED, (error,), clause, demand=abs(demands.tu), capacity=limit, unit="N*mm")
    return None


def _tension_steel(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[float, float] | Check:
    """Área y profundidad del acero a tracción por flexión en la estación (d y ρw)."""
    layers = steel_layers(station.layout, bars)
    if isinstance(layers, StructuredError):
        return check_from_errors(STRENGTH, [layers])
    try:
        state = nominal_flexure(profile, materials, member.section, layers, station.demands)
    except NoEquilibrium:
        return check_from_errors(STRENGTH, [blocked("Sin equilibrio a flexion no se puede definir d")])
    if isinstance(state, StructuredError):
        return check_from_errors(STRENGTH, [state])
    tension = [layer for layer in state.layers if layer.strain > 0]
    area = sum(layer.area for layer in tension)
    if area == 0:
        return check_from_errors(STRENGTH, [blocked("No hay acero a traccion para definir d")])
    return area, sum(layer.depth * layer.area for layer in tension) / area


def shear_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    """Verificaciones a cortante de una estación que ya está dentro del alcance de viga."""
    blocking = _not_evaluable(profile, materials, member, station)
    if blocking is not None:
        return (blocking,)
    steel = _tension_steel(profile, materials, member, station, bars)
    if isinstance(steel, Check):
        return (steel,)
    tension_area, d = steel
    demands, section, shear = station.demands, member.section, profile.shear
    assert demands.vu is not None and demands.pu is not None and demands.mu is not None
    lam = profile.strength_assumptions.concrete_lambda(materials.concrete) or 1.0
    fc, bw, phi = materials.fc, section.bw, shear.strength_reduction()
    clauses = shear.clauses()
    fyt = min(materials.fyt, shear.max_stirrup_yield())
    stirrups = station.layout.stirrups
    specs = {bar.designation: bar for bar in bars}
    av_s = 0.0 if stirrups is None else stirrups.legs * specs[stirrups.designation].area_mm2 / stirrups.spacing
    av_min_s = shear.min_shear_reinforcement(fc, bw, fyt)
    vc = shear.concrete_shear(
        fc=fc, lam=lam, bw=bw, d=d, h=section.h, rho_w=tension_area / (bw * d), nu=demands.pu, ag=section.area,
        vu=abs(demands.vu), mu=abs(demands.mu), av_ge_min=av_s >= av_min_s,
    )
    vs = av_s * fyt * d if stirrups is None else shear.steel_shear(av_s * stirrups.spacing, fyt, d, stirrups.spacing)
    vs_max = shear.max_steel_shear(fc, bw, d)
    vu = abs(demands.vu)
    values = (("phi", phi), ("Vc", vc), ("Vs", vs), ("d", d))
    capacity = phi * (vc + min(vs, vs_max))
    checks = [
        Check(STRENGTH, Status.PASS if capacity >= vu else Status.FAIL, clause=clauses["strength"],
              demand=vu, capacity=capacity, unit="N", values=values),
        Check(SECTION, Status.PASS if vu <= phi * (vc + vs_max) else Status.FAIL, clause=clauses["section"],
              demand=vu, capacity=phi * (vc + vs_max), unit="N"),
    ]
    threshold = shear.min_reinforcement_threshold(vc, fc, lam, bw, d, shear.min_reinforcement_exempt(section.h, bw, section.hf))
    if threshold is None or vu <= threshold:
        checks.append(Check(MIN_REINFORCEMENT, Status.PASS, clause=clauses["min_reinforcement"], note="No se requiere Av,min"))
    else:
        checks.append(Check(MIN_REINFORCEMENT, Status.PASS if av_s >= av_min_s else Status.FAIL, clause=clauses["min_reinforcement"],
                            demand=av_min_s, capacity=av_s, unit="mm2/mm"))
    if stirrups is None:
        checks.append(Check(SPACING, Status.PASS, clause=clauses["spacing"], note="Sin estribos"))
        return tuple(checks)
    required_vs = max(vu / phi - vc, 0.0)
    along = shear.max_spacing(required_vs, fc, bw, d)
    across_limit = shear.max_leg_spacing_across(required_vs, fc, bw, d)
    across = (bw - 2 * section.cover - specs[stirrups.designation].diameter_mm) / (stirrups.legs - 1)
    ok = stirrups.spacing <= along and (across_limit is None or across <= across_limit)
    extra = () if across_limit is None else (("across", across), ("across_max", across_limit))
    checks.append(Check(SPACING, Status.PASS if ok else Status.FAIL, clause=clauses["spacing"],
                        demand=stirrups.spacing, capacity=along, unit="mm", values=extra))
    return tuple(checks)
