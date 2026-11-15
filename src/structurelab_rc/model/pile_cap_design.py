"""Proyecto de diseño de cabezales sobre pilotes (D-141).

Cada cabezal trae su columna y sus cargas. Con las de la columna (loads_from = column) el diseño elige el número y el
arreglo de los pilotes, de familias generadas con la separación entre centros (pile_spacing) y la distancia del centro de
los pilotes al borde (edge_distance) declaradas, y el cabezal; con las de los pilotes (loads_from = piles) el arreglo
queda declarado y se diseña solo el cabezal. Se elige la solución de menor costo: concreto, acero y pilotes. Unidades de
entrada como en los cabezales (mm, kN, kN·m, kN/m², kN/m³); precios en la moneda del usuario.
"""

from typing import Any, Literal, Self

from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, model_validator

from structurelab_rc.model.design import DesignEnds, DesignMaterials, Prices, _check_drawing, check_options
from structurelab_rc.model.footing import FootingLoad, _Input
from structurelab_rc.model.layout import internal
from structurelab_rc.model.pile_cap import CornerClip, Pile, PileCapSoil, PileType
from structurelab_rc.model.project import DetailingSettings, DrawingSettings, SeismicFacts


class PileCapPrices(Prices):
    """Precios del diseño de cabezales: los del concreto por f'c y del acero por kg, y el de cada pilote."""

    pile_each: PositiveFloat


class PileCapDesign(_Input):
    """Límites del diseño de cabezales (D-141): f'c que se evalúan y sus precios; el pilote, la separación mínima entre
    centros y la distancia del centro de los pilotes al borde (datos del usuario); el máximo de pilotes por cabezal; el
    espesor (h_min, h_step, h_max), los recubrimientos, el relleno, el pedestal y las sobrecargas; las barras permitidas,
    el paso de su separación, cómo terminan (ends) y las barras de los pasadores; la tolerancia de mala ubicación."""

    fc_options: tuple[float, ...] = Field(min_length=1)
    prices: PileCapPrices
    pile: PileType
    pile_spacing: PositiveFloat
    edge_distance: PositiveFloat
    max_piles: PositiveInt = 30
    h_min: PositiveFloat
    h_step: PositiveFloat
    h_max: PositiveFloat
    cover: PositiveFloat
    bottom_cover: PositiveFloat
    fill_height: NonNegativeFloat
    pedestal_height: NonNegativeFloat
    surcharge_dead: NonNegativeFloat = Field(validation_alias="surcharge_dead_kNm2")
    surcharge_live: NonNegativeFloat = Field(validation_alias="surcharge_live_kNm2")
    bars: tuple[str, ...] = Field(min_length=1)
    spacing_step: PositiveFloat
    ends: DesignEnds
    dowel_bars: tuple[str, ...] = Field(min_length=1)
    mislocation: NonNegativeFloat = Field(validation_alias="mislocation_mm")

    @model_validator(mode="after")
    def _check(self) -> Self:
        check_options(self.fc_options, self.prices, (self.h_min, self.h_max))
        if self.pile_spacing <= self.pile.size:
            raise ValueError("pile_spacing debe ser mayor que el tamano del pilote")
        if self.edge_distance <= self.pile.size / 2:
            raise ValueError("edge_distance debe dejar el pilote dentro del cabezal")
        return self


class DesignCapColumn(_Input):
    """La columna del cabezal: sección cx × cy, en el centroide del grupo de pilotes."""

    cx: PositiveFloat
    cy: PositiveFloat


class DesignCap(_Input):
    """Un cabezal a diseñar: su columna y sus cargas, de la columna (loads) o de cada pilote (piles con sus coordenadas
    y cargas, y si sus reacciones incluyen el peso); clipped_corners solo con el arreglo declarado."""

    id: str = Field(min_length=1)
    loads_from: Literal["column", "piles"]
    column: DesignCapColumn
    loads: tuple[FootingLoad, ...] = ()
    piles: tuple[Pile, ...] = ()
    reactions_include_weight: bool | None = None
    clipped_corners: tuple[CornerClip, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.loads_from == "column":
            if not self.loads or self.piles or self.reactions_include_weight is not None or self.clipped_corners:
                raise ValueError(f"el cabezal '{self.id}' con loads_from = column lleva loads; el diseño elige los pilotes")
        elif self.loads or len(self.piles) < 2 or self.reactions_include_weight is None:  # noqa: PLR2004 - un grupo
            raise ValueError(f"el cabezal '{self.id}' con loads_from = piles lleva sus pilotes (dos o mas) con sus cargas y "
                             "reactions_include_weight")
        return self


class PileCapDesignProject(_Input):
    """Proyecto de diseño de cabezales (D-141); concrete sin f'c (lo elige el diseño), reinforcement_steel y soil como en
    los cabezales (D-139)."""

    description: str
    profile: str
    seismic: SeismicFacts
    materials: DesignMaterials
    soil: PileCapSoil
    pile_cap_design: PileCapDesign
    caps: tuple[DesignCap, ...] = Field(min_length=1)
    detailing: DetailingSettings | None = None
    drawing: DrawingSettings | None = None

    @model_validator(mode="before")
    @classmethod
    def _layout(cls, data: Any) -> Any:
        """concrete, reinforcement_steel y soil de la entrada a la estructura interna (D-139)."""
        return internal(data)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [cap.id for cap in self.caps]
        if len(ids) != len(set(ids)):
            raise ValueError("los identificadores de los cabezales deben ser unicos")
        _check_drawing(self.detailing, self.drawing)
        return self
