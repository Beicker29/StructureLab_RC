"""Resultante sobre la base de la zapata: fuerzas de la columna, pesos propios y sobrecargas (D-052, D-054, D-057).

Ejes globales con origen en el centroide de la base. Las fuerzas de la columna (P hacia abajo, Vx, Vy, Mx, My) actúan
en su eje, a la altura H = h + altura del pedestal y desplazado (ox, oy). El momento respecto al centroide de la base
es M + r × F con r = (ox, oy, H) y F = (Vx, Vy, −P):

    Mx_base = Mx − P·oy − H·Vy
    My_base = My + P·ox + H·Vx

La zapata, el relleno y las sobrecargas actúan con centro en el centroide; el pedestal está en el eje de la columna
y ocupa esa área, donde no hay relleno ni sobrecarga. Los pesos y la sobrecarga muerta se multiplican por el factor de
carga muerta del caso y la sobrecarga viva por el de carga viva. Con la resultante vertical N, la excentricidad es
ex = My_base/N y ey = −Mx_base/N.
"""

from dataclasses import dataclass

from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing, FootingLoad, Soil


@dataclass(frozen=True)
class BaseResultant:
    """N positiva en compresión contra el suelo, en N; momentos en N·mm; excentricidades en mm (None si N ≤ 0)."""

    n: float
    mx: float
    my: float
    weight: float

    @property
    def ex(self) -> float | None:
        return self.my / self.n if self.n > 0 else None

    @property
    def ey(self) -> float | None:
        return -self.mx / self.n if self.n > 0 else None


def base_resultant(footing: Footing, soil: Soil, load: FootingLoad) -> BaseResultant:
    """Resultante en el centroide de la base con los factores de carga muerta y viva del caso."""
    column = footing.column
    ox, oy = column.offset_x, column.offset_y
    height = footing.h + footing.pedestal_height
    footing_weight, pedestal_weight, _ = footing.weights(soil)
    # Relleno y sobrecargas por unidad de área sobre toda la base; el área de la columna se resta en su eje.
    dead_per_area = soil.unit_weight_fill * footing.fill_height + footing.surcharge_dead
    live_per_area = footing.surcharge_live
    centred = load.dead_factor * (footing_weight + dead_per_area * footing.area) + load.live_factor * live_per_area * footing.area
    at_column = load.dead_factor * (pedestal_weight - dead_per_area * footing.column_area)
    at_column -= load.live_factor * live_per_area * footing.column_area
    vertical_at_column = load.p + at_column
    mx = load.mx - vertical_at_column * oy - height * load.vy
    my = load.my + vertical_at_column * ox + height * load.vx
    return BaseResultant(load.p + centred + at_column, mx, my, centred + at_column)


def combined_resultant(footing: CombinedFooting, soil: Soil, loads: tuple[FootingLoad, ...]) -> BaseResultant:
    """Resultante de una zapata combinada (D-080) para un caso: las fuerzas de cada columna en su eje (x, y) a la altura
    h + pedestal, su pedestal y el área que ocupa (sin relleno ni sobrecarga), y la zapata, el relleno y las sobrecargas
    en el centroide; los factores de carga muerta y viva son los del caso, iguales en las dos columnas."""
    case = loads[0]
    height = footing.h + footing.pedestal_height
    footing_weight, _, _ = footing.weights(soil)
    dead_per_area = soil.unit_weight_fill * footing.fill_height + footing.surcharge_dead
    live_per_area = footing.surcharge_live
    n = case.dead_factor * (footing_weight + dead_per_area * footing.area) + case.live_factor * live_per_area * footing.area
    mx = my = 0.0
    weight = n
    for column, load in zip(footing.columns, loads, strict=True):
        at_column = case.dead_factor * (soil.unit_weight_concrete * column.area * footing.pedestal_height - dead_per_area * column.area)
        at_column -= case.live_factor * live_per_area * column.area
        vertical = load.p + at_column
        mx += load.mx - vertical * column.y - height * load.vy
        my += load.my + vertical * column.x + height * load.vx
        n += vertical
        weight += at_column
    return BaseResultant(n, mx, my, weight)
