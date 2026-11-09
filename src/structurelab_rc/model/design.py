"""Proyecto de diseño de zapatas por tipologías (V3F, D-069).

En lugar de zapatas con dimensiones, trae columnas con sus casos de carga y un bloque `design` con el número de
tipologías, los f'c comerciales permitidos, los precios y los límites de la búsqueda. Unidades de entrada: mm, kN, kN·m,
kPa, kN/m² y kN/m³ (como en las zapatas); precios en la moneda del usuario por m³ de concreto y por kg de acero.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, PositiveInt, field_validator, model_validator

from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Coating, SeismicFacts

COMMERCIAL_FC = (21.0, 24.5, 28.0, 31.5, 35.0, 42.0, 48.0)  # MPa


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DesignMaterials(_Input):
    """Materiales que no se diseñan: el acero y el tipo de concreto. f'c sale de la búsqueda (D-069)."""

    fy: PositiveFloat
    fyt: PositiveFloat
    concrete: Literal["normalweight", "lightweight"]
    coating: Coating


class Prices(_Input):
    """Precio del concreto por m³ por f'c comercial (clave en MPa, como texto; puede traer más resistencias que las que se
    evalúan) y del acero por kg."""

    concrete_per_m3: dict[str, PositiveFloat] = Field(min_length=1)
    steel_per_kg: PositiveFloat

    @field_validator("concrete_per_m3")
    @classmethod
    def _commercial(cls, value: dict[str, float]) -> dict[str, float]:
        for key in value:
            if float(key) not in COMMERCIAL_FC:
                raise ValueError(f"f'c = {key} MPa no es un valor comercial; valores: {', '.join(f'{fc:g}' for fc in COMMERCIAL_FC)}")
        return value

    def concrete(self, fc: float) -> float:
        return next(price for key, price in self.concrete_per_m3.items() if float(key) == fc)

    def has(self, fc: float) -> bool:
        return any(float(key) == fc for key in self.concrete_per_m3)


class FootingDesign(_Input):
    """Límites de la búsqueda. fc_options son las resistencias comerciales que se evalúan, cada una con su precio (D-072).
    La forma en planta es cuadrada por defecto (D-069); "ratio" fija lx/ly."""

    typologies: PositiveInt
    fc_options: tuple[float, ...] = Field(min_length=1)
    prices: Prices
    shape: Literal["square", "equal_cantilevers", "ratio"] = "square"
    ratio: PositiveFloat | None = None
    plan_step: PositiveFloat
    plan_max: PositiveFloat
    h_min: PositiveFloat
    h_step: PositiveFloat
    h_max: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead: NonNegativeFloat = Field(validation_alias="surcharge_dead_kNm2")
    surcharge_live: NonNegativeFloat = Field(validation_alias="surcharge_live_kNm2")
    bars: tuple[str, ...] = Field(min_length=1)
    spacing_step: PositiveFloat
    end: Literal["straight", "hook"]
    dowel_bars: tuple[str, ...] = Field(min_length=1)
    method: Literal["dp", "milp"] = "milp"  # E2, D-075: milp (por defecto) exige structurelab-rc[opt]
    milp_time_limit: PositiveFloat = Field(120.0, validation_alias="milp_time_limit_s")  # s por f'c

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.shape == "ratio") != (self.ratio is not None):
            raise ValueError("ratio se declara solo con shape = 'ratio'")
        if self.h_max < self.h_min:
            raise ValueError("h_max debe ser al menos h_min")
        for fc in self.fc_options:
            if fc not in COMMERCIAL_FC:
                raise ValueError(f"f'c = {fc:g} MPa no es un valor comercial; valores: {', '.join(f'{v:g}' for v in COMMERCIAL_FC)}")
            if not self.prices.has(fc):
                raise ValueError(f"f'c = {fc:g} MPa no tiene precio en prices.concrete_per_m3")
        if len(set(self.fc_options)) != len(self.fc_options):
            raise ValueError("fc_options repite una resistencia")
        return self


class DesignColumn(_Input):
    """Columna a cimentar: sección cx × cy (cx a lo largo de X) y sus casos de carga en la base."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    loads: tuple[FootingLoad, ...] = Field(min_length=1)


class FootingDesignProject(_Input):
    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: Soil
    design: FootingDesign
    columns: tuple[DesignColumn, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [column.id for column in self.columns]
        if len(ids) != len(set(ids)):
            raise ValueError("los identificadores de las columnas deben ser únicos")
        if self.design.typologies > len(self.columns):
            raise ValueError("hay más tipologías que columnas")
        return self
