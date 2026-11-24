"""Zapata combinada rectangular de dos o más columnas alineadas (D-080, D-163). Las mismas unidades que la zapata aislada
(D-052, D-055, D-057): geometría en mm, sobrecargas en kN/m² al declarar. Se declara en ejes globales de ETABS, con el
origen en el centroide de la base; principal_direction dice en qué eje va la viga que une las columnas. El cálculo
trabaja en ejes de la viga (X a lo largo de ella): con la dirección principal en la Y global, la geometría, el armado y
las cargas se rotan al cargar (D-094). Las propiedades derivadas se calculan; nunca se declaran."""

import math
from functools import cached_property
from typing import Any, Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, field_validator, model_validator

from structurelab_rc.model.footing import (
    MPA_PER_KPA,
    BarSet,
    Dowels,
    FootingLoad,
    Location,
    Mat,
    RectangularBase,
    UnitWeighted,
    _Input,
)
from structurelab_rc.model.reinforcement import BarEnd, BarLayer, Stirrups

COLUMNS = 2


class SkinBars(_Input):
    """Refuerzo superficial en las caras laterales largas (y = ±ly/2) de la zapata combinada: barras paralelas a X a la
    separación vertical spacing, al recubrimiento de la cara (ACI 9.7.2.3, NSR-10 C.10.6.7; D-083), y su extremo (D-134)."""

    designation: str = Field(min_length=1)
    spacing: PositiveFloat
    end: BarEnd


class FoundationBeam(_Input):
    """Viga de la zapata combinada en T invertida (D-093): alma de ancho width centrada en Y sobre la zarpa, con altura
    total height medida desde la base (la zarpa tiene el espesor h de la zapata).

    El refuerzo de la viga se declara como en las vigas (D-106): layers con depth desde la cara superior de la viga, role
    (flexure, skin o torsion), bars con x desde la cara −Y del alma y end, cómo terminan sus barras (obligatorio, D-134);
    stirrups, los estribos, con su gancho de cierre (end, obligatorio). La capa de flexión más profunda es la inferior:
    puede salir del alma,
    sobre la zarpa, hasta bottom_width (centrado en el alma; por defecto, el ala efectiva del perfil); fuera de ese ancho
    van las barras x de la malla de la zarpa.
    """

    width: PositiveFloat
    height: PositiveFloat
    layers: tuple[BarLayer, ...] = Field(min_length=1)
    stirrups: Stirrups | None = None
    bottom_width: PositiveFloat | None = None
    axis: float | None = None  # D-167: con plan, la coordenada t del eje del alma; sin ella, el centroide de la planta

    @model_validator(mode="after")
    def _check_layers(self) -> Self:
        if not any(layer.role == "flexure" for layer in self.layers):
            raise ValueError("la viga de la T invertida necesita al menos una capa de flexion")
        if any(layer.end is None for layer in self.layers):
            raise ValueError("cada capa de la viga de la T invertida declara end: straight, hook90 o hook180 (D-134, D-161)")
        if self.stirrups is not None and self.stirrups.end is None:
            raise ValueError("los estribos de la viga de la T invertida declaran end: hook90, hook135 o hook180 (D-134)")
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
    opcional, pero hay al menos una, cada una con su extremo (D-134). first es la dirección más cercana a la cara
    superior: obligatoria con las dos."""

    first: Literal["x", "y"] | None = None
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


Point = tuple[float, float]


class PlanEdge(_Input):
    """Un extremo del trapecio (D-164): sus coordenadas transversales mínima y máxima, en mm."""

    low: float
    high: float

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.high <= self.low:
            raise ValueError("en la planta, high debe ser mayor que low")
        return self


class PlanPart(PlanEdge):
    """Un tramo de la planta en T o L (D-164): su largo a lo largo de la dirección principal y sus coordenadas
    transversales mínima y máxima, en mm."""

    length: PositiveFloat


class Plan(_Input):
    """Planta no rectangular de la combinada (D-164), en ejes globales: a lo largo de la dirección principal desde el
    borde negativo de la zapata (a = 0) y en el eje global transversal desde la línea de referencia del usuario (t = 0).
    trapezoid: length, start (extremo negativo) y end (positivo); stepped: los tramos en orden, dos o más (T, L u otra
    forma escalonada). Las columnas se dan en el mismo sistema; el área y el centroide se calculan."""

    shape: Literal["trapezoid", "stepped"]
    length: PositiveFloat | None = None
    start: PlanEdge | None = None
    end: PlanEdge | None = None
    parts: tuple[PlanPart, ...] | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.shape == "trapezoid":
            if self.length is None or self.start is None or self.end is None or self.parts is not None:
                raise ValueError("la planta trapezoid declara length, start y end (y no parts)")
        elif self.parts is None or len(self.parts) < COLUMNS or any(
                value is not None for value in (self.length, self.start, self.end)):
            raise ValueError("la planta stepped declara parts con dos o más tramos (y no length, start ni end)")
        elif any(min(a.high, b.high) <= max(a.low, b.low) for a, b in zip(self.parts, self.parts[1:], strict=False)):
            raise ValueError("en la planta stepped, cada tramo debe compartir ancho con el siguiente")
        return self

    def polygon(self) -> tuple[Point, ...]:
        """Contorno en (a, t), antihorario, sin vértices alineados en los escalones."""
        if self.shape == "trapezoid":
            assert self.length is not None and self.start is not None and self.end is not None
            return ((0.0, self.start.low), (self.length, self.end.low), (self.length, self.end.high), (0.0, self.start.high))
        assert self.parts is not None
        lower: list[Point] = []
        upper: list[Point] = []
        a = 0.0
        for part in self.parts:
            lower += [(a, part.low), (a + part.length, part.low)]
            upper += [(a, part.high), (a + part.length, part.high)]
            a += part.length
        return _without_collinear((*lower, *reversed(upper)))

    def area_centroid(self) -> tuple[float, float, float]:
        """Área y centroide (a, t) del contorno (fórmula de Gauss)."""
        points = self.polygon()
        area = ca = ct = 0.0
        for (a1, t1), (a2, t2) in zip(points, (*points[1:], points[0]), strict=True):
            cross = a1 * t2 - a2 * t1
            area, ca, ct = area + cross, ca + (a1 + a2) * cross, ct + (t1 + t2) * cross
        return area / 2, ca / (3 * area), ct / (3 * area)


_COLLINEAR = 1e-9  # mm²: producto cruz por debajo del cual tres puntos están alineados


def _without_collinear(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """El contorno sin puntos repetidos ni intermedios sobre una recta (los escalones de ancho igual)."""
    unique = [point for index, point in enumerate(points) if point != points[index - 1]]
    kept = []
    for index, point in enumerate(unique):
        before, after = unique[index - 1], unique[(index + 1) % len(unique)]
        cross = (point[0] - before[0]) * (after[1] - before[1]) - (point[1] - before[1]) * (after[0] - before[0])
        if abs(cross) > _COLLINEAR:
            kept.append(point)
    return tuple(kept)


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
    """Zapata combinada de espesor h con dos o más columnas a lo largo de X (D-163). bottom es la malla inferior en las dos direcciones;
    top, las barras superiores con la misma estructura (D-099; opcional: sin barras superiores en una dirección, su
    momento negativo se revisa como concreto simple, D-072); stirrups, los estribos de la dirección larga, como en las
    vigas (opcional, D-081; solo para el cortante: la torsión es de placa, D-118, y torsion_layers se rechaza);
    deep_beam declara que la viga larga es de gran altura (D-089); beam la vuelve una T invertida: h es el espesor de
    la zarpa y la viga, con las columnas encima, va centrada en Y (D-093). fill_height, pedestal_height, cover y las
    sobrecargas, como en la zapata aislada (D-057). typology (opcional) es el tipo de combinada que rotula la planta de
    localización y el cuadro de tipologías (D-157); sin él, el id."""

    id: str = Field(min_length=1)
    quantity: PositiveInt  # D-159: las veces que se construye; la cartilla se reporta por unidad y por las N unidades
    typology: str | None = Field(default=None, min_length=1)
    lx: PositiveFloat
    ly: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead: NonNegativeFloat = Field(validation_alias="surcharge_dead_kNm2")
    surcharge_live: NonNegativeFloat = Field(validation_alias="surcharge_live_kNm2")
    columns: tuple[CombinedColumn, ...] = Field(min_length=COLUMNS)  # D-163: dos o más, alineadas a lo largo de la viga
    bottom: Mat
    top: TopMat | None = None
    stirrups: Stirrups | None = None
    skin: SkinBars | None = None
    min_steel_exception: bool  # D-123: la excepción de 4/3 del As,min en la viga larga, las franjas y la viga de la T
    deep_beam: bool = False
    beam: FoundationBeam | None = None
    principal_direction: Literal["x", "y"] = "x"
    plan: Plan | None = None  # D-164: planta trapezoidal o en T/L; sin ella, el rectángulo lx × ly

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
        data = _place_plan(data)
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
        first_x, last_x = self.x_range
        for column in self.columns:
            x0, x1 = column.x - column.cx / 2, column.x + column.cx / 2
            low, high = self.across(x0, x1) if first_x <= x0 and x1 <= last_x else (math.inf, -math.inf)
            if x0 < first_x or x1 > last_x or column.y - column.cy / 2 < low or column.y + column.cy / 2 > high:
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' se sale de la base")
        ordered = sorted(self.columns, key=lambda column: column.x)
        if any(first.x + first.cx / 2 >= second.x - second.cx / 2 for first, second in zip(ordered, ordered[1:], strict=False)):
            # Se compara en ejes de la viga; el mensaje nombra el eje global en que la escribió el usuario (D-094).
            raise ValueError(f"las columnas de la zapata combinada '{self.id}' se traslapan a lo largo de la viga (dirección "
                             f"principal {self.principal_direction.upper()} global)")
        self._check_beam()
        if self.stirrups is not None and self.stirrups.end is None:
            raise ValueError(f"los estribos de la zapata combinada '{self.id}' declaran end: hook90, hook135 o hook180 (D-134)")
        if 2 * self.cover >= self.h:
            raise ValueError(f"el recubrimiento de la zapata combinada '{self.id}' no deja espacio para las mallas")
        if any(bar_set.band_spacing is not None for bar_set in (self.bottom.x, self.bottom.y)):
            raise ValueError(f"la zapata combinada '{self.id}' no usa band_spacing: el refuerzo bajo cada columna va en band")
        cases = [{(load.kind, load.case): (load.dead_factor, load.live_factor, load.seismic) for load in column.loads}
                 for column in self.columns]
        for column, own in zip(self.columns, cases, strict=True):
            if len(own) != len(column.loads):
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' repite un caso de carga")
        if any(own != cases[0] for own in cases[1:]):
            raise ValueError(f"las columnas de la zapata combinada '{self.id}' deben tener los mismos casos de carga, "
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
        if beam.axis is not None and self.plan is None:
            raise ValueError(f"beam.axis de la zapata combinada '{self.id}' solo se declara con plan: sin ella el alma va centrada")
        low_face, high_face = self.web_faces
        if self.plan is not None:  # el alma cabe en la planta en todo su largo (D-167)
            low, high = self.across(*self.x_range)
            if low_face < low - 1e-6 or high_face > high + 1e-6:
                raise ValueError(f"el alma de la zapata combinada '{self.id}' se sale de la planta en algún tramo (D-167)")
        misplaced = [name for name, value in (("stirrups", self.stirrups), ("skin", self.skin)) if value]
        if misplaced:
            raise ValueError(f"la zapata combinada en T invertida '{self.id}' declara el refuerzo de la viga en beam (layers y "
                             f"stirrups), no en {', '.join(misplaced)} (D-106)")
        for column in self.columns:
            if column.y - column.cy / 2 < low_face - 1e-6 or column.y + column.cy / 2 > high_face + 1e-6:
                raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' se sale del ancho de la viga")
            if column.band is not None or column.band_top is not None:
                raise ValueError(f"la zapata combinada en T invertida '{self.id}' no usa band ni band_top (columna '{column.id}')")

    @cached_property
    def geometry_key(self) -> str:
        """Todo lo que fija la presión del suelo y las fuerzas de la viga, sin el refuerzo (D-165): con la misma clave, dos
        zapatas tienen los mismos casos mayorados y la misma viga, y el diseño los reutiliza entre candidatas."""
        exclude: dict[str, Any] = {"bottom": True, "top": True, "stirrups": True, "skin": True, "min_steel_exception": True,
                                   "deep_beam": True, "typology": True, "quantity": True,
                                   "columns": {"__all__": {"dowels", "band", "band_top", "location"}},
                                   "beam": {"layers", "stirrups", "bottom_width"}}
        return self.model_dump_json(exclude=exclude)

    @cached_property
    def outline(self) -> tuple[Point, ...]:
        """Contorno de la base en ejes de la viga, con el origen en su centroide, antihorario: el rectángulo lx × ly o la
        planta declarada (D-164)."""
        if self.plan is None:
            hx, hy = self.lx / 2, self.ly / 2
            return ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))
        _, ca, ct = self.plan.area_centroid()
        points = [(a - ca, t - ct) for a, t in self.plan.polygon()]
        if self.principal_direction == "x":
            return tuple(points)
        # Y de la viga = −X global (D-094): el reflejo t → −t invierte el sentido de recorrido.
        return tuple((a, -t) for a, t in reversed(points))

    @property
    def area(self) -> float:
        """Área de la base, en mm²: la del rectángulo o la de la planta (D-164)."""
        return self.lx * self.ly if self.plan is None else self.plan.area_centroid()[0]

    def _second_moments(self) -> tuple[float, float]:
        """(∫y² dA, ∫x² dA) de la planta respecto a su centroide (fórmula de Green)."""
        ixx = iyy = 0.0
        points = self.outline
        for (x1, y1), (x2, y2) in zip(points, (*points[1:], points[0]), strict=True):
            cross = x1 * y2 - x2 * y1
            ixx += (y1 * y1 + y1 * y2 + y2 * y2) * cross / 12
            iyy += (x1 * x1 + x1 * x2 + x2 * x2) * cross / 12
        return abs(ixx), abs(iyy)

    @property
    def inertia_x(self) -> float:
        """Inercia respecto al eje X por el centroide, en mm⁴ (en una planta trapezoidal o en T/L, la del polígono)."""
        return super().inertia_x if self.plan is None else self._second_moments()[0]

    @property
    def inertia_y(self) -> float:
        """Inercia respecto al eje Y por el centroide, en mm⁴."""
        return super().inertia_y if self.plan is None else self._second_moments()[1]

    @property
    def modulus_x(self) -> float:
        """Módulo de sección respecto al eje X con la fibra más alejada, en mm³."""
        return super().modulus_x if self.plan is None else self.inertia_x / max(abs(y) for _, y in self.outline)

    @property
    def modulus_y(self) -> float:
        """Módulo de sección respecto al eje Y con la fibra más alejada, en mm³."""
        return super().modulus_y if self.plan is None else self.inertia_y / max(abs(x) for x, _ in self.outline)

    @property
    def kern(self) -> tuple[float, float]:
        """Núcleo central en cada eje (S/A; lx/6 y ly/6 en el rectángulo)."""
        return super().kern if self.plan is None else (self.modulus_y / self.area, self.modulus_x / self.area)

    @cached_property
    def x_range(self) -> tuple[float, float]:
        """Extremos de la base a lo largo de la viga, en ejes de la viga (−lx/2 y lx/2 en el rectángulo)."""
        xs = [x for x, _ in self.outline]
        return min(xs), max(xs)

    @cached_property
    def y_range(self) -> tuple[float, float]:
        """Extremos de la base transversales a la viga, en ejes de la viga (−ly/2 y ly/2 en el rectángulo)."""
        ys = [y for _, y in self.outline]
        return min(ys), max(ys)

    def across(self, x0: float, x1: float | None = None) -> tuple[float, float]:
        """Bordes −Y y +Y de la base en la abscisa x0 o, entre x0 y x1, los más estrechos (D-164): en un escalón cuenta
        el tramo más angosto. En el rectángulo, (−ly/2, ly/2)."""
        if self.plan is None:
            return -self.ly / 2, self.ly / 2
        high_x = x0 if x1 is None else x1
        first, last = self.x_range
        points = [x0, high_x, *(x for x, _ in self.outline if x0 < x < high_x)]
        low, high = -math.inf, math.inf
        for x in points:
            # A cada lado del punto (en un escalón, los dos tramos): la planta es monótona en x.
            for side in (x - _NUDGE, x + _NUDGE):
                values = _crossings(self.outline, min(max(side, first + _NUDGE), last - _NUDGE))
                low, high = max(low, min(values)), min(high, max(values))
        return low, high

    @cached_property
    def web_axis(self) -> float:
        """Ordenada del eje del alma de la T invertida en ejes de la viga, desde el centroide (0 sin plan o sin axis,
        D-167): beam.axis está en el sistema de la planta y se lleva al centroide y, con la viga en la Y global, se refleja
        como toda la planta (Y de la viga = −X global)."""
        if self.plan is None or self.beam is None or self.beam.axis is None:
            return 0.0
        offset = self.beam.axis - self.plan.area_centroid()[2]
        return offset if self.principal_direction == "x" else -offset

    @property
    def web_faces(self) -> tuple[float, float]:
        """Caras −Y y +Y del alma en ejes de la viga (D-167)."""
        assert self.beam is not None
        return self.web_axis - self.beam.width / 2, self.web_axis + self.beam.width / 2

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
        """Área de las columnas (o pedestales), en mm²: el relleno y las sobrecargas ocupan el resto de la base."""
        return sum(column.area for column in self.columns)

    def weights(self, soil: UnitWeighted) -> tuple[float, float, float]:
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


_NUDGE = 1e-6  # mm: a cada lado de una abscisa, para leer los dos tramos de un escalón


def _crossings(outline: tuple[Point, ...], x: float) -> list[float]:
    """Las y en que la recta vertical de abscisa x (fuera de los lados verticales) corta el contorno."""
    found = []
    for (x1, y1), (x2, y2) in zip(outline, (*outline[1:], outline[0]), strict=True):
        if x1 != x2 and min(x1, x2) <= x <= max(x1, x2):
            found.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
    return found


def _place_plan(data: Any) -> Any:
    """Con plan (D-164): lx y ly son la caja de la planta en ejes globales y las columnas pasan del sistema de la planta
    (a desde el borde negativo de la dirección principal, t desde la línea de referencia transversal) al centroide de la
    base, aún en ejes globales; después se rotan como toda la zapata (D-094)."""
    if not isinstance(data, dict) or not isinstance(data.get("plan"), dict):
        return data
    if "lx" in data or "ly" in data:
        raise ValueError(f"la zapata combinada '{data.get('id', '')}' declara plan: lx y ly se calculan, no se declaran (D-164)")
    plan = Plan.model_validate(data["plan"])
    _, ca, ct = plan.area_centroid()
    points = plan.polygon()
    along = max(a for a, _ in points) - min(a for a, _ in points)
    width = max(t for _, t in points) - min(t for _, t in points)
    principal = data.get("principal_direction", "x")
    sizes = {"lx": along, "ly": width} if principal == "x" else {"lx": width, "ly": along}

    def moved(column: Any) -> Any:
        if not isinstance(column, dict) or "x" not in column or "y" not in column:
            return column
        if principal == "x":
            return {**column, "x": column["x"] - ca, "y": column["y"] - ct}
        return {**column, "x": column["x"] - ct, "y": column["y"] - ca}

    return {**data, **sizes, "columns": [moved(column) for column in data.get("columns", [])]}


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

