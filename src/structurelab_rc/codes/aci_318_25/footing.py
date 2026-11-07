"""Zapatas aisladas según ACI CODE-318-25, capítulo 13 y las disposiciones aplicables del capítulo 8 (13.3.3.1)."""

_MIN_RATIO = 0.0018
_MAX_SPACING = 450.0
_SPACING_THICKNESS = 2.0
_MIN_DEPTH = 150.0


def clauses() -> dict[str, str]:
    return {
        "bearing": "13.3.1.1",
        "strength": "13.2.6.6 y 13.2.7.1",
        "net_tensile_strain": "8.3.3.1",
        "min_reinforcement": "8.6.1.1",
        "spacing": "8.7.2.2",
        "band": "13.3.3.3",
        "min_depth": "13.3.1.2",
    }


def min_reinforcement_ratio(fy: float) -> float:
    """8.6.1.1: As,min = 0.0018Ag, sin depender de fy."""
    return _MIN_RATIO


def max_bar_spacing(h: float) -> float:
    """8.7.2.2: en secciones críticas, el menor de 2h y 450 mm."""
    return min(_SPACING_THICKNESS * h, _MAX_SPACING)


def band_fraction(beta: float) -> float:
    """13.3.3.3, ecuación (13.3.3.3): γs = 2/(β + 1), con β = lado largo / lado corto."""
    return 2 / (beta + 1)


def min_depth() -> float:
    """13.3.1.2: la altura efectiva del refuerzo inferior es al menos 150 mm."""
    return _MIN_DEPTH


def footing_depth(h: float, cover: float, first_db: float, second_db: float) -> float:
    """13.3.1.2 mide la altura efectiva d del refuerzo inferior; se toma la menor, la de la segunda capa."""
    return h - cover - first_db - second_db / 2
