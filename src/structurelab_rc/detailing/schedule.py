"""Despiece de barras y cartilla (v3 Fase 4A, D-125). Neutro: recibe las barras con los límites que ya calculó el perfil
(diámetro de doblado, extensión de los ganchos y longitud de empalme) y no contiene fórmulas normativas.

Formas, nombradas por sus extremos con la notación de DL-NET (D-150): "recta" sin ganchos; un código por gancho, L (90°),
U (180°) o 135 (135°), unidos por un guion en el orden de los extremos ("L", "L-L", "U-U", "L-U", …); y "E", el estribo
cerrado con ganchos a 135° en una esquina.

Convención de DL-NET (decisión del usuario, D-147): la longitud total de una barra es su tramo horizontal exterior A
(redondeado hacia arriba a 1 cm) más la longitud de cada gancho (hook_length, redondeada hacia arriba a
50 mm): con 90°, L = extensión + π·(D + 0.5·db)/8; con 180°, U = extensión + 0.5·π·(D + 0.5·db) − 0.5·(D + 0.5·db), con D
el diámetro interior de doblado. Así DL-NET reconstruye el tramo como Ltotal − 2L o Ltotal − 2U. El gancho de 135° de una
barra (que DL-NET no fabrica) sigue por el eje de la barra (tramos rectos más arcos de radio D/2 + db/2), con la longitud
total redondeada a 1 cm. El estribo cerrado, como lo calcula DL-NET (D-160): L = 2·(b + h) + 2·g, con b × h exteriores a
1 cm y g = extensión + arco del doblez por el eje − 0.5·(D + 0.5·db), hacia arriba a 10 mm.
Una barra más larga que la longitud comercial se parte en tramos con su empalme por
traslapo; en las barras vecinas los empalmes se escalonan (la mitad de las barras empieza con medio tramo comercial),
para no empalmar más de la mitad del acero en una sección.
"""

import math
from dataclasses import dataclass

ROUNDING = 10.0  # mm: redondeo hacia arriba de la longitud total y del tramo de cada barra (D-147)
HOOK_ROUNDING = 50.0  # mm: redondeo hacia arriba de la longitud de cada gancho, L o U (D-147)
_MM_PER_M = 1000.0
_HALF_TURN = 180  # °: un gancho de 180° vuelve paralelo a la barra


@dataclass(frozen=True)
class Hook:
    """Gancho en un extremo: ángulo del doblez (°), diámetro interior de doblado y extensión recta, en mm."""

    angle: int
    bend_diameter: float
    extension: float


@dataclass(frozen=True)
class Placement:
    """Dónde van las barras de una corrida, para el dibujo (D-126), en los ejes del elemento: origen en el centro de la
    planta, z hacia arriba desde la base, en mm.

    along: "x" o "y" (barras horizontales paralelas a ese eje: positions es la otra coordenada de cada barra, level la z
    de su eje y span el inicio y el fin de su eje a lo largo de along); "estribo" (positions, las abscisas x de los
    estribos; level, la z de su cara inferior exterior; cross, la y de su centro); "z" (pasadores de una columna:
    positions, el centro (x, y) de la columna; span, la z del pie y del extremo superior; cross, la distancia del eje de
    la columna a los pasadores que se dibujan, en x y en y, que es esquemática)."""

    along: str
    positions: tuple[float, ...]
    level: float
    span: tuple[float, float]
    cross: tuple[float, float] = (0.0, 0.0)


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
    placement: Placement | None = None


@dataclass(frozen=True)
class Piece:
    """Un tipo de barra cortada: forma, dimensiones exteriores (mm), longitud de corte redondeada (mm) y el ángulo del
    gancho de cada extremo (None si no tiene; en el estribo, los dos ganchos de cierre). Es el modelo de despiece de
    todos los elementos: la cartilla, el dibujo y la cartilla DL-NET (D-133) lo leen."""

    group: str
    designation: str
    shape: str
    dimensions: tuple[tuple[str, float], ...]
    cut_length: float
    mass_kg_m: float
    count: int
    note: str
    angles: tuple[int | None, int | None] = (None, None)


@dataclass(frozen=True)
class ScheduleRow:
    """Fila de la cartilla: una marca."""

    mark: str
    piece: Piece

    @property
    def mass(self) -> float:
        """Peso total de la marca, en kg."""
        return self.piece.count * self.piece.cut_length / _MM_PER_M * self.piece.mass_kg_m


def round_up(length: float, step: float = ROUNDING) -> float:
    """Longitud redondeada hacia arriba a step (con tolerancia para no subir un múltiplo exacto)."""
    return math.ceil(length / step - 1e-9) * step


def _hook_parts(hook: Hook, db: float) -> tuple[float, float, float]:
    """(lo que el gancho resta al tramo recto exterior, longitud del arco por el eje, pata exterior) de un gancho."""
    radius = hook.bend_diameter / 2
    arc = math.radians(hook.angle) * (radius + db / 2)
    leg = hook.extension + radius + db if hook.angle < _HALF_TURN else hook.bend_diameter + 2 * db
    return radius + db, arc, leg


_QUARTER_TURN = 90  # °


def hook_length(hook: Hook, db: float) -> float:
    """Longitud de un gancho en la convención de DL-NET (decisión del usuario, D-147), la dimensión B o C de la cartilla:
    la extensión más el doblez medido con D + 0.5·db, redondeada hacia arriba a 50 mm. Con 90°, L = extensión +
    π·(D + 0.5·db)/8; con 180°, U = extensión + 0.5·π·(D + 0.5·db) − 0.5·(D + 0.5·db). Con 135° (no lo fabrica DL-NET), lo
    que el gancho agrega por el eje a la dimensión exterior. En mm."""
    base = hook.bend_diameter + 0.5 * db
    if hook.angle == _QUARTER_TURN:
        raw = hook.extension + math.pi * base / 8
    elif hook.angle == _HALF_TURN:
        raw = hook.extension + 0.5 * math.pi * base - 0.5 * base
    else:
        cut, arc, _ = _hook_parts(hook, db)
        raw = arc + hook.extension - cut
    return round_up(raw, HOOK_ROUNDING)


def hook_leg(hook: Hook, db: float) -> float:
    """Pata que se dibuja de un gancho, en mm: con 90°, su longitud L de la cartilla (hook_length); con 180°, el ancho
    exterior de la U (D + 2·db); con 135°, la pata exterior (extensión + D/2 + db)."""
    if hook.angle == _QUARTER_TURN:
        return hook_length(hook, db)
    return _hook_parts(hook, db)[2]


def _straight_length(run: BarRun, length: float, hooks: tuple[Hook | None, Hook | None]) -> tuple[float, list[tuple[str, float]]]:
    """Longitud total y dimensiones de una barra de tramo exterior length con ganchos opcionales (D-147): el tramo A
    redondeado hacia arriba a 1 cm más la longitud de cada gancho (hook_length)."""
    straight = round_up(length)
    total, dimensions = straight, [("A", straight)]
    for hook, name in zip(hooks, ("B", "C"), strict=True):
        if hook is None:
            continue
        leg = hook_length(hook, run.diameter)
        total += leg
        dimensions.append((name, leg))
    return total, dimensions


def stirrup_hook_length(hook: Hook, db: float) -> float:
    """g, el gancho del estribo en la convención de DL-NET (decisión del usuario, D-160): la extensión recta más el arco
    del doblez por el eje menos 0.5·(D + 0.5·db), redondeado hacia arriba a 10 mm. En mm."""
    arc = math.radians(hook.angle) * (hook.bend_diameter / 2 + db / 2)
    return round_up(hook.extension + arc - 0.5 * (hook.bend_diameter + 0.5 * db))


def _stirrup_length(run: BarRun) -> tuple[float, list[tuple[str, float]]]:
    """Estribo cerrado en la convención de DL-NET (D-160): b × h exteriores, cada uno hacia arriba a 10 mm, y
    L = 2·(b + h) + 2·g, la misma longitud que calcula DL-NET con la línea del .dli."""
    assert run.stirrup is not None
    width, height = (round_up(value) for value in run.stirrup)
    hook = run.hooks[0]
    assert hook is not None
    g = stirrup_hook_length(hook, run.diameter)
    return 2 * (width + height) + 2 * g, [("A", width), ("B", height), ("C", g)]


def _angles(hooks: tuple[Hook | None, Hook | None]) -> tuple[int | None, int | None]:
    start, end = hooks
    return None if start is None else start.angle, None if end is None else end.angle


HOOK_SHAPE = {90: "L", 180: "U", 135: "135"}  # código de cada gancho en el nombre de la forma (D-150)
STIRRUP_SHAPE = "E"
STRAIGHT_SHAPE = "recta"


def _shape(hooks: tuple[Hook | None, Hook | None]) -> str:
    """El nombre de la forma por sus extremos (D-150): "recta" o los códigos de sus ganchos en orden ("L-L")."""
    return "-".join(HOOK_SHAPE[hook.angle] for hook in hooks if hook is not None) or STRAIGHT_SHAPE


def pieces(run: BarRun, stock: float) -> list[Piece]:
    """Las barras cortadas de una corrida: una sola si cabe en la longitud comercial; si no, tramos empalmados por
    traslapo, con los empalmes de la mitad de las barras corridos medio tramo comercial."""
    if run.stirrup is not None:
        length, dimensions = _stirrup_length(run)
        return [Piece(run.group, run.designation, STIRRUP_SHAPE, tuple(dimensions), round_up(length), run.mass_kg_m, run.count, run.note,
                      _angles(run.hooks))]
    total, dimensions = _straight_length(run, run.length, run.hooks)
    if total <= stock or run.lap is None:
        note = run.note if total <= stock else f"{run.note}; supera la longitud comercial y no se empalma".lstrip("; ")
        return [Piece(run.group, run.designation, _shape(run.hooks), tuple(dimensions), total, run.mass_kg_m, run.count, note,
                      _angles(run.hooks))]
    patterns = [(math.ceil(run.count / 2), stock), (run.count // 2, stock / 2)] if run.count > 1 else [(1, stock)]
    result: list[Piece] = []
    for count, first in patterns:
        if count:
            result += _spliced(run, (total, count), (first, stock))
    return result


def _cuts(total: float, lap: float, lengths: tuple[float, float]) -> tuple[list[float], list[float]]:
    """Inicio y fin, por el eje, de los tramos de una barra de largo total: el primero de largo first, los siguientes de la
    longitud comercial, cada uno traslapado lap con el anterior; lengths = (first, stock)."""
    first, stock = lengths
    starts, ends, start, size = [], [], 0.0, first
    while start + size < total:
        starts.append(start)
        ends.append(start + size)
        start, size = start + size - lap, stock
    starts.append(start)
    ends.append(total)
    return starts, ends


def splice_spans(run: BarRun, stock: float) -> list[tuple[float, float]]:
    """Los tramos de las barras de una corrida que empiezan con un tramo comercial entero, para el dibujo (D-132): inicio y
    fin de cada uno a lo largo del tramo recto exterior (de 0 a run.length); uno solo si la barra no se empalma."""
    total, _ = _straight_length(run, run.length, run.hooks)
    if run.lap is None or total <= stock:
        return [(0.0, run.length)]
    hook = run.hooks[0]  # lo que el gancho inicial agrega antes del tramo recto exterior (D-147)
    start_extra = 0.0 if hook is None else hook_length(hook, run.diameter)
    starts, ends = _cuts(total, run.lap, (stock, stock))
    return [(max(begin - start_extra, 0.0), min(end - start_extra, run.length)) for begin, end in zip(starts, ends, strict=True)]


def _spliced(run: BarRun, total_count: tuple[float, int], lengths: tuple[float, float]) -> list[Piece]:
    """Tramos de una barra partida: el primero de largo first (por el eje), los siguientes de la longitud comercial, cada
    uno traslapado lap con el anterior; los ganchos van en el primero y en el último."""
    total, count = total_count
    assert run.lap is not None
    starts, ends = _cuts(total, run.lap, lengths)
    result = []
    for index, (begin, end) in enumerate(zip(starts, ends, strict=True)):
        hooks = (run.hooks[0] if index == 0 else None, run.hooks[1] if index == len(starts) - 1 else None)
        # El tramo A de la pieza: su longitud menos la de sus ganchos (D-147).
        extra = sum(hook_length(hook, run.diameter) for hook in hooks if hook is not None)
        length, dimensions = _straight_length(run, end - begin - extra, hooks)
        note = f"tramo {index + 1} de {len(starts)}, traslapo {run.lap:.0f} mm" + (f"; {run.note}" if run.note else "")
        result.append(Piece(run.group, run.designation, _shape(hooks), tuple(dimensions), length, run.mass_kg_m, count, note,
                            _angles(hooks)))
    return result


def schedule(element: str, runs: list[BarRun], stock: float) -> list[ScheduleRow]:
    """La cartilla de un elemento: las barras cortadas de todas sus corridas; las iguales (designación, forma, dimensiones
    redondeadas y longitud de corte) comparten marca, numerada en el orden de aparición ("<elemento>-01", "-02", …), y la
    fila nombra todos los grupos que reúne."""
    marks: dict[tuple[object, ...], int] = {}
    counts: dict[tuple[object, ...], Piece] = {}
    for _, key, piece in _keyed(runs, stock):
        if key in counts:
            previous = counts[key]
            groups = previous.group if piece.group in previous.group.split(", ") else f"{previous.group}, {piece.group}"
            notes = previous.note if piece.note in previous.note.split(" | ") else f"{previous.note} | {piece.note}"
            counts[key] = Piece(groups, previous.designation, previous.shape, previous.dimensions, previous.cut_length,
                                previous.mass_kg_m, previous.count + piece.count, notes, previous.angles)
        else:
            marks[key] = len(marks) + 1
            counts[key] = piece
    return [ScheduleRow(f"{element}-{marks[key]:02d}", counts[key]) for key in marks]


def _keyed(runs: list[BarRun], stock: float) -> list[tuple[int, tuple[object, ...], Piece]]:
    """(índice de la corrida, clave de la marca, barra cortada) de todas las corridas, en orden."""
    return [(index, (piece.designation, piece.shape, tuple((name, round_up(value)) for name, value in piece.dimensions),
                     piece.cut_length, piece.angles), piece)
            for index, run in enumerate(runs) for piece in pieces(run, stock)]


def run_marks(element: str, runs: list[BarRun], stock: float) -> list[tuple[str, ...]]:
    """Las marcas de la cartilla (las de schedule) de cada corrida, para rotular el dibujo (D-126)."""
    numbers: dict[tuple[object, ...], int] = {}
    result: list[list[str]] = [[] for _ in runs]
    for index, key, _ in _keyed(runs, stock):
        mark = f"{element}-{numbers.setdefault(key, len(numbers) + 1):02d}"
        if mark not in result[index]:
            result[index].append(mark)
    return [tuple(marks) for marks in result]


def totals(rows: list[ScheduleRow]) -> dict[str, float]:
    """Peso total por designación, en kg, en el orden en que aparecen."""
    result: dict[str, float] = {}
    for row in rows:
        result[row.piece.designation] = result.get(row.piece.designation, 0.0) + row.mass
    return result
