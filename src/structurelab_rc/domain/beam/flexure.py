"""Verificación a flexión de vigas por estación, con Pn = Pu (D-024), en los dos ejes (D-046)."""

import math
from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.geometry import flexure_points, section_polygon
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import flexure_phi, material_models, net_tensile_strain_check
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import FlexureState, SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.section import SectionState, biaxial_state, section_state
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Demands, Materials, Member, Section, Station
from structurelab_rc.model.reinforcement import ReinforcementLayout

STRENGTH = "Flexion: resistencia"
NET_TENSILE_STRAIN = "Flexion: deformacion neta de traccion (M3)"
NET_TENSILE_STRAIN_M2 = "Flexion: deformacion neta de traccion (M2)"
NET_TENSILE_STRAIN_BIAXIAL = "Flexion: deformacion neta de traccion (biaxial)"
MIN_REINFORCEMENT = "Flexion: acero minimo (M3)"
MIN_REINFORCEMENT_M2 = "Flexion: acero minimo (M2)"
# d de As,min, del cortante y de la torsión: no menor que 0.8h (D-043).
MIN_DEPTH_RATIO = 0.8


def steel_layers(layout: ReinforcementLayout, bars: Sequence[RebarSpec]) -> tuple[SteelLayer, ...] | StructuredError:
    """Capas de flexión con su área total; la profundidad sigue medida desde la fibra superior (D-027)."""
    areas = {bar.designation: bar.area_mm2 for bar in bars}
    layers = []
    for layer in layout.layers:
        if layer.role != "flexure":
            continue
        names = layer.designations()
        missing = [name for name in names if name not in areas]
        if missing:
            return invalid_input(f"La barra '{missing[0]}' no esta en el catalogo")
        layers.append(SteelLayer(layer.depth, sum(areas[name] for name in names)))
    return tuple(layers)


def nominal_flexure(
    profile: Profile, materials: Materials, section: Section, layers: tuple[SteelLayer, ...], demands: Demands
) -> FlexureState | StructuredError:
    """Estado nominal con la cara comprimida que indica el signo de Mu y la carga axial Pn = Pu.

    Lanza NoEquilibrium si la sección no puede equilibrar Pu.
    """
    if demands.mu is None or demands.pu is None:
        return incomplete("La flexion requiere Mu y Pu")
    models = material_models(profile, materials)
    if isinstance(models, StructuredError):
        return models
    top_in_compression = demands.mu >= 0
    # Con bf = bw el valor de hf no afecta el resultado.
    bf = section.bw if section.bf is None else section.bf
    hf = section.h / 2 if section.hf is None else section.hf
    strips = compression_strips(section.bw, section.h, bf, hf, flange_in_compression=top_in_compression)
    from_face = tuple(layer if top_in_compression else SteelLayer(section.h - layer.depth, layer.area) for layer in layers)
    return flexure_state(strips, from_face, *models, demands.pu)


def section_states(given: StationInput) -> tuple[SectionState, SectionState] | StructuredError:
    """Estado biaxial en la dirección de (Mu, M2) y estado uniaxial de M2 solo, con la sección completa (D-046).

    Lanza NoEquilibrium si la sección no puede equilibrar Pu.
    """
    demands, section = given.station.demands, given.member.section
    if demands.mu is None or demands.m2 is None or demands.pu is None:
        return incomplete("La flexion requiere Mu, M2 y Pu")
    models = material_models(given.profile, given.materials)
    if isinstance(models, StructuredError):
        return models
    polygon = section_polygon(section)
    points = flexure_points(given.station.layout, section, given.bars)
    biaxial = biaxial_state(polygon, points, models, demands.pu, (demands.mu, demands.m2))
    weak = section_state(polygon, points, models, demands.pu, 0.0 if demands.m2 >= 0 else math.pi)
    return biaxial, weak


def _min_reinforcement(profile: Profile, materials: Materials, member: Member, state: FlexureState, mu: float) -> Check:
    clause = profile.flexure.clauses()["min_reinforcement"]
    if mu == 0:
        return Check(MIN_REINFORCEMENT, Status.PASS, clause=clause, note="Sin momento no se requiere refuerzo a traccion")
    section = member.section
    bw = section.bw
    if section.bf is not None and mu < 0:
        if member.statically_determinate is None:
            return check_from_errors(MIN_REINFORCEMENT, [incomplete("Falta declarar si el miembro es isostatico (ala a traccion)")])
        if member.statically_determinate:
            bw = profile.flexure.determinate_flange_width(section.bw, section.bf)
    # Cuenta todo el acero a tracción en el estado nominal (D-025); d es su centroide, no menor que 0.8h (D-043).
    tension = [layer for layer in state.layers if layer.strain > 0]
    provided = sum(layer.area for layer in tension)
    centroid = sum(layer.depth * layer.area for layer in tension) / provided if provided else 0.0
    depth = max(centroid, MIN_DEPTH_RATIO * section.h)
    required = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, bw, depth)
    if provided >= required:
        return Check(MIN_REINFORCEMENT, Status.PASS, clause=clause, demand=required, capacity=provided, unit="mm2")
    exception = profile.flexure.clauses()["min_reinforcement_exception"]
    error = blocked(f"As < As,min; la excepcion de {exception} no esta implementada (D-022)")
    return Check(MIN_REINFORCEMENT, Status.BLOCKED, (error,), clause, demand=required, capacity=provided, unit="mm2")


def _weak_min_reinforcement(profile: Profile, materials: Materials, member: Member, weak: SectionState, m2: float) -> Check:
    """As,min del eje débil: ancho h y d del estado girado, no menor que 0.8 veces el ancho total (D-046)."""
    clause = profile.flexure.clauses()["min_reinforcement"]
    if m2 == 0:
        return Check(MIN_REINFORCEMENT_M2, Status.PASS, clause=clause, note="Sin M2 no se requiere refuerzo a traccion")
    section = member.section
    tension = [bar for bar in weak.bars if bar.strain > 0]
    provided = sum(bar.area for bar in tension)
    centroid = sum(bar.depth * bar.area for bar in tension) / provided if provided else 0.0
    depth = max(centroid, MIN_DEPTH_RATIO * section.flange_width)
    required = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, section.h, depth)
    if provided >= required:
        return Check(MIN_REINFORCEMENT_M2, Status.PASS, clause=clause, demand=required, capacity=provided, unit="mm2")
    exception = profile.flexure.clauses()["min_reinforcement_exception"]
    error = blocked(f"As < As,min; la excepcion de {exception} no esta implementada (D-022)")
    return Check(MIN_REINFORCEMENT_M2, Status.BLOCKED, (error,), clause, demand=required, capacity=provided, unit="mm2")


def _strain_check(name: str, profile: Profile, materials: Materials, strain: float | None) -> Check:
    return net_tensile_strain_check(name, profile.flexure.clauses()["net_tensile_strain"], profile, materials, strain)


def _biaxial_checks(given: StationInput) -> tuple[Check, ...]:
    """Resistencia biaxial, εt del eje débil y del estado biaxial, y As,min del eje débil."""
    profile, materials, demands = given.profile, given.materials, given.station.demands
    clause = profile.flexure.clauses()["strength"]
    try:
        states = section_states(given)
    except NoEquilibrium as error:
        return (Check(STRENGTH, Status.FAIL, clause=clause, note=str(error)),)
    if isinstance(states, StructuredError):
        return (check_from_errors(STRENGTH, [states]),)
    biaxial, weak = states
    assert demands.mu is not None and demands.m2 is not None
    phi = flexure_phi(profile, materials, biaxial.extreme_strain)
    demand = math.hypot(demands.mu, demands.m2)
    capacity = phi * math.hypot(biaxial.mn3, biaxial.mn2)
    values = (("phi", phi), ("Mn3", biaxial.mn3), ("Mn2", biaxial.mn2), ("theta", math.degrees(biaxial.theta)),
              ("c", biaxial.c), ("et", biaxial.extreme_strain))
    strength = Check(STRENGTH, Status.PASS if capacity >= demand else Status.FAIL, clause=clause,
                     demand=demand, capacity=capacity, unit="N*mm", values=values)
    moments = demands.mu != 0 or demands.m2 != 0
    return (
        strength,
        _strain_check(NET_TENSILE_STRAIN_M2, profile, materials, weak.extreme_strain if demands.m2 != 0 else None),
        _strain_check(NET_TENSILE_STRAIN_BIAXIAL, profile, materials, biaxial.extreme_strain if moments else None),
        _weak_min_reinforcement(profile, materials, given.member, weak, demands.m2),
    )


def flexure_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    """Verificaciones a flexión de una estación dentro del alcance de viga, en los dos ejes (D-046)."""
    demands = station.demands
    if demands.mu is None or demands.pu is None:
        return (check_from_errors(STRENGTH, [incomplete("La flexion requiere Mu y Pu")]),)
    layers = steel_layers(station.layout, bars)
    if isinstance(layers, StructuredError):
        return (check_from_errors(STRENGTH, [layers]),)
    try:
        state = nominal_flexure(profile, materials, member.section, layers, demands)
    except NoEquilibrium as error:
        return (Check(STRENGTH, Status.FAIL, clause=profile.flexure.clauses()["strength"], note=str(error)),)
    if isinstance(state, StructuredError):
        return (check_from_errors(STRENGTH, [state]),)
    strong_strain = _strain_check(NET_TENSILE_STRAIN, profile, materials, state.extreme_strain if demands.mu != 0 else None)
    if demands.mu == 0:
        strong_strain = _strain_check(NET_TENSILE_STRAIN, profile, materials, None)
    strong_minimum = _min_reinforcement(profile, materials, member, state, demands.mu)
    return (*_biaxial_checks(StationInput(profile, materials, member, station, bars)), strong_strain, strong_minimum)
