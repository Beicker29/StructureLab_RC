"""Carga neta de una zapata en cada caso mayorado, común a flexión, cortante y punzonamiento (D-054, D-057, D-061).

La carga neta hacia arriba es la presión del suelo (Bellos y Bakas 2017, con la resultante factorada de la columna, los
pesos y las sobrecargas) menos las cargas uniformes sobre la zapata fuera de la columna: fd·(γc·h + γf·hf + qD) + fl·qL.
"""

from dataclasses import dataclass

from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import base_resultant
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import invalid_input
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.polygon import Point, area_centroid
from structurelab_rc.mechanics.soil_pressure import SoilPressure, footing_pressure
from structurelab_rc.model.footing import Footing, FootingLoad, Soil

EQUILIBRIUM = "Zapata: equilibrio con cargas mayoradas"


@dataclass(frozen=True)
class FactoredCase:
    """Presión del suelo y carga uniforme hacia abajo (N/mm²) de un caso mayorado."""

    case: str
    pressure: SoilPressure
    net_load: float

    def net(self, polygon: tuple[Point, ...]) -> tuple[float, float, float]:
        """Carga neta hacia arriba sobre el polígono y sus momentos estáticos: ∫q dA, ∫x·q dA, ∫y·q dA, en N y N·mm.

        La carga uniforme se aplica en todo el polígono; quien integre una región con la columna dentro debe restarla
        de la misma forma en las dos regiones que compare.
        """
        force, sx, sy = self.pressure.resultant(polygon)
        area, cx, cy = area_centroid(polygon)
        return force - self.net_load * area, sx - self.net_load * area * cx, sy - self.net_load * area * cy

    def beyond(self, footing: Footing, axis: int, plane: float, outward: float) -> tuple[float, float]:
        """Cortante y momento, respecto al plano, de la carga neta más allá de un plano vertical normal a x (axis = 0) o a
        y (axis = 1), del lado outward (+1 o −1), en todo el ancho. Momento positivo tracciona la cara inferior."""
        hx, hy = footing.lx / 2, footing.ly / 2
        half = hx if axis == 0 else hy
        low, high = (plane, half) if outward > 0 else (-half, plane)
        if high - low <= 0:
            return 0.0, 0.0
        polygon = (((low, -hy), (high, -hy), (high, hy), (low, hy)) if axis == 0
                   else ((-hx, low), (hx, low), (hx, high), (-hx, high)))
        force, sx, sy = self.net(polygon)
        return force, outward * ((sx if axis == 0 else sy) - plane * force)


def _net_load(footing: Footing, soil: Soil, load: FootingLoad) -> float:
    dead = soil.unit_weight_concrete * footing.h + soil.unit_weight_fill * footing.fill_height + footing.surcharge_dead
    return load.dead_factor * dead + load.live_factor * footing.surcharge_live


def factored_cases(footing: Footing, soil: Soil) -> tuple[list[FactoredCase], list[Check]]:
    """Cada caso mayorado con su presión; un caso sin equilibrio con el suelo es FAIL (D-054)."""
    cases, failures = [], []
    for load in footing.loads:
        if load.kind != "factored":
            continue
        resultant = base_resultant(footing, soil, load)
        try:
            if resultant.ex is None or resultant.ey is None:
                raise NoEquilibrium("la carga mayorada sobre el suelo no es de compresion")
            pressure = footing_pressure(footing.lx, footing.ly, resultant.n, resultant.ex, resultant.ey)
        except NoEquilibrium as error:
            failure = invalid_input(f"La resultante mayorada sale de la base: {error}", member=footing.id, case=load.case)
            failures.append(Check(EQUILIBRIUM, Status.FAIL, (failure,), "D-054", member=footing.id, case=load.case))
            continue
        cases.append(FactoredCase(load.case, pressure, _net_load(footing, soil, load)))
    return cases, failures


def column_faces(footing: Footing) -> dict[str, tuple[float, float]]:
    """Caras de la columna por dirección de las barras: {"x": (+X, −X), "y": (+Y, −Y)}."""
    column = footing.column
    return {"x": (column.offset_x + column.cx / 2, column.offset_x - column.cx / 2),
            "y": (column.offset_y + column.cy / 2, column.offset_y - column.cy / 2)}
