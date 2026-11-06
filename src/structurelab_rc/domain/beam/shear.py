"""Verificación a cortante de vigas por estación cuando la torsión es despreciable (Tu < φTth)."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.flexure import MIN_DEPTH_RATIO, nominal_flexure, section_states, steel_layers
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station

STRENGTH = "Cortante: resistencia"
SECTION = "Cortante: dimensiones de la seccion"
MIN_REINFORCEMENT = "Cortante: refuerzo minimo"
SPACING = "Cortante: separacion maxima"
STRENGTH_V3 = "Cortante V3: resistencia"
SECTION_V3 = "Cortante V3: dimensiones de la seccion"
MIN_REINFORCEMENT_V3 = "Cortante V3: refuerzo minimo"
SPACING_V3 = "Cortante V3: separacion maxima"
INTERACTION = "Cortante: interaccion V2-V3"
_CLOSED_LEGS = 2


@dataclass(frozen=True)
class ShearTerms:
    """Términos de cortante de una estación, en N, mm y MPa. transverse es n·Ab/s de los estribos."""

    lam: float
    d: float
    vc: float
    vs_max: float
    fyt: float
    transverse: float


def missing_demands(station: Station) -> Check | None:
    demands = station.demands
    if None in (demands.vu, demands.v3, demands.pu, demands.mu, demands.m2, demands.tu):
        return check_from_errors(STRENGTH, [incomplete("El cortante y la torsion requieren Vu, V3, Pu, Mu, M2 y Tu")])
    return None


def concrete_lambda(profile: Profile, materials: Materials) -> float | Check:
    lam = profile.strength_assumptions.concrete_lambda(materials.concrete)
    if lam is None:
        return check_from_errors(STRENGTH, [blocked("El concreto liviano no esta implementado (D-028)")])
    return lam


def _tension_steel(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[float, float] | Check:
    """Área del acero a tracción y d del cortante: su centroide, no menor que 0.8h (D-043)."""
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
    centroid = sum(layer.depth * layer.area for layer in tension) / area
    return area, max(centroid, MIN_DEPTH_RATIO * member.section.h)


def shear_terms(given: StationInput, minimum: float) -> ShearTerms | Check:
    """Vc con Av ≥ Av,min cuando n·Ab/s alcanza minimum (Av,min/s, o (Av + 2At)min/s con torsión)."""
    profile, materials, member, station, bars = given.profile, given.materials, given.member, given.station, given.bars
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, Check):
        return lam
    steel = _tension_steel(profile, materials, member, station, bars)
    if isinstance(steel, Check):
        return steel
    tension_area, d = steel
    demands, section, shear = station.demands, member.section, profile.shear
    assert demands.vu is not None and demands.pu is not None and demands.mu is not None
    stirrups = station.layout.stirrups
    specs = {bar.designation: bar for bar in bars}
    transverse = 0.0 if stirrups is None else stirrups.legs * specs[stirrups.designation].area_mm2 / stirrups.spacing
    vc = shear.concrete_shear(
        fc=materials.fc, lam=lam, bw=section.bw, d=d, h=section.h, rho_w=tension_area / (section.bw * d), nu=demands.pu,
        ag=section.area, vu=abs(demands.vu), mu=abs(demands.mu), av_ge_min=transverse >= minimum,
    )
    fyt = min(materials.fyt, shear.max_stirrup_yield())
    return ShearTerms(lam, d, vc, shear.max_steel_shear(materials.fc, section.bw, d), fyt, transverse)


def leg_spacing_across(member: Member, station: Station, bars: Sequence[RebarSpec]) -> float | None:
    """Separación entre ramas de estribo a lo ancho, de centro a centro."""
    stirrups = station.layout.stirrups
    if stirrups is None:
        return None
    diameter = {bar.designation: bar.diameter_mm for bar in bars}[stirrups.designation]
    return (member.section.bw - 2 * member.section.cover - diameter) / (stirrups.legs - 1)


def shear_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    """Verificaciones a cortante de una estación dentro del alcance de viga y con torsión despreciable."""
    shear, section = profile.shear, member.section
    fyt = min(materials.fyt, shear.max_stirrup_yield())
    av_min_s = shear.min_shear_reinforcement(materials.fc, section.bw, fyt)
    terms = shear_terms(StationInput(profile, materials, member, station, bars), av_min_s)
    if isinstance(terms, Check):
        return (terms,)
    assert station.demands.vu is not None
    fc, bw, phi, d, vc = materials.fc, section.bw, shear.strength_reduction(), terms.d, terms.vc
    clauses = shear.clauses()
    vs = shear.steel_shear(terms.transverse, fyt, d, 1.0)
    vu = abs(station.demands.vu)
    capacity = phi * (vc + min(vs, terms.vs_max))
    checks = [
        Check(STRENGTH, Status.PASS if capacity >= vu else Status.FAIL, clause=clauses["strength"],
              demand=vu, capacity=capacity, unit="N", values=(("phi", phi), ("Vc", vc), ("Vs", vs), ("d", d))),
        Check(SECTION, Status.PASS if vu <= phi * (vc + terms.vs_max) else Status.FAIL, clause=clauses["section"],
              demand=vu, capacity=phi * (vc + terms.vs_max), unit="N"),
    ]
    threshold = shear.min_reinforcement_threshold(vc, fc, terms.lam, bw, d, shear.min_reinforcement_exempt(section.h, bw, section.hf))
    if threshold is None or vu <= threshold:
        checks.append(Check(MIN_REINFORCEMENT, Status.PASS, clause=clauses["min_reinforcement"], note="No se requiere Av,min"))
    else:
        status = Status.PASS if terms.transverse >= av_min_s else Status.FAIL
        checks.append(Check(MIN_REINFORCEMENT, status, clause=clauses["min_reinforcement"],
                            demand=av_min_s, capacity=terms.transverse, unit="mm2/mm"))
    stirrups = station.layout.stirrups
    if stirrups is None:
        checks.append(Check(SPACING, Status.PASS, clause=clauses["spacing"], note="Sin estribos"))
        return tuple(checks)
    required_vs = max(vu / phi - vc, 0.0)
    along = shear.max_spacing(required_vs, fc, bw, d)
    across_limit = shear.max_leg_spacing_across(required_vs, fc, bw, d)
    across = leg_spacing_across(member, station, bars) or 0.0
    ok = stirrups.spacing <= along and (across_limit is None or across <= across_limit)
    extra = () if across_limit is None else (("across", across), ("across_max", across_limit))
    checks.append(Check(SPACING, Status.PASS if ok else Status.FAIL, clause=clauses["spacing"],
                        demand=stirrups.spacing, capacity=along, unit="mm", values=extra))
    return tuple(checks)


def _weak_tension(given: StationInput) -> tuple[float, float] | Check:
    """Área a tracción del estado de M2 solo y d del cortante V3: su centroide, no menor que 0.8bw (D-047)."""
    try:
        states = section_states(given)
    except NoEquilibrium:
        return check_from_errors(STRENGTH_V3, [blocked("Sin equilibrio en el eje debil no se puede definir d")])
    if isinstance(states, StructuredError):
        return check_from_errors(STRENGTH_V3, [states])
    tension = [bar for bar in states[1].bars if bar.strain > 0]
    area = sum(bar.area for bar in tension)
    if area == 0:
        return check_from_errors(STRENGTH_V3, [blocked("No hay acero a traccion en el eje debil para definir d")])
    centroid = sum(bar.depth * bar.area for bar in tension) / area
    return area, max(centroid, MIN_DEPTH_RATIO * given.member.section.bw)


def weak_shear_checks(given: StationInput, at_s: float = 0.0) -> tuple[Check, ...]:
    """Cortante V3 (D-046): ancho h, d del estado girado y ramas horizontales (2 en estribo cerrado, 1 en abierto).

    Con torsión (at_s > 0), las ramas horizontales cumplen Av3/s + 2At/s ≤ (ramas horizontales)·Ab/s.
    """
    profile, materials, member, station = given.profile, given.materials, given.member, given.station
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, Check):
        return (lam,)
    steel = _weak_tension(given)
    if isinstance(steel, Check):
        return (steel,)
    area, d = steel
    shear, section, demands, stirrups = profile.shear, member.section, station.demands, station.layout.stirrups
    assert demands.v3 is not None and demands.m2 is not None and demands.pu is not None
    width, phi, clauses = section.h, shear.strength_reduction(), shear.clauses()
    fyt = min(materials.fyt, shear.max_stirrup_yield())
    specs = {bar.designation: bar for bar in given.bars}
    legs = 0 if stirrups is None else (_CLOSED_LEGS if stirrups.closed else 1)
    horizontal = 0.0 if stirrups is None else legs * specs[stirrups.designation].area_mm2 / stirrups.spacing
    av_min_s = shear.min_shear_reinforcement(materials.fc, width, fyt)
    vc = shear.concrete_shear(
        fc=materials.fc, lam=lam, bw=width, d=d, h=section.bw, rho_w=area / (width * d), nu=demands.pu, ag=section.area,
        vu=abs(demands.v3), mu=abs(demands.m2), av_ge_min=horizontal >= av_min_s,
    )
    vs, vs_max, vu = shear.steel_shear(horizontal, fyt, d, 1.0), shear.max_steel_shear(materials.fc, width, d), abs(demands.v3)
    values = (("phi", phi), ("Vc", vc), ("Vs", vs), ("d", d))
    if at_s > 0:
        required = max(vu / phi - vc, 0.0) / (fyt * d) + 2 * at_s
        strength = Check(STRENGTH_V3, Status.PASS if required <= horizontal else Status.FAIL, clause=clauses["strength"],
                         demand=required, capacity=horizontal, unit="mm2/mm", values=(*values, ("At/s", at_s)),
                         note="Ramas horizontales con cortante V3 y torsion")
    else:
        capacity = phi * (vc + min(vs, vs_max))
        strength = Check(STRENGTH_V3, Status.PASS if capacity >= vu else Status.FAIL, clause=clauses["strength"],
                         demand=vu, capacity=capacity, unit="N", values=values)
    checks = [
        strength,
        Check(SECTION_V3, Status.PASS if vu <= phi * (vc + vs_max) else Status.FAIL, clause=clauses["section"],
              demand=vu, capacity=phi * (vc + vs_max), unit="N"),
    ]
    exempt = shear.min_reinforcement_exempt(section.bw, width, None)
    threshold = shear.min_reinforcement_threshold(vc, materials.fc, lam, width, d, exempt)
    if threshold is None or vu <= threshold:
        # Sin refuerzo a cortante exigido en esta dirección, tampoco se exige su separación (D-048).
        note = "V3 no exige refuerzo a cortante: no se requiere Av,min ni se limita la separacion"
        checks.append(Check(MIN_REINFORCEMENT_V3, Status.PASS, clause=clauses["min_reinforcement"], note=note))
        checks.append(Check(SPACING_V3, Status.PASS, clause=clauses["spacing"], note=note))
        return tuple(checks)
    checks.append(Check(MIN_REINFORCEMENT_V3, Status.PASS if horizontal >= av_min_s else Status.FAIL,
                        clause=clauses["min_reinforcement"], demand=av_min_s, capacity=horizontal, unit="mm2/mm"))
    if stirrups is None:
        checks.append(Check(SPACING_V3, Status.FAIL, clause=clauses["spacing"], note="V3 exige refuerzo a cortante y no hay estribos"))
        return tuple(checks)
    required_vs = max(vu / phi - vc, 0.0)
    along = shear.max_spacing(required_vs, materials.fc, width, d)
    across_limit = shear.max_leg_spacing_across(required_vs, materials.fc, width, d)
    # Lo análogo a "a lo ancho" en V3 es la separación vertical entre las ramas horizontales del estribo cerrado.
    across = section.h - 2 * section.cover - specs[stirrups.designation].diameter_mm if legs == _CLOSED_LEGS else None
    ok = stirrups.spacing <= along and (across_limit is None or across is None or across <= across_limit)
    extra = () if across_limit is None or across is None else (("across", across), ("across_max", across_limit))
    checks.append(Check(SPACING_V3, Status.PASS if ok else Status.FAIL, clause=clauses["spacing"],
                        demand=stirrups.spacing, capacity=along, unit="mm", values=extra))
    return tuple(checks)


def interaction_check(profile: Profile, checks: tuple[Check, ...]) -> Check | None:
    """Interacción de V2 y V3 (ACI 22.5.1.10 y 22.5.1.11); None si falta una dirección o el perfil no la exige."""
    found = {check.name: check for check in checks}
    strong, weak = found.get(STRENGTH), found.get(STRENGTH_V3)
    if strong is None or weak is None or weak.unit != "N" or not strong.capacity or not weak.capacity:
        return None
    ratio_2, ratio_3 = (strong.demand or 0.0) / strong.capacity, (weak.demand or 0.0) / weak.capacity
    result = profile.shear.biaxial_interaction(ratio_2, ratio_3)
    if result is None:
        return None
    return Check(INTERACTION, Status.PASS if result else Status.FAIL, clause=profile.shear.clauses()["biaxial"],
                 demand=ratio_2 + ratio_3, capacity=1.5, values=(("Vu2/phiVn2", ratio_2), ("Vu3/phiVn3", ratio_3)))
