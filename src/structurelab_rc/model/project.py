"""Proyecto de entrada. Geometría en mm y esfuerzos en MPa; las demandas se convierten a N y N·mm."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from structurelab_rc.model.reinforcement import ReinforcementLayout

N_PER_KN = 1e3
NMM_PER_KNM = 1e6


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SeismicFacts(_Input):
    level: str = Field(min_length=1)
    justification: str = Field(min_length=1)


class Materials(_Input):
    """fy del refuerzo longitudinal y fyt de los estribos; concrete declara el tipo de concreto (D-028)."""

    fc: PositiveFloat
    fy: PositiveFloat
    fyt: PositiveFloat
    concrete: Literal["normalweight", "lightweight"]


class Section(_Input):
    """Rectangular sin bf ni hf; en T con el ala en la cara superior. cover es el recubrimiento libre a los estribos.

    flange_sides indica si el ala sobresale a un lado (viga L) o a ambos (viga T); se exige en secciones con ala.
    """

    bw: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    bf: PositiveFloat | None = None
    hf: PositiveFloat | None = None
    flange_sides: Literal[1, 2] | None = None

    @model_validator(mode="after")
    def _check_flange(self) -> Self:
        if (self.bf is None) != (self.hf is None):
            raise ValueError("una sección en T requiere bf y hf")
        if self.bf is not None and self.bf < self.bw:
            raise ValueError("bf no puede ser menor que bw")
        if self.hf is not None and self.hf >= self.h:
            raise ValueError("hf debe ser menor que h")
        if (self.bf is None) != (self.flange_sides is None):
            raise ValueError("flange_sides se declara solo, y siempre, en secciones con ala (bf y hf)")
        return self

    @property
    def area(self) -> float:
        """Área bruta, en mm²."""
        flange = 0.0 if self.bf is None or self.hf is None else (self.bf - self.bw) * self.hf
        return self.bw * self.h + flange


class Demands(_Input):
    """Fuerzas mayoradas. Momento positivo: fibra superior comprimida. Axial positiva: compresión."""

    pu: float | None = Field(default=None, validation_alias="Pu_kN")
    mu: float | None = Field(default=None, validation_alias="Mu_kNm")
    vu: float | None = Field(default=None, validation_alias="Vu_kN")
    tu: float | None = Field(default=None, validation_alias="Tu_kNm")

    @field_validator("mu", "tu")
    @classmethod
    def _knm_to_nmm(cls, value: float | None) -> float | None:
        return None if value is None else value * NMM_PER_KNM

    @field_validator("pu", "vu")
    @classmethod
    def _kn_to_n(cls, value: float | None) -> float | None:
        return None if value is None else value * N_PER_KN


class Station(_Input):
    """case nombra el estado de carga de la estación, por ejemplo la combinación de ETABS; es solo informativo."""

    x: NonNegativeFloat
    layout: ReinforcementLayout
    demands: Demands
    case: str | None = None


class Member(_Input):
    """type declara el tipo de miembro; statically_determinate solo se exige para As,min con el ala a tracción (D-021)."""

    id: str = Field(min_length=1)
    type: Literal["beam", "column", "footing", "wall", "slab"]
    statically_determinate: bool | None = None
    length: PositiveFloat
    section: Section
    stations: tuple[Station, ...] = Field(min_length=1)


class Project(_Input):
    description: str
    profile: str
    seismic: SeismicFacts
    materials: Materials
    members: tuple[Member, ...] = Field(min_length=1)
