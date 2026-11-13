"""Zapata combinada rectangular de dos columnas (D-080). Las mismas unidades que la zapata aislada (D-052, D-055, D-057):
geometría en mm, sobrecargas en kN/m² al declarar. Se declara en ejes globales de ETABS, con el origen en el centroide de
la base; principal_direction dice en qué eje va la viga que une las columnas. El cálculo trabaja en ejes de la viga (X a
lo largo de ella): con la dirección principal en la Y global, la geometría, el armado y las cargas se rotan al cargar
(D-094). Las propiedades derivadas se calculan; nunca se declaran.
"""

from typing import Any, Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.footing import MPA_PER_KPA, BarSet, Dowels, FootingLoad, Location, Mat, RectangularBase, Soil, _Input
from structurelab_rc.model.reinforcement import BarLayer, Stirrups

COLUMNS = 2


class SkinBars(_Input):
    """Refuerzo superficial en las caras laterales largas (y = ±ly/2) de la zapata combinada: barras paralelas a X a la
    separación vertical spacing, al recubrimiento de la cara (ACI 9.7.2.3, NSR-10 C.10.6.7; D-083)."""

    designation: str = Field(min_length=1)
    spacing: PositiveFloat


class FoundationBeam(_Input):
    """Viga de la zapata combinada en T invertida (D-093): alma de ancho width centrada en Y sobre la zarpa, con altura
    total height medida desde la base (la zarpa tiene el espesor h de la zapata).

    El refuerzo de la viga se declara como en las vigas (D-106): layers con depth desde la cara superior de la viga, role
    (flexure, skin o torsion) y bars con x desde la cara −Y del alma; stirrups, los estribos; end, cómo terminan las barras
    longitudinales (rectas o con gancho estándar). La capa de flexión más profunda es la inferior: puede salir del alma,
    sobre la zarpa, hasta bottom_width (centrado en el alma; por defecto, el ala efectiva del perfil); fuera de ese ancho
    van las barras x de la malla de la zarpa.
    """

    width: PositiveFloat
    height: PositiveFloat
    layers: tuple[BarLayer, ...] = Field(min_length=1)
    stirrups: Stirrups | None = None
    end: Literal["straight", "hook"]
    bottom_width: PositiveFloat | None = None

    @model_validator(mode="after")
    def _check_layers(self) -> Self:
        if not any(layer.role == "flexure" for layer in self.layers):
            raise ValueError("la viga de la T invertida necesita al menos una capa de flexion")
        if any(layer.depth >= self.height for layer in self.layers):
            raise ValueError("las capas de la viga de la T invertida deben quedar dentro de su altura")
        if self.bottom_width is not None and self.bottom_width < self.width:
            raise ValueError("bottom_width de la viga de la T invertida no puede ser menor que el ancho del alma")
        return self

    @property
    def bottom_layer(self) -> BarLayer:
        """La capa de flexión más profunda: la inferior de la viga."""
        return max((layer for layer in self.layers if layer.role == "flexure"), key=lambda layer: layer.depth)


class TopMat(_Input):
    """Barras superiores de la zapata combinada, con la estructura de la malla inferior (D-099): x son las paralelas a X
    (a lo largo de la viga) y y las paralelas a Y (transversales, uniformes en todo el largo, D-097); cada dirección es
    opcional, pero hay al menos una. first es la dirección más cercana a la cara superior: obligatoria con las dos. end
    declara cómo terminan las dos: rectas o con gancho estándar (D-082)."""

    first: Literal["x", "y"] | None = None
    end: Literal["straight", "hook"]
    x: BarSet | None = None
    y: BarSet | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        declared = [direction for direction in ("x", "y") if getattr(self, direction) is not None]
        if not declared:
            raise ValueError("top necesita barras x, y o las dos")
        if self.x is not None and self.y is not None and self.first is None:
            raise ValueError("top con barras x e y necesita first (la dirección más cercana a la cara superior)")
        if self.first is not None and self.first not in declared:
            raise ValueError(f"top.first es '{self.first}' pero top no declara barras {self.first}")
        if any(getattr(self, direction).band_spacing is not None for direction in declared):
            raise ValueError("top no usa band_spacing")
        return self

    @property
    def nearest(self) -> str:
        """La dirección más cercana a la cara superior: first o la única declarada."""
        return self.first or ("x" if self.x is not None else "y")


class CombinedColumn(_Input):
    """Columna cx × cy (cx a lo largo de X) con su eje en (x, y) respecto al centroide de la base; dowels son sus
    pasadores (si faltan, sus verificaciones quedan INCOMPLETE) y band el refuerzo inferior transversal bajo ella,
    paralelo a Y, en el ancho de su franja (opcional): si lo hay, es el único refuerzo inferior transversal de esa zona y
    la malla inferior en Y va fuera de ella (D-097). band_top es lo mismo arriba (D-119): las barras superiores
    transversales de la franja, para su momento negativo y el de la torsión de placa; si lo hay, top.y va fuera de esa
    zona. loads son sus casos de carga en la base de la columna. location (opcional, D-130) es su eje en el proyecto, en
    ejes globales: no se rota con la zapata."""

    id: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    x: float
    y: float
    location: Location | None = None
    dowels: Dowels | None = None
    band: BarSet | None = None
    band_top: BarSet | None = None
    loads: tuple[FootingLoad, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_band_top(self) -> Self:
        if self.band_top is not None and self.band_top.band_spacing is not None:
            raise ValueError(f"band_top de la columna '{self.id}' no usa band_spacing")
        return self

    @property
    def area(self) -> float:
        return self.cx * self.cy


class CombinedFooting(RectangularBase, _Input):
    """Zapata combinada de espesor h con dos columnas a lo largo de X. bottom es la malla inferior en las dos direcciones;
    top, las barras superiores con la misma estructura (D-099; opcional: sin barras superiores en una dirección, su
    momento negativo se revisa como concreto simple, D-072); stirrups, los estribos de la dirección larga, como en las
    vigas (opcional, D-081; solo para el cortante: la torsión es de placa, D-118, y torsion_layers se rechaza);
    deep_beam declara que la viga larga es de gran altura (D-089); beam la vuelve una T invertida: h es el espesor de
    la zarpa y la viga, con las columnas encima, va centrada en Y (D-093). fill_height, pedestal_height, cover y las
    sobrecargas, como en la zapata aislada (D-057)."""

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
    top: TopMat | None = None
    stirrups: Stirrups | None = None
    skin: SkinBars | None = None
    min_steel_exception: bool  # D-123: la excepción de 4/3 del As,min en la viga larga, las franjas y la viga de la T
    deep_beam: bool = False
    beam: FoundationBeam | None = None
    principal_direction: Literal["x", "y"] = "x"

    @model_validator(mode="before")
    @classmethod
    def _no_torsion_layers(cls, data: Any) -> Any:
        """La torsión de la combinada es de placa (decisión del usuario, D-118): no lleva Aℓ de vigas. En la T invertida
        la torsión del alma la toman las capas de beam (D-106)."""
        if isinstance(data, dict) and "torsion_layers" in data:
            raise ValueError(f"la zapata combinada '{data.get('id', '')}' no usa torsion_layers: la torsión se diseña como de "
                             "placa (Wood-Armer, D-118) con las barras x e y; en la T invertida, con las capas de beam")
        return data

    @model_validator(mode="before")
    @classmethod
    def _to_beam_axes(cls, data: Any) -> Any:
        """Dirección principal en la Y global (D-094): la zapata se escribe en ejes globales (ly a lo largo de la viga,
        columnas a distintas y, bottom.y paralela a la viga) y se pasa a los ejes de la viga, en los que trabaja todo el
        cálculo, con un giro de +90° alrededor de Z (X de la viga = +Y global, Y de la viga = −X global): lx' = ly,
        ly' = lx; columnas x' = y, y' = −x, cx' = cy, cy' = cx; las barras x e y (y first) de bottom y de top se
        intercambian (D-099); cargas Vx' = Vy, Vy' = −Vx, Mx' = My, My' = −Mx (P no cambia). Estribos, refuerzo
        superficial, band y la viga de la T no tienen dirección propia: ya van paralelos o transversales
        a la viga. El modelo queda en ejes de la viga: no se vuelve a serializar como entrada."""
        if not isinstance(data, dict) or data.get("principal_direction") != "y":
            return data
        rotated = {**data, "lx": data.get("ly"), "ly": data.get("lx"),
                   "columns": [_column_to_beam_axes(column) for column in data.get("columns", [])]}
        for name in ("bottom", "top"):
            mat = data.get(name)
            if isinstance(mat, dict):
                swapped = {key: value for key, value in mat.items() if key not in ("x", "y", "first")}
                swapped.update({new: mat[old] for old, new in (("x", "y"), ("y", "x")) if old in mat})
                if "first" in mat:
                    swapped["first"] = {"x": "y", "y": "x"}.get(mat["first"], mat["first"])
                rotated[name] = swapped
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
        """T invertida (D-093, D-106): viga más alta que la zarpa y más angosta que la base, columnas dentro de su ancho y
        sin band; el refuerzo de la viga (barras superiores e inferiores, estribos, piel y torsión) va en beam, no en la
        zapata. top es la malla superior de la zarpa (D-114)."""
        beam = self.beam
        if beam is None:
            return
        if beam.height <= self.h or beam.width >= self.ly:
            raise ValueError(f"la viga de la zapata combinada '{self.id}' debe ser más alta que la zarpa y más angosta que la base")
        if beam.bottom_width is not None and beam.bottom_width > self.ly:
            raise ValueError(f"bottom_width de la zapata combinada '{self.id}' no puede superar el ancho de la base")
        misplaced = [name for name, value in (("stirrups", self.stirrups), ("skin", self.skin)) if value]
        if misplaced:
            raise ValueError(f"la zapata combinada en T invertida '{self.id}' declara el refuerzo de la viga en beam (layers y "
                             f"stirrups), no en {', '.join(misplaced)} (D-106)")
        for column in self.columns:
            if abs(column.y) + column.cy / 2 > beam.width / 2:
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' se sale del ancho de la viga")
            if column.band is not None or column.band_top is not None:
                raise ValueError(f"la zapata combinada en T invertida '{self.id}' no usa band ni band_top (columna '{column.id}')")

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


def beam_to_global(x: float, y: float) -> tuple[float, float]:
    """Un punto (o vector) en ejes de una viga en la Y global, en los ejes globales declarados: el giro inverso del de la
    carga (D-094, D-101): x = −y', y = x' (0 − y: sin −0.0 en la salida)."""
    return 0.0 - y, x


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

