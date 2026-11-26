"""Presión lateral de tierras, por unidad de ancho (N, mm, MPa; ángulos en radianes).

Pasiva de Rankine con coeficiente Kp dado: la presión a la profundidad z es Kp·γ·z + 2c·√Kp. Entre las profundidades top y
top + height:

    Pp = ½·Kp·γ·((top + height)² − top²) + 2c·√Kp·height

Coeficientes de empuje de un relleno granular (c' = 0), de B. M. Das, *Principles of Foundation Engineering*, 8.ª ed.,
2016 (capítulo 12 y §13.3), y *Principles of Geotechnical Engineering* SI, 8.ª ed., 2014 (§13.3):

- Rankine activo con relleno inclinado α sobre un plano vertical (θ = 0): Ka = cos α·(cos α − √(cos²α − cos²φ'))/
  (cos α + √(cos²α − cos²φ')); con α = 0, tan²(45° − φ'/2). El empuje es paralelo al talud.
- Rankine generalizado de Chu (§12.4, ec. 12.14, 12.15 y 12.17): Ka y la inclinación β'_a del empuje respecto a la
  normal a un plano inclinado θ respecto a la vertical.
- Coulomb activo (ec. 12.26): β es el ángulo del plano respecto a la horizontal, medido abajo, del lado del muro, y δ'
  la inclinación del empuje respecto a la normal al plano.
- En reposo: Jaky, Ko = 1 − sen φ' (ec. 13.5), y Mayne y Kulhawy, Ko = (1 − sen φ')·OCR^(sen φ') (ec. 13.7).
- η (ec. 13.1): el ángulo con la vertical de la línea AC que limita la zona de corte de Rankine detrás del talón.

Las funciones no revisan su rango de validez (α ≤ φ', c' = 0): eso lo decide quien las llama.
"""

import math


def passive_force(kp: float, unit_weight: float, top: float, height: float, cohesion: float) -> float:
    """Empuje pasivo por unidad de ancho (N/mm) sobre la altura height que empieza a la profundidad top."""
    return 0.5 * kp * unit_weight * ((top + height) ** 2 - top**2) + 2 * cohesion * math.sqrt(kp) * height


def rankine_active_coefficient(phi: float, alpha: float) -> float:
    """Ka de Rankine sobre un plano vertical con relleno granular inclinado α (Das 2016, §12.4 con θ = 0)."""
    root = math.sqrt(math.cos(alpha) ** 2 - math.cos(phi) ** 2)
    return math.cos(alpha) * (math.cos(alpha) - root) / (math.cos(alpha) + root)


def _chu_psi(phi: float, alpha: float, theta: float) -> float:
    """ψ_a (Das 2016, ec. 12.14) = asen(sen α / sen φ') − α + 2θ."""
    return math.asin(math.sin(alpha) / math.sin(phi)) - alpha + 2 * theta


def chu_active_coefficient(phi: float, alpha: float, theta: float) -> float:
    """Ka de Rankine generalizado de Chu (Das 2016, ec. 12.17) sobre un plano inclinado θ respecto a la vertical (positivo
    como en la fig. 12.8), con relleno granular inclinado α."""
    psi = _chu_psi(phi, alpha, theta)
    root = math.sqrt(1 + math.sin(phi) ** 2 - 2 * math.sin(phi) * math.cos(psi))
    return math.cos(alpha - theta) * root / (math.cos(theta) ** 2 * (math.cos(alpha) + math.sqrt(math.sin(phi) ** 2
                                                                                                 - math.sin(alpha) ** 2)))


def chu_inclination(phi: float, alpha: float, theta: float) -> float:
    """β'_a (Das 2016, ec. 12.15): la inclinación del empuje de Chu respecto a la normal al plano."""
    psi = _chu_psi(phi, alpha, theta)
    return math.atan(math.sin(phi) * math.sin(psi) / (1 - math.sin(phi) * math.cos(psi)))


def coulomb_active_coefficient(beta: float, phi: float, delta: float, alpha: float) -> float:
    """Ka de Coulomb (Das 2016, ec. 12.26) sobre un plano a β de la horizontal, con el empuje inclinado δ' respecto a su
    normal y el relleno granular inclinado α."""
    root = math.sqrt(math.sin(phi + delta) * math.sin(phi - alpha) / (math.sin(beta - delta) * math.sin(alpha + beta)))
    return math.sin(beta + phi) ** 2 / (math.sin(beta) ** 2 * math.sin(beta - delta) * (1 + root) ** 2)


def jaky_at_rest_coefficient(phi: float) -> float:
    """Ko de Jaky, suelo normalmente consolidado (Das 2014, ec. 13.5)."""
    return 1 - math.sin(phi)


def mayne_kulhawy_at_rest_coefficient(phi: float, ocr: float) -> float:
    """Ko de Mayne y Kulhawy con la relación de sobreconsolidación OCR (Das 2014, ec. 13.7)."""
    return (1 - math.sin(phi)) * math.pow(ocr, math.sin(phi))


def rankine_wedge_angle(phi: float, alpha: float) -> float:
    """η (Das 2016, ec. 13.1): 45° + α/2 − φ'/2 − ½·asen(sen α / sen φ')."""
    return math.pi / 4 + alpha / 2 - phi / 2 - 0.5 * math.asin(math.sin(alpha) / math.sin(phi))


def thrust(coefficient: float, unit_weight: float, height: float) -> float:
    """El empuje ½·K·γ·H² por unidad de ancho (N/mm) sobre un plano de altura vertical H."""
    return 0.5 * coefficient * unit_weight * height**2
