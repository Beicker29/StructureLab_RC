"""Zapatas aisladas según NSR-10 Título C, capítulo C.15."""

from structurelab_rc.codes.nsr_10 import shear

_MAX_SPACING = 450.0
_SPACING_THICKNESS = 3.0
_MIN_DEPTH = 150.0
_SIZE_FACTOR = 1.0
_DOWEL_RATIO = 0.005
_GRADE_350 = 350.0
_GRADE_420 = 420.0
_RATIO_LOW_GRADE = 0.0020
_RATIO_420 = 0.0018
_RATIO_FLOOR = 0.0014


def clauses() -> dict[str, str]:
    return {
        "bearing": "C.15.2.2",
        "stability": "Titulo H (remision), factores declarados (D-070)",
        "strength": "C.15.4.1 y C.15.4.2",
        "net_tensile_strain": "C.10.3.5",
        "min_reinforcement": "C.10.5.4 y C.7.12.2.1",
        "spacing": "C.10.5.4",
        "band": "C.15.4.4.2",
        "min_depth": "C.15.7",
        "one_way_shear": "C.15.5.1, C.15.5.2 y C.11.2",
        "punching_min_reinforcement": "no aplica en NSR-10",
        "moment_transfer": "C.11.11.7.1 y C.13.5.3.2",
        "dowels": "C.15.8.2.1",
        "dowel_excess": "C.15.8.1.2(a)",
        "combined_spacing": "C.10.5.4",
        "combined_min_reinforcement": "C.10.5.4 y C.7.12.2.1",
        "combined_min_shear": "C.11.4.6.1(a)",
    }


def min_reinforcement_ratio(fy: float) -> float:
    """C.10.5.4 remite a C.7.12.2.1, leído por tramos (D-062): 0.0020 con fy ≤ 350 MPa (grados 280 y 350), 0.0018 con
    350 < fy ≤ 420 MPa (grado 420) y 0.0018·420/fy con fy > 420 MPa, no menor que 0.0014."""
    if fy <= _GRADE_350:
        return _RATIO_LOW_GRADE
    if fy <= _GRADE_420:
        return _RATIO_420
    return max(_RATIO_420 * _GRADE_420 / fy, _RATIO_FLOOR)


def max_bar_spacing(h: float) -> float:
    """C.10.5.4: no mayor que tres veces el espesor ni que 450 mm."""
    return min(_SPACING_THICKNESS * h, _MAX_SPACING)


def combined_max_bar_spacing(h: float) -> float:
    """Zapata combinada: la de las zapatas de espesor uniforme, C.10.5.4 (tres veces el espesor y 450 mm), en mm. El
    control de agrietamiento (C.10.6.4) lo revisa la flexión de vigas."""
    return max_bar_spacing(h)


def combined_min_shear_threshold(vc: float) -> float | None:
    """C.11.4.6.1(a): las zapatas no requieren Av,min; None."""
    return None


def band_fraction(beta: float) -> float:
    """C.15.4.4.2, ecuación (C.15-1): γs = 2/(β + 1), con β = lado largo / lado corto."""
    return 2 / (beta + 1)


def min_depth() -> float:
    """C.15.7: la altura sobre el refuerzo inferior no es menor que 150 mm (zapatas sobre el suelo)."""
    return _MIN_DEPTH


def footing_depth(h: float, cover: float, first_db: float, second_db: float) -> float:
    """C.15.7 mide la altura sobre el refuerzo inferior: desde la cara superior de la malla inferior."""
    return h - cover - first_db - second_db


def one_way_concrete_shear(*, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float) -> float:
    """C.15.5.1 remite a C.11 (C.11.11.1.1): la misma Vc de vigas, el mayor entre C.11.2.1 y C.11.2.2 (D-030), sin carga
    axial y sin refuerzo a cortante, en N. Vu y Mu en valor absoluto en la sección."""
    return shear.concrete_shear(fc=fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=0.0, ag=bw * h, vu=vu, mu=mu, av_ge_min=False)


def punching_size_factor() -> float:
    """NSR-10 no tiene factor de efecto de tamaño en el cortante en dos direcciones: λs = 1.0."""
    return _SIZE_FACTOR


def dowel_min_ratio() -> float:
    """C.15.8.2.1: el refuerzo que cruza la interfaz entre columna o pedestal y zapata es al menos 0.005Ag del elemento
    soportado."""
    return _DOWEL_RATIO
