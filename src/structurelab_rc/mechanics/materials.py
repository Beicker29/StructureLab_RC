"""Modelos de material de la mecánica: bloque equivalente del concreto y acero elastoplástico, en MPa."""

from dataclasses import dataclass


class NoEquilibrium(ValueError):
    """La sección no puede equilibrar la carga axial."""


@dataclass(frozen=True)
class ConcreteBlock:
    fc: float
    stress_factor: float
    beta1: float
    max_strain: float


@dataclass(frozen=True)
class SteelModel:
    fy: float
    modulus: float
