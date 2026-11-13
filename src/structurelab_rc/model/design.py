"""Proyecto de diseño de zapatas por tipologías (V3F, D-069).

En lugar de zapatas con dimensiones, trae columnas con sus casos de carga y un bloque `design` con el número de
tipologías, los f'c comerciales permitidos, los precios y los límites de la búsqueda. Unidades de entrada: mm, kN, kN·m,
kPa, kN/m² y kN/m³ (como en las zapatas); precios en la moneda del usuario por m³ de concreto y por kg de acero.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, PositiveInt, field_validator, model_validator

from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Coating, DetailingSettings, DrawingSettings, SeismicFacts

COMMERCIAL_FC = (21.0, 24.5, 28.0, 31.5, 35.0, 42.0, 48.0)  # MPa


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DesignMaterials(_Input):
    """Materiales que no se diseñan: el acero y el tipo de concreto. f'c sale de la búsqueda (D-069)."""

    fy: PositiveFloat
    fyt: PositiveFloat
    concrete: Literal["normalweight", "lightweight"]
    coating: Coating
    max_aggregate: PositiveFloat | None = None  # mm (D-102)


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


class DesignLimits(_Input):
    """Límites comunes del diseño de zapatas (D-069, D-107). fc_options son las resistencias comerciales que se evalúan,
    cada una con su precio (D-072); plan_step y plan_max, el paso y el mayor lado en planta; h_min, h_step y h_max, los
    del espesor; bars y dowel_bars, las barras permitidas para las mallas y para los pasadores; spacing_step, el paso de
    la separación; end, cómo terminan las barras."""

    fc_options: tuple[float, ...] = Field(min_length=1)
    prices: Prices
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

    @model_validator(mode="after")
    def _check_limits(self) -> Self:
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


class FootingDesign(DesignLimits):
    """Límites del diseño por tipologías (D-069): el número de tipologías y la forma en planta, cuadrada por defecto;
    "ratio" fija lx/ly."""

    typologies: PositiveInt
    shape: Literal["square", "equal_cantilevers", "ratio"] = "square"
    ratio: PositiveFloat | None = None
    method: Literal["dp", "milp", "milp_iter"] = "milp_iter"  # D-077: milp_iter (por defecto desde E3b) y milp exigen [opt]
    milp_time_limit: PositiveFloat = Field(120.0, validation_alias="milp_time_limit_s")  # s por f'c (cada solución del MILP)
    iter_max: PositiveInt = 10  # milp_iter: iteraciones por f'c
    iter_time_limit: PositiveFloat = Field(600.0, validation_alias="iter_time_limit_s")  # milp_iter: s por f'c

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.shape == "ratio") != (self.ratio is not None):
            raise ValueError("ratio se declara solo con shape = 'ratio'")
        return self


class DesignColumn(_Input):
    """Columna a cimentar: sección cx × cy (cx a lo largo de X) y sus casos de carga en la base."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    loads: tuple[FootingLoad, ...] = Field(min_length=1)


class CurveSettings(_Input):
    """La curva costo–N (D-078) como ejemplo propio (D-096): los valores de N, como lista o como texto "1-6", "2,4,6" o
    "1-4,8"."""

    n: tuple[PositiveInt, ...] = Field(min_length=1)

    @field_validator("n", mode="before")
    @classmethod
    def _ranges(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        counts: set[int] = set()
        for part in value.split(","):
            low, _, high = part.strip().partition("-")
            try:
                counts.update(range(int(low), int(high or low) + 1))
            except ValueError as error:
                raise ValueError(f"valores de N no validos: {value}") from error
        return tuple(sorted(counts))


class FootingDesignProject(_Input):
    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: Soil
    design: FootingDesign
    columns: tuple[DesignColumn, ...] = Field(min_length=1)
    curve: CurveSettings | None = None  # solo el ejemplo de la curva costo–N (D-096)
    detailing: DetailingSettings | None = None  # D-127: con él, el costo sale de la cartilla y el proyecto diseñado lo lleva
    drawing: DrawingSettings | None = None  # D-127: pasa al proyecto diseñado; requiere detailing (D-126)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [column.id for column in self.columns]
        if len(ids) != len(set(ids)):
            raise ValueError("los identificadores de las columnas deben ser únicos")
        if self.design.typologies > len(self.columns):
            raise ValueError("hay más tipologías que columnas")
        _check_drawing(self.detailing, self.drawing)
        return self


def _check_drawing(detailing: DetailingSettings | None, drawing: DrawingSettings | None) -> None:
    if drawing is not None and detailing is None:
        raise ValueError("drawing requiere detailing: el dibujo rotula las marcas de la cartilla (D-126)")


class CombinedDesign(DesignLimits):
    """Límites del diseño de una zapata combinada de dos columnas (D-107). plan_max limita el largo y el ancho.
    max_cantilever_start y max_cantilever_end limitan el voladizo más allá de la cara exterior de la columna de cada
    extremo, a lo largo de la dirección principal (start: el de la columna con la menor coordenada; por ejemplo, 0 en una
    columna de lindero); sin ellos, la base se centra en la resultante. placement_case es el caso de servicio sin sismo
    cuya resultante ubica la base (D-108); sin él, el de servicio sin sismo de mayor carga total. stirrup_bars son las
    barras permitidas para estribos de la viga larga (D-110): con ellas, el cortante y la torsión pueden tomarlos estribos
    en lugar de un espesor mayor; sin ellas no se proponen estribos. shape = "inverted_t" diseña una T invertida (D-113):
    h_min, h_step y h_max son los del espesor de la zarpa; beam_h_* los del alto total de la viga, y el alma parte de la
    columna más ancha más web_margin a cada lado y crece de a web_step."""

    min_steel_exception: bool  # D-123: si el diseño y la verificación admiten la excepción de 4/3 del As,min
    max_cantilever_start: NonNegativeFloat | None = None
    max_cantilever_end: NonNegativeFloat | None = None
    placement_case: str | None = Field(None, min_length=1)
    stirrup_bars: tuple[str, ...] = ()  # D-110: barras para estribos de la viga larga; sin ellas, no se proponen
    shape: Literal["rectangular", "inverted_t"] = "rectangular"  # D-113
    web_margin: NonNegativeFloat | None = None  # T invertida: margen del alma a cada lado de la columna más ancha, mm
    web_step: PositiveFloat | None = None  # T invertida: paso del ancho del alma, mm
    beam_h_min: PositiveFloat | None = None  # T invertida: alto total de la viga, mm
    beam_h_step: PositiveFloat | None = None
    beam_h_max: PositiveFloat | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        t_fields = ("web_margin", "web_step", "beam_h_min", "beam_h_step", "beam_h_max")
        declared = [name for name in t_fields if getattr(self, name) is not None]
        if self.shape == "inverted_t":
            missing = [name for name in t_fields if name not in declared]
            if missing:
                raise ValueError(f"la T invertida necesita {', '.join(missing)} en combined_design (D-113)")
            assert self.beam_h_min is not None and self.beam_h_max is not None
            if self.beam_h_max < self.beam_h_min:
                raise ValueError("beam_h_max debe ser al menos beam_h_min")
            if self.beam_h_min <= self.h_min:
                raise ValueError("beam_h_min debe superar h_min (el espesor de la zarpa)")
        elif declared:
            raise ValueError(f"{', '.join(declared)} solo se declaran con shape = 'inverted_t' (D-113)")
        return self


class CombinedDesignColumn(_Input):
    """Columna de la zapata combinada a diseñar: sección cx × cy (cx a lo largo de X global), su eje en (x, y) en ejes
    globales con cualquier origen (el diseño ubica la base) y sus casos de carga en la base."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    x: float
    y: float
    loads: tuple[FootingLoad, ...] = Field(min_length=1)


class CombinedDesignProject(_Input):
    """Proyecto de diseño de una zapata combinada rectangular de dos columnas (D-107): las columnas con sus posiciones y
    sus cargas, la dirección principal (el eje global en que va la viga que las une) y el bloque combined_design."""

    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: Soil
    principal_direction: Literal["x", "y"] = "x"
    combined_design: CombinedDesign
    columns: tuple[CombinedDesignColumn, ...] = Field(min_length=2, max_length=2)
    detailing: DetailingSettings | None = None  # D-127: con él, el costo sale de la cartilla y el proyecto diseñado lo lleva
    drawing: DrawingSettings | None = None  # D-127: pasa al proyecto diseñado; requiere detailing (D-126)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_drawing(self.detailing, self.drawing)
        first, second = self.columns
        if first.id == second.id:
            raise ValueError("los identificadores de las columnas deben ser únicos")
        keys = [{(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in column.loads}
                for column in self.columns]
        if any(len(own) != len(column.loads) for own, column in zip(keys, self.columns, strict=True)) or keys[0] != keys[1]:
            raise ValueError("las dos columnas deben tener los mismos casos de carga, sin repetir, con los mismos factores y "
                             "la misma marca de sismo")
        chosen = self.combined_design.placement_case
        if chosen is not None:
            facts = keys[0].get(("service", chosen))
            if facts is None:
                raise ValueError(f"placement_case '{chosen}' no es un caso de servicio de las columnas (D-108)")
            if facts[2]:
                raise ValueError(f"placement_case '{chosen}' es un caso con sismo: la base se ubica con un caso sostenido (D-108)")
        elif not any(kind == "service" and not facts[2] for (kind, _), facts in keys[0].items()):
            raise ValueError("la ubicación de la base necesita un caso de servicio sin sismo (D+L, D-107)")
        if not any(kind == "factored" for kind, _ in keys[0]):
            raise ValueError("el diseño necesita casos mayorados")
        return self
