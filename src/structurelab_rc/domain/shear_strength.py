"""Resistencia a cortante común a todos los elementos (vigas, zapatas y las losas que vendrán): una sola fuente de verdad.

Cada elemento elige la sección, la demanda y el numeral; aquí se toman del perfil λ, φ y vc, y se evalúa el esfuerzo de
cortante en dos direcciones con la fracción del momento transferida por excentricidad del cortante (ACI 8.4.4.2,
NSR-10 C.11.11.7), sobre las propiedades geométricas de mechanics/perimeter.py.
"""

from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.errors import StructuredError, blocked
from structurelab_rc.mechanics.perimeter import Perimeter
from structurelab_rc.model.project import Materials


def concrete_lambda(profile: Profile, materials: Materials) -> float | StructuredError:
    lam = profile.strength_assumptions.concrete_lambda(materials.concrete)
    if lam is None:
        return blocked("El concreto liviano no esta implementado (D-028)")
    return lam


@dataclass(frozen=True)
class TwoWayShear:
    """Esfuerzos en MPa y momentos en N·mm. vu es el máximo en el perímetro; vuv, el de la fuerza sin momento; corners,
    el esfuerzo en cada esquina del perímetro (x, y, v), ordenadas por y y luego por x; jc, el Jc de cada eje."""

    vu: float
    vuv: float
    phi_vc: float
    alpha_s: float
    gamma_v: tuple[float, float]
    perimeter: Perimeter
    corners: tuple[tuple[float, float, float], ...] = ()
    jc: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class TransferredLoad:
    """Fuerza que atraviesa la sección crítica (N) y momentos respecto a su centroide: el que hace variar el esfuerzo a lo
    largo de x y el que lo hace variar a lo largo de y (N·mm)."""

    force: float
    moment_along_x: float
    moment_along_y: float


def two_way_shear(
    profile: Profile, materials: Materials, perimeter: Perimeter, loaded: tuple[float, float, float], load: TransferredLoad
) -> TwoWayShear | StructuredError:
    """vu = vuv + Σ γv·Msc·c/Jc en los extremos de los lados, frente a φvc del perfil. loaded = (c1, c2, λs)."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return lam
    shear = profile.shear
    alpha_s = shear.punching_alpha_s(perimeter.outside)
    if alpha_s is None or not perimeter.sides:
        return blocked("El perimetro critico pierde mas de dos lados contra el borde: caso no implementado")
    c1, c2, lam_s = loaded
    (x0, y0), (x1, y1) = perimeter.region
    b0, d = perimeter.length, perimeter.depth
    vuv = load.force / (b0 * d)
    gamma_x = 1 - shear.moment_transfer_fraction(x1 - x0, y1 - y0)
    gamma_y = 1 - shear.moment_transfer_fraction(y1 - y0, x1 - x0)
    jx, jy = perimeter.polar(0), perimeter.polar(1)
    xc, yc = perimeter.centroid
    corners = tuple(sorted(((x, y, vuv + gamma_x * load.moment_along_x * (x - xc) / jx + gamma_y * load.moment_along_y * (y - yc) / jy)
                            for x, y in perimeter.corners()), key=lambda corner: (corner[1], corner[0])))
    vu = max(corner[2] for corner in corners)
    beta = max(c1, c2) / min(c1, c2)
    vc = shear.punching_concrete_stress(fc=materials.fc, lam=lam, lam_s=lam_s, beta=beta, alpha_s=alpha_s, d=d, b0=b0)
    return TwoWayShear(vu, vuv, shear.strength_reduction() * vc, alpha_s, (gamma_x, gamma_y), perimeter, corners, (jx, jy))
