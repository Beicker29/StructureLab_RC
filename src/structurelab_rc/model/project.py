"""Proyecto de entrada. Geometría en mm y esfuerzos en MPa; las demandas se convierten a N y N·mm."""

from typing import Self

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
    fc: PositiveFloat
    fy: PositiveFloat


class Section(_Input):
    """Rectangular sin bf ni hf; en T con el ala en la cara superior."""

    bw: PositiveFloat
    h: PositiveFloat
    bf: PositiveFloat | None = None
    hf: PositiveFloat | None = None

    @model_validator(mode="after")
    def _check_flange(self) -> Self:
        if (self.bf is None) != (self.hf is None):
            raise ValueError("una sección en T requiere bf y hf")
        if self.bf is not None and self.bf < self.bw:
            raise ValueError("bf no puede ser menor que bw")
        if self.hf is not None and self.hf >= self.h:
            raise ValueError("hf debe ser menor que h")
        return self


class Demands(_Input):
    """Fuerzas mayoradas. Momento positivo: fibra superior comprimida."""

    mu: float | None = Field(default=None, validation_alias="Mu_kNm")
    vu: float | None = Field(default=None, validation_alias="Vu_kN")
    tu: float | None = Field(default=None, validation_alias="Tu_kNm")

    @field_validator("mu", "tu")
    @classmethod
    def _knm_to_nmm(cls, value: float | None) -> float | None:
        return None if value is None else value * NMM_PER_KNM

    @field_validator("vu")
    @classmethod
    def _kn_to_n(cls, value: float | None) -> float | None:
        return None if value is None else value * N_PER_KN


class Station(_Input):
    x: NonNegativeFloat
    layout: ReinforcementLayout
    demands: Demands


class Member(_Input):
    id: str = Field(min_length=1)
    length: PositiveFloat
    section: Section
    stations: tuple[Station, ...] = Field(min_length=1)


class Project(_Input):
    description: str
    profile: str
    seismic: SeismicFacts
    materials: Materials
    members: tuple[Member, ...] = Field(min_length=1)
