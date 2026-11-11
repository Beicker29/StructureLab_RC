"""Zapatas aisladas según ACI CODE-318-25, capítulo 13 y las disposiciones aplicables del capítulo 8 (13.3.3.1)."""

from structurelab_rc.codes.aci_318_25 import shear

_MIN_RATIO = 0.0018
_MAX_SPACING = 450.0
_SPACING_THICKNESS = 2.0
_MIN_DEPTH = 150.0
_SIZE_FACTOR = 1.0
_DOWEL_RATIO = 0.005
_ONE_WAY_SPACING_THICKNESS = 3.0


def clauses() -> dict[str, str]:
    return {
        "bearing": "13.3.1.1",
        "stability": "13.2.6.1",
        "strength": "13.2.6.6 y 13.2.7.1",
        "net_tensile_strain": "8.3.3.1",
        "min_reinforcement": "8.6.1.1",
        "spacing": "8.7.2.2",
        "band": "13.3.3.3",
        "min_depth": "13.3.1.2",
        "one_way_shear": "13.2.6.2(a) y 13.2.7.2",
        "punching_min_reinforcement": "8.6.1.2",
        "moment_transfer": "8.4.2.2.1 a 8.4.2.2.3 (13.3.3.1)",
        "dowels": "16.3.4.1",
        "dowel_excess": "16.3.3.4",
        "combined_spacing": "13.3.2.1 y 7.7.2.3",
        "combined_min_reinforcement": "13.3.2.1 y 7.6.1.1",
        "combined_min_shear": "13.3.2.1 y 7.6.3.1",
    }


def min_reinforcement_ratio(fy: float) -> float:
    """8.6.1.1: As,min = 0.0018Ag, sin depender de fy."""
    return _MIN_RATIO


def max_bar_spacing(h: float) -> float:
    """8.7.2.2: en secciones críticas, el menor de 2h y 450 mm."""
    return min(_SPACING_THICKNESS * h, _MAX_SPACING)


def combined_max_bar_spacing(h: float) -> float:
    """Zapata combinada en una dirección (13.3.2.1 remite a los capítulos 7 y 9): el menor de 3h y 450 mm (7.7.2.3), en
    mm. El límite de fisuración (24.3.2) lo revisa la flexión de vigas."""
    return min(_ONE_WAY_SPACING_THICKNESS * h, _MAX_SPACING)


def combined_min_shear_threshold(vc: float) -> float | None:
    """Zapata combinada (13.3.2.1 remite al capítulo 7): Av,min donde Vu > φVc (7.6.3.1), en N."""
    return shear.strength_reduction() * vc


def band_fraction(beta: float) -> float:
    """13.3.3.3, ecuación (13.3.3.3): γs = 2/(β + 1), con β = lado largo / lado corto."""
    return 2 / (beta + 1)


def min_depth() -> float:
    """13.3.1.2: la altura efectiva del refuerzo inferior es al menos 150 mm."""
    return _MIN_DEPTH


def footing_depth(h: float, cover: float, first_db: float, second_db: float) -> float:
    """13.3.1.2 mide la altura efectiva d del refuerzo inferior; se toma la menor, la de la segunda capa."""
    return h - cover - first_db - second_db / 2


def one_way_concrete_shear(*, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, vu: float, mu: float) -> float:
    """13.2.6.2(a): Vc = 0.17λ√f'c·bw·d en zapatas apoyadas en el suelo, con √f'c ≤ 8.3 MPa (22.5.3.1), en N.

    No usa h, ρw, Vu ni Mu: el capítulo 13 permite omitir el efecto de tamaño y el del refuerzo a flexión.
    """
    return 0.17 * lam * shear.limited_sqrt_fc(fc, av_ge_min=False) * bw * d


def punching_size_factor() -> float:
    """13.2.6.2(b): λs = 1.0 en el cortante en dos direcciones de zapatas apoyadas en el suelo."""
    return _SIZE_FACTOR


def dowel_min_ratio() -> float:
    """16.3.4.1: el refuerzo que cruza la interfaz entre columna o pedestal y zapata es al menos 0.005Ag del elemento
    soportado."""
    return _DOWEL_RATIO
