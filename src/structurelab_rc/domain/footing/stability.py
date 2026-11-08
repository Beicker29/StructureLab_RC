"""Estabilidad de la zapata con los casos de servicio: deslizamiento y volcamiento (D-070).

Deslizamiento: resistencia R = μ·N + c_a·A_contacto + f_p·P_p, con N la resultante vertical sobre la base, A_contacto
el área en contacto de Bellos y Bakas y P_p el empuje pasivo sobre el espesor de la zapata (con la sobrecarga del
relleno), afectado por f_p porque la fricción y la pasiva no se movilizan por completo a la vez. Se revisan la dirección
de la resultante del cortante, con P_p(θ) = P_p,x·|cos θ| + P_p,y·|sin θ|, y cada eje por separado; gobierna la mayor
razón FS·V/R. P_p,x actúa sobre la cara de ancho ly, normal a X.

Volcamiento: alrededor del borde de cada eje, momento resistente N·L/2 contra el momento volcador |M_base| (la
resultante en la base ya incluye el cortante por h + pedestal); equivale a (L/2)/|e|. La pasiva no se cuenta.

Los factores de seguridad son los que declara el usuario, sísmicos en los casos marcados seismic.
"""

import math

from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import base_resultant
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.earth_pressure import passive_force
from structurelab_rc.model.footing import Footing, FootingLoad, Soil

SLIDING = "Deslizamiento"
OVERTURNING = "Volcamiento"


def _ratio(demand: float, capacity: float) -> float:
    if demand == 0:
        return 0.0
    return math.inf if capacity <= 0 else demand / capacity


def sliding_check(clause: str, footing: Footing, soil: Soil, load: FootingLoad, contact: float) -> Check:
    """contact: fracción de la base en contacto (Bellos y Bakas) con la resultante del caso, en equilibrio."""
    resultant = base_resultant(footing, soil, load)
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


def overturning_check(clause: str, footing: Footing, soil: Soil, load: FootingLoad) -> Check:
    resultant = base_resultant(footing, soil, load)
    safety = soil.overturning_safety_factor_seismic if load.seismic else soil.overturning_safety_factor
    axes = [("el eje X", abs(resultant.my), resultant.n * footing.lx / 2), ("el eje Y", abs(resultant.mx), resultant.n * footing.ly / 2)]
    name, moment, resisting = max(axes, key=lambda item: _ratio(item[1], item[2]))
    values: tuple[tuple[str, float], ...] = (("N", resultant.n), ("Mo", moment), ("Mr", resisting), ("FS requerido", safety))
    if moment > 0 and resisting > 0:
        values += (("FS", resisting / moment),)
    ok = safety * moment <= resisting
    return Check(OVERTURNING, Status.PASS if ok else Status.FAIL, clause=clause, demand=safety * moment, capacity=resisting,
                 unit="N*mm", values=values, note=f"Gobierna el volcamiento en {name}", member=footing.id, case=load.case)
