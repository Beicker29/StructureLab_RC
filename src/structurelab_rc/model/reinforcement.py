"""Armado de una sección: el contrato entre diseño, verificación, despiece y dibujo."""

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


class BarLayer(BaseModel):
    """Capa de barras iguales; depth es la distancia a la fibra superior, en mm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    count: PositiveInt
    depth: PositiveFloat


class Stirrups(BaseModel):
    """Estribos verticales: barra, número de ramas y separación a lo largo del miembro, en mm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    legs: int = Field(ge=2)
    spacing: PositiveFloat


class ReinforcementLayout(BaseModel):
    """stirrups es obligatorio: null declara explícitamente que no hay refuerzo a cortante."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    layers: tuple[BarLayer, ...] = Field(min_length=1)
    stirrups: Stirrups | None
