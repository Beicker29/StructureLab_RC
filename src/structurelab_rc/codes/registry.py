"""Registro de perfiles normativos."""

from dataclasses import dataclass
from typing import Protocol

from structurelab_rc.codes.aci_318_25 import flexure as aci_flexure
from structurelab_rc.codes.aci_318_25 import seismic as aci_seismic
from structurelab_rc.codes.aci_318_25 import strength_assumptions as aci_strength_assumptions
from structurelab_rc.codes.nsr_10 import flexure as nsr_flexure
from structurelab_rc.codes.nsr_10 import seismic as nsr_seismic
from structurelab_rc.codes.nsr_10 import strength_assumptions as nsr_strength_assumptions


class StrengthAssumptions(Protocol):
    def max_concrete_strain(self) -> float: ...

    def stress_block_factor(self) -> float: ...

    def beta1(self, fc: float) -> float | None: ...

    def steel_modulus(self) -> float: ...


class Flexure(Protocol):
    def clauses(self) -> dict[str, str]: ...

    def yield_strain(self, fy: float, es: float) -> float: ...

    def strength_reduction_moment(self, et: float, ety: float) -> float: ...

    def beam_min_net_tensile_strain(self, ety: float) -> float: ...

    def beam_axial_limit(self, fc: float, ag: float) -> float: ...

    def min_flexural_reinforcement(self, fc: float, fy: float, bw: float, d: float) -> float: ...

    def determinate_flange_width(self, bw: float, bf: float) -> float: ...


class Seismic(Protocol):
    def seismic_levels(self) -> frozenset[str]: ...


@dataclass(frozen=True)
class Profile:
    id: str
    strength_assumptions: StrengthAssumptions
    flexure: Flexure
    seismic: Seismic


PROFILES = {
    "aci-318-25": Profile("aci-318-25", aci_strength_assumptions, aci_flexure, aci_seismic),
    "nsr-10": Profile("nsr-10", nsr_strength_assumptions, nsr_flexure, nsr_seismic),
}
