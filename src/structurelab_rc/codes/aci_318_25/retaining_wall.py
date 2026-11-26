"""Muros de contención en voladizo según ACI CODE-318-25 (13.1.1(j), 13.3.6): la pantalla es una losa en una dirección
del capítulo 7 (13.3.6.1). Lo que coincide con otras piezas del perfil se toma de ellas con su numeral: el As mínimo de
losa (7.6.1.1) y la separación máxima (7.7.2.3) son los de la zapata combinada en una dirección; la retracción y
temperatura (24.4.3.2 y 24.4.3.3), la de las zapatas; la separación por agrietamiento (24.3.2), la de las vigas."""

from structurelab_rc.codes.aci_318_25 import footing, shear

_SHEAR_FACTOR = 0.17


def clauses() -> dict[str, str]:
    return {
        "stem_strength": "13.3.6.1 y 7.5.1.1(a)",
        "stem_net_tensile_strain": "13.3.6.1 y 7.3.3.1",
        "stem_min_reinforcement": "13.3.6.1 y 7.6.1.1",
        "stem_spacing": "13.3.6.1 y 7.7.2.3",
        "stem_crack_spacing": "7.7.2.2 y 24.3.2",
        "stem_shear": "7.5.1.1(b), 22.5.1.1 (Vs = 0), 22.5.1.5, 22.5.3.1, mayor de 13.3.6.1.1 y Tabla 22.5.5.1, 13.3.6.3 y 7.6.3.1",
        "stem_horizontal": "7.6.4.1, 24.4.3.2 y 24.4.3.3",
        "stem_front": "7.6.4.1, 24.4.3.2 y 24.4.3.3",
    }


def stem_min_reinforcement_ratio(fy: float) -> float:
    """7.6.1.1 (13.3.6.1): As,min = 0.0018Ag, el mismo valor de losa que usan las zapatas."""
    return footing.min_reinforcement_ratio(fy)


def stem_max_spacing(h: float) -> float:
    """7.7.2.3 (13.3.6.1): el menor de 3h y 450 mm, el de la zapata combinada en una dirección, en mm."""
    return footing.combined_max_bar_spacing(h)


def stem_concrete_shear(*, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float) -> float:
    """Vc de la pantalla en N: el mayor de los dos procedimientos permitidos (decisión del usuario, D-173), 13.3.6.1.1,
    Vc = 0.17·λ·√f'c·bw·d, y 22.5.5.1 (22.5.1.3), la Tabla 22.5.5.1 sin Av,min (fila (c), con λs y ρw) y sin carga axial,
    la misma de las vigas. λ de 19.2.4 (22.5.1.5) y √f'c ≤ 8.3 MPa (22.5.3.1). Sin refuerzo de cortante, Vn = Vc (22.5.1.1)
    y debe cumplirse Vu ≤ φVc (7.6.3.1)."""
    slab = _SHEAR_FACTOR * lam * shear.limited_sqrt_fc(fc, False) * bw * d
    general = shear.concrete_shear(fc=fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=0.0, ag=bw * h, vu=vu, mu=mu, av_ge_min=False)
    return max(slab, general)


def stem_horizontal_ratio(fy: float, db: float) -> float:
    """Refuerzo horizontal de la pantalla: el de retracción y temperatura (7.6.4.1 remite a 24.4.3.2), sobre el área
    bruta de la pantalla, repartido entre las dos caras (manual ACI MNL-17(21), ejemplo 2 del capítulo 12)."""
    return footing.shrinkage_temperature_ratio(fy)


def stem_horizontal_max_spacing(h: float) -> float:
    """24.4.3.3: el menor de 5h y 450 mm, en mm."""
    return footing.shrinkage_temperature_max_spacing(h)


def stem_front_ratio(fy: float) -> float:
    """Verticales de la cara exterior: la mitad del refuerzo de retracción y temperatura (24.4.3.2), sobre el área bruta,
    como cada cara horizontal (manual ACI MNL-17(21), ejemplo 2 del capítulo 12)."""
    return footing.shrinkage_temperature_ratio(fy) / 2


def stem_front_max_spacing(h: float) -> float:
    """24.4.3.3: el menor de 5h y 450 mm, en mm."""
    return footing.shrinkage_temperature_max_spacing(h)
