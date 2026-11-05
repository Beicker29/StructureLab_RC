"""Armado de una sección: el contrato entre diseño, verificación, despiece y dibujo."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


class BarLayer(BaseModel):
    """Capa de barras iguales; depth es la distancia a la fibra superior, en mm.

    role declara su función: las capas de torsión (Aℓ) no cuentan como As de flexión (D-027).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    count: PositiveInt
    depth: PositiveFloat
    role: Literal["flexure", "torsion"]


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
