"""Despiece de barras y cartilla (v3 Fase 4A, D-125). Neutro: recibe las barras con los límites que ya calculó el perfil
(diámetro de doblado, extensión de los ganchos y longitud de empalme) y no contiene fórmulas normativas.

Formas: recta (sin ganchos), L (gancho en un extremo), U (ganchos en los dos) y estribo cerrado con ganchos a 135° en
una esquina. Las dimensiones de la cartilla son exteriores (de cara exterior a cara exterior de la barra); la longitud de
corte se mide por el eje de la barra (tramos rectos más arcos de radio D/2 + db/2) y se redondea hacia arriba a
ROUNDING (decisión del usuario). Una barra más larga que la longitud comercial se parte en tramos con su empalme por
traslapo; en las barras vecinas los empalmes se escalonan (la mitad de las barras empieza con medio tramo comercial),
para no empalmar más de la mitad del acero en una sección.
"""

import math
from dataclasses import dataclass

ROUNDING = 50.0  # mm: redondeo hacia arriba de las longitudes de corte (D-125)
_MM_PER_M = 1000.0
_HALF_TURN = 180  # °: un gancho de 180° vuelve paralelo a la barra


@dataclass(frozen=True)
class Hook:
    """Gancho en un extremo: ángulo del doblez (°), diámetro interior de doblado y extensión recta, en mm."""

    angle: int
    bend_diameter: float
    extension: float


@dataclass(frozen=True)
class BarRun:
    """Barras iguales de un grupo del elemento. length es la dimensión exterior del tramo recto principal (de cara
    exterior a cara exterior, ganchos incluidos); hooks, el gancho de cada extremo (None si es recto); lap, la longitud
    de empalme por traslapo si hay que partir la barra (None si no se empalma); stirrup, el ancho y el alto exteriores de
    un estribo cerrado (con ganchos de 135° en hooks); note, lo que la cartilla debe decir de la barra."""

    group: str
    designation: str
    diameter: float
    mass_kg_m: float
    count: int
    length: float
    hooks: tuple[Hook | None, Hook | None] = (None, None)
    lap: float | None = None
    stirrup: tuple[float, float] | None = None
    note: str = ""


@dataclass(frozen=True)
class Piece:
    """Un tipo de barra cortada: forma, dimensiones exteriores (mm) y longitud de corte redondeada (mm)."""

    group: str
    designation: str
    shape: str
    dimensions: tuple[tuple[str, float], ...]
    cut_length: float
    mass_kg_m: float
    count: int
    note: str


@dataclass(frozen=True)
class ScheduleRow:
    """Fila de la cartilla: una marca."""

    mark: str
    piece: Piece

    @property
    def mass(self) -> float:
        """Peso total de la marca, en kg."""
        return self.piece.count * self.piece.cut_length / _MM_PER_M * self.piece.mass_kg_m


def round_up(length: float) -> float:
    """Longitud redondeada hacia arriba a ROUNDING (con tolerancia para no subir un múltiplo exacto)."""
    return math.ceil(length / ROUNDING - 1e-9) * ROUNDING


def _hook_parts(hook: Hook, db: float) -> tuple[float, float, float]:
    """(lo que el gancho resta al tramo recto exterior, longitud del arco por el eje, pata exterior) de un gancho."""
    radius = hook.bend_diameter / 2
    arc = math.radians(hook.angle) * (radius + db / 2)
    leg = hook.extension + radius + db if hook.angle < _HALF_TURN else hook.bend_diameter + 2 * db
    return radius + db, arc, leg


def _straight_length(run: BarRun, length: float, hooks: tuple[Hook | None, Hook | None]) -> tuple[float, list[tuple[str, float]]]:
    """Longitud por el eje y dimensiones exteriores de una barra recta con ganchos opcionales, de largo exterior length."""
    db = run.diameter
    total, dimensions = length, [("A", length)]
    for hook, name in zip(hooks, ("B", "C"), strict=True):
        if hook is None:
            continue
        cut, arc, leg = _hook_parts(hook, db)
        total += arc + hook.extension - cut
        dimensions.append((name, leg))
    return total, dimensions


def _stirrup_length(run: BarRun) -> tuple[float, list[tuple[str, float]]]:
    """Estribo cerrado de ancho × alto exteriores: cuatro lados, tres esquinas a 90° y los dos ganchos de 135° en la
    esquina de cierre, por el eje."""
    assert run.stirrup is not None
    width, height = run.stirrup
    hook = run.hooks[0]
    assert hook is not None
    db = run.diameter
    radius = hook.bend_diameter / 2
    straight = 2 * (width - 2 * (radius + db)) + 2 * (height - 2 * (radius + db))
    corners = 3 * math.radians(90) * (radius + db / 2) + 2 * math.radians(hook.angle) * (radius + db / 2)
    return straight + corners + 2 * hook.extension, [("A", width), ("B", height), ("C", hook.extension)]


def _shape(hooks: tuple[Hook | None, Hook | None]) -> str:
    count = sum(hook is not None for hook in hooks)
    return ("recta", "L", "U")[count]


def pieces(run: BarRun, stock: float) -> list[Piece]:
    """Las barras cortadas de una corrida: una sola si cabe en la longitud comercial; si no, tramos empalmados por
    traslapo, con los empalmes de la mitad de las barras corridos medio tramo comercial."""
    if run.stirrup is not None:
        length, dimensions = _stirrup_length(run)
        return [Piece(run.group, run.designation, "estribo", tuple(dimensions), round_up(length), run.mass_kg_m, run.count, run.note)]
    total, dimensions = _straight_length(run, run.length, run.hooks)
    if round_up(total) <= stock or run.lap is None:
        note = run.note if round_up(total) <= stock else f"{run.note}; supera la longitud comercial y no se empalma".lstrip("; ")
        return [Piece(run.group, run.designation, _shape(run.hooks), tuple(dimensions), round_up(total), run.mass_kg_m, run.count, note)]
    patterns = [(math.ceil(run.count / 2), stock), (run.count // 2, stock / 2)] if run.count > 1 else [(1, stock)]
    result: list[Piece] = []
    for count, first in patterns:
        if count:
            result += _spliced(run, (total, count), (first, stock))
    return result


def _spliced(run: BarRun, total_count: tuple[float, int], lengths: tuple[float, float]) -> list[Piece]:
    """Tramos de una barra partida: el primero de largo first (por el eje), los siguientes de la longitud comercial, cada
    uno traslapado lap con el anterior; los ganchos van en el primero y en el último."""
    total, count = total_count
    first, stock = lengths
    assert run.lap is not None
    starts, ends, start, size = [], [], 0.0, first
    while start + size < total:
        starts.append(start)
        ends.append(start + size)
        start, size = start + size - run.lap, stock
    starts.append(start)
    ends.append(total)
    result = []
    for index, (begin, end) in enumerate(zip(starts, ends, strict=True)):
        hooks = (run.hooks[0] if index == 0 else None, run.hooks[1] if index == len(starts) - 1 else None)
        axis = end - begin
        # La dimensión exterior A del tramo: su largo por el eje menos lo que agregan sus ganchos.
        extra = sum(_hook_parts(hook, run.diameter)[1] + hook.extension - _hook_parts(hook, run.diameter)[0]
                    for hook in hooks if hook is not None)
        _, dimensions = _straight_length(run, axis - extra, hooks)
        note = f"tramo {index + 1} de {len(starts)}, traslapo {run.lap:.0f} mm" + (f"; {run.note}" if run.note else "")
        result.append(Piece(run.group, run.designation, _shape(hooks), tuple(dimensions), round_up(axis), run.mass_kg_m, count, note))
    return result


def schedule(element: str, runs: list[BarRun], stock: float) -> list[ScheduleRow]:
    """La cartilla de un elemento: las barras cortadas de todas sus corridas; las iguales (designación, forma, dimensiones
    redondeadas y longitud de corte) comparten marca, numerada en el orden de aparición ("<elemento>-01", "-02", …), y la
    fila nombra todos los grupos que reúne."""
    marks: dict[tuple[object, ...], int] = {}
    counts: dict[tuple[object, ...], Piece] = {}
    for run in runs:
        for piece in pieces(run, stock):
            key = (piece.designation, piece.shape, tuple((name, round_up(value)) for name, value in piece.dimensions), piece.cut_length)
            if key in counts:
                previous = counts[key]
                groups = previous.group if piece.group in previous.group.split(", ") else f"{previous.group}, {piece.group}"
                notes = previous.note if piece.note in previous.note.split(" | ") else f"{previous.note} | {piece.note}"
                counts[key] = Piece(groups, previous.designation, previous.shape, previous.dimensions, previous.cut_length,
                                    previous.mass_kg_m, previous.count + piece.count, notes)
            else:
                marks[key] = len(marks) + 1
                counts[key] = piece
    return [ScheduleRow(f"{element}-{marks[key]:02d}", counts[key]) for key in marks]


def totals(rows: list[ScheduleRow]) -> dict[str, float]:
    """Peso total por designación, en kg, en el orden en que aparecen."""
    result: dict[str, float] = {}
    for row in rows:
        result[row.piece.designation] = result.get(row.piece.designation, 0.0) + row.mass
    return result
