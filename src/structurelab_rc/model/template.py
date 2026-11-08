"""Plantilla para importar fuerzas de ETABS: todo lo que el archivo de ETABS no trae (D-042)."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from structurelab_rc.model.footing import Column, Mat
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


class TemplateFooting(_Input):
    """Tipo de zapata: sus dimensiones y mallas se aplican a cada nudo de apoyo de ETABS listado (D-055)."""

    id: str = Field(min_length=1)
    etabs_unique_names: tuple[str, ...] = Field(min_length=1)
    lx: PositiveFloat
    ly: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead_kNm2: NonNegativeFloat
    surcharge_live_kNm2: NonNegativeFloat
    column: Column
    bottom: Mat
    top: Mat | None

    @model_validator(mode="after")
    def _check_names(self) -> Self:
        if len(set(self.etabs_unique_names)) != len(self.etabs_unique_names):
            raise ValueError(f"el tipo de zapata '{self.id}' repite un Unique Name")
        return self


class LoadFactors(_Input):
    """Factores de carga muerta y viva de una combinación de ETABS (D-054, D-057) y si incluye sismo (D-070)."""

    dead: NonNegativeFloat
    live: NonNegativeFloat
    seismic: bool = False


class EtabsFootingTemplate(_Input):
    """Plantilla de zapatas: lo que las tablas de reacciones de ETABS no traen.

    load_factors da los factores de carga muerta y viva de cada combinación, de servicio y mayorada; se aplican al
    peso propio, al relleno y a las sobrecargas (D-054, D-057).
    """

    description: str
    profile: str
    seismic: SeismicFacts
    materials: Materials
    soil: dict[str, float]
    load_factors: dict[str, LoadFactors] = Field(min_length=1)
    footings: tuple[TemplateFooting, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_names(self) -> Self:
        names = [name for footing in self.footings for name in footing.etabs_unique_names]
        if len(set(names)) != len(names):
            raise ValueError("un Unique Name aparece en dos tipos de zapata")
        return self


class TemplateColumns(_Input):
    """Columnas de la misma sección: los Unique Name de sus nudos de apoyo en ETABS y la sección cx × cy (D-069)."""

    etabs_unique_names: tuple[str, ...] = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat


class EtabsFootingDesignTemplate(_Input):
    """Plantilla de diseño de zapatas por tipologías: el bloque design y las columnas; la asignación a tipologías la
    hace el diseño (D-069). soil y design se validan con el proyecto de diseño que se genera."""

    description: str
    profile: str
    seismic: SeismicFacts
    materials: dict[str, Any]
    soil: dict[str, float]
    load_factors: dict[str, LoadFactors] = Field(min_length=1)
    design: dict[str, Any]
    columns: tuple[TemplateColumns, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_names(self) -> Self:
        names = [name for group in self.columns for name in group.etabs_unique_names]
        if len(set(names)) != len(names):
            raise ValueError("un Unique Name aparece en dos grupos de columnas")
        return self

