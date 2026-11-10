"""Zapata combinada rectangular de dos columnas (D-080). Las mismas unidades y ejes que la zapata aislada (D-052,
D-055, D-057): geometría en mm, sobrecargas en kN/m² al declarar; X es la dirección larga, a lo largo de la cual van las
columnas, con el origen en el centroide de la base. Las propiedades derivadas se calculan; nunca se declaran.
"""

from typing import Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.footing import MPA_PER_KPA, BarSet, Dowels, FootingLoad, Mat, Soil, _Input
from structurelab_rc.model.reinforcement import Stirrups

COLUMNS = 2


class CombinedColumn(_Input):
    """Columna cx × cy (cx a lo largo de X) con su eje en (x, y) respecto al centroide de la base; dowels son sus
    pasadores (si faltan, sus verificaciones quedan INCOMPLETE) y band el refuerzo transversal adicional bajo ella,
    paralelo a Y, en el ancho de su franja (opcional). loads son sus casos de carga en la base de la columna."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    x: float
    y: float
    dowels: Dowels | None = None
    band: BarSet | None = None
    loads: tuple[FootingLoad, ...] = Field(min_length=1)

    @property
    def area(self) -> float:
        return self.cx * self.cy


class CombinedFooting(_Input):
    """Zapata combinada de espesor h con dos columnas a lo largo de X. bottom es la malla inferior en las dos direcciones;
    top, las barras superiores paralelas a X (opcional: sin ellas, el momento negativo se revisa como concreto simple,
    D-072); stirrups, los estribos de la dirección larga, como en las vigas (opcional, D-081). fill_height,
    pedestal_height, cover y las sobrecargas, como en la zapata aislada (D-057)."""

    id: str = Field(min_length=1)
    lx: PositiveFloat
    ly: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead: NonNegativeFloat = Field(validation_alias="surcharge_dead_kNm2")
    surcharge_live: NonNegativeFloat = Field(validation_alias="surcharge_live_kNm2")
    columns: tuple[CombinedColumn, ...] = Field(min_length=COLUMNS, max_length=COLUMNS)
    bottom: Mat
    top: BarSet | None = None
    stirrups: Stirrups | None = None

    @field_validator("surcharge_dead", "surcharge_live")
    @classmethod
    def _kn_m2_to_mpa(cls, value: float) -> float:
        return value * MPA_PER_KPA

    @model_validator(mode="after")
    def _check(self) -> Self:
        for column in self.columns:
            if abs(column.x) + column.cx / 2 > self.lx / 2 or abs(column.y) + column.cy / 2 > self.ly / 2:
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' se sale de la base")
        first, second = sorted(self.columns, key=lambda column: column.x)
        if first.x + first.cx / 2 >= second.x - second.cx / 2:
            raise ValueError(f"las columnas de la zapata combinada '{self.id}' se traslapan a lo largo de X")
        if 2 * self.cover >= self.h:
            raise ValueError(f"el recubrimiento de la zapata combinada '{self.id}' no deja espacio para las mallas")
        if any(bar_set.band_spacing is not None for bar_set in (self.bottom.x, self.bottom.y)):
            raise ValueError(f"la zapata combinada '{self.id}' no usa band_spacing: el refuerzo bajo cada columna va en band")
        cases = [{(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in column.loads}
                 for column in self.columns]
        for column, own in zip(self.columns, cases, strict=True):
            if len(own) != len(column.loads):
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' repite un caso de carga")
        if cases[0] != cases[1]:
            raise ValueError(f"las dos columnas de la zapata combinada '{self.id}' deben tener los mismos casos de carga, "
                             "con los mismos factores y la misma marca de sismo")
        return self

    @property
    def area(self) -> float:
        """Área de la base, en mm²."""
        return self.lx * self.ly

    @property
    def column_area(self) -> float:
        """Área de las dos columnas (o pedestales), en mm²: el relleno y las sobrecargas ocupan el resto de la base."""
        return sum(column.area for column in self.columns)

    def cases(self) -> list[tuple[FootingLoad, ...]]:
        """Los casos de carga, cada uno con la carga de cada columna (en el orden de columns)."""
        by_column = [{(load.kind, load.case): load for load in column.loads} for column in self.columns]
        return [tuple(own[key] for own in by_column) for key in by_column[0]]

    def weights(self, soil: Soil) -> tuple[float, float, float]:
        """Pesos de la zapata, de los dos pedestales y del relleno, en N."""
        footing = soil.unit_weight_concrete * self.area * self.h
        pedestals = soil.unit_weight_concrete * self.column_area * self.pedestal_height
        fill = soil.unit_weight_fill * (self.area - self.column_area) * self.fill_height
        return footing, pedestals, fill
