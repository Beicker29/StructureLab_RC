"""Armado de una sección: el contrato entre diseño, verificación, despiece y dibujo."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat


class BarPosition(BaseModel):
    """Barra con posición propia; z es la distancia de la cara izquierda del alma al centro de la barra, en mm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    z: PositiveFloat


class BarLayer(BaseModel):
    """Capa de barras a la profundidad depth (centros, desde la fibra superior), listadas de izquierda a derecha.

    bars admite dos formas (D-040): solo designaciones, repartidas de forma uniforme entre las esquinas
    interiores del estribo, o barras con posición z. role declara su función: las capas de torsión (Aℓ)
    no cuentan como As de flexión (D-027).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    depth: PositiveFloat
    role: Literal["flexure", "torsion"]
    bars: tuple[str, ...] | tuple[BarPosition, ...] = Field(min_length=1)


class Stirrups(BaseModel):
    """Estribos verticales: barra, número de ramas, separación a lo largo del miembro (mm) y si son cerrados."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    legs: int = Field(ge=2)
    spacing: PositiveFloat
    closed: bool


class ReinforcementLayout(BaseModel):
    """stirrups es obligatorio: null declara explícitamente que no hay refuerzo a cortante."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    layers: tuple[BarLayer, ...] = Field(min_length=1)
    stirrups: Stirrups | None

    def designations(self) -> set[str]:
        """Designaciones de todas las barras longitudinales y del estribo."""
        names = {bar if isinstance(bar, str) else bar.designation for layer in self.layers for bar in layer.bars}
        return names if self.stirrups is None else names | {self.stirrups.designation}
