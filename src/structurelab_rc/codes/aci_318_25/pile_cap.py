"""Cabezales sobre pilotes según ACI CODE-318-25, 13.4 (D-138).

Los límites de la cara de la columna son los de la guía CRSI "Design Guide for Pile Caps" (2015, estados límite 4 a 6),
que R13.4.6.7 recomienda cuando hay pilotes dentro de las secciones críticas a d o d/2 de la columna. Sus constantes
en √psi se pasan a √MPa con el factor 0.083 del código en SI (2√f'c → 0.17√f'c; decisión del usuario, D-138).
"""

import math

from structurelab_rc.codes.aci_318_25 import shear

_MIN_DEPTH = 300.0
_MIN_EMBEDMENT = 75.0
_MIN_EDGE = 100.0
_MIN_MISLOCATION = 75.0
_MISLOCATION_CAPACITY = 1.10
_CLOSE_SPACING = 4.0
_CLOSE_ONE_WAY = 0.17  # 13.4.6.8(a) en SI (D-138)
_SIZE_REFERENCE = 250.0
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
        "pile_capacity": "13.4.1.1",
        "mislocation": "13.4.1.4",
        "min_depth": "13.4.6.2",
        "embedment": "13.4.6.3",
        "edge": "13.4.6.3",
        "reaction_share": "13.4.6.4 y 13.4.6.7",
        "one_way_shear": "13.4.6.5(a), 13.4.6.7, 13.4.6.8(a) y 22.5",
        "punching": "13.4.6.5(b), 13.4.6.7 y 22.6",
        "closely_spaced": "13.4.6.8",
        "plain": "14.1.4",
        "min_reinforcement": "9.6.1.2, 9.6.1.3 y 24.4.3.2 (interpretacion de la guia CRSI, 4.5)",
        "column_face_two_way": "Guia CRSI, estado limite 4 (R13.4.6.7)",
        "column_face_one_way": "Guia CRSI, estados limite 5 y 6 (R13.4.6.7)",
        "pile_punching": "13.4.6.5(b) y 22.6 (guia CRSI, estados limite P1 y P3)",
        "adjacent_piles_punching": "13.4.6.5(b) y 22.6 (guia CRSI, estado limite P2, y su extension a grupos)",
        "corner_one_way": "Guia CRSI, estado limite P4 (R13.4.6.7)",
    }


def min_depth() -> float:
    """13.4.6.2: la altura efectiva del refuerzo inferior del cabezal es al menos 300 mm."""
    return _MIN_DEPTH


def min_embedment() -> float | None:
    """13.4.6.3: los pilotes se empotran en el cabezal al menos 75 mm, en mm."""
    return _MIN_EMBEDMENT


def min_edge_distance() -> float | None:
    """13.4.6.3: el cabezal se extiende al menos 100 mm más allá del borde del pilote, en mm."""
    return _MIN_EDGE


def min_mislocation() -> float | None:
    """13.4.1.4: el diseño considera una mala ubicación de cualquier pilote de al menos 75 mm, en mm."""
    return _MIN_MISLOCATION


def mislocation_capacity_factor() -> float:
    """13.4.1.4: al considerar la mala ubicación, la resistencia a compresión del pilote puede aumentarse 10 %."""
    return _MISLOCATION_CAPACITY


def reaction_share(offset: float, pile_size: float) -> float:
    """13.4.6.7: fracción de la reacción de un pilote que produce cortante en una sección, con offset la distancia
    del centro del pilote a la sección, positiva hacia afuera: 1 a dpile/2 o más afuera, 0 a dpile/2 o más adentro y
    lineal entre ambos."""
    return min(max(0.5 + offset / pile_size, 0.0), 1.0)


def closely_spaced_limit() -> float | None:
    """13.4.6.8: separación de los pilotes, en diámetros, hasta la que se permiten el Vc de (a) y λs = 1.0 de (b)."""
    return _CLOSE_SPACING


def one_way_concrete_shear(
    *, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float, closely_spaced: bool
) -> float:
    """13.4.6.5(a): Vc de 22.5 (Tabla 22.5.5.1 sin Av,min, con el efecto de tamaño λs y ρw), sin carga axial, en N. Con
    pilotes a 4 diámetros o menos, 13.4.6.8(a) permite Vc = 0.17λ√f'c·bw·d (decisión del usuario, D-138: el PDF en SI
    escribe 2λ√f'c, la forma en √psi); se toma el mayor de los dos, ambos permitidos. √f'c ≤ 8.3 MPa (22.5.3.1).

    El 13.2.6.2(a) de las zapatas no aplica: es para zapatas apoyadas en el suelo.
    """
    general = shear.concrete_shear(fc=fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=0.0, ag=bw * h, vu=vu, mu=mu, av_ge_min=False)
    if not closely_spaced:
        return general
    return max(general, _CLOSE_ONE_WAY * lam * shear.limited_sqrt_fc(fc, av_ge_min=False) * bw * d)


def punching_size_factor(d: float, closely_spaced: bool) -> float:
    """λs del cortante en dos direcciones: 1.0 con pilotes a 4 diámetros o menos (13.4.6.8(b)); si no, el de 22.5.5.1.3,
    √(2/(1 + d/250)) ≤ 1 (Tabla 22.6.5.2)."""
    if closely_spaced:
        return 1.0
    return min(math.sqrt(2 / (1 + d / _SIZE_REFERENCE)), 1.0)


def column_face_two_way_stress(*, fc: float, lam: float, d: float, w: float, c: float) -> float:
    """Guía CRSI, estado límite 4: vc = (d/w)(1 + d/c)·0.17λ√f'c ≤ 2.66λ√f'c en el perímetro de la cara de la columna,
    con w la distancia de la cara al centro del pilote más cercano (w < d/2) y c el lado medio de la columna; en MPa."""
    sqrt_fc = shear.limited_sqrt_fc(fc, av_ge_min=False)
    return min(d / w * (1 + d / c) * _CRSI_TWO_WAY_BASE, _CRSI_TWO_WAY_MAX) * lam * sqrt_fc


def column_face_one_way_stress(*, fc: float, lam: float, d: float, w: float, vu: float, mu: float) -> float:
    """Guía CRSI, estados límite 5 y 6 (w < d): vc = (d/w)(3.5 − 2.5·Mu/(Vu·d))(0.158 + 0.0083·Vu·d/Mu)λ√f'c ≤
    0.83λ√f'c, con Mu/(Vu·d) ≤ 1, en la cara de la columna a todo el ancho; en MPa."""
    sqrt_fc = shear.limited_sqrt_fc(fc, av_ge_min=False)
    if mu <= 0 or vu <= 0:
        return _CRSI_ONE_WAY_MAX * lam * sqrt_fc
    ratio = min(mu / (vu * d), 1.0)
    stress = d / w * (_CRSI_DEEP_A - _CRSI_DEEP_B * ratio) * (_CRSI_ONE_WAY_BASE + _CRSI_ONE_WAY_SHEAR_SPAN / ratio)
    return min(stress, _CRSI_ONE_WAY_MAX) * lam * sqrt_fc


def corner_one_way_stress(*, fc: float, lam: float) -> float:
    """Guía CRSI, estado límite P4: cortante en una dirección en la esquina de un pilote, vc = 0.166λ√f'c (2√f'c);
    en MPa."""
    return _CRSI_CORNER * lam * shear.limited_sqrt_fc(fc, av_ge_min=False)


def corner_depth_limit() -> float:
    """Guía CRSI, estado límite P4: d que entra en la longitud de la sección, ≤ 330 mm (13 in); en mm."""
    return _CRSI_CORNER_DEPTH
