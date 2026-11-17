"""Cabezal de una o varias columnas sobre un grupo de pilotes (D-138, D-143). Geometría en mm y fuerzas en kN y kN·m al
declarar, convertidas a N y N·mm al cargar.

El cabezal comparte con la zapata aislada (model/footing.py, FootingBody) su planta, espesor, mallas, relleno, pedestal y
sobrecargas; sus columnas van en columns. cover es el recubrimiento libre de las caras laterales y la superior;
bottom_cover, el de la cara inferior a la malla inferior, que queda sobre la cabeza de los pilotes (mayor que su
empotramiento).

Las cargas llegan de las columnas (columns[].loads, como en la zapata, D-052) o de cada pilote (piles[].loads), según
loads_from.
Las de un pilote son la acción del pilote sobre el cabezal en su cabeza, en ejes globales: P positiva en compresión del
pilote (empuja el cabezal hacia arriba), Vx y Vy la fuerza horizontal y Mx, My el momento (regla de la mano derecha).
"""

import math
from typing import Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.footing import N_MM3_PER_KN_M3, N_PER_KN, Column, FootingBody, FootingLoad, _Input


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


_ON_EDGE = 1e-9  # mm²: tolerancia del producto cruz para un punto sobre el borde
Corner = Literal["+x+y", "-x+y", "-x-y", "+x-y"]
_CORNER_SIGNS: dict[str, tuple[float, float]] = {"-x-y": (-1.0, -1.0), "+x-y": (1.0, -1.0), "+x+y": (1.0, 1.0), "-x+y": (-1.0, 1.0)}


class CornerClip(_Input):
    """Una esquina recortada del cabezal (D-141): la esquina y lo que el recorte quita de cada borde, along_x sobre el
    borde paralelo a X y along_y sobre el paralelo a Y, en mm. El recorte es la recta que une esos dos puntos."""

    corner: Corner
    along_x: PositiveFloat
    along_y: PositiveFloat


def _inside_convex(outline: tuple[tuple[float, float], ...], point: tuple[float, float]) -> bool:
    """Si el punto queda dentro del polígono convexo (en sentido antihorario) o en su borde."""
    count = len(outline)
    return all((outline[(i + 1) % count][0] - outline[i][0]) * (point[1] - outline[i][1])
               - (outline[(i + 1) % count][1] - outline[i][1]) * (point[0] - outline[i][0]) >= -_ON_EDGE for i in range(count))


class CapColumn(Column):
    """Una columna del cabezal (D-143): id, sección cx × cy centrada en (offset_x, offset_y) respecto al centroide del
    cabezal, sus pasadores y sus cargas (loads). Con loads_from = column son las fuerzas de la columna en su base; con
    loads_from = piles son opcionales y solo mayoradas: dan la carga de la columna para el aplastamiento, los pasadores y
    las secciones que la necesitan (si faltan, esas revisiones quedan INCOMPLETE)."""

    id: str = Field(min_length=1)
    loads: tuple[FootingLoad, ...] = ()

    @property
    def area(self) -> float:
        return self.cx * self.cy


def _case_key(load: FootingLoad) -> tuple[float, float, bool]:
    return load.dead_factor, load.live_factor, load.seismic


class PileCap(FootingBody):
    """Cabezal (D-138) de una o varias columnas (columns, D-143). mislocation es la tolerancia de mala ubicación de los
    pilotes, en mm (obligatoria en los dos perfiles; con ACI 318-25, menor que 75 mm no cumple, 13.4.1.4): con las cargas
    de las columnas aumenta los brazos y las reacciones (excentricidad accidental); con las de los pilotes, solo los brazos
    (decisión del usuario, D-138). reactions_include_weight dice, con las cargas de los pilotes, si sus reacciones ya
    incluyen el peso del cabezal, el relleno y las sobrecargas; si no, se suman repartidos por igual. loads_from declara,
    sin ambigüedad, de dónde llegan las cargas: column (loads de cada columna) o piles (loads de cada pilote)."""

    loads_from: Literal["column", "piles"]
    bottom_cover: PositiveFloat
    pile: PileType
    piles: tuple[Pile, ...] = Field(min_length=1)
    columns: tuple[CapColumn, ...] = Field(min_length=1)
    mislocation: NonNegativeFloat = Field(validation_alias="mislocation_mm")
    reactions_include_weight: bool | None = None
    clipped_corners: tuple[CornerClip, ...] = ()

    @model_validator(mode="after")
    def _check_piles(self) -> Self:
        ids = [pile.id for pile in self.piles]
        if len(ids) != len(set(ids)):
            raise ValueError(f"el cabezal '{self.id}' repite un pilote")
        self._check_clips()
        outline = self.outline
        for pile in self.piles:
            if not _inside_convex(outline, (pile.x, pile.y)) or abs(pile.x) >= self.lx / 2 or abs(pile.y) >= self.ly / 2:
                raise ValueError(f"el pilote '{pile.id}' del cabezal '{self.id}' queda fuera del cabezal")
        self._check_columns()
        if self.bottom_cover <= self.pile.embedment:
            raise ValueError(f"en el cabezal '{self.id}' bottom_cover debe ser mayor que el empotramiento de los pilotes: "
                             "la malla inferior va sobre su cabeza")
        if self.bottom_cover + self.cover >= self.h:
            raise ValueError(f"los recubrimientos del cabezal '{self.id}' no dejan espacio para las mallas")
        self._check_loads()
        return self

    def _check_columns(self) -> None:
        """Ids únicos, cada columna dentro del contorno y sin traslaparse con otra."""
        ids = [column.id for column in self.columns]
        if len(ids) != len(set(ids)):
            raise ValueError(f"el cabezal '{self.id}' repite una columna")
        outline = self.outline
        for column in self.columns:
            corners = [(column.offset_x + sx * column.cx / 2, column.offset_y + sy * column.cy / 2) for sx, sy in _CORNER_SIGNS.values()]
            if not all(_inside_convex(outline, point) and abs(point[0]) <= self.lx / 2 and abs(point[1]) <= self.ly / 2
                       for point in corners):
                raise ValueError(f"la columna '{column.id}' del cabezal '{self.id}' queda fuera de su contorno")
        for index, a in enumerate(self.columns):
            for b in self.columns[index + 1 :]:
                if (abs(a.offset_x - b.offset_x) < (a.cx + b.cx) / 2 and abs(a.offset_y - b.offset_y) < (a.cy + b.cy) / 2):
                    raise ValueError(f"las columnas '{a.id}' y '{b.id}' del cabezal '{self.id}' se traslapan")

    def _check_loads(self) -> None:
        """Una sola fuente de cargas, con los mismos casos y factores en todas las columnas o en todos los pilotes; con las
        de los pilotes, reactions_include_weight, y las cargas de las columnas (opcionales) solo mayoradas y de casos de
        los pilotes."""
        with_loads = [bool(pile.loads) for pile in self.piles]
        if self.loads_from == "column":
            if not all(column.loads for column in self.columns) or any(with_loads):
                raise ValueError(f"el cabezal '{self.id}' declara loads_from = column: cada columna lleva sus cargas (loads) y "
                                 "sus pilotes no llevan cargas")
            if self.reactions_include_weight is not None:
                raise ValueError(f"reactions_include_weight del cabezal '{self.id}' solo se declara con las cargas de los pilotes")
            self._same_cases([(f"la columna '{column.id}'", column.loads) for column in self.columns], "columnas")
            return
        if not all(with_loads):
            raise ValueError(f"el cabezal '{self.id}' declara loads_from = piles: cada pilote lleva sus cargas")
        if self.reactions_include_weight is None:
            raise ValueError(f"el cabezal '{self.id}' toma las cargas de los pilotes: declara reactions_include_weight")
        self._same_cases([(f"el pilote '{pile.id}'", pile.loads) for pile in self.piles], "pilotes")
        factored = {(load.case): _case_key(load) for load in self.piles[0].loads if load.kind == "factored"}
        for column in self.columns:
            names = [load.case for load in column.loads]
            if len(names) != len(set(names)):
                raise ValueError(f"la columna '{column.id}' del cabezal '{self.id}' repite un caso de carga")
            for load in column.loads:
                if load.kind != "factored" or factored.get(load.case) != _case_key(load):
                    raise ValueError(f"con las cargas de los pilotes, la columna '{column.id}' del cabezal '{self.id}' solo lleva "
                                     "casos mayorados de los pilotes, con sus mismos factores (D-143)")

    def _same_cases(self, owners: list[tuple[str, tuple[FootingLoad, ...]]], plural: str) -> None:
        first = {(load.kind, load.case): _case_key(load) for load in owners[0][1]}
        for name, loads in owners:
            cases = {(load.kind, load.case): _case_key(load) for load in loads}
            if len(cases) != len(loads):
                raise ValueError(f"{name} del cabezal '{self.id}' repite un caso de carga")
            if cases != first:
                raise ValueError(f"los {plural} del cabezal '{self.id}' deben tener los mismos casos, con los mismos factores")

    def _check_clips(self) -> None:
        """Una esquina se recorta una vez; los recortes caben en sus bordes sin cruzarse."""
        corners = [clip.corner for clip in self.clipped_corners]
        if len(corners) != len(set(corners)):
            raise ValueError(f"el cabezal '{self.id}' recorta dos veces la misma esquina")
        taken = {"x": {1.0: 0.0, -1.0: 0.0}, "y": {1.0: 0.0, -1.0: 0.0}}  # lo recortado de cada borde: y = ±ly/2, x = ±lx/2
        for clip in self.clipped_corners:
            sx, sy = _CORNER_SIGNS[clip.corner]
            taken["x"][sy] += clip.along_x
            taken["y"][sx] += clip.along_y
        if any(value >= self.lx for value in taken["x"].values()) or any(value >= self.ly for value in taken["y"].values()):
            raise ValueError(f"los recortes de esquina del cabezal '{self.id}' no caben en sus bordes")

    @property
    def outline(self) -> tuple[tuple[float, float], ...]:
        """Contorno del cabezal en sentido antihorario, con las esquinas recortadas (D-141), en mm."""
        hx, hy = self.lx / 2, self.ly / 2
        clips: dict[str, CornerClip] = {clip.corner: clip for clip in self.clipped_corners}
        points: list[tuple[float, float]] = []
        for corner, (sx, sy) in _CORNER_SIGNS.items():
            clip = clips.get(corner)
            if clip is None:
                points.append((sx * hx, sy * hy))
                continue
            vertical, horizontal = (sx * hx, sy * (hy - clip.along_y)), (sx * (hx - clip.along_x), sy * hy)
            points.extend((vertical, horizontal) if corner in ("-x-y", "+x+y") else (horizontal, vertical))
        return tuple(points)

    @property
    def area(self) -> float:
        """Área del cabezal: el rectángulo menos los triángulos de las esquinas recortadas, en mm²."""
        return self.lx * self.ly - sum(clip.along_x * clip.along_y / 2 for clip in self.clipped_corners)

    @property
    def bottom_face_cover(self) -> float:
        return self.bottom_cover

    @property
    def column_area(self) -> float:
        """Área de las columnas (o pedestales), donde no hay relleno ni sobrecarga, en mm²."""
        return sum(column.area for column in self.columns)

    @property
    def all_columns(self) -> tuple[Column, ...]:
        return self.columns

    @property
    def band_centre(self) -> tuple[float, float] | None:
        """La franja central γs solo con una columna (D-138); con varias, la franja de cada columna (D-143)."""
        if len(self.columns) != 1:
            return None
        return self.columns[0].offset_x, self.columns[0].offset_y

    @property
    def from_piles(self) -> bool:
        """Si las cargas llegan de los pilotes (no de las columnas)."""
        return self.loads_from == "piles"

    def case_loads(self) -> list[tuple[FootingLoad, tuple[FootingLoad, ...], tuple[FootingLoad | None, ...]]]:
        """Cada caso: su carga de referencia (la de la primera columna, o la del primer pilote, para el nombre, el tipo y los
        factores), la de cada pilote (vacía con las cargas de las columnas) y la de cada columna (None si no la declara)."""
        def own(loads: tuple[FootingLoad, ...], load: FootingLoad) -> FootingLoad | None:
            return next((item for item in loads if (item.kind, item.case) == (load.kind, load.case)), None)

        source = self.piles[0].loads if self.from_piles else self.columns[0].loads
        cases = []
        for load in source:
            piles = tuple(item for pile in self.piles if (item := own(pile.loads, load)) is not None) if self.from_piles else ()
            cases.append((load, piles, tuple(own(column.loads, load) for column in self.columns)))
        return cases
