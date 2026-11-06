"""Armado de una sección: el contrato entre diseño, verificación, despiece y dibujo."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator


class BarPosition(BaseModel):
    """Barra con posición propia; x es la coordenada de su centro sobre el eje 3, desde la cara −3 del alma, en mm.

    Fuera del alma (x < 0 o x > bw) solo se admite dentro del ala (D-045).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    designation: str
    x: float


class BarSpacing(BaseModel):
    """Barras iguales cada spacing mm, desde x = from hasta x = to inclusive; pensada para la malla del ala (D-045)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    designation: str
    spacing: PositiveFloat
    start: float = Field(alias="from")
    end: float = Field(alias="to")

    def positions(self) -> tuple[float, ...]:
        count = int((self.end - self.start) / self.spacing + 1e-9) + 1
        return tuple(self.start + index * self.spacing for index in range(max(count, 0)))


class BarLayer(BaseModel):
    """Capa de barras a la profundidad depth (centros, desde la fibra superior), listadas en orden de x creciente.

    bars admite tres formas (D-040, D-045): solo designaciones, repartidas de forma uniforme en el alma entre las
    esquinas interiores del estribo; barras con posición x; o barras iguales por separación. role declara su función:
    las capas de torsión (Aℓ) no cuentan como As de flexión (D-027).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    depth: PositiveFloat
    role: Literal["flexure", "torsion"]
    bars: tuple[str, ...] | tuple[BarPosition, ...] | BarSpacing

    @model_validator(mode="after")
    def _check_bars(self) -> Self:
        if not self.designations():
            raise ValueError("la capa no tiene barras")
        return self

    def designations(self) -> list[str]:
        if isinstance(self.bars, BarSpacing):
            return [self.bars.designation] * len(self.bars.positions())
        return [bar if isinstance(bar, str) else bar.designation for bar in self.bars]


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
        names = {name for layer in self.layers for name in layer.designations()}
        return names if self.stirrups is None else names | {self.stirrups.designation}
