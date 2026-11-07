"""Zapata aislada rectangular (D-052, D-055, D-057). Geometría en mm; pesos unitarios en kN/m³, presión admisible en
kPa y sobrecargas en kN/m² al declarar, convertidos a N/mm³ y MPa al cargar. Las fuerzas se convierten a N y N·mm.

Ejes globales de ETABS: X a lo largo de lx, Y a lo largo de ly y Z hacia arriba, con origen en el centroide de la
base. Las propiedades derivadas (área, inercias, módulos, núcleo central, pesos) se calculan de las dimensiones;
nunca se declaran.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

N_PER_KN = 1e3
NMM_PER_KNM = 1e6
MPA_PER_KPA = 1e-3  # también kN/m² a N/mm²
N_MM3_PER_KN_M3 = 1e-6


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Soil(_Input):
    """Datos del suelo y de los pesos propios; todos obligatorios (D-052, puntos 3 y 5)."""

    allowable_pressure: PositiveFloat = Field(validation_alias="allowable_pressure_kPa")
    min_contact_fraction: float = Field(gt=0, le=1)
    unit_weight_concrete: PositiveFloat = Field(validation_alias="unit_weight_concrete_kNm3")
    unit_weight_fill: NonNegativeFloat = Field(validation_alias="unit_weight_fill_kNm3")

    @field_validator("allowable_pressure")
    @classmethod
    def _kpa_to_mpa(cls, value: float) -> float:
        return value * MPA_PER_KPA

    @field_validator("unit_weight_concrete", "unit_weight_fill")
    @classmethod
    def _kn_m3_to_n_mm3(cls, value: float) -> float:
        return value * N_MM3_PER_KN_M3


class Column(_Input):
    """Columna rectangular cx × cy (cx a lo largo de X); offset_x y offset_y ubican su eje respecto al centroide de la base."""

    cx: PositiveFloat
    cy: PositiveFloat
    offset_x: float
    offset_y: float


class BarSet(_Input):
    """Barras paralelas, de designación única, a una separación centro a centro constante."""

    designation: str = Field(min_length=1)
    spacing: PositiveFloat


class Mat(_Input):
    """Malla: x son las barras paralelas a X y y las paralelas a Y. first es la dirección más cercana a la cara."""

    first: Literal["x", "y"]
    x: BarSet
    y: BarSet


class FootingLoad(_Input):
    """Fuerzas de la columna sobre la zapata en la base de la columna, ejes globales (D-052, punto 4).

    P positiva en compresión contra el suelo; Vx y Vy son las fuerzas horizontales y Mx, My los momentos con la regla
    de la mano derecha. kind distingue los casos de servicio de los mayorados. Cada caso declara los factores de su
    combinación: dead_factor multiplica el peso de la zapata, el pedestal y el relleno y la sobrecarga muerta;
    live_factor, la sobrecarga viva (D-054, D-057).
    """

    case: str = Field(min_length=1)
    kind: Literal["service", "factored"]
    dead_factor: NonNegativeFloat
    live_factor: NonNegativeFloat
    p: float = Field(validation_alias="P_kN")
    vx: float = Field(validation_alias="Vx_kN")
    vy: float = Field(validation_alias="Vy_kN")
    mx: float = Field(validation_alias="Mx_kNm")
    my: float = Field(validation_alias="My_kNm")

    @field_validator("p", "vx", "vy")
    @classmethod
    def _kn_to_n(cls, value: float) -> float:
        return value * N_PER_KN

    @field_validator("mx", "my")
    @classmethod
    def _knm_to_nmm(cls, value: float) -> float:
        return value * NMM_PER_KNM


class Footing(_Input):
    """Zapata aislada de espesor h. fill_height es la altura del relleno sobre la zapata y pedestal_height la del
    pedestal, que tiene la sección de la columna; cover es el recubrimiento libre de las mallas. top es la malla
    superior, o None si no la hay. surcharge_dead y surcharge_live son las sobrecargas superimpuestas muerta y viva
    sobre el relleno, repartidas en el área de la base menos la de la columna (D-057).
    """

    id: str = Field(min_length=1)
    lx: PositiveFloat
    ly: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead: NonNegativeFloat = Field(validation_alias="surcharge_dead_kNm2")
    surcharge_live: NonNegativeFloat = Field(validation_alias="surcharge_live_kNm2")
    column: Column
    bottom: Mat
    top: Mat | None
    loads: tuple[FootingLoad, ...] = Field(min_length=1)

    @field_validator("surcharge_dead", "surcharge_live")
    @classmethod
    def _kn_m2_to_mpa(cls, value: float) -> float:
        return value * MPA_PER_KPA

    @model_validator(mode="after")
    def _check_geometry(self) -> Self:
        column = self.column
        if abs(column.offset_x) + column.cx / 2 > self.lx / 2 or abs(column.offset_y) + column.cy / 2 > self.ly / 2:
            raise ValueError(f"la columna de la zapata '{self.id}' se sale de la base")
        if 2 * self.cover >= self.h:
            raise ValueError(f"el recubrimiento de la zapata '{self.id}' no deja espacio para las mallas")
        names = [(load.kind, load.case) for load in self.loads]
        if len(names) != len(set(names)):
            raise ValueError(f"la zapata '{self.id}' repite un caso de carga")
        return self

    @property
    def area(self) -> float:
        """Área de la base, en mm²."""
        return self.lx * self.ly

    @property
    def inertia_x(self) -> float:
        """Inercia de la base respecto al eje X (flexión en la dirección Y), en mm⁴."""
        return self.lx * self.ly**3 / 12

    @property
    def inertia_y(self) -> float:
        """Inercia de la base respecto al eje Y (flexión en la dirección X), en mm⁴."""
        return self.ly * self.lx**3 / 12

    @property
    def modulus_x(self) -> float:
        """Módulo de sección respecto al eje X, en mm³."""
        return self.lx * self.ly**2 / 6

    @property
    def modulus_y(self) -> float:
        """Módulo de sección respecto al eje Y, en mm³."""
        return self.ly * self.lx**2 / 6

    @property
    def kern(self) -> tuple[float, float]:
        """Semidiagonales del núcleo central (lx/6, ly/6): con |ex|/lx + |ey|/ly ≤ 1/6 todo el contacto se comprime."""
        return self.lx / 6, self.ly / 6

    @property
    def column_area(self) -> float:
        return self.column.cx * self.column.cy

    def weights(self, soil: Soil) -> tuple[float, float, float]:
        """Pesos de la zapata, del pedestal y del relleno, en N. El relleno ocupa la base menos la columna o el pedestal."""
        footing = soil.unit_weight_concrete * self.area * self.h
        pedestal = soil.unit_weight_concrete * self.column_area * self.pedestal_height
        fill = soil.unit_weight_fill * (self.area - self.column_area) * self.fill_height
        return footing, pedestal, fill

    def surcharges(self) -> tuple[float, float]:
        """Fuerzas de las sobrecargas muerta y viva sobre el área de la base menos la de la columna, en N."""
        area = self.area - self.column_area
        return self.surcharge_dead * area, self.surcharge_live * area
