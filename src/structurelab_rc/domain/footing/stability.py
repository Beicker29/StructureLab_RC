"""Estabilidad de la zapata con los casos de servicio: deslizamiento y volcamiento (D-070).

Deslizamiento: resistencia R = μ·N + c_a·A_contacto + f_p·P_p, con N la resultante vertical sobre la base, A_contacto
el área en contacto de Bellos y Bakas y P_p el empuje pasivo sobre el espesor de la zapata (con la sobrecarga del
relleno), afectado por f_p porque la fricción y la pasiva no se movilizan por completo a la vez. Se revisan la dirección
de la resultante del cortante, con P_p(θ) = P_p,x·|cos θ| + P_p,y·|sin θ|, y cada eje por separado; gobierna la mayor
razón FS·V/R. P_p,x actúa sobre la cara de ancho ly, normal a X.

Volcamiento: alrededor del borde de cada eje, momento resistente N·L/2 contra el momento volcador |M_base| (la
resultante en la base ya incluye el cortante por h + pedestal); equivale a (L/2)/|e|. La pasiva no se cuenta. En una
planta trapezoidal o en T/L (D-164), alrededor de cada lado de su envolvente convexa (los lados oblicuos incluidos):
resistente N·d, con d la distancia del centroide al lado, y volcador N·(e·n), con n la normal exterior del lado. Los
anchos de la pasiva son los de la planta proyectada normal a cada dirección (lx y ly, su caja).

Los factores de seguridad son los que declara el usuario, sísmicos en los casos marcados seismic.
"""

import math

from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import BaseResultant
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.earth_pressure import passive_force
from structurelab_rc.mechanics.polygon import convex_hull
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import FootingBase, FootingLoad, Soil

SLIDING = "Deslizamiento"
OVERTURNING = "Volcamiento"


def _ratio(demand: float, capacity: float) -> float:
    if demand == 0:
        return 0.0
    return math.inf if capacity <= 0 else demand / capacity


def sliding_check(clause: str, footing: FootingBase, soil: Soil, load: FootingLoad, support: tuple[BaseResultant, float]) -> Check:
    """support: la resultante en la base del caso y la fracción de la base en contacto (Bellos y Bakas), en equilibrio.
    load da la fuerza horizontal (Vx, Vy), el nombre del caso y la marca de sismo."""
    resultant, contact = support
    safety = soil.sliding_safety_factor_seismic if load.seismic else soil.sliding_safety_factor
    friction = soil.friction_coefficient * resultant.n
    adhesion = soil.adhesion * contact * footing.area
    per_width = passive_force(soil.passive_coefficient, soil.unit_weight_fill, footing.fill_height, footing.h, soil.cohesion)
    passive_x, passive_y = per_width * footing.ly, per_width * footing.lx
    base = friction + adhesion
    factor = soil.passive_factor
    vx, vy = abs(load.vx), abs(load.vy)
    shear = math.hypot(vx, vy)
    directions = [("el eje X", vx, base + factor * passive_x), ("el eje Y", vy, base + factor * passive_y)]
    if shear > 0:
        directions.insert(0, ("la resultante", shear, base + factor * (passive_x * vx + passive_y * vy) / shear))
    name, force, resistance = max(directions, key=lambda item: _ratio(item[1], item[2]))
    values: tuple[tuple[str, float], ...] = (
        ("N", resultant.n), ("contacto", contact), ("mu N", friction), ("ca Ac", adhesion), ("Pp x", passive_x),
        ("Pp y", passive_y), ("V", force), ("R", resistance), ("FS requerido", safety))
    if force > 0 and resistance > 0:
        values += (("FS", resistance / force),)
    ok = safety * force <= resistance
    return Check(SLIDING, Status.PASS if ok else Status.FAIL, clause=clause, demand=safety * force, capacity=resistance,
                 unit="N", values=values, note=f"Gobierna {name}", member=footing.id, case=load.case)


def overturning_check(clause: str, footing: FootingBase, soil: Soil, load: FootingLoad, resultant: BaseResultant) -> Check:
    safety = soil.overturning_safety_factor_seismic if load.seismic else soil.overturning_safety_factor
    axes = _overturning_axes(footing, resultant)
    name, moment, resisting = max(axes, key=lambda item: _ratio(item[1], item[2]))
    values: tuple[tuple[str, float], ...] = (("N", resultant.n), ("Mo", moment), ("Mr", resisting), ("FS requerido", safety))
    if moment > 0 and resisting > 0:
        values += (("FS", resisting / moment),)
    ok = safety * moment <= resisting
    return Check(OVERTURNING, Status.PASS if ok else Status.FAIL, clause=clause, demand=safety * moment, capacity=resisting,
                 unit="N*mm", values=values, note=f"Gobierna el volcamiento en {name}", member=footing.id, case=load.case)


def _overturning_axes(footing: FootingBase, resultant: BaseResultant) -> list[tuple[str, float, float]]:
    """(nombre, momento volcador, momento resistente) de cada eje de volcamiento: los bordes de cada eje en el rectángulo
    y los lados de la envolvente convexa en una planta trapezoidal o en T/L (D-164)."""
    if not isinstance(footing, CombinedFooting) or footing.plan is None:
        return [("el eje X", abs(resultant.my), resultant.n * footing.lx / 2),
                ("el eje Y", abs(resultant.mx), resultant.n * footing.ly / 2)]
    ex, ey = resultant.ex or 0.0, resultant.ey or 0.0
    hull = convex_hull(footing.outline)
    axes = []
    for index, (start, end) in enumerate(zip(hull, (*hull[1:], hull[0]), strict=True), start=1):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        normal = ((end[1] - start[1]) / length, -(end[0] - start[0]) / length)  # exterior: el contorno es antihorario
        distance = start[0] * normal[0] + start[1] * normal[1]
        lever = ex * normal[0] + ey * normal[1]
        axes.append((f"el lado {index} (de ({start[0]:.0f}, {start[1]:.0f}) a ({end[0]:.0f}, {end[1]:.0f}) mm)",
                     max(resultant.n * lever, 0.0), resultant.n * distance))
    return axes
