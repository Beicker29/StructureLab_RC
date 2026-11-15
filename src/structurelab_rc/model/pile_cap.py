"""Cabezal de una columna sobre un grupo de pilotes (D-138). Geometría en mm y fuerzas en kN y kN·m al declarar,
convertidas a N y N·mm al cargar.

El cabezal es una zapata aislada (model/footing.py) apoyada en pilotes: hereda su planta, espesor, columna, mallas,
relleno, pedestal y sobrecargas. cover es el recubrimiento libre de las caras laterales y la superior; bottom_cover,
el de la cara inferior a la malla inferior, que queda sobre la cabeza de los pilotes (mayor que su empotramiento).

Las cargas llegan de la columna (loads, como en la zapata, D-052) o de cada pilote (piles[].loads), nunca de ambos.
Las de un pilote son la acción del pilote sobre el cabezal en su cabeza, en ejes globales: P positiva en compresión del
pilote (empuja el cabezal hacia arriba), Vx y Vy la fuerza horizontal y Mx, My el momento (regla de la mano derecha).
"""

import math
from typing import Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.footing import N_MM3_PER_KN_M3, N_PER_KN, Footing, FootingLoad, _Input


class PileCapSoil(_Input):
    """Suelo de los cabezales (bloque soil del proyecto, como en las zapatas; D-138): pesos unitarios del concreto y del
    relleno (kN/m³) y los datos geotécnicos de los pilotes para las cargas de servicio: capacidades admisibles a
    compresión (obligatoria), tracción y lateral (opcionales: si un caso las necesita y faltan, la revisión queda
    INCOMPLETE), el aumento de las capacidades en las combinaciones con sismo (1.0 si no se declara), la eficiencia del
    grupo y la excentricidad máxima de la resultante en las combinaciones de servicio sin sismo (D+L)."""

    unit_weight_concrete: PositiveFloat = Field(validation_alias="unit_weight_concrete_kNm3")
    unit_weight_fill: NonNegativeFloat = Field(validation_alias="unit_weight_fill_kNm3")
    pile_capacity_compression: PositiveFloat = Field(validation_alias="pile_capacity_compression_kN")
    pile_capacity_tension: NonNegativeFloat | None = Field(default=None, validation_alias="pile_capacity_tension_kN")
    pile_capacity_lateral: NonNegativeFloat | None = Field(default=None, validation_alias="pile_capacity_lateral_kN")
    seismic_capacity_factor: float = Field(default=1.0, ge=1.0)
    group_efficiency: float = Field(gt=0, le=1)
    max_eccentricity: NonNegativeFloat = Field(validation_alias="max_eccentricity_mm")

    @field_validator("unit_weight_concrete", "unit_weight_fill")
    @classmethod
    def _kn_m3_to_n_mm3(cls, value: float) -> float:
        return value * N_MM3_PER_KN_M3

    @field_validator("pile_capacity_compression", "pile_capacity_tension", "pile_capacity_lateral")
    @classmethod
    def _kn_to_n(cls, value: float | None) -> float | None:
        return None if value is None else value * N_PER_KN

    def factor(self, seismic: bool) -> float:
        """Aumento de las capacidades del caso: seismic_capacity_factor si incluye sismo, si no 1.0."""
        return self.seismic_capacity_factor if seismic else 1.0


class PileType(_Input):
    """El pilote del cabezal: sección circular (size = diámetro) o cuadrada (size = lado) y empotramiento en el cabezal.
    Sus capacidades van en el suelo (PileCapSoil)."""

    shape: Literal["circular", "square"]
    size: PositiveFloat
    embedment: NonNegativeFloat

    @property
    def side(self) -> float:
        """Lado del cuadrado de igual área (ACI 13.2.7.3, NSR-10 C.15.3), para el perímetro de punzonamiento, en mm."""
        return self.size if self.shape == "square" else self.size * math.sqrt(math.pi) / 2


class Pile(_Input):
    """Un pilote: centro (x, y) respecto al centroide del cabezal, en mm, y, si las cargas llegan de los pilotes, su
    acción sobre el cabezal en cada caso."""

    id: str = Field(min_length=1)
    x: float
    y: float
    loads: tuple[FootingLoad, ...] = ()


class PileCap(Footing):
    """Cabezal (D-138). mislocation es la tolerancia de mala ubicación de los pilotes, en mm (obligatoria en los dos
    perfiles; con ACI 318-25, menor que 75 mm no cumple, 13.4.1.4): con las cargas de la columna aumenta los brazos y las
    reacciones (excentricidad accidental); con las de los pilotes, solo los brazos (decisión del usuario, D-138).
    reactions_include_weight dice, con las cargas de los pilotes, si sus reacciones ya incluyen el
    peso del cabezal, el relleno y las sobrecargas; si no, se suman repartidos por igual. loads_from declara, sin
    ambigüedad, de dónde llegan las cargas: column (loads del cabezal) o piles (loads de cada pilote)."""

    loads_from: Literal["column", "piles"]
    bottom_cover: PositiveFloat
    pile: PileType
    piles: tuple[Pile, ...] = Field(min_length=1)
    mislocation: NonNegativeFloat = Field(validation_alias="mislocation_mm")
    reactions_include_weight: bool | None = None
    loads: tuple[FootingLoad, ...] = ()

    @model_validator(mode="after")
    def _check_piles(self) -> Self:
        ids = [pile.id for pile in self.piles]
        if len(ids) != len(set(ids)):
            raise ValueError(f"el cabezal '{self.id}' repite un pilote")
        for pile in self.piles:
            if abs(pile.x) >= self.lx / 2 or abs(pile.y) >= self.ly / 2:
                raise ValueError(f"el pilote '{pile.id}' del cabezal '{self.id}' queda fuera del cabezal")
        if self.bottom_cover <= self.pile.embedment:
            raise ValueError(f"en el cabezal '{self.id}' bottom_cover debe ser mayor que el empotramiento de los pilotes: "
                             "la malla inferior va sobre su cabeza")
        if self.bottom_cover + self.cover >= self.h:
            raise ValueError(f"los recubrimientos del cabezal '{self.id}' no dejan espacio para las mallas")
        self._check_loads()
        return self

    def _check_loads(self) -> None:
        """Una sola fuente de cargas; con las de los pilotes, reactions_include_weight y los mismos casos en todos."""
        with_loads = [bool(pile.loads) for pile in self.piles]
        if self.loads_from == "column":
            if not self.loads or any(with_loads):
                raise ValueError(f"el cabezal '{self.id}' declara loads_from = column: lleva las cargas de la columna (loads) y "
                                 "sus pilotes no llevan cargas")
        elif self.loads or not all(with_loads):
            raise ValueError(f"el cabezal '{self.id}' declara loads_from = piles: cada pilote lleva sus cargas y el cabezal no "
                             "lleva loads")
        if self.loads:
            if self.reactions_include_weight is not None:
                raise ValueError(f"reactions_include_weight del cabezal '{self.id}' solo se declara con las cargas de los pilotes")
            return
        if self.reactions_include_weight is None:
            raise ValueError(f"el cabezal '{self.id}' toma las cargas de los pilotes: declara reactions_include_weight")
        first = {(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in self.piles[0].loads}
        for pile in self.piles:
            cases = {(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in pile.loads}
            if len(cases) != len(pile.loads):
                raise ValueError(f"el pilote '{pile.id}' del cabezal '{self.id}' repite un caso de carga")
            if cases != first:
                raise ValueError(f"los pilotes del cabezal '{self.id}' deben tener los mismos casos, con los mismos factores")

    @property
    def bottom_face_cover(self) -> float:
        return self.bottom_cover

    @property
    def from_piles(self) -> bool:
        """Si las cargas llegan de los pilotes (no de la columna)."""
        return self.loads_from == "piles"

    def case_loads(self) -> list[tuple[FootingLoad, tuple[FootingLoad, ...]]]:
        """Cada caso: su carga de referencia (la de la columna, o la del primer pilote para el nombre, el tipo y los
        factores) y la de cada pilote (vacía con las cargas de la columna)."""
        if not self.from_piles:
            return [(load, ()) for load in self.loads]
        cases = []
        for index, load in enumerate(self.piles[0].loads):
            own = tuple(next(item for item in pile.loads if (item.kind, item.case) == (load.kind, load.case)) for pile in self.piles)
            cases.append((self.piles[0].loads[index], own))
        return cases
