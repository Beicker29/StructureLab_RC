"""Armado de una sección: el contrato entre diseño, verificación, despiece y dibujo."""

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


class BarLayer(BaseModel):
    """Capa de barras iguales; depth es la distancia a la fibra superior, en mm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    count: PositiveInt
    depth: PositiveFloat


class ReinforcementLayout(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    layers: tuple[BarLayer, ...] = Field(min_length=1)
