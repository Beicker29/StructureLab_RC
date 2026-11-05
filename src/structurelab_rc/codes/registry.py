"""Registro de perfiles normativos."""

from dataclasses import dataclass
from typing import Protocol

from structurelab_rc.codes.aci_318_25 import flexure as aci_flexure
from structurelab_rc.codes.aci_318_25 import seismic as aci_seismic
from structurelab_rc.codes.aci_318_25 import shear as aci_shear
from structurelab_rc.codes.aci_318_25 import strength_assumptions as aci_strength_assumptions
from structurelab_rc.codes.aci_318_25 import torsion as aci_torsion
from structurelab_rc.codes.nsr_10 import flexure as nsr_flexure
from structurelab_rc.codes.nsr_10 import seismic as nsr_seismic
from structurelab_rc.codes.nsr_10 import shear as nsr_shear
from structurelab_rc.codes.nsr_10 import strength_assumptions as nsr_strength_assumptions
from structurelab_rc.codes.nsr_10 import torsion as nsr_torsion


class StrengthAssumptions(Protocol):
    def max_concrete_strain(self) -> float: ...

    def stress_block_factor(self) -> float: ...

    def beta1(self, fc: float) -> float | None: ...

    def steel_modulus(self) -> float: ...

    def concrete_lambda(self, concrete: str) -> float | None: ...


class Flexure(Protocol):
    def clauses(self) -> dict[str, str]: ...

    def yield_strain(self, fy: float, es: float) -> float: ...

    def strength_reduction_moment(self, et: float, ety: float) -> float: ...

    def beam_min_net_tensile_strain(self, ety: float) -> float: ...

    def beam_axial_limit(self, fc: float, ag: float) -> float: ...

    def min_flexural_reinforcement(self, fc: float, fy: float, bw: float, d: float) -> float: ...

    def determinate_flange_width(self, bw: float, bf: float) -> float: ...


class Shear(Protocol):
    def clauses(self) -> dict[str, str]: ...

    def strength_reduction(self) -> float: ...

    def concrete_shear(
        self,
        *,
        fc: float,
        lam: float,
        bw: float,
        d: float,
        h: float,
        rho_w: float,
        nu: float,
        ag: float,
        vu: float,
        mu: float,
        av_ge_min: bool,
    ) -> float: ...

    def max_stirrup_yield(self) -> float: ...

    def steel_shear(self, av: float, fyt: float, d: float, s: float) -> float: ...

    def max_steel_shear(self, fc: float, bw: float, d: float) -> float: ...

    def min_shear_reinforcement(self, fc: float, bw: float, fyt: float) -> float: ...

    def min_reinforcement_exempt(self, h: float, bw: float, hf: float | None) -> bool: ...

    def min_reinforcement_threshold(
        self, vc: float, fc: float, lam: float, bw: float, d: float, exempt: bool
    ) -> float | None: ...

    def max_spacing(self, vs: float, fc: float, bw: float, d: float) -> float: ...

    def max_leg_spacing_across(self, vs: float, fc: float, bw: float, d: float) -> float | None: ...


class Torsion(Protocol):
    def clauses(self) -> dict[str, str]: ...

    def strength_reduction(self) -> float: ...

    def threshold_torsion(self, fc: float, lam: float, acp: float, pcp: float, nu: float, ag: float) -> float: ...


class Seismic(Protocol):
    def seismic_levels(self) -> frozenset[str]: ...


@dataclass(frozen=True)
class Profile:
    id: str
    strength_assumptions: StrengthAssumptions
    flexure: Flexure
    shear: Shear
    torsion: Torsion
    seismic: Seismic


PROFILES = {
    "aci-318-25": Profile("aci-318-25", aci_strength_assumptions, aci_flexure, aci_shear, aci_torsion, aci_seismic),
    "nsr-10": Profile("nsr-10", nsr_strength_assumptions, nsr_flexure, nsr_shear, nsr_torsion, nsr_seismic),
}
