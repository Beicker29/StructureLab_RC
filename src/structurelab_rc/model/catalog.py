"""Tipos del catálogo de materiales."""

from pydantic import BaseModel, ConfigDict, PositiveFloat


class RebarSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    designation: str
    diameter_mm: PositiveFloat
    area_mm2: PositiveFloat
    mass_kg_m: PositiveFloat
