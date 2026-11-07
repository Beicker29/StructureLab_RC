"""Resistencia a flexión común a todos los elementos (vigas, zapatas y los que vengan): una sola fuente de verdad.

El equilibrio y la compatibilidad son de `mechanics`; aquí se toman del perfil los valores que mechanics recibe como
números (εcu, 0.85, β1, Es), el factor φ según εt y la εt mínima. Cada elemento solo elige la sección, las capas y el
numeral que cita.
"""

from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.mechanics.flexure import CompressionStrip, FlexureState, SteelLayer, flexure_state
from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel
from structurelab_rc.model.project import Materials

_BISECTION_STEPS = 80


@dataclass(frozen=True)
class RectangularSection:
    """Sección rectangular de ancho width y altura height, en mm."""

    width: float
    height: float


@dataclass(frozen=True)
class MomentStrength:
    """Estado nominal, φ y φMn de una sección; momentos en N·mm."""

    state: FlexureState
    phi: float

    @property
    def nominal(self) -> float:
        return self.state.nominal_moment

    @property
    def design(self) -> float:
        return self.phi * self.state.nominal_moment


def material_models(profile: Profile, materials: Materials) -> tuple[ConcreteBlock, SteelModel] | StructuredError:
    assumptions = profile.strength_assumptions
    beta1 = assumptions.beta1(materials.fc)
    if beta1 is None:
        return invalid_input(f"{profile.id} no define beta1 para fc = {materials.fc} MPa")
    concrete = ConcreteBlock(materials.fc, assumptions.stress_block_factor(), beta1, assumptions.max_concrete_strain())
    return concrete, SteelModel(materials.fy, assumptions.steel_modulus())


def yield_strain(profile: Profile, materials: Materials) -> float:
    return profile.flexure.yield_strain(materials.fy, profile.strength_assumptions.steel_modulus())


def flexure_phi(profile: Profile, materials: Materials, extreme_strain: float) -> float:
    return profile.flexure.strength_reduction_moment(extreme_strain, yield_strain(profile, materials))


def rectangular_strength(
    profile: Profile, materials: Materials, section: RectangularSection, layers: tuple[SteelLayer, ...]
) -> MomentStrength | StructuredError:
    """Sección rectangular sin carga axial; las capas se miden desde la cara comprimida."""
    models = material_models(profile, materials)
    if isinstance(models, StructuredError):
        return models
    state = flexure_state((CompressionStrip(section.width, 0.0, section.height),), layers, *models)
    return MomentStrength(state, flexure_phi(profile, materials, state.extreme_strain))


def required_area(profile: Profile, materials: Materials, section: RectangularSection, depth: float, moment: float) -> float | None:
    """Área de una capa a la profundidad depth con φMn = moment, por bisección; None si ninguna cuantía la alcanza."""
    if moment <= 0:
        return 0.0
    low, high = 0.0, section.width * depth  # cuantía 100 %: cota superior holgada

    def design(area: float) -> float:
        result = rectangular_strength(profile, materials, section, (SteelLayer(depth, area),))
        return result.design if isinstance(result, MomentStrength) else 0.0

    if design(high) < moment:
        return None
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2
        low, high = (middle, high) if design(middle) < moment else (low, middle)
    return high


def net_tensile_strain_check(name: str, clause: str, profile: Profile, materials: Materials, strain: float | None) -> Check:
    """εt en el estado nominal frente a la εt mínima del perfil; strain None si no hay momento en esa dirección."""
    if strain is None:
        return Check(name, Status.PASS, clause=clause, note="Sin momento en esta direccion")
    minimum = profile.flexure.min_net_tensile_strain(yield_strain(profile, materials))
    return Check(name, Status.PASS if strain >= minimum else Status.FAIL, clause=clause, demand=minimum, capacity=strain)
