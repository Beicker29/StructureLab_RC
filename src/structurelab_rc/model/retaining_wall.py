"""Muro de contención en voladizo (D-173). Geometría en mm; pesos unitarios en kN/m³, presiones en kPa y ángulos en
grados al declarar, convertidos a N/mm³, MPa y radianes al cargar. Los nombres de los campos propios del muro no llevan
la unidad (decisión del usuario); los comunes con las zapatas (BearingSoil) conservan los suyos. El cálculo es por metro
de muro.

Sección transversal: la pantalla (stem) de espesor constante se apoya en la base, que se extiende hacia el lado del
relleno (talón, heel) y hacia el frente (puntera, toe). El relleno es horizontal en esta fase; su cara superior queda a
backfill_height sobre la cara superior de la base. Las propiedades que salen de las dimensiones (ancho de la base,
alturas, pesos) se calculan; nunca se declaran.
"""

import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, PositiveInt, field_validator, model_validator

from structurelab_rc.model.footing import MPA_PER_KPA, N_MM3_PER_KN_M3, BarSet, BearingSoil


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# Cómo se obtiene cada coeficiente (D-173): Ka con Rankine o Coulomb, Ko con Jaky o Mayne y Kulhawy, o declarado.
METHODS = {"active": ("rankine", "coulomb", "declared"), "at_rest": ("jaky", "mayne_kulhawy", "declared")}


class EarthPressure(_Input):
    """La teoría de presión lateral del muro (D-173, decisión 9), declarada por muro y usada en todos sus cálculos: state
    es el activo (Ka) o el de reposo (Ko); method, cómo se obtiene (Das 2016, capítulo 12, y Das 2014, §13.3): rankine o
    coulomb (ec. 12.26) para Ka; jaky (ec. 13.5) o mayne_kulhawy (ec. 13.7, con ocr) para Ko; declared, con
    coefficient. wall_friction_angle es el δ' declarado (fricción suelo–concreto, en grados), solo con coulomb: se usa
    en las caras de concreto; en los planos dentro del suelo, δ' sale del plano (decisión 9)."""

    state: Literal["active", "at_rest"]
    method: Literal["rankine", "coulomb", "jaky", "mayne_kulhawy", "declared"]
    coefficient: PositiveFloat | None = None
    ocr: float | None = Field(default=None, ge=1.0)
    wall_friction_angle: float | None = Field(default=None, ge=0.0, lt=90.0)

    @field_validator("wall_friction_angle")
    @classmethod
    def _degrees_to_radians(cls, value: float | None) -> float | None:
        return None if value is None else math.radians(value)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.method not in METHODS[self.state]:
            raise ValueError(f"el coeficiente {self.state} se obtiene con {', '.join(METHODS[self.state])}, no con "
                             f"{self.method} (D-173)")
        if (self.method == "declared") != (self.coefficient is not None):
            raise ValueError("coefficient se declara solo con method = 'declared' (D-173)")
        if (self.method == "mayne_kulhawy") != (self.ocr is not None):
            raise ValueError("ocr se declara solo con method = 'mayne_kulhawy' (D-173)")
        if (self.method == "coulomb") != (self.wall_friction_angle is not None):
            raise ValueError("wall_friction_angle (δ', suelo–concreto) se declara solo con el método coulomb (D-173)")
        return self


class RetainingSoil(BearingSoil):
    """El suelo del muro, todo declarado (D-173): lo común con las zapatas (BearingSoil: concreto, qa, contacto mínimo, μ
    y factores de seguridad) y lo propio del relleno: su peso unitario, su ángulo de fricción interna φ' (en grados), su
    cohesión c' (en kPa; obligatoria con Coulomb, que solo la admite nula) y la pasiva frente a la puntera
    (passive_coefficient; sin él no cuenta) con el peso unitario del suelo del frente."""

    unit_weight_backfill: PositiveFloat
    friction_angle: float = Field(gt=0.0, lt=90.0)
    cohesion: NonNegativeFloat | None = None
    passive_coefficient: PositiveFloat | None = None
    unit_weight_front: PositiveFloat | None = None

    @field_validator("unit_weight_backfill", "unit_weight_front")
    @classmethod
    def _kn_m3_to_n_mm3(cls, value: float | None) -> float | None:
        return None if value is None else value * N_MM3_PER_KN_M3

    @field_validator("cohesion")
    @classmethod
    def _kpa_to_mpa(cls, value: float | None) -> float | None:
        return None if value is None else value * MPA_PER_KPA

    @field_validator("friction_angle")
    @classmethod
    def _degrees_to_radians(cls, value: float) -> float:
        return math.radians(value)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.passive_coefficient is not None) != (self.unit_weight_front is not None):
            raise ValueError("la pasiva frente a la puntera necesita passive_coefficient y unit_weight_front (D-173)")
        return self


class StemReinforcement(_Input):
    """El refuerzo de la pantalla: back, las barras verticales de la cara del relleno (las de flexión, que bajan a la
    base y terminan con su extremo); front, las verticales de la cara exterior; horizontal, las horizontales de cada
    cara."""

    back: BarSet
    front: BarSet
    horizontal: BarSet


class BaseReinforcement(_Input):
    """El refuerzo de la base: top, las barras transversales superiores (las de flexión del talón); bottom, las
    transversales inferiores (las de flexión de la puntera); longitudinal, las paralelas al muro en cada cara."""

    top: BarSet
    bottom: BarSet
    longitudinal: BarSet


class WallCase(_Input):
    """Un caso de carga del muro (D-173, como D-057): kind distingue servicio (estabilidad y presiones) de mayorado
    (resistencia); cada caso declara los factores de su combinación: dead_factor multiplica el peso propio del concreto,
    fill_factor el peso del relleno sobre el talón y earth_factor el empuje del relleno."""

    case: str = Field(min_length=1)
    kind: Literal["service", "factored"]
    dead_factor: NonNegativeFloat
    fill_factor: NonNegativeFloat
    earth_factor: NonNegativeFloat


class RetainingWall(_Input):
    """Muro de contención en voladizo (D-173): la pantalla (altura sobre la base y espesor constante), la puntera y el
    talón (salientes desde las caras de la pantalla), el espesor de la base, la altura del relleno sobre la cara superior
    de la base, los recubrimientos libres de la pantalla y de la base, la teoría de presión lateral (earth_pressure,
    decisión 9), el refuerzo y los casos de carga."""

    id: str = Field(min_length=1)
    quantity: PositiveInt  # D-159: las veces que se construye
    stem_height: PositiveFloat
    stem_thickness: PositiveFloat
    toe: NonNegativeFloat
    heel: NonNegativeFloat
    base_thickness: PositiveFloat
    backfill_height: PositiveFloat
    stem_cover: PositiveFloat
    base_cover: PositiveFloat
    earth_pressure: EarthPressure
    stem: StemReinforcement
    base: BaseReinforcement
    cases: tuple[WallCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.backfill_height > self.stem_height:
            raise ValueError(f"el relleno del muro '{self.id}' pasa de la altura de la pantalla")
        if self.toe <= 0 or self.heel <= 0:
            raise ValueError(f"el muro '{self.id}' necesita puntera y talón: el muro sin uno de ellos queda para la fase A2 "
                             "(D-173)")
        for part, cover, thickness in (("la pantalla", self.stem_cover, self.stem_thickness),
                                       ("la base", self.base_cover, self.base_thickness)):
            if 2 * cover >= thickness:
                raise ValueError(f"el recubrimiento de {part} del muro '{self.id}' no deja espacio para el refuerzo")
        names = [(case.kind, case.case) for case in self.cases]
        if len(names) != len(set(names)):
            raise ValueError(f"el muro '{self.id}' repite un caso de carga")
        bar_sets = (self.stem.back, self.stem.front, self.stem.horizontal, self.base.top, self.base.bottom,
                    self.base.longitudinal)
        if any(bar_set.band_spacing is not None for bar_set in bar_sets):
            raise ValueError(f"el refuerzo del muro '{self.id}' no lleva band_spacing (es de las zapatas)")
        return self

    @property
    def base_width(self) -> float:
        """Ancho de la base: puntera + pantalla + talón, en mm."""
        return self.toe + self.stem_thickness + self.heel

    @property
    def retained_height(self) -> float:
        """Altura del empuje para la estabilidad (D-173): del fondo de la base a la cara superior del relleno, en mm."""
        return self.base_thickness + self.backfill_height
