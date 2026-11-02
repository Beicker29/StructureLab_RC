"""Registro de perfiles normativos."""

from dataclasses import dataclass
from typing import Protocol

from structurelab_rc.codes.aci_318_25 import seismic as aci_seismic
from structurelab_rc.codes.aci_318_25 import strength_assumptions as aci_strength_assumptions
from structurelab_rc.codes.nsr_10 import seismic as nsr_seismic
from structurelab_rc.codes.nsr_10 import strength_assumptions as nsr_strength_assumptions


class StrengthAssumptions(Protocol):
    def max_concrete_strain(self) -> float: ...

    def stress_block_factor(self) -> float: ...

    def beta1(self, fc: float) -> float | None: ...

    def steel_modulus(self) -> float: ...


class Seismic(Protocol):
    def seismic_levels(self) -> frozenset[str]: ...


@dataclass(frozen=True)
class Profile:
    id: str
    strength_assumptions: StrengthAssumptions
    seismic: Seismic


PROFILES = {
    "aci-318-25": Profile("aci-318-25", aci_strength_assumptions, aci_seismic),
    "nsr-10": Profile("nsr-10", nsr_strength_assumptions, nsr_seismic),
}
