"""Proyecto de entrada. Geometría en mm y esfuerzos en MPa; las demandas se convierten a N y N·mm."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.reinforcement import ReinforcementLayout

N_PER_KN = 1e3
NMM_PER_KNM = 1e6


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SeismicFacts(_Input):
    level: str = Field(min_length=1)
    justification: str = Field(min_length=1)


Coating = Literal["uncoated", "galvanized", "epoxy", "zinc_epoxy"]


class Materials(_Input):
    """fy del refuerzo longitudinal y fyt de los estribos; concrete declara el tipo de concreto (D-028) y coating el
    recubrimiento de las barras, que cambia su longitud de desarrollo (D-071). max_aggregate es el tamaño máximo nominal
    del agregado grueso, en mm (D-102): sin él, la separación mínima de las barras queda INCOMPLETE."""

    fc: PositiveFloat
    fy: PositiveFloat
    fyt: PositiveFloat
    concrete: Literal["normalweight", "lightweight"]
    coating: Coating
    max_aggregate: PositiveFloat | None = None


class Section(_Input):
    """Ejes de ETABS (D-044): X = eje 3 (horizontal), Y = eje 2 (vertical, hacia arriba), Z = eje 1 (eje del miembro).

    El alma va de x = 0 (cara del lado −3) a x = bw. Una sección con ala declara hf y los salientes a cada lado
    (overhang_x_neg hacia −3 y overhang_x_pos hacia +3; 0 si no hay): T con ambos, L con uno. El ala está en la
    cara superior. cover es el recubrimiento libre a los estribos.
    """

    bw: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    hf: PositiveFloat | None = None
    overhang_x_neg: NonNegativeFloat | None = None
    overhang_x_pos: NonNegativeFloat | None = None

    @model_validator(mode="after")
    def _check_flange(self) -> Self:
        overhangs = (self.overhang_x_neg, self.overhang_x_pos)
        if self.hf is None:
            if any(overhang is not None for overhang in overhangs):
                raise ValueError("los salientes del ala requieren hf")
            return self
        if any(overhang is None for overhang in overhangs):
            raise ValueError("una sección con ala declara overhang_x_neg y overhang_x_pos (0 si no hay)")
        if self.flange_width == self.bw:
            raise ValueError("una sección con ala necesita al menos un saliente mayor que cero")
        if self.hf >= self.h:
            raise ValueError("hf debe ser menor que h")
        return self

    @property
    def flange_width(self) -> float:
        """Ancho total en la cara superior: bw más los salientes."""
        return self.bw + (self.overhang_x_neg or 0.0) + (self.overhang_x_pos or 0.0)

    @property
    def bf(self) -> float | None:
        """Ancho del ala, o None en secciones rectangulares."""
        return None if self.hf is None else self.flange_width

    @property
    def area(self) -> float:
        """Área bruta, en mm²."""
        return self.bw * self.h + (self.flange_width - self.bw) * (self.hf or 0.0)


class Demands(_Input):
    """Fuerzas mayoradas con la convención de ETABS (D-044).

    Pu positiva en compresión. Mu (M3) positivo comprime la cara +2 (superior); M2 positivo comprime la cara +3
    (x = bw). Vu es V2 (vertical) y V3 es el cortante horizontal; Tu es la torsión.
    """

    pu: float | None = Field(default=None, validation_alias="Pu_kN")
    mu: float | None = Field(default=None, validation_alias="Mu_kNm")
    m2: float | None = Field(default=None, validation_alias="M2_kNm")
    vu: float | None = Field(default=None, validation_alias="Vu_kN")
    v3: float | None = Field(default=None, validation_alias="V3_kN")
    tu: float | None = Field(default=None, validation_alias="Tu_kNm")

    @field_validator("mu", "m2", "tu")
    @classmethod
    def _knm_to_nmm(cls, value: float | None) -> float | None:
        return None if value is None else value * NMM_PER_KNM

    @field_validator("pu", "vu", "v3")
    @classmethod
    def _kn_to_n(cls, value: float | None) -> float | None:
        return None if value is None else value * N_PER_KN


class Station(_Input):
    """z es la posición a lo largo del miembro (eje 1), en mm. case nombra el estado de carga; es solo informativo."""

    z: NonNegativeFloat
    layout: ReinforcementLayout
    demands: Demands
    case: str | None = None


class Member(_Input):
    """type declara el tipo de miembro; statically_determinate solo se exige para As,min con el ala a tracción (D-021);
    deep_beam declara que es viga de gran altura (ACI 9.9.1.1, NSR-10 C.11.7.1): se verifican sus criterios (D-089);
    min_steel_exception declara si el As,min de flexión admite la excepción de 4/3 del As requerido por análisis (ACI
    9.6.1.3, NSR-10 C.10.5.3), en los dos ejes (obligatorio, D-123)."""

    id: str = Field(min_length=1)
    type: Literal["beam", "column", "footing", "wall", "slab"]
    min_steel_exception: bool
    statically_determinate: bool | None = None
    deep_beam: bool = False
    length: PositiveFloat
    section: Section
    stations: tuple[Station, ...] = Field(min_length=1)


class DetailingSettings(_Input):
    """Despiece (D-125): longitud comercial de las barras en mm; las más largas se empalman por traslapo."""

    stock_length: PositiveFloat = Field(validation_alias="stock_length_mm")


class DrawingSettings(_Input):
    """Dibujo del refuerzo (D-126): escala de impresión (50 para 1:50), que fija la altura de los textos y las cotas."""

    scale: PositiveFloat


class Project(_Input):
    """Vigas (members), zapatas aisladas (footings), zapatas combinadas (combined_footings, D-080) o varias; las zapatas
    requieren los datos del suelo (D-052)."""

    description: str
    profile: str
    seismic: SeismicFacts
    materials: Materials
    members: tuple[Member, ...] = ()
    soil: Soil | None = None
    footings: tuple[Footing, ...] = ()
    combined_footings: tuple[CombinedFooting, ...] = ()
    detailing: DetailingSettings | None = None  # D-125: sin él no se despieza
    drawing: DrawingSettings | None = None  # D-126: sin él no se dibuja; requiere detailing

    @model_validator(mode="after")
    def _check_content(self) -> Self:
        any_footing = bool(self.footings or self.combined_footings)
        if not self.members and not any_footing:
            raise ValueError("el proyecto debe tener al menos un miembro o una zapata")
        if any_footing and self.soil is None:
            raise ValueError("las zapatas requieren los datos del suelo (soil)")
        if self.soil is not None and not any_footing:
            raise ValueError("soil solo se declara con zapatas")
        ids = ([member.id for member in self.members] + [footing.id for footing in self.footings]
               + [footing.id for footing in self.combined_footings])
        if len(ids) != len(set(ids)):
            raise ValueError("los identificadores de miembros y zapatas deben ser únicos")
        if self.drawing is not None and self.detailing is None:
            raise ValueError("drawing requiere detailing: el dibujo rotula las marcas de la cartilla (D-126)")
        return self
