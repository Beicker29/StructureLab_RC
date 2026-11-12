"""Zapata combinada: nombres de sus direcciones y salida en los ejes declarados (D-101).

El cálculo trabaja en ejes de la viga (D-094): X a lo largo de la viga que une las columnas (la dirección principal) e Y
transversal (la dirección secundaria). Las verificaciones nombran las barras por su dirección, principal o secundaria,
no por un eje. Con la dirección principal en la Y global, las verificaciones y los diagramas vuelven a los ejes globales
en que el usuario escribió la zapata, con el giro inverso del de la carga (X de la viga = +Y global, Y de la viga = −X
global, así x = −y' e y = x'): los rótulos de caras, bordes y ejes de las notas, las posiciones transversales (la z de
las franjas, medida desde el borde −X global) y los valores con eje (excentricidades, momentos en la base, pasiva,
punzonamiento y presiones en las esquinas). Con la dirección principal en la X global no cambia nada. Las demandas,
las capacidades y los estados no dependen de los ejes.
"""

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from structurelab_rc.domain.check import Check
from structurelab_rc.model.combined import CombinedFooting, beam_to_global

if TYPE_CHECKING:  # combined_diagrams importa los módulos que usan los nombres de las direcciones de este
    from structurelab_rc.domain.footing.combined_diagrams import Envelope

PRINCIPAL = "direccion principal"
SECONDARY = "direccion secundaria"
DIRECTIONS = {"x": PRINCIPAL, "y": SECONDARY}

_FACE = re.compile(r"\b([Cc]ara|[Bb]orde|[Vv]oladizo|Aleta) ([+−-])([XY])\b")
_AXIS = re.compile(r"\beje ([XY])\b")
_ALONG = re.compile(r"\ben x = ")
_FLIP = {"+": "-", "-": "+", "−": "+"}
# Pares (x, y) de valores: con signo, x = −y', y = x' (posiciones y momentos); sin signo, solo se intercambian
# (magnitudes de cada eje).
_SIGNED = (("ex", "ey"), ("Mx base", "My base"), ("xc", "yc"), ("Msc x", "Msc y"))
_SWAPPED = (("Jc x", "Jc y"), ("gamma v x", "gamma v y"), ("Pp x", "Pp y"))
_CORNER_NAMES = ("-x-y", "+x-y", "+x+y", "-x+y")


def _rotated(footing: CombinedFooting) -> bool:
    return footing.principal_direction == "y"


def _face(match: re.Match[str]) -> str:
    word, sign, axis = match.groups()
    # X de la viga = +Y global; Y de la viga = −X global.
    return f"{word} {sign}Y" if axis == "X" else f"{word} {_FLIP[sign]}X"


def declared_text(footing: CombinedFooting, text: str) -> str:
    """Una nota con rótulos de ejes de la viga, en los ejes declarados."""
    if not _rotated(footing):
        return text
    text = _FACE.sub(_face, text)
    text = _AXIS.sub(lambda match: f"eje {'Y' if match.group(1) == 'X' else 'X'}", text)
    return _ALONG.sub("en y = ", text)


def _pressure_corner(name: str) -> str:
    """La esquina de la viga que es la esquina global name: con x = −y' e y = x', la global (sx, sy) es la de la viga
    (sy, −sx)."""
    sx, sy = name[0], name[2]
    return f"{sy}x{_FLIP[sx]}y"


def declared_values(footing: CombinedFooting, values: tuple[tuple[str, float], ...]) -> tuple[tuple[str, float], ...]:
    """Los valores con eje de una verificación, en los ejes declarados; los demás no cambian y conservan su orden."""
    if not _rotated(footing):
        return values
    beam = dict(values)
    out = dict(beam)
    for x_key, y_key in _SIGNED:
        if x_key in beam and y_key in beam:
            out[x_key], out[y_key] = 0.0 - beam[y_key], beam[x_key]  # 0 − y: sin −0.0
    for x_key, y_key in _SWAPPED:
        if x_key in beam and y_key in beam:
            out[x_key], out[y_key] = beam[y_key], beam[x_key]
    for name in _CORNER_NAMES:
        key = f"p esquina {name}"
        if key in beam:
            out[key] = beam[f"p esquina {_pressure_corner(name)}"]
    corners = []
    index = 1
    while f"esquina {index} v" in beam:
        x, y = beam_to_global(beam[f"esquina {index} x"], beam[f"esquina {index} y"])
        corners.append((x, y, beam[f"esquina {index} v"]))
        index += 1
    # Las esquinas del perímetro de punzonamiento van ordenadas por y y luego por x, como en el cálculo.
    for number, (x, y, stress) in enumerate(sorted(corners, key=lambda corner: (corner[1], corner[0])), start=1):
        out[f"esquina {number} x"], out[f"esquina {number} y"], out[f"esquina {number} v"] = x, y, stress
    return tuple((key, out[key]) for key, _ in values)


def declared_checks(footing: CombinedFooting, checks: list[Check]) -> list[Check]:
    """Las verificaciones de la zapata combinada en los ejes declarados. La z de las franjas transversales se mide desde
    el borde −X global (la de la viga, desde su borde −Y, que es el +X global)."""
    if not _rotated(footing):
        return checks
    out = []
    for check in checks:
        z = check.z
        if z is not None and check.note.startswith("Franja"):
            z = footing.ly - z
        out.append(replace(check, note=declared_text(footing, check.note), values=declared_values(footing, check.values), z=z))
    return out


def declared_envelope(footing: CombinedFooting, envelope: "Envelope") -> "Envelope":
    """Un diagrama transversal (posición y de la viga) en el eje X declarado: x = −y, así que las posiciones se invierten
    de orden y V, del cuerpo libre a la izquierda (−X), cambia de signo; M no cambia."""
    if not _rotated(footing):
        return envelope
    count = len(envelope.positions)

    def reverse(values: tuple[float, ...], sign: float = 1.0) -> tuple[float, ...]:
        return tuple(0.0 + sign * value for value in reversed(values))  # 0 + …: sin −0.0

    extremes = []
    for name, value, position, case in envelope.extremes:
        if name.startswith("V"):
            name, value = ("V-" if name == "V+" else "V+"), 0.0 - value
        extremes.append((name, value, 0.0 - position, case))
    order = {"M+": 0, "M-": 1, "V+": 2, "V-": 3}
    return replace(envelope, positions=reverse(envelope.positions, -1.0), moment_max=reverse(envelope.moment_max),
                   moment_min=reverse(envelope.moment_min), shear_max=reverse(envelope.shear_min, -1.0),
                   shear_min=reverse(envelope.shear_max, -1.0),
                   segments=tuple((count - 1 - end, count - 1 - start) for start, end in reversed(envelope.segments)),
                   marks=tuple((0.0 - position, declared_text(footing, label)) for position, label in reversed(envelope.marks)),
                   extremes=tuple(sorted(extremes, key=lambda item: order[item[0]])))
