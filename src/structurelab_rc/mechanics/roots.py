"""Raíz de una función continua entre dos puntos con signos opuestos, por el método de Brent (D-124).

Combina interpolación cuadrática inversa, secante y bisección: converge como la secante en las funciones suaves y nunca
peor que la bisección, porque conserva siempre un intervalo con cambio de signo. Neutro: sin unidades ni normas.
"""

from collections.abc import Callable

_MAX_STEPS = 200


def _interpolate(points: tuple[float, float, float], values: tuple[float, float, float]) -> float:
    """Interpolación cuadrática inversa por los tres puntos o, si dos valores coinciden, secante entre a y b."""
    (a, b, c), (fa, fb, fc) = points, values
    if fc not in (fa, fb):
        return (a * fb * fc / ((fa - fb) * (fa - fc)) + b * fa * fc / ((fb - fa) * (fb - fc))
                + c * fa * fb / ((fc - fa) * (fc - fb)))
    return b - fb * (b - a) / (fb - fa)


def _bisect_instead(s: float, points: tuple[float, float, float, float], bisected: bool, step: float) -> bool:
    """Las condiciones de Brent para descartar el paso interpolado: fuera de [(3a + b)/4, b] o sin achicar lo suficiente."""
    a, b, c, d = points
    low, high = sorted(((3 * a + b) / 4, b))
    if not low < s < high:
        return True
    previous = abs(b - c) if bisected else abs(c - d)
    return abs(s - b) >= previous / 2 or previous < step


def find_root(function: Callable[[float], float], bracket: tuple[float, float], values: tuple[float, float],
              tolerance: Callable[[float], float]) -> float:
    """Raíz de function entre bracket = (a, b), con values = (f(a), f(b)) de signos opuestos (o uno nulo). Termina cuando
    el intervalo que encierra la raíz mide menos que tolerance(b) (b, la mejor estimación) o se anula la función."""
    a, b = bracket
    fa, fb = values
    if fa == 0 or fb == 0:
        return a if fa == 0 else b
    if (fa > 0) == (fb > 0):
        raise ValueError("los extremos no encierran una raíz")
    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc, d = a, fa, 0.0
    bisected = True
    for _ in range(_MAX_STEPS):
        if fb == 0 or abs(b - a) <= tolerance(b):
            return b
        s = _interpolate((a, b, c), (fa, fb, fc))
        bisected = _bisect_instead(s, (a, b, c, d), bisected, tolerance(b))
        if bisected:
            s = (a + b) / 2
        fs = function(s)
        d, c, fc = c, b, fb
        if (fa > 0) == (fs > 0):
            a, fa = s, fs  # el cambio de signo queda entre s y b
        else:
            b, fb = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa
    return b
