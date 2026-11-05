"""Verificación a cortante de vigas por estación cuando la torsión es despreciable (Tu < φTth)."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.flexure import nominal_flexure, steel_layers
from structurelab_rc.domain.beam.station_input import StationInput
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
    if demands.vu is None or demands.pu is None or demands.mu is None or demands.tu is None:
        return check_from_errors(STRENGTH, [incomplete("El cortante y la torsion requieren Vu, Pu, Mu y Tu")])
    return None


def concrete_lambda(profile: Profile, materials: Materials) -> float | Check:
    lam = profile.strength_assumptions.concrete_lambda(materials.concrete)
    if lam is None:
        return check_from_errors(STRENGTH, [blocked("El concreto liviano no esta implementado (D-028)")])
    return lam


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
