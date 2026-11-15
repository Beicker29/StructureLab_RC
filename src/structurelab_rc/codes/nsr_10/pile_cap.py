"""Cabezales sobre pilotes según NSR-10 Título C, C.15.5.3, C.15.5.4 y C.15.7 (D-138).

C.15.5.3 permite en todos los cabezales el método por secciones (C.11.11 con C.15.5.4). NSR-10 no exige empotramiento
del pilote, borde del cabezal ni tolerancia de mala ubicación (esta se declara y se aplica, D-138). Los límites de la
cara de la columna son los de la guía CRSI "Design Guide for Pile Caps" (2015, estados límite 4 a 6), con sus
constantes en √psi pasadas a √MPa con el factor 0.083 (2√f'c → 0.17√f'c; decisión del usuario, D-138).
"""

from structurelab_rc.codes.nsr_10 import shear

_MIN_DEPTH = 300.0
_PSI_TO_MPA = 0.083  # √psi → √MPa (D-138)
_CRSI_TWO_WAY_BASE = 2.0 * _PSI_TO_MPA  # LS4: 2√f'c·(d/w)(1 + d/c)
_CRSI_TWO_WAY_MAX = 32.0 * _PSI_TO_MPA  # LS4: ≤ 32√f'c
_CRSI_ONE_WAY_BASE = 1.9 * _PSI_TO_MPA  # LS5 y LS6: 1.9√f'c
_CRSI_ONE_WAY_SHEAR_SPAN = 0.1 * _PSI_TO_MPA  # LS5 y LS6: 0.1√f'c·Vu·d/Mu
_CRSI_ONE_WAY_MAX = 10.0 * _PSI_TO_MPA  # LS5 y LS6: ≤ 10√f'c
_CRSI_DEEP_A, _CRSI_DEEP_B = 3.5, 2.5  # factor de viga alta 3.5 − 2.5·Mu/(Vu·d)
_CRSI_CORNER = 2.0 * _PSI_TO_MPA  # P4: 2√f'c
_CRSI_CORNER_DEPTH = 330.0  # P4: d ≤ 13 in en la longitud de la sección (decisión del usuario, D-138)


def clauses() -> dict[str, str]:
    return {
        "pile_capacity": "C.15.2.1",
        "mislocation": "no aplica en NSR-10 (tolerancia declarada)",
        "min_depth": "C.15.7",
        "embedment": "no aplica en NSR-10",
        "edge": "no aplica en NSR-10",
        "reaction_share": "C.15.5.4",
        "one_way_shear": "C.15.5.3, C.15.5.4 y C.11.11.1",
        "punching": "C.15.5.3, C.15.5.4 y C.11.11.2.1",
        "closely_spaced": "no aplica en NSR-10",
        "plain": "C.22.2.1",
        "min_reinforcement": "C.10.5.1, C.10.5.3 y C.7.12.2.1 (interpretacion de la guia CRSI, 4.5)",
        "column_face_two_way": "Guia CRSI, estado limite 4",
        "column_face_one_way": "Guia CRSI, estados limite 5 y 6",
        "pile_punching": "C.11.11.2.1 (guia CRSI, estados limite P1 y P3)",
        "adjacent_piles_punching": "C.11.11.2.1 (guia CRSI, estado limite P2, y su extension a grupos)",
        "corner_one_way": "Guia CRSI, estado limite P4",
    }


def min_depth() -> float:
    """C.15.7: la altura de los cabezales sobre el refuerzo inferior no es menor que 300 mm."""
    return _MIN_DEPTH


def min_embedment() -> float | None:
    """NSR-10 no fija el empotramiento del pilote en el cabezal: None."""
    return None


def min_edge_distance() -> float | None:
    """NSR-10 no fija la distancia del borde del pilote al borde del cabezal: None."""
    return None


def min_mislocation() -> float | None:
    """NSR-10 no fija una tolerancia mínima de mala ubicación de los pilotes: None (se aplica la declarada)."""
    return None


def mislocation_capacity_factor() -> float:
    """NSR-10 no aumenta la capacidad del pilote al considerar la mala ubicación: 1.0."""
    return 1.0


def reaction_share(offset: float, pile_size: float) -> float:
    """C.15.5.4.1 a C.15.5.4.3: fracción de la reacción de un pilote que produce cortante en una sección, con offset la
    distancia del centro del pilote a la sección, positiva hacia afuera: 1 a dpile/2 o más afuera, 0 a dpile/2 o más
    adentro e interpolación lineal entre ambos."""
    return min(max(0.5 + offset / pile_size, 0.0), 1.0)


def closely_spaced_limit() -> float | None:
    """NSR-10 no tiene el aumento por pilotes cercanos: None."""
    return None


def one_way_concrete_shear(
    *, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float, closely_spaced: bool
) -> float:
    """C.15.5.3 remite a C.11.11 (C.11.11.1.1): la Vc de vigas, el mayor entre C.11.2.1 y C.11.2.2 (D-030), sin carga
    axial y sin refuerzo a cortante, en N. Vu y Mu en valor absoluto en la sección. NSR-10 no tiene el aumento por pilotes
    cercanos: closely_spaced no se usa."""
    return shear.concrete_shear(fc=fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=0.0, ag=bw * h, vu=vu, mu=mu, av_ge_min=False)


def punching_size_factor(d: float, closely_spaced: bool) -> float:
    """NSR-10 no tiene factor de efecto de tamaño en el cortante en dos direcciones: λs = 1.0."""
    return 1.0


def column_face_two_way_stress(*, fc: float, lam: float, d: float, w: float, c: float) -> float:
    """Guía CRSI, estado límite 4: vc = (d/w)(1 + d/c)·0.17λ√f'c ≤ 2.66λ√f'c en el perímetro de la cara de la columna,
    con w la distancia de la cara al centro del pilote más cercano (w < d/2) y c el lado medio de la columna; √f'c ≤
    8.3 MPa (C.11.1.2); en MPa."""
    sqrt_fc = shear.limited_sqrt_fc(fc, av_ge_min=False)
    return min(d / w * (1 + d / c) * _CRSI_TWO_WAY_BASE, _CRSI_TWO_WAY_MAX) * lam * sqrt_fc


def column_face_one_way_stress(*, fc: float, lam: float, d: float, w: float, vu: float, mu: float) -> float:
    """Guía CRSI, estados límite 5 y 6 (w < d): vc = (d/w)(3.5 − 2.5·Mu/(Vu·d))(0.158 + 0.0083·Vu·d/Mu)λ√f'c ≤
    0.83λ√f'c, con Mu/(Vu·d) ≤ 1, en la cara de la columna a todo el ancho; √f'c ≤ 8.3 MPa (C.11.1.2); en MPa."""
    sqrt_fc = shear.limited_sqrt_fc(fc, av_ge_min=False)
    if mu <= 0 or vu <= 0:
        return _CRSI_ONE_WAY_MAX * lam * sqrt_fc
    ratio = min(mu / (vu * d), 1.0)
    stress = d / w * (_CRSI_DEEP_A - _CRSI_DEEP_B * ratio) * (_CRSI_ONE_WAY_BASE + _CRSI_ONE_WAY_SHEAR_SPAN / ratio)
    return min(stress, _CRSI_ONE_WAY_MAX) * lam * sqrt_fc


def corner_one_way_stress(*, fc: float, lam: float) -> float:
    """Guía CRSI, estado límite P4: cortante en una dirección en la esquina de un pilote, vc = 0.166λ√f'c (2√f'c), con
    √f'c ≤ 8.3 MPa (C.11.1.2); en MPa."""
    return _CRSI_CORNER * lam * shear.limited_sqrt_fc(fc, av_ge_min=False)


def corner_depth_limit() -> float:
    """Guía CRSI, estado límite P4: d que entra en la longitud de la sección, ≤ 330 mm (13 in); en mm."""
    return _CRSI_CORNER_DEPTH
