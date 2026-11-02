"""Estado nominal a flexión de una viga con los valores de su perfil."""

from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.mechanics.flexure import ConcreteBlock, FlexureState, SteelLayer, SteelModel, compression_strips, flexure_state
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Section
from structurelab_rc.model.reinforcement import ReinforcementLayout


def steel_layers(layout: ReinforcementLayout, bars: Sequence[RebarSpec]) -> tuple[SteelLayer, ...] | StructuredError:
    """Capas con su área total; la profundidad sigue medida desde la fibra superior."""
    areas = {bar.designation: bar.area_mm2 for bar in bars}
    layers = []
    for layer in layout.layers:
        area = areas.get(layer.designation)
        if area is None:
            return invalid_input(f"La barra '{layer.designation}' no esta en el catalogo")
        layers.append(SteelLayer(layer.depth, layer.count * area))
    return tuple(layers)


def nominal_flexure(
    profile: Profile, materials: Materials, section: Section, layers: tuple[SteelLayer, ...], *, top_in_compression: bool
) -> FlexureState | StructuredError:
    assumptions = profile.strength_assumptions
    beta1 = assumptions.beta1(materials.fc)
    if beta1 is None:
        return invalid_input(f"{profile.id} no define beta1 para fc = {materials.fc} MPa")
    # Con bf = bw el valor de hf no afecta el resultado.
    bf = section.bw if section.bf is None else section.bf
    hf = section.h / 2 if section.hf is None else section.hf
    strips = compression_strips(section.bw, section.h, bf, hf, flange_in_compression=top_in_compression)
    from_compression_face = tuple(
        layer if top_in_compression else SteelLayer(section.h - layer.depth, layer.area) for layer in layers
    )
    concrete = ConcreteBlock(materials.fc, assumptions.stress_block_factor(), beta1, assumptions.max_concrete_strain())
    steel = SteelModel(materials.fy, assumptions.steel_modulus())
    return flexure_state(strips, from_compression_face, concrete, steel)
