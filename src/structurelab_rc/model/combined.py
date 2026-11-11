"""Zapata combinada rectangular de dos columnas (D-080). Las mismas unidades que la zapata aislada (D-052, D-055, D-057):
geometría en mm, sobrecargas en kN/m² al declarar. Se declara en ejes globales de ETABS, con el origen en el centroide de
la base; principal_direction dice en qué eje va la viga que une las columnas. El cálculo trabaja en ejes de la viga (X a
lo largo de ella): con la dirección principal en la Y global, la geometría, el armado y las cargas se rotan al cargar
(D-094). Las propiedades derivadas se calculan; nunca se declaran.
"""

from typing import Any, Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.footing import MPA_PER_KPA, BarSet, Dowels, FootingLoad, Mat, RectangularBase, Soil, _Input
from structurelab_rc.model.reinforcement import BarLayer, Stirrups

COLUMNS = 2


class SkinBars(_Input):
    """Refuerzo superficial en las caras laterales largas (y = ±ly/2) de la zapata combinada: barras paralelas a X a la
    separación vertical spacing, al recubrimiento de la cara (ACI 9.7.2.3, NSR-10 C.10.6.7; D-083)."""

    designation: str = Field(min_length=1)
    spacing: PositiveFloat


class FoundationBeam(_Input):
    """Viga de la zapata combinada en T invertida (D-093): alma de ancho width centrada en Y sobre la zarpa, con altura
    total height medida desde la base (la zarpa tiene el espesor h de la zapata)."""

    width: PositiveFloat
    height: PositiveFloat


class TopBars(BarSet):
    """Barras superiores paralelas a X de la zapata combinada; end declara cómo terminan: rectas o con gancho estándar
    (D-082)."""

    end: Literal["straight", "hook"]


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


class CombinedFooting(RectangularBase, _Input):
    """Zapata combinada de espesor h con dos columnas a lo largo de X. bottom es la malla inferior en las dos direcciones;
    top, las barras superiores paralelas a X (opcional: sin ellas, el momento negativo se revisa como concreto simple,
    D-072); stirrups, los estribos de la dirección larga, como en las vigas (opcional, D-081); torsion_layers, las capas
    de Aℓ de la viga larga con el formato de las vigas y role "torsion" (x desde la cara −Y, profundidad desde la cara
    superior; opcional, D-088); deep_beam declara que la viga larga es de gran altura (D-089); beam la vuelve una T
    invertida: h es el espesor de la zarpa y la viga, con las columnas encima, va centrada en Y (D-093). fill_height,
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
    top: TopBars | None = None
    stirrups: Stirrups | None = None
    skin: SkinBars | None = None
    torsion_layers: tuple[BarLayer, ...] = ()
    deep_beam: bool = False
    beam: FoundationBeam | None = None
    principal_direction: Literal["x", "y"] = "x"

    @model_validator(mode="before")
    @classmethod
    def _to_beam_axes(cls, data: Any) -> Any:
        """Dirección principal en la Y global (D-094): la zapata se escribe en ejes globales (ly a lo largo de la viga,
        columnas a distintas y, bottom.y paralela a la viga) y se pasa a los ejes de la viga, en los que trabaja todo el
        cálculo, con un giro de +90° alrededor de Z (X de la viga = +Y global, Y de la viga = −X global): lx' = ly,
        ly' = lx; columnas x' = y, y' = −x, cx' = cy, cy' = cx; las mallas x e y (y first) se intercambian; cargas
        Vx' = Vy, Vy' = −Vx, Mx' = My, My' = −Mx (P no cambia). top, estribos, refuerzo superficial, capas de torsión,
        band y la viga de la T no tienen dirección propia: ya van paralelos o transversales a la viga. El modelo queda en
        ejes de la viga: no se vuelve a serializar como entrada."""
        if not isinstance(data, dict) or data.get("principal_direction") != "y":
            return data
        rotated = {**data, "lx": data.get("ly"), "ly": data.get("lx"),
                   "columns": [_column_to_beam_axes(column) for column in data.get("columns", [])]}
        bottom = data.get("bottom")
        if isinstance(bottom, dict):
            first = {"x": "y", "y": "x"}.get(bottom.get("first", ""), bottom.get("first"))
            rotated["bottom"] = {**bottom, "first": first, "x": bottom.get("y"), "y": bottom.get("x")}
        return rotated

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
            # Se compara en ejes de la viga; el mensaje nombra el eje global en que la escribió el usuario (D-094).
            raise ValueError(f"las columnas de la zapata combinada '{self.id}' se traslapan a lo largo de la viga (dirección "
                             f"principal {self.principal_direction.upper()} global)")
        self._check_beam()
        for layer in self.torsion_layers:
            if layer.role != "torsion" or layer.depth >= self.total_height:
                raise ValueError(f"las capas de torsion de la zapata combinada '{self.id}' deben tener role 'torsion' y quedar "
                                 "dentro del espesor")
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

    def _check_beam(self) -> None:
        """T invertida (D-093): viga más alta que la zarpa y más angosta que la base, columnas dentro de su ancho, barras
        superiores obligatorias (con momento negativo la cara superior de la viga queda a tracción) y sin band."""
        beam = self.beam
        if beam is None:
            return
        if beam.height <= self.h or beam.width >= self.ly:
            raise ValueError(f"la viga de la zapata combinada '{self.id}' debe ser más alta que la zarpa y más angosta que la base")
        for column in self.columns:
            if abs(column.y) + column.cy / 2 > beam.width / 2:
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' se sale del ancho de la viga")
            if column.band is not None:
                raise ValueError(f"la zapata combinada en T invertida '{self.id}' no usa band (columna '{column.id}')")
        if self.top is None:
            raise ValueError(f"la zapata combinada en T invertida '{self.id}' requiere barras superiores (top) en la viga")

    @property
    def total_height(self) -> float:
        """Altura total: la de la viga en la T invertida (D-093) o el espesor h, en mm."""
        return self.h if self.beam is None else self.beam.height

    @property
    def stem_height(self) -> float:
        """Altura del alma de la viga sobre la zarpa (0 sin viga), en mm."""
        return self.total_height - self.h

    @property
    def column_area(self) -> float:
        """Área de las dos columnas (o pedestales), en mm²: el relleno y las sobrecargas ocupan el resto de la base."""
        return sum(column.area for column in self.columns)

    def weights(self, soil: "Soil") -> tuple[float, float, float]:
        """Pesos de la zapata (zarpa y viga), de los pedestales y del relleno, en N (D-093): el relleno ocupa la base sobre
        la zarpa menos la viga y, sobre la viga, su ancho menos las columnas."""
        if self.beam is None:
            return super().weights(soil)
        web = self.beam.width * self.lx
        footing = soil.unit_weight_concrete * (self.area * self.h + web * self.stem_height)
        pedestal = soil.unit_weight_concrete * self.column_area * self.pedestal_height
        over_beam = max(self.fill_height - self.stem_height, 0.0)
        fill = soil.unit_weight_fill * ((self.area - web) * self.fill_height + (web - self.column_area) * over_beam)
        return footing, pedestal, fill

    def cases(self) -> list[tuple[FootingLoad, ...]]:
        """Los casos de carga, cada uno con la carga de cada columna (en el orden de columns)."""
        by_column = [{(load.kind, load.case): load for load in column.loads} for column in self.columns]
        return [tuple(own[key] for own in by_column) for key in by_column[0]]


_GLOBAL_KEYS = ("Vx_kN", "Vy_kN", "Mx_kNm", "My_kNm")


def _column_to_beam_axes(column: Any) -> Any:
    """Una columna de entrada (ejes globales) en los ejes de una viga en la Y global (D-094)."""
    if not isinstance(column, dict):
        return column  # la validación de la columna reporta lo que falte
    moved = {**column, "loads": [_load_to_beam_axes(load) for load in column.get("loads", [])]}
    if "x" in column and "y" in column:
        moved["x"], moved["y"] = column["y"], -column["x"]
    if "cx" in column and "cy" in column:
        moved["cx"], moved["cy"] = column["cy"], column["cx"]
    return moved


def _load_to_beam_axes(load: Any) -> Any:
    """Un caso de carga de entrada (kN, kN·m, ejes globales) rotado a los ejes de una viga en la Y global (D-094)."""
    if not isinstance(load, dict) or not all(key in load for key in _GLOBAL_KEYS):
        return load  # la validación del caso reporta lo que falte
    return {**load, "Vx_kN": load["Vy_kN"], "Vy_kN": -load["Vx_kN"], "Mx_kNm": load["My_kNm"], "My_kNm": -load["Mx_kNm"]}

