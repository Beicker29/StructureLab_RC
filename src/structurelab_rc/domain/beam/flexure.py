"""Verificación a flexión de vigas por estación, con Pn = Pu (D-024)."""

from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import (
    ConcreteBlock,
    FlexureState,
    NoEquilibrium,
    SteelLayer,
    SteelModel,
    compression_strips,
    flexure_state,
)
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Demands, Materials, Member, Section, Station
from structurelab_rc.model.reinforcement import ReinforcementLayout

STRENGTH = "Flexion: resistencia"
NET_TENSILE_STRAIN = "Flexion: deformacion neta de traccion"
MIN_REINFORCEMENT = "Flexion: acero minimo"
# d de As,min, del cortante y de la torsión: no menor que 0.8h (D-043).
MIN_DEPTH_RATIO = 0.8


def steel_layers(layout: ReinforcementLayout, bars: Sequence[RebarSpec]) -> tuple[SteelLayer, ...] | StructuredError:
    """Capas de flexión con su área total; la profundidad sigue medida desde la fibra superior (D-027)."""
    areas = {bar.designation: bar.area_mm2 for bar in bars}
    layers = []
    for layer in layout.layers:
        if layer.role != "flexure":
            continue
        names = [bar if isinstance(bar, str) else bar.designation for bar in layer.bars]
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
    assumptions = profile.strength_assumptions
    beta1 = assumptions.beta1(materials.fc)
    if beta1 is None:
        return invalid_input(f"{profile.id} no define beta1 para fc = {materials.fc} MPa")
    top_in_compression = demands.mu >= 0
    # Con bf = bw el valor de hf no afecta el resultado.
    bf = section.bw if section.bf is None else section.bf
    hf = section.h / 2 if section.hf is None else section.hf
    strips = compression_strips(section.bw, section.h, bf, hf, flange_in_compression=top_in_compression)
    from_face = tuple(layer if top_in_compression else SteelLayer(section.h - layer.depth, layer.area) for layer in layers)
    concrete = ConcreteBlock(materials.fc, assumptions.stress_block_factor(), beta1, assumptions.max_concrete_strain())
    steel = SteelModel(materials.fy, assumptions.steel_modulus())
    return flexure_state(strips, from_face, concrete, steel, demands.pu)


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


def flexure_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    """Verificaciones a flexión de una estación que ya está dentro del alcance de viga."""
    clauses = profile.flexure.clauses()
    demands = station.demands
    if demands.mu is None or demands.pu is None:
        return (check_from_errors(STRENGTH, [incomplete("La flexion requiere Mu y Pu")]),)
    layers = steel_layers(station.layout, bars)
    if isinstance(layers, StructuredError):
        return (check_from_errors(STRENGTH, [layers]),)
    try:
        state = nominal_flexure(profile, materials, member.section, layers, demands)
    except NoEquilibrium as error:
        return (Check(STRENGTH, Status.FAIL, clause=clauses["strength"], note=str(error)),)
    if isinstance(state, StructuredError):
        return (check_from_errors(STRENGTH, [state]),)
    ety = profile.flexure.yield_strain(materials.fy, profile.strength_assumptions.steel_modulus())
    phi = profile.flexure.strength_reduction_moment(state.extreme_strain, ety)
    capacity = phi * state.nominal_moment
    demand = abs(demands.mu)
    values = (("phi", phi), ("Mn", state.nominal_moment), ("c", state.c), ("et", state.extreme_strain))
    strength = Check(STRENGTH, Status.PASS if capacity >= demand else Status.FAIL, clause=clauses["strength"],
                     demand=demand, capacity=capacity, unit="N*mm", values=values)
    et_min = profile.flexure.beam_min_net_tensile_strain(ety)
    strain = Check(NET_TENSILE_STRAIN, Status.PASS if state.extreme_strain >= et_min else Status.FAIL,
                   clause=clauses["net_tensile_strain"], demand=et_min, capacity=state.extreme_strain)
    return strength, strain, _min_reinforcement(profile, materials, member, state, demands.mu)
