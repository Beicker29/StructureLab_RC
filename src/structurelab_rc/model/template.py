"""Plantilla para importar fuerzas de ETABS: todo lo que el archivo de ETABS no trae (D-042)."""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from structurelab_rc.model.footing import Column, Dowels, Mat
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
    deep_beam: bool = False
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


class LoadsSource(_Input):
    """De dónde salen las cargas de cada tipo de una zapata combinada (D-084): del Excel de ETABS de ese tipo
    ("etabs") o de la plantilla ("json", en columns[].loads)."""

    service: Literal["etabs", "json"] = "etabs"
    factored: Literal["etabs", "json"] = "etabs"


class TemplateCombinedColumn(_Input):
    """Columna de una zapata combinada en la plantilla: la del proyecto (D-080), con el Unique Name del nudo de ETABS
    del que salen sus reacciones; loads trae solo los casos de los tipos que vienen de la plantilla."""

    id: str = Field(min_length=1)
    etabs_unique_name: str = Field(min_length=1)
    cx: PositiveFloat
    cy: PositiveFloat
    x: float
    y: float
    dowels: Dowels | None = None
    band: dict[str, Any] | None = None
    loads: tuple[dict[str, Any], ...] = ()


class TemplateCombinedFooting(_Input):
    """Zapata combinada de la plantilla (D-084): la del proyecto con columnas de ETABS y el origen de cada tipo de carga.
    El armado y la geometría se validan con el proyecto que se genera."""

    id: str = Field(min_length=1)
    lx: PositiveFloat
    ly: PositiveFloat
    h: PositiveFloat
    cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead_kNm2: NonNegativeFloat
    surcharge_live_kNm2: NonNegativeFloat
    loads_source: LoadsSource = LoadsSource()
    columns: tuple[TemplateCombinedColumn, ...] = Field(min_length=2, max_length=2)
    bottom: dict[str, Any]
    top: dict[str, Any] | None = None
    stirrups: dict[str, Any] | None = None
    skin: dict[str, Any] | None = None
    torsion_layers: list[dict[str, Any]] | None = None
    deep_beam: bool = False

    @model_validator(mode="after")
    def _check_sources(self) -> Self:
        sources = {"service": self.loads_source.service, "factored": self.loads_source.factored}
        for column in self.columns:
            kinds = {load.get("kind") for load in column.loads}
            for kind, source in sources.items():
                if source == "json" and kind not in kinds:
                    raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' no trae casos '{kind}' "
                                     "y loads_source los pide de la plantilla")
                if source == "etabs" and kind in kinds:
                    raise ValueError(f"la columna '{column.id}' de la zapata combinada '{self.id}' trae casos '{kind}' que "
                                     "loads_source toma de ETABS")
        if self.columns[0].etabs_unique_name == self.columns[1].etabs_unique_name:
            raise ValueError(f"las dos columnas de la zapata combinada '{self.id}' tienen el mismo Unique Name")
        return self

    def etabs_kinds(self) -> tuple[str, ...]:
        """Los tipos de carga que salen de los Excel de ETABS."""
        return tuple(kind for kind in ("service", "factored") if getattr(self.loads_source, kind) == "etabs")


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
    footings: tuple[TemplateFooting, ...] = ()
    combined_footings: tuple[TemplateCombinedFooting, ...] = ()

    @model_validator(mode="after")
    def _check_names(self) -> Self:
        if not self.footings and not self.combined_footings:
            raise ValueError("la plantilla debe tener al menos una zapata aislada (footings) o combinada (combined_footings)")
        names = [name for footing in self.footings for name in footing.etabs_unique_names]
        names += [column.etabs_unique_name for footing in self.combined_footings for column in footing.columns]
        if len(set(names)) != len(names):
            raise ValueError("un Unique Name aparece en dos zapatas")
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

