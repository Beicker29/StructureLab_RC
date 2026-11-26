"""Muros de contención en voladizo según NSR-10 Título C: C.14.1.2, la pantalla se diseña por flexión según C.10, con el
refuerzo horizontal mínimo de C.14.3.3 (D-173). Lo que coincide con otras piezas del perfil se toma de ellas con su
numeral: el As mínimo de C.10.5.4 (que remite a C.7.12.2.1) y su separación máxima (3h y 450 mm) son los de las zapatas
de espesor uniforme; la retracción y temperatura (C.7.12.2.1 y C.7.12.2.2), la de las zapatas; la separación por
agrietamiento (C.10.6.4), la de las vigas."""

from structurelab_rc.codes.nsr_10 import footing, shear

_SMALL_BAR = 16.0  # mm: barras no mayores que No. 5 (5/8") o 16M
_GRADE = 420.0
_RATIO_SMALL = 0.0020
_RATIO_OTHER = 0.0025


def clauses() -> dict[str, str]:
    return {
        "stem_strength": "C.14.1.2 y C.10",
        "stem_net_tensile_strain": "C.14.1.2 y C.10.3.5",
        "stem_min_reinforcement": "C.14.1.2, C.10.5.4 y C.7.12.2.1",
        "stem_spacing": "C.14.1.2 y C.10.5.4",
        "stem_crack_spacing": "C.10.6.4",
        "stem_shear": "C.11.1.1 (Vs = 0), C.11.1.2, mayor de C.11.2.1.1 y C.11.2.2.1, C.11.4.6.1(a) y C.11.4.7.1 "
                      "(seccion en la union, D-173)",
        "stem_horizontal": "C.14.3.3 y C.14.3.5",
        "stem_front": "C.7.12.2.1 y C.7.12.2.2",
    }


def stem_min_reinforcement_ratio(fy: float) -> float:
    """C.10.5.4, que remite a C.7.12.2.1: la cuantía de las losas y zapatas de espesor uniforme (D-173, como el mínimo de
    0.0018·Ag del manual ACI)."""
    return footing.min_reinforcement_ratio(fy)


def stem_max_spacing(h: float) -> float:
    """C.10.5.4: no mayor que tres veces el espesor ni que 450 mm, en mm."""
    return footing.max_bar_spacing(h)


def stem_concrete_shear(*, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float) -> float:
    """Vc de la pantalla en N: la de vigas, el mayor entre C.11.2.1.1 (ec. C.11-3) y C.11.2.2.1 (ec. C.11-5, con ρw y
    Vu·d/Mu ≤ 1), como en las zapatas (D-030), sin carga axial; √f'c ≤ 8.3 MPa (C.11.1.2). Sin refuerzo de cortante,
    Vn = Vc (C.11.1.1, ec. C.11-2): la pantalla, como losa, no exige Av,min (C.11.4.6.1(a)), pero con Vu > φVc lo
    necesitaría (C.11.4.7.1), así que debe cumplirse Vu ≤ φVc."""
    return shear.concrete_shear(fc=fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=0.0, ag=bw * h, vu=vu, mu=mu, av_ge_min=False)


def stem_horizontal_ratio(fy: float, db: float) -> float:
    """C.14.3.3: cuantía horizontal mínima sobre el área bruta, 0.0020 con barras corrugadas no mayores que No. 5 (16 mm)
    y fy ≥ 420 MPa, 0.0025 con las demás (C.14.1.2 la exige en el muro en voladizo)."""
    return _RATIO_SMALL if db <= _SMALL_BAR and fy >= _GRADE else _RATIO_OTHER


def stem_horizontal_max_spacing(h: float) -> float:
    """C.14.3.5: no mayor que tres veces el espesor del muro ni que 450 mm (el mismo valor de C.10.5.4), en mm."""
    return footing.max_bar_spacing(h)


def stem_front_ratio(fy: float) -> float:
    """Verticales de la cara exterior: la mitad del refuerzo de retracción y temperatura (C.7.12.2.1), sobre el área bruta,
    como en el manual ACI MNL-17(21), ejemplo 2 del capítulo 12 (D-173)."""
    return footing.shrinkage_temperature_ratio(fy) / 2


def stem_front_max_spacing(h: float) -> float:
    """C.7.12.2.2: no mayor que cinco veces el espesor ni que 450 mm, en mm."""
    return footing.shrinkage_temperature_max_spacing(h)
