"""Empuje del relleno sobre el muro en voladizo (D-173, decisión 9): el plano donde actúa, el coeficiente, el empuje y
sus componentes, y si la teoría declarada no vale para el muro (BLOCKED, sin sustituirla).

Coordenadas de la sección por unidad de ancho, en mm: x desde el borde de la puntera hacia el talón, y desde la cara
inferior de la base hacia arriba. A = (ancho de la base, 0), el extremo inferior del talón; C, el punto de la cara de la
pantalla contra el relleno en la superficie del relleno (la corona, si el relleno llega a ella).

- Rankine (caso 1) y el coeficiente declarado: plano vertical AB, empuje inclinado α (paralelo al talud). Con talón
  corto (θ_v < η) el supuesto de Rankine no vale (Das 2016, §13.3).
- Coulomb (caso 4, extensión aprobada por el usuario, no Das): talón largo (θ_v ≥ η), plano AB con β = 90° y δ' = α,
  que da lo mismo que Rankine; talón corto, plano AC con β = 90° − θ_v y δ' = φ', con la cuña de suelo entre la
  pantalla, el talón y AC.
- En reposo: plano AB, empuje horizontal; solo con relleno horizontal.

Sobre la cara de la pantalla actúa la misma teoría: Rankine o el coeficiente declarado inclinados α, Coulomb con β = 90°
y el δ' declarado (suelo–concreto) y el reposo horizontal.
"""

import math
from dataclasses import dataclass

from structurelab_rc.mechanics.earth_pressure import (
    coulomb_active_coefficient,
    jaky_at_rest_coefficient,
    mayne_kulhawy_at_rest_coefficient,
    rankine_active_coefficient,
    rankine_wedge_angle,
    thrust,
)
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

VERTICAL = math.pi / 2
SHORT_HEEL = "talón corto: supuesto de Rankine no válido (Das §13.3)"
COHESIVE_COULOMB = "Coulomb con c' > 0: la ec. 12.26 de Das es para c' = 0"
COHESIVE = "relleno cohesivo (c' > 0) no implementado (D-173)"
STEEP = "α > φ': el relleno no tiene solución con ninguna teoría"
SLOPED_AT_REST = "Ko con relleno inclinado: las ec. 13.5 y 13.7 de Das son para α = 0"


@dataclass(frozen=True)
class Thrust:
    """El empuje sobre un plano, por unidad de ancho: case (1, 4a, 4b o reposo), el plano (AB, AC o la cara de la
    pantalla), el coeficiente, β y δ' del plano (rad), la altura vertical del plano (mm), el empuje y sus componentes
    horizontal y vertical (N/mm), su punto de aplicación (x, y) en mm, el suelo que cuenta como peso (N/mm, con su x), η y
    θ_v (rad; None donde no aplican) y blocked, el motivo si la teoría declarada no vale ("" si vale)."""

    case: str
    plane: str
    coefficient: float
    beta: float
    delta: float
    height: float
    force: float
    horizontal: float
    vertical: float
    point: tuple[float, float]
    soil_weight: float
    soil_x: float
    eta: float | None
    theta_v: float | None
    blocked: str = ""


def _blocked(wall: RetainingWall, soil: RetainingSoil, alpha: float) -> str:
    """Lo que invalida la teoría declarada antes de calcular (decisión 9)."""
    pressure = wall.earth_pressure
    cohesion = soil.cohesion or 0.0
    if alpha > soil.friction_angle:
        return STEEP
    if cohesion > 0:
        return COHESIVE_COULOMB if pressure.method == "coulomb" else COHESIVE
    if pressure.state == "at_rest" and alpha != 0:
        return SLOPED_AT_REST
    return ""


def _coefficient(wall: RetainingWall, soil: RetainingSoil, alpha: float) -> float:
    """El coeficiente de la teoría declarada sobre un plano vertical en el suelo (Rankine, reposo o el declarado)."""
    pressure = wall.earth_pressure
    if pressure.method == "declared":
        assert pressure.coefficient is not None
        return pressure.coefficient
    if pressure.method == "jaky":
        return jaky_at_rest_coefficient(soil.friction_angle)
    if pressure.method == "mayne_kulhawy":
        assert pressure.ocr is not None
        return mayne_kulhawy_at_rest_coefficient(soil.friction_angle, pressure.ocr)
    return rankine_active_coefficient(soil.friction_angle, alpha)


def stability_thrust(wall: RetainingWall, soil: RetainingSoil, alpha: float = 0.0) -> Thrust:
    """El empuje para la estabilidad, con el caso que corresponde a la teoría declarada y al talón (decisión 9). alpha
    es la inclinación del relleno: 0 en la fase A (la fase A2 la declara)."""
    gamma, phi = soil.unit_weight_backfill, soil.friction_angle
    ax, height = wall.base_width, wall.retained_height
    cx = wall.toe + wall.stem_thickness
    blocked = _blocked(wall, soil, alpha)
    eta = None if blocked == STEEP else rankine_wedge_angle(phi, alpha)
    theta_v = math.atan((ax - cx) / height)
    short = eta is not None and theta_v < eta
    heel_soil = gamma * wall.heel * wall.backfill_height  # el relleno sobre el talón (horizontal en la fase A)
    heel_x = cx + wall.heel / 2
    pressure = wall.earth_pressure
    if pressure.method == "coulomb" and short and not blocked:
        # 4b: gravedad equivalente con trasdós AC (δ' = φ', rotura suelo contra suelo) y la cuña entre la pantalla, el
        # talón y AC; AC corta el talón en edge_x, a la altura de su cara superior.
        beta = VERTICAL - theta_v
        coefficient = coulomb_active_coefficient(beta, phi, phi, alpha)
        edge_x = ax + (cx - ax) * wall.base_thickness / height
        wedge = gamma * 0.5 * (edge_x - cx) * wall.backfill_height
        return Thrust("4b", "AC", coefficient, beta, phi, height, *_force(coefficient, (beta, phi), (gamma, height), blocked),
                      (ax + (cx - ax) / 3, height / 3), wedge, (2 * cx + edge_x) / 3, eta, theta_v, blocked)
    if pressure.state == "at_rest":
        case, delta, coefficient = "reposo", 0.0, 0.0 if blocked else _coefficient(wall, soil, alpha)
    else:
        coulomb = pressure.method == "coulomb"
        case = "4a" if coulomb else "1"
        delta = alpha  # plano vertical dentro del suelo: δ' = α (Rankine del talud infinito)
        if blocked == STEEP:
            coefficient = 0.0
        else:  # 4a: la ec. 12.26 con β = 90° y δ' = α, que se reduce exactamente a Rankine
            coefficient = coulomb_active_coefficient(VERTICAL, phi, alpha, alpha) if coulomb else _coefficient(wall, soil, alpha)
        if not coulomb and short and not blocked:
            blocked = SHORT_HEEL
    return Thrust(case, "AB", coefficient, VERTICAL, delta, height, *_force(coefficient, (VERTICAL, delta), (gamma, height), blocked),
                  (ax, height / 3), heel_soil, heel_x, eta, theta_v, blocked)


def stem_thrust(wall: RetainingWall, soil: RetainingSoil, alpha: float = 0.0) -> Thrust:
    """El empuje sobre la cara de la pantalla (para su diseño), con la misma teoría: Coulomb con β = 90° y el δ' declarado
    (suelo–concreto); Rankine o el declarado inclinados α; el reposo, horizontal. Su altura es la del relleno sobre la
    base."""
    gamma, phi = soil.unit_weight_backfill, soil.friction_angle
    height, cx = wall.backfill_height, wall.toe + wall.stem_thickness
    blocked = _blocked(wall, soil, alpha)
    pressure = wall.earth_pressure
    if blocked:
        coefficient, delta = 0.0, 0.0
    elif pressure.method == "coulomb":
        assert pressure.wall_friction_angle is not None
        delta = pressure.wall_friction_angle
        coefficient = coulomb_active_coefficient(VERTICAL, phi, delta, alpha)
    else:
        delta = 0.0 if pressure.state == "at_rest" else alpha
        coefficient = _coefficient(wall, soil, alpha)
    case = "reposo" if pressure.state == "at_rest" else ("4" if pressure.method == "coulomb" else "1")
    return Thrust(case, "cara de la pantalla", coefficient, VERTICAL, delta, height,
                  *_force(coefficient, (VERTICAL, delta), (gamma, height), blocked), (cx, wall.base_thickness + height / 3),
                  0.0, cx, None, None, blocked)


def _force(coefficient: float, plane: tuple[float, float], soil: tuple[float, float], blocked: str) -> tuple[float, float, float]:
    """El empuje ½·K·γ·H² y sus componentes horizontal y vertical: forma con la horizontal el ángulo 90° − β + δ'
    (decisión 9). plane = (β, δ'); soil = (γ, H). Nulo si la teoría no vale."""
    if blocked:
        return 0.0, 0.0, 0.0
    beta, delta = plane
    force = thrust(coefficient, *soil)
    angle = VERTICAL - beta + delta
    return force, force * math.cos(angle), force * math.sin(angle)
