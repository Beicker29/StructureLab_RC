"""Resistencia a flexión de una sección rectangular de concreto estructural simple, común a todos los elementos
(zapatas ahora; muros y pedestales después): φMn = φ·(esfuerzo de tracción por flexión del perfil)·Sm, con Sm el
módulo elástico de la sección y el espesor reducido si el concreto se vacía contra el suelo (D-072). Al acero que
pudiera haber no se le asigna resistencia.
"""

from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.errors import StructuredError
from structurelab_rc.model.project import Materials


@dataclass(frozen=True)
class PlainMoment:
    phi: float
    nominal: float  # N·mm
    modulus: float  # mm³
    thickness: float  # mm, el espesor usado en el cálculo

    @property
    def design(self) -> float:
        return self.phi * self.nominal


def plain_rectangular_moment(
    profile: Profile, materials: Materials, width: float, h: float, cast_against_soil: bool
) -> PlainMoment | StructuredError:
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return lam
    plain = profile.plain
    thickness = h - plain.soil_cast_reduction() if cast_against_soil else h
    modulus = width * thickness**2 / 6
    return PlainMoment(plain.strength_reduction(), plain.flexural_tension_stress(materials.fc, lam) * modulus, modulus, thickness)
