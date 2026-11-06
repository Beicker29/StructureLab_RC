"""Plantilla para importar fuerzas de ETABS: todo lo que el archivo de ETABS no trae (D-042)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from structurelab_rc.model.project import Materials, Section, SeismicFacts
from structurelab_rc.model.reinforcement import ReinforcementLayout


class _Input(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class Segment(_Input):
    """Tramo del miembro, en mm desde la estación 0 de ETABS, con su armado."""

    start: NonNegativeFloat = Field(alias="from")
    end: PositiveFloat = Field(alias="to")
    layout: ReinforcementLayout

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("el tramo debe terminar despues de empezar")
        return self


class TemplateMember(_Input):
    id: str = Field(min_length=1)
    type: Literal["beam", "column", "footing", "wall", "slab"]
    etabs_unique_name: str = Field(min_length=1)
    statically_determinate: bool | None = None
    length: PositiveFloat
    section: Section
    segments: tuple[Segment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_segments(self) -> Self:
        ordered = sorted(self.segments, key=lambda segment: segment.start)
        if any(second.start < first.end for first, second in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("los tramos de armado se superponen")
        return self


class EtabsTemplate(_Input):
    """combinations limita las combinaciones que se importan; si falta, se importan todas."""

    description: str
    profile: str
    seismic: SeismicFacts
    materials: Materials
    combinations: tuple[str, ...] | None = None
    members: tuple[TemplateMember, ...] = Field(min_length=1)
