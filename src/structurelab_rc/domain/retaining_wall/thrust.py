"""Empuje del relleno sobre el muro (D-173, decisión 9): el plano donde actúa, el coeficiente, el empuje y sus
componentes, por unidad de ancho.

El plano lo define el talón, no el tipo de muro (thrust_plane, una sola función para gravedad, semigravedad y voladizo).
A es el extremo del talón en la cara inferior de la base; B, el punto de la superficie del relleno sobre A (AB, el
trasdós virtual vertical, de altura H'); C, la corona de la cara del muro en contacto con el relleno. Talón largo:
θ_v ≥ η (ec. 13.1); corto: θ_v < η; sin talón: proyección nula.

- Rankine: talón largo, AB con Ka de Rankine, inclinado α (Das fig. 13.4a y b); talón corto, AC con el Rankine
  generalizado de Chu (§12.4, ec. 12.13 a 12.17) con θ = +θ_v, inclinado β'_a respecto a la normal a AC. Chu en AC más la
  cuña equivale exactamente a Rankine en AB más el suelo sobre el talón.
- Coulomb (ec. 12.26): sin talón, la cara real con el δ' declarado (Das fig. 13.4c); talón corto, AC con β = 90° − θ_v y
  δ = φ' (rotura suelo contra suelo), con la cuña; talón largo, AB con β = 90° y δ = α, que da lo mismo que Rankine.
- El coeficiente declarado y Ko actúan siempre sobre AB (Ko horizontal).
- Pesos: el suelo del lado del muro respecto al plano se suma (con AB, todo el que está entre la cara y AB; con AC, la
  cuña entre la cara, la cara superior del talón y AC; con la cara, ninguno); el del lado del relleno ya está en P_a.

Las verificaciones no válidas por la fórmula (α > φ', c' > 0, Ko con talud) anulan el empuje y lo marcan en blocked.
Sobre la cara de la pantalla actúa la misma teoría: Coulomb con β = 90° y el δ' declarado; Rankine o el declarado
inclinados α; el reposo, horizontal.
"""

import math
from dataclasses import dataclass

from structurelab_rc.mechanics.earth_pressure import (
    chu_active_coefficient,
    chu_inclination,
    coulomb_active_coefficient,
    jaky_at_rest_coefficient,
    mayne_kulhawy_at_rest_coefficient,
    rankine_active_coefficient,
    rankine_wedge_angle,
    thrust,
)
from structurelab_rc.model.retaining_wall import EarthPressure, RetainingSoil, RetainingWall

VERTICAL = math.pi / 2
COHESIVE_COULOMB = "Coulomb con c' > 0: la ec. 12.26 de Das es para c' = 0"
COHESIVE = "relleno cohesivo (c' > 0) no implementado (D-173)"
STEEP = "α > φ': el relleno no tiene solución con ninguna teoría"
SLOPED_AT_REST = "Ko con relleno inclinado: las ec. 13.5 y 13.7 de Das son para α = 0"
NO_HEEL, SHORT, LONG = "sin talón", "corto", "largo"


@dataclass(frozen=True)
class Backfill:
    """La geometría del relleno detrás del muro, sea cual sea su tipo: la proyección del talón, H' (de A a la superficie
    del relleno), la profundidad del relleno sobre la cara superior del talón y β de la cara del muro en contacto con el
    relleno (90°, vertical). Longitudes en mm, ángulos en radianes."""

    projection: float
    height: float
    depth: float
    face_beta: float = VERTICAL


@dataclass(frozen=True)
class Plane:
    """El plano de empuje (decisión 9): heel (sin talón, corto o largo), name (la cara, AC o AB), β y δ (rad; P_a forma
    con la horizontal el ángulo 90° − β + δ; en AC con Chu, δ = β'_a), su altura vertical (mm), el punto de aplicación de
    P_a (dx desde el pie de la cara hacia A, y desde A, en mm), el suelo del lado del muro (área en mm², con su dx), η,
    θ_v (rad) y el suelo sobre el talón que P_a contiene (área en mm², con su dx): en AC con Chu, el triángulo ABC, que
    lleva el factor del relleno y no el del empuje (opción b de la decisión 9)."""

    heel: str
    name: str
    beta: float
    delta: float
    height: float
    point: tuple[float, float]
    soil_area: float
    soil_dx: float
    eta: float
    theta_v: float
    inside_area: float = 0.0
    inside_dx: float = 0.0


def thrust_plane(backfill: Backfill, pressure: EarthPressure, phi: float, alpha: float) -> Plane:
    """El plano de empuje que corresponde al talón y a la teoría declarada; la misma función para todo tipo de muro."""
    projection, height, depth = backfill.projection, backfill.height, backfill.depth
    eta = rankine_wedge_angle(phi, alpha)
    theta_v = math.atan(projection / height)
    heel = NO_HEEL if projection <= 0 else (SHORT if theta_v < eta else LONG)
    coulomb = pressure.method == "coulomb"
    if coulomb and heel == NO_HEEL:  # la cara real, con el δ' declarado (Das fig. 13.4c)
        assert pressure.wall_friction_angle is not None
        return Plane(heel, "cara", backfill.face_beta, pressure.wall_friction_angle, height,
                     (height / 3 / math.tan(backfill.face_beta), height / 3), 0.0, 0.0, eta, theta_v)
    if heel == SHORT and pressure.method in ("rankine", "coulomb"):
        # AC, de A (dx = proyección, y = 0) a C (0, H'): con Rankine, Chu (δ = β'_a); con Coulomb, δ = φ' (rotura suelo
        # contra suelo). Del lado del muro: la cuña de suelo entre la cara, la cara superior del talón y AC, menos la cuña
        # de concreto del talón entre AC y AB (por debajo de la cara superior del talón), que P_a ya cuenta como suelo y
        # W_c como concreto (opción 2 de la decisión 9).
        edge = projection * depth / height  # donde AC corta la cara superior del talón
        base = height - depth
        wedge, wedge_dx = 0.5 * edge * depth, edge / 3
        sliver, sliver_dx = 0.5 * base * (projection - edge), (2 * projection + edge) / 3
        area = wedge - sliver
        # Con Chu, P_a contiene el triángulo ABC, que se corrige al factor del relleno (opción b de la decisión 9).
        inside, delta = (0.0, phi) if coulomb else (0.5 * projection * height, chu_inclination(phi, alpha, theta_v))
        return Plane(heel, "AC", VERTICAL - theta_v, delta, height, (2 * projection / 3, height / 3), area,
                     (wedge * wedge_dx - sliver * sliver_dx) / area, eta, theta_v, inside, 2 * projection / 3)
    # AB: Rankine, Coulomb con talón largo, el coeficiente declarado o Ko; el suelo entre la cara y AB (relleno horizontal
    # en la fase A).
    delta = 0.0 if pressure.state == "at_rest" else alpha
    return Plane(heel, "AB", VERTICAL, delta, height, (projection, height / 3), projection * depth, projection / 2, eta,
                 theta_v)


@dataclass(frozen=True)
class Thrust:
    """El empuje sobre el plano, por unidad de ancho: el plano (Plane), el coeficiente, el empuje y sus componentes
    horizontal y vertical (N/mm), su punto (x, y) en mm en la sección del muro, el peso del suelo del lado del muro (N/mm,
    con su x), el del suelo sobre el talón que P_a contiene (N/mm, con su x; la estabilidad lo corrige al factor del
    relleno) y blocked, el motivo si la fórmula no vale (empuje nulo; "" si vale)."""

    plane: Plane
    coefficient: float
    force: float
    horizontal: float
    vertical: float
    point: tuple[float, float]
    soil_weight: float
    soil_x: float
    inside_weight: float
    inside_x: float
    blocked: str = ""


def _blocked(pressure: EarthPressure, soil: RetainingSoil, alpha: float) -> str:
    """Lo que invalida la fórmula de la teoría declarada (decisión 9)."""
    if alpha > soil.friction_angle:
        return STEEP
    if (soil.cohesion or 0.0) > 0:
        return COHESIVE_COULOMB if pressure.method == "coulomb" else COHESIVE
    if pressure.state == "at_rest" and alpha != 0:
        return SLOPED_AT_REST
    return ""


def _coefficient(pressure: EarthPressure, phi: float, plane: Plane, alpha: float) -> float:
    """El coeficiente de la teoría declarada sobre el plano."""
    if pressure.method == "declared":
        assert pressure.coefficient is not None
        return pressure.coefficient
    if pressure.method == "jaky":
        return jaky_at_rest_coefficient(phi)
    if pressure.method == "mayne_kulhawy":
        assert pressure.ocr is not None
        return mayne_kulhawy_at_rest_coefficient(phi, pressure.ocr)
    if pressure.method == "coulomb":
        return coulomb_active_coefficient(plane.beta, phi, plane.delta, alpha)
    if plane.name == "AC":
        return chu_active_coefficient(phi, alpha, plane.theta_v)
    return rankine_active_coefficient(phi, alpha)


def _thrust(pressure: EarthPressure, soil: RetainingSoil, plane: Plane, given: tuple[float, float, str]) -> Thrust:
    """El empuje ½·K·γ·H² sobre el plano, con sus componentes (forma con la horizontal el ángulo 90° − β + δ), en la
    sección del muro. given = (x del pie de la cara, α, motivo de BLOCKED)."""
    face, alpha, blocked = given
    gamma = soil.unit_weight_backfill
    coefficient = force = 0.0
    if not blocked:
        coefficient = _coefficient(pressure, soil.friction_angle, plane, alpha)
        force = thrust(coefficient, gamma, plane.height)
    angle = VERTICAL - plane.beta + plane.delta
    return Thrust(plane, coefficient, force, force * math.cos(angle), force * math.sin(angle),
                  (face + plane.point[0], plane.point[1]), gamma * plane.soil_area, face + plane.soil_dx,
                  gamma * plane.inside_area, face + plane.inside_dx, blocked)


def stability_thrust(wall: RetainingWall, soil: RetainingSoil, alpha: float = 0.0) -> Thrust:
    """El empuje para la estabilidad del voladizo: el plano de thrust_plane con la proyección del talón, H' y el relleno
    sobre el talón. alpha es la inclinación del relleno: 0 en la fase A (la fase A2 la declara)."""
    pressure = wall.earth_pressure
    blocked = _blocked(pressure, soil, alpha)
    plane = thrust_plane(Backfill(wall.heel, wall.retained_height, wall.backfill_height), pressure, soil.friction_angle,
                         0.0 if blocked == STEEP else alpha)
    return _thrust(pressure, soil, plane, (wall.toe + wall.stem_thickness, alpha, blocked))


def stem_thrust(wall: RetainingWall, soil: RetainingSoil, alpha: float = 0.0) -> Thrust:
    """El empuje sobre la cara de la pantalla (para su diseño), con la misma teoría: Coulomb con β = 90° y el δ' declarado
    (suelo–concreto); Rankine o el declarado inclinados α; el reposo, horizontal. Su altura es la del relleno sobre la
    base."""
    pressure = wall.earth_pressure
    blocked = _blocked(pressure, soil, alpha)
    if pressure.method == "coulomb":
        assert pressure.wall_friction_angle is not None
        delta = pressure.wall_friction_angle
    else:
        delta = 0.0 if pressure.state == "at_rest" else alpha
    height = wall.backfill_height
    eta = rankine_wedge_angle(soil.friction_angle, 0.0 if blocked == STEEP else alpha)
    plane = Plane(NO_HEEL, "cara de la pantalla", VERTICAL, delta, height, (0.0, wall.base_thickness + height / 3), 0.0, 0.0,
                  eta, 0.0)
    return _thrust(pressure, soil, plane, (wall.toe + wall.stem_thickness, alpha, blocked))
