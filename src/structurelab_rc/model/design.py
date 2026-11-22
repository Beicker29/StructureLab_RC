"""Proyecto de diseño de zapatas por tipologías (V3F, D-069).

En lugar de zapatas con dimensiones, trae columnas con sus casos de carga y un bloque `design` con el número de
tipologías, los f'c comerciales permitidos, los precios y los límites de la búsqueda. Unidades de entrada: mm, kN, kN·m,
kPa, kN/m² y kN/m³ (como en las zapatas); precios en la moneda del usuario por m³ de concreto y por kg de acero.
"""

from collections.abc import Sequence
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, PositiveInt, field_validator, model_validator

from structurelab_rc.model.footing import FootingLoad, Location, Soil
from structurelab_rc.model.layout import internal
from structurelab_rc.model.project import Coating, DetailingSettings, DrawingSettings, SeismicFacts
from structurelab_rc.model.reinforcement import BarEnd, StirrupEnd

COMMERCIAL_FC = (21.0, 24.5, 28.0, 31.5, 35.0, 42.0, 48.0)  # MPa


_TOUCH = 1e-6  # mm


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


def check_options(fc_options: tuple[float, ...], prices: Prices, heights: tuple[float, float]) -> None:
    """f'c comerciales, con precio y sin repetir, y h_max ≥ h_min: lo común a los diseños de zapatas y cabezales."""
    h_min, h_max = heights
    if h_max < h_min:
        raise ValueError("h_max debe ser al menos h_min")
    for fc in fc_options:
        if fc not in COMMERCIAL_FC:
            raise ValueError(f"f'c = {fc:g} MPa no es un valor comercial; valores: {', '.join(f'{v:g}' for v in COMMERCIAL_FC)}")
        if not prices.has(fc):
            raise ValueError(f"f'c = {fc:g} MPa no tiene precio en prices.concrete_per_m3")
    if len(set(fc_options)) != len(fc_options):
        raise ValueError("fc_options repite una resistencia")


class DesignEnds(_Input):
    """Cómo terminan las barras que diseña (D-134), por clase de grupo, sin valor por defecto: bottom (malla inferior,
    band y capa inferior de la viga de la T), top (malla y barras superiores, band superior y capa superior de la viga),
    dowels (el pie de los pasadores), stirrups (el gancho de cierre de los estribos, si se diseñan) y skin (la piel, si
    se diseña)."""

    bottom: BarEnd
    top: BarEnd
    dowels: BarEnd
    stirrups: StirrupEnd | None = None
    skin: BarEnd | None = None


class DesignLimits(_Input):
    """Límites comunes del diseño de zapatas (D-069, D-107). fc_options son las resistencias comerciales que se evalúan,
    cada una con su precio (D-072); plan_step y plan_max, el paso y el mayor lado en planta; h_min, h_step y h_max, los
    del espesor; bars y dowel_bars, las barras permitidas para las mallas y para los pasadores; spacing_step, el paso de
    la separación; ends, cómo terminan las barras de cada clase de grupo (D-134)."""

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
    ends: DesignEnds
    dowel_bars: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_limits(self) -> Self:
        check_options(self.fc_options, self.prices, (self.h_min, self.h_max))
        return self


class FootingDesign(DesignLimits):
    """Límites del diseño por tipologías (D-069): el número de tipologías y la forma en planta, cuadrada por defecto;
    "ratio" fija lx/ly."""

    typologies: PositiveInt
    combined_typologies: PositiveInt | None = None  # D-157: tipos de combinadas; sin él, una por par (D-153)
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
    """Columna a cimentar: sección cx × cy (cx a lo largo de X) y sus casos de carga en la base; location (opcional,
    D-130) pasa a su zapata en el proyecto diseñado, para la planta de localización."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    location: Location | None = None
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

    @model_validator(mode="before")
    @classmethod
    def _layout(cls, data: Any) -> Any:
        """concrete, reinforcement_steel y soil de la entrada a la estructura interna (D-139)."""
        return internal(data)

    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: Soil
    design: FootingDesign
    columns: tuple[DesignColumn, ...] = ()  # las de las zapatas aisladas; puede quedar vacío con combined_footings (D-156)
    curve: CurveSettings | None = None  # solo el ejemplo de la curva costo–N (D-096)
    detailing: DetailingSettings | None = None  # D-127: con él, el costo sale de la cartilla y el proyecto diseñado lo lleva
    drawing: DrawingSettings | None = None  # D-127: pasa al proyecto diseñado; requiere detailing (D-126)
    combined_footings: tuple["DesignPair", ...] = ()  # D-153: pares de columnas en zapata combinada, una por par
    min_clear_spacing: PositiveFloat | None = None  # D-156: separación libre mínima entre zapatas vecinas (mm); solo avisa

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [column.id for column in self.columns]
        ids += [column.id for pair in self.combined_footings for column in pair.columns]
        if len(ids) != len(set(ids)):
            raise ValueError("los identificadores de las columnas deben ser únicos (también entre las aisladas y las combinadas)")
        pairs = [pair.id for pair in self.combined_footings]
        if len(pairs) != len(set(pairs)):
            raise ValueError("los identificadores de las zapatas combinadas deben ser únicos")
        if not self.columns and not self.combined_footings:
            raise ValueError("el diseño necesita columnas aisladas (columns) o zapatas combinadas (combined_footings)")
        if self.columns and self.design.typologies > len(self.columns):
            raise ValueError("hay más tipologías que columnas")
        _check_drawing(self.detailing, self.drawing)
        for pair in self.combined_footings:
            # Un solo f'c para toda la cimentación (D-153): las combinadas prueban los mismos f'c que las aisladas.
            if sorted(pair.combined_design.fc_options) != sorted(self.design.fc_options):
                raise ValueError(f"la zapata combinada '{pair.id}' debe probar los mismos f'c que design.fc_options (D-153)")
            pair_project(self, pair)  # los casos, placement_case y el resto del diseño de la combinada se validan ya
        return self


def _check_drawing(detailing: DetailingSettings | None, drawing: DrawingSettings | None) -> None:
    if drawing is not None and detailing is None:
        raise ValueError("drawing requiere detailing: el dibujo rotula las marcas de la cartilla (D-126)")


class CombinedDesign(DesignLimits):
    """Límites del diseño de una zapata combinada (D-107). plan_max limita el largo y el ancho. Los
    linderos (medianería) se declaran en cada columna (property_lines, D-154); sin ellos, la base se centra en la
    resultante. placement_case es el caso de servicio sin sismo
    cuya resultante ubica la base (D-108); sin él, el de servicio sin sismo de mayor carga total. stirrup_bars son las
    barras permitidas para estribos de la viga larga (D-110): con ellas, el cortante y la torsión pueden tomarlos estribos
    en lugar de un espesor mayor; sin ellas no se proponen estribos. shape = "inverted_t" diseña una T invertida (D-113):
    h_min, h_step y h_max son los del espesor de la zarpa; beam_h_* los del alto total de la viga, y el alma parte de la
    columna más ancha más web_margin a cada lado y crece de a web_step hasta web_max (D-136). shape = "trapezoid" o
    "stepped" (planta en T o L, D-164) se puede declarar, pero el diseño responde que no está implementado (D-165)."""

    min_steel_exception: bool  # D-123: si el diseño y la verificación admiten la excepción de 4/3 del As,min
    placement_case: str | None = Field(None, min_length=1)
    stirrup_bars: tuple[str, ...] = ()  # D-110: barras para estribos de la viga larga; sin ellas, no se proponen
    # D-113; trapezoid y stepped (T o L, D-164) se declaran, pero su diseño todavía no está implementado (D-165)
    shape: Literal["rectangular", "inverted_t", "trapezoid", "stepped"] = "rectangular"
    web_margin: NonNegativeFloat | None = None  # T invertida: margen del alma a cada lado de la columna más ancha, mm
    web_step: PositiveFloat | None = None  # T invertida: paso del ancho del alma, mm
    web_max: PositiveFloat | None = None  # T invertida: ancho máximo del alma que prueba la búsqueda, mm (D-136)
    beam_h_min: PositiveFloat | None = None  # T invertida: alto total de la viga, mm
    beam_h_step: PositiveFloat | None = None
    beam_h_max: PositiveFloat | None = None

    @model_validator(mode="before")
    @classmethod
    def _old_cantilevers(cls, data: Any) -> Any:
        """max_cantilever_start y max_cantilever_end se reemplazaron por los linderos de cada columna (D-154)."""
        if isinstance(data, dict) and {"max_cantilever_start", "max_cantilever_end"} & set(data):
            raise ValueError("max_cantilever_start y max_cantilever_end se reemplazaron por property_lines en cada columna: el "
                             "voladizo maximo mas alla de la cara de esa columna en cada lado global (-x, +x, -y, +y), D-154")
        return data

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.ends.skin is None:
            raise ValueError("combined_design.ends necesita skin: cómo terminan las barras de piel que se diseñen (D-134)")
        if self.stirrup_bars and self.ends.stirrups is None:
            raise ValueError("combined_design.ends necesita stirrups (hook90, hook135 o hook180) si hay stirrup_bars (D-134)")
        t_fields = ("web_margin", "web_step", "web_max", "beam_h_min", "beam_h_step", "beam_h_max")
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


Side = Literal["-x", "+x", "-y", "+y"]


class CombinedDesignColumn(_Input):
    """Columna de la zapata combinada a diseñar: sección cx × cy (cx a lo largo de X global), su eje en (x, y) en ejes
    globales con cualquier origen (el diseño ubica la base; el proyecto diseñado las da respecto al centro de la base) y
    sus casos de carga en la base. property_lines (D-154): los linderos de la columna, el voladizo máximo de la base más
    allá de la cara de esta columna en cada lado global (0: la cara al ras del lindero)."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    x: float
    y: float
    property_lines: dict[Side, NonNegativeFloat] | None = None
    loads: tuple[FootingLoad, ...] = Field(min_length=1)

    def face(self, side: Side) -> float:
        """La coordenada global de la cara de la columna en ese lado."""
        sign = 1.0 if side[0] == "+" else -1.0
        return (self.x + sign * self.cx / 2) if side[1] == "x" else (self.y + sign * self.cy / 2)


def side_limits(columns: Sequence[CombinedDesignColumn]) -> dict[Side, float]:
    """El borde más lejano que permiten los linderos en cada lado global declarado (D-154): en los lados negativos, el
    mayor de (cara − voladizo) de las columnas que lo declaran; en los positivos, el menor de (cara + voladizo)."""
    limits: dict[Side, float] = {}
    for column in columns:
        for side, overhang in (column.property_lines or {}).items():
            edge = column.face(side) + (overhang if side[0] == "+" else -overhang)
            limits[side] = edge if side not in limits else (min(limits[side], edge) if side[0] == "+" else max(limits[side], edge))
    return limits


class CombinedDesignProject(_Input):
    """Proyecto de diseño de una zapata combinada rectangular de dos o más columnas alineadas (D-107, D-163): las columnas
    con sus posiciones y sus cargas, la dirección principal (el eje global en que va la viga que las une) y el bloque combined_design."""

    @model_validator(mode="before")
    @classmethod
    def _layout(cls, data: Any) -> Any:
        """concrete, reinforcement_steel y soil de la entrada a la estructura interna (D-139)."""
        return internal(data)


    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: Soil
    principal_direction: Literal["x", "y"] = "x"
    quantity: PositiveInt  # D-159: las veces que se construye; la cartilla se reporta por unidad y por las N unidades
    combined_design: CombinedDesign
    columns: tuple[CombinedDesignColumn, ...] = Field(min_length=2)  # D-163: dos o más, alineadas
    detailing: DetailingSettings | None = None  # D-127: con él, el costo sale de la cartilla y el proyecto diseñado lo lleva
    drawing: DrawingSettings | None = None  # D-127: pasa al proyecto diseñado; requiere detailing (D-126)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _combined_rules(self)
        return self


def _combined_rules(project: CombinedDesignProject) -> None:
    """Las reglas propias del proyecto de la combinada: columnas distintas, los mismos casos en las dos, placement_case
    de servicio sin sismo (D-108) y casos mayorados."""
    _check_drawing(project.detailing, project.drawing)
    if len({column.id for column in project.columns}) != len(project.columns):
        raise ValueError("los identificadores de las columnas deben ser únicos")
    keys = [{(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in column.loads}
            for column in project.columns]
    repeated = any(len(own) != len(column.loads) for own, column in zip(keys, project.columns, strict=True))
    if repeated or any(own != keys[0] for own in keys[1:]):
        raise ValueError("las columnas deben tener los mismos casos de carga, sin repetir, con los mismos factores y "
                         "la misma marca de sismo")
    chosen = project.combined_design.placement_case
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
    for side, edge in side_limits(project.columns).items():  # los linderos dejan cubrir las columnas (D-154)
        faces = [column.face(side) for column in project.columns]
        reach = max(faces) if side[0] == "+" else min(faces)
        if (side[0] == "+" and edge < reach - _TOUCH) or (side[0] == "-" and edge > reach + _TOUCH):
            raise ValueError(f"el lindero {side} no deja cubrir las columnas: la base debe llegar a la cara {side} de cada una "
                             "(D-154)")


class PairColumn(CombinedDesignColumn):
    """Columna de un par del diseño por tipologías (D-153): la de la combinada con su ubicación de ETABS (D-130)."""

    location: Location | None = None


class DesignPair(_Input):
    """Un par de columnas en zapata combinada dentro del diseño por tipologías (D-153): se diseña con el diseño de la
    combinada (D-107, D-110, D-113), con sus dos columnas ubicadas en ejes globales (de la tabla de coordenadas de
    ETABS), su dirección principal y su bloque combined_design (el común de la plantilla con lo propio del par)."""

    id: str = Field(min_length=1)
    principal_direction: Literal["x", "y"]
    combined_design: CombinedDesign
    columns: tuple[PairColumn, PairColumn]


def pair_project(project: FootingDesignProject, pair: DesignPair) -> CombinedDesignProject:
    """El proyecto de diseño de la combinada de un par (D-153), con los datos comunes del diseño por tipologías. Se arma
    con los modelos ya validados (en unidades internas) y se le aplican las reglas propias del proyecto de la combinada
    (los mismos casos en las dos columnas, placement_case, casos mayorados)."""
    combined = CombinedDesignProject.model_construct(
        description=f"Zapata combinada {pair.id} del diseño por tipologías (D-153).", profile=project.profile,
        seismic=project.seismic, materials=project.materials, soil=project.soil, principal_direction=pair.principal_direction,
        quantity=1,  # D-159: un par es una zapata; su tipo suma las de sus pares
        combined_design=pair.combined_design, columns=pair.columns, detailing=project.detailing, drawing=project.drawing)
    try:
        _combined_rules(combined)
    except ValueError as error:
        raise ValueError(f"la zapata combinada '{pair.id}': {error}") from error
    return combined


FootingDesignProject.model_rebuild()
