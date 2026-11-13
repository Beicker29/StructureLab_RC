"""Detalles del refuerzo según ACI CODE-318-25: ganchos estándar (Tabla 25.3.1), ganchos y doblado de estribos (Tabla
25.3.2) y empalmes por traslapo a tracción (25.5.2.1) y a compresión (25.5.5.1). Valores en mm y MPa (D-125)."""

_BAR_25 = 25.4 + 0.5  # mm: No. 10 a No. 25
_BAR_36 = 35.8 + 0.5  # mm: No. 29 a No. 36
_BAR_16 = 15.9 + 0.5  # mm: No. 10 a No. 16 (Tabla 25.3.2)
_ANGLE_90, _ANGLE_135, _ANGLE_180 = 90, 135, 180  # grados del doblez
_HOOK_180_MIN = 65.0
_STIRRUP_EXTENSION_MIN = 75.0
_LAP_MIN = 300.0
_LAP_FACTORS = {"A": 1.0, "B": 1.3}
_CLASS_A_RATIO = 2.0
_CLASS_A_FRACTION = 0.5
_FY_COMPRESSION, _FY_COMPRESSION_HIGH = 420.0, 550.0
_FC_COMPRESSION = 21.0


def clauses() -> dict[str, str]:
    return {
        "hook": "25.3.1 y Tabla 25.3.1",
        "stirrup_hook": "25.3.2 y Tabla 25.3.2",
        "bend": "Tabla 25.3.1",
        "stirrup_bend": "Tabla 25.3.2",
        "tension_lap": "25.5.2.1 y Tabla 25.5.2.1",
        "lap_class": "Tabla 25.5.2.1",
        "compression_lap": "25.5.5.1",
    }


def hook_bend_diameter(db: float) -> float:
    """Tabla 25.3.1: diámetro interior mínimo de doblado de los ganchos estándar, 6db (No. 10 a No. 25), 8db (No. 29 a
    No. 36) o 10db (No. 43 y No. 57), en mm."""
    return (6.0 if db <= _BAR_25 else 8.0 if db <= _BAR_36 else 10.0) * db


def hook_extension(db: float, angle: int) -> float:
    """Tabla 25.3.1: extensión recta del gancho estándar, 12db con 90° y el mayor de 4db y 65 mm con 180°, en mm."""
    if angle == _ANGLE_180:
        return max(4.0 * db, _HOOK_180_MIN)
    if angle == _ANGLE_90:
        return 12.0 * db
    raise ValueError(f"gancho estándar de {angle}° no definido en la Tabla 25.3.1")


def stirrup_bend_diameter(db: float) -> float:
    """Tabla 25.3.2: 4db (No. 10 a No. 16) o 6db (No. 19 a No. 25), en mm."""
    return (4.0 if db <= _BAR_16 else 6.0) * db


def stirrup_hook_extension(db: float, angle: int) -> float | None:
    """Tabla 25.3.2: 90° con el mayor de 6db y 75 mm (No. 10 a No. 16) o 12db (No. 19 a No. 25); 135° con el mayor de 6db
    y 75 mm; 180° con el mayor de 4db y 65 mm (No. 10 a No. 25), en mm. None si la tabla no define ese gancho."""
    if db > _BAR_25:
        return None
    if angle == _ANGLE_90:
        return max(6.0 * db, _STIRRUP_EXTENSION_MIN) if db <= _BAR_16 else 12.0 * db
    if angle == _ANGLE_135:
        return max(6.0 * db, _STIRRUP_EXTENSION_MIN)
    if angle == _ANGLE_180:
        return max(4.0 * db, _HOOK_180_MIN)
    return None


def tension_lap_length(development: float, splice_class: str) -> float:
    """Tabla 25.5.2.1: el mayor de 1.0ℓd y 300 mm (clase A) o de 1.3ℓd y 300 mm (clase B), con ℓd de 25.4.2.1(a) (sin el
    mínimo de 25.4.2.1(b)), en mm."""
    return max(_LAP_FACTORS[splice_class] * development, _LAP_MIN)


def lap_splice_class(provided_ratio: float, spliced_fraction: float) -> str:
    """Tabla 25.5.2.1: clase A si As provisto/As requerido ≥ 2.0 en el empalme y se empalma el 50 % o menos del acero
    dentro de la longitud de traslapo; en todos los demás casos, clase B."""
    return "A" if provided_ratio >= _CLASS_A_RATIO and spliced_fraction <= _CLASS_A_FRACTION else "B"


def compression_lap_length(fy: float, fc: float, db: float) -> float | None:
    """25.5.5.1 (a) y (b): el mayor de 0.071fy·db y 300 mm con fy ≤ 420 MPa, o de (0.13fy − 24)·db y 300 mm con
    420 < fy ≤ 550 MPa; aumentada en un tercio con f'c < 21 MPa, en mm. None con fy > 550 MPa: (c) también exige ℓst
    de 25.5.2.1, que depende de la barra empalmada."""
    if fy > _FY_COMPRESSION_HIGH:
        return None
    length = max((0.071 * fy if fy <= _FY_COMPRESSION else 0.13 * fy - 24.0) * db, _LAP_MIN)
    return length * 4.0 / 3.0 if fc < _FC_COMPRESSION else length
