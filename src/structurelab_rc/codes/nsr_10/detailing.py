"""Detalles del refuerzo según NSR-10 Título C: ganchos estándar y de estribo (C.7.1), diámetros mínimos de doblado (C.7.2)
y empalmes por traslapo a tracción (C.12.15) y a compresión (C.12.16). Valores en mm y MPa (D-125)."""

_BAR_8 = 25.4 + 0.5  # mm: No. 3 a No. 8 (Tabla C.7.2)
_BAR_11 = 35.8 + 0.5  # mm: No. 9 a No. 11
_BAR_5 = 15.9 + 0.5  # mm: No. 5 y menores (estribos, C.7.1.3 y C.7.2.2)
_ANGLE_90, _ANGLE_135, _ANGLE_180 = 90, 135, 180  # grados del doblez
_HOOK_180_MIN = 65.0
_LAP_MIN = 300.0
_LAP_FACTORS = {"A": 1.0, "B": 1.3}
_CLASS_A_RATIO = 2.0
_CLASS_A_FRACTION = 0.5
_FY_COMPRESSION = 420.0
_FC_COMPRESSION = 21.0


def clauses() -> dict[str, str]:
    return {
        "hook": "C.7.1.1 y C.7.1.2",
        "stirrup_hook": "C.7.1.3",
        "bend": "C.7.2.1 y Tabla C.7.2",
        "stirrup_bend": "C.7.2.2",
        "tension_lap": "C.12.15.1",
        "lap_class": "C.12.15.2",
        "compression_lap": "C.12.16.1",
    }


def hook_bend_diameter(db: float) -> float:
    """Tabla C.7.2: diámetro interior mínimo de doblado de los ganchos estándar, 6db (No. 3 a No. 8), 8db (No. 9 a No. 11)
    o 10db (No. 14 y No. 18), en mm."""
    return (6.0 if db <= _BAR_8 else 8.0 if db <= _BAR_11 else 10.0) * db


def hook_extension(db: float, angle: int) -> float:
    """Extensión recta del gancho estándar en el extremo libre: 4db no menor de 65 mm con 180° (C.7.1.1) y 12db con 90°
    (C.7.1.2), en mm."""
    if angle == _ANGLE_180:
        return max(4.0 * db, _HOOK_180_MIN)
    if angle == _ANGLE_90:
        return 12.0 * db
    raise ValueError(f"gancho estándar de {angle}° no definido en C.7.1")


def stirrup_bend_diameter(db: float) -> float:
    """C.7.2.2: 4db para estribos No. 5 y menores; para mayores, la Tabla C.7.2 (6db hasta No. 8), en mm."""
    return 4.0 * db if db <= _BAR_5 else hook_bend_diameter(db)


def stirrup_hook_extension(db: float, angle: int) -> float | None:
    """C.7.1.3: 90° más 6db (No. 5 y menores) o 12db (No. 6 a No. 8); 135° más 6db (No. 8 y menores), en mm. None si
    C.7.1.3 no define ese gancho para la barra."""
    if angle == _ANGLE_90:
        return 6.0 * db if db <= _BAR_5 else 12.0 * db if db <= _BAR_8 else None
    if angle == _ANGLE_135:
        return 6.0 * db if db <= _BAR_8 else None
    return None


def tension_lap_length(development: float, splice_class: str) -> float:
    """C.12.15.1: 1.0ℓd (clase A) o 1.3ℓd (clase B), no menor que 300 mm, con ℓd de C.12.2 sin su mínimo de 300 mm ni el
    factor de C.12.2.5, en mm."""
    return max(_LAP_FACTORS[splice_class] * development, _LAP_MIN)


def lap_splice_class(provided_ratio: float, spliced_fraction: float) -> str:
    """C.12.15.2: clase A si As provisto/As requerido ≥ 2 en todo el empalme y se empalma la mitad o menos del refuerzo;
    si no, clase B."""
    return "A" if provided_ratio >= _CLASS_A_RATIO and spliced_fraction <= _CLASS_A_FRACTION else "B"


def compression_lap_length(fy: float, fc: float, db: float) -> float | None:
    """C.12.16.1: 0.071fy·db con fy ≤ 420 MPa o (0.13fy − 24)·db si es mayor, no menor que 300 mm; aumentada en 1/3 con
    f'c < 21 MPa, en mm."""
    length = max((0.071 * fy if fy <= _FY_COMPRESSION else 0.13 * fy - 24.0) * db, _LAP_MIN)
    return length * 4.0 / 3.0 if fc < _FC_COMPRESSION else length
