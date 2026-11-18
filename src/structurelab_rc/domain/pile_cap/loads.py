"""Acción de cada pilote sobre el cabezal en cada caso (D-138) y cuerpos libres de sus secciones (D-143).

Con las cargas de las columnas, el cabezal es rígido y los pilotes, articulados (guía CRSI, cap. 3): la resultante N de
las columnas (con su pedestal y lo que desplazan), los pesos y las sobrecargas y su momento en el plano de la cabeza de
los pilotes se reparten como R_i = N/n + b·dx_i + c·dy_i, con (dx, dy) respecto al centroide del grupo y (b, c) del
equilibrio de momentos Σ R·dx = My y Σ R·dy = −Mx (pseudoinversa si los pilotes están alineados; el momento que el grupo
no resiste se reporta). El cortante de las columnas se reparte por igual. Con las cargas de los pilotes, sus fuerzas y
momentos se toman tal cual, más el peso repartido por igual si sus reacciones no lo incluyen.

Mala ubicación (13.4.1.4, D-138): la excentricidad accidental de magnitud igual a la tolerancia, en la dirección más
desfavorable para cada pilote, cambia su reacción en ±|N|·t·|K⁺·(dx, dy)|. Se aplica solo con las cargas de las columnas
(a la capacidad de los pilotes y a las solicitaciones del cabezal); con las de los pilotes la tolerancia solo cambia los
brazos (decisión del usuario, D-138).

Una sola fuente de la acción de los pilotes y de las columnas en un cuerpo libre (pile_head, column_head, column_action),
de las caras de una columna (column_faces_along) y del lado del cuerpo libre (free_sides: el que tiene menos columnas,
los dos si empatan, D-143), que usan las secciones, el cortante, el punzonamiento y las franjas.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from structurelab_rc.domain.footing.base import BaseResultant
from structurelab_rc.domain.footing.flexure import FaceMoments, Section
from structurelab_rc.domain.footing.loads import uniform_load
from structurelab_rc.domain.pile_cap.outline import beyond, centroid
from structurelab_rc.model.footing import FootingLoad, UnitWeighted
from structurelab_rc.model.pile_cap import CapColumn, PileCap

_SINGULAR = 1e-9


@dataclass(frozen=True)
class PileForces:
    """Acción de cada pilote sobre el cabezal, en el orden de cap.piles: reacción vertical (N, positiva en compresión del
    pilote), fuerza horizontal (Vx, Vy) en N y momento (Mx, My) en N·mm; spread es el cambio de la reacción por la mala
    ubicación (0 si no se aplica)."""

    reactions: tuple[float, ...]
    shears: tuple[tuple[float, float], ...]
    moments: tuple[tuple[float, float], ...]
    spread: tuple[float, ...]


@dataclass(frozen=True)
class CapCase:
    """Un caso: su carga de referencia (nombre, tipo, factores), las fuerzas de los pilotes, la carga de cada columna (None
    si no se conoce: cargas de los pilotes sin la de esa columna, D-143), la fuerza vertical de cada columna para el
    aplastamiento (N; con las cargas de los pilotes y una sola columna sin cargas, la que da el equilibrio), la vertical
    total sobre los pilotes y el momento que el grupo no resiste (N·mm, con las cargas de las columnas y pilotes
    alineados)."""

    load: FootingLoad
    forces: PileForces
    columns: tuple[FootingLoad | None, ...]
    bearing: tuple[float | None, ...]
    total: float
    unresisted: float = 0.0

    @property
    def case(self) -> str:
        return self.load.case

    def reaction(self, index: int, sense: float = 0.0) -> float:
        """La reacción de un pilote con la mala ubicación del lado que pide la revisión: sense = +1 la aumenta (compresión
        desfavorable), −1 la reduce (tracción o momento negativo desfavorables) y 0 no la aplica."""
        return self.forces.reactions[index] + sense * self.forces.spread[index]


def _pinv(sxx: float, sxy: float, syy: float) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float] | None]:
    """Pseudoinversa de la matriz simétrica [[sxx, sxy], [sxy, syy]] y la dirección que no resiste (None si es
    invertible)."""
    det = sxx * syy - sxy**2
    scale = max(sxx, syy, 1.0)
    if abs(det) > _SINGULAR * scale**2:
        return (syy / det, -sxy / det), (-sxy / det, sxx / det), None
    trace = sxx + syy
    if trace <= _SINGULAR * scale:
        return (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)
    # Rango 1: K = trace·u·uᵀ con u el eje de los pilotes; K⁺ = u·uᵀ/trace y la dirección normal no resiste.
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(angle), math.sin(angle)
    return (ux * ux / trace, ux * uy / trace), (ux * uy / trace, uy * uy / trace), (-uy, ux)


@dataclass(frozen=True)
class _Group:
    """Centroide del grupo, coordenadas relativas y pseudoinversa de su matriz de segundos momentos."""

    centre: tuple[float, float]
    offsets: tuple[tuple[float, float], ...]
    inverse: tuple[tuple[float, float], tuple[float, float]]
    weak: tuple[float, float] | None


def group_centre(cap: PileCap) -> tuple[float, float]:
    """Centroide del grupo de pilotes, en mm."""
    n = len(cap.piles)
    return sum(pile.x for pile in cap.piles) / n, sum(pile.y for pile in cap.piles) / n


def _group(cap: PileCap) -> _Group:
    xc, yc = group_centre(cap)
    offsets = tuple((pile.x - xc, pile.y - yc) for pile in cap.piles)
    sxx = sum(dx * dx for dx, _ in offsets)
    syy = sum(dy * dy for _, dy in offsets)
    sxy = sum(dx * dy for dx, dy in offsets)
    first, second, weak = _pinv(sxx, sxy, syy)
    return _Group((xc, yc), offsets, (first, second), weak)


def _spread(group: _Group, total: float, tolerance: float) -> tuple[float, ...]:
    """|N|·t·|K⁺·(dx, dy)| de cada pilote: el mayor cambio de su reacción con una excentricidad accidental de magnitud t."""
    (a, b), (c, d) = group.inverse
    return tuple(abs(total) * tolerance * math.hypot(a * dx + b * dy, c * dx + d * dy) for dx, dy in group.offsets)


def column_vertical(cap: PileCap, weights: UnitWeighted, column: CapColumn, load: FootingLoad) -> float:
    """Fuerza vertical hacia abajo en el eje de una columna, en N: P más su pedestal, menos el relleno y las sobrecargas
    que la columna desplaza (la carga uniforme los cuenta en toda la base)."""
    return load.p + _at_column(cap, weights, column, load)


def _at_column(cap: PileCap, weights: UnitWeighted, column: CapColumn, load: FootingLoad) -> float:
    """El pedestal menos el relleno y las sobrecargas que desplaza la columna, con los factores del caso, en N."""
    area = column.area
    dead_per_area = weights.unit_weight_fill * cap.fill_height + cap.surcharge_dead
    at_column = load.dead_factor * (weights.unit_weight_concrete * area * cap.pedestal_height - dead_per_area * area)
    at_column -= load.live_factor * cap.surcharge_live * area
    return at_column


def cap_resultant(cap: PileCap, weights: UnitWeighted, loads: tuple[FootingLoad, ...]) -> BaseResultant:
    """Resultante en el centroide de la base de las cargas de todas las columnas, en su eje a la altura h + pedestal, con
    su pedestal y el área que ocupan, y del cabezal, el relleno y las sobrecargas en el centroide; los factores son los del
    caso (iguales en todas las columnas). Con una columna, la de domain/footing/base.py."""
    case = loads[0]
    height = cap.h + cap.pedestal_height
    footing_weight = weights.unit_weight_concrete * cap.area * cap.h
    dead_per_area = weights.unit_weight_fill * cap.fill_height + cap.surcharge_dead
    centred = case.dead_factor * (footing_weight + dead_per_area * cap.area) + case.live_factor * cap.surcharge_live * cap.area
    p = mx = my = at = 0.0
    for column, load in zip(cap.columns, loads, strict=True):
        at_column = _at_column(cap, weights, column, load)
        vertical = load.p + at_column
        at += at_column
        p += load.p
        mx += load.mx - vertical * column.offset_y - height * load.vy
        my += load.my + vertical * column.offset_x + height * load.vx
    return BaseResultant(p + centred + at, mx, my, centred + at)


def _from_columns(cap: PileCap, weights: UnitWeighted, loads: tuple[FootingLoad, ...], group: _Group) -> CapCase:
    resultant = cap_resultant(cap, weights, loads)
    embedment = cap.pile.embedment
    vx, vy = sum(load.vx for load in loads), sum(load.vy for load in loads)
    # Momentos en el plano de la cabeza de los pilotes y respecto al centroide del grupo (N hacia abajo en el origen).
    mx = resultant.mx + embedment * vy + group.centre[1] * resultant.n
    my = resultant.my - embedment * vx - group.centre[0] * resultant.n
    if cap.clipped_corners:  # D-141: el peso del cabezal, el relleno y las sobrecargas actúa en el centroide del contorno
        area, xc, yc = centroid(cap)
        spread_weight = uniform_load(cap, weights, loads[0]) * area
        mx -= spread_weight * yc
        my += spread_weight * xc
    (a, b), (c, d) = group.inverse
    slope_x, slope_y = a * my + b * -mx, c * my + d * -mx
    n = len(cap.piles)
    reactions = tuple(resultant.n / n + slope_x * dx + slope_y * dy for dx, dy in group.offsets)
    unresisted = 0.0 if group.weak is None else abs(group.weak[0] * my + group.weak[1] * -mx)
    forces = PileForces(reactions, ((vx / n, vy / n),) * n, ((0.0, 0.0),) * n, _spread(group, resultant.n, cap.mislocation))
    return CapCase(loads[0], forces, loads, tuple(load.p for load in loads), resultant.n, unresisted)


def _weight(cap: PileCap, weights: UnitWeighted, load: FootingLoad) -> float:
    """Peso del cabezal, los pedestales, el relleno y las sobrecargas con los factores del caso, en N."""
    footing, pedestal, fill = cap.weights(weights)
    dead, live = cap.surcharges()
    return load.dead_factor * (footing + pedestal + fill + dead) + load.live_factor * live


def _from_piles(cap: PileCap, weights: UnitWeighted,
                given: tuple[FootingLoad, tuple[FootingLoad, ...], tuple[FootingLoad | None, ...]]) -> CapCase:
    load, piles, columns = given
    weight = _weight(cap, weights, load)
    share = 0.0 if cap.reactions_include_weight else weight / len(piles)
    reactions = tuple(pile.p + share for pile in piles)
    total = sum(reactions)
    forces = PileForces(reactions, tuple((pile.vx, pile.vy) for pile in piles), tuple((pile.mx, pile.my) for pile in piles),
                        (0.0,) * len(piles))
    # Con una sola columna sin cargas, su fuerza sale del equilibrio (D-138); con varias, no se reparte (D-143).
    bearing = tuple(None if item is None else item.p for item in columns)
    if len(columns) == 1 and columns[0] is None:
        bearing = (total - weight,)
    return CapCase(load, forces, columns, bearing, total)


def cap_cases(cap: PileCap, weights: UnitWeighted) -> list[CapCase]:
    """Cada caso, de servicio y mayorado, con la acción de cada pilote sobre el cabezal."""
    group = _group(cap)
    cases = []
    for load, piles, columns in cap.case_loads():
        if cap.from_piles:
            cases.append(_from_piles(cap, weights, (load, piles, columns)))
        else:
            cases.append(_from_columns(cap, weights, tuple(item for item in columns if item is not None), group))
    return cases


def spread_on_cap(cap: PileCap) -> bool:
    """Si la mala ubicación cambia también las reacciones: solo con las cargas de las columnas (D-138)."""
    return not cap.from_piles


AXES = {"x": 0, "y": 1}


SCAN_STEP = 50.0  # mm: separación de las secciones de flexión entre columnas y en las franjas (D-143, D-145)
_ON_PLANE = 1e-6  # mm


@dataclass(frozen=True)
class FactoredCap:
    """Un caso mayorado del cabezal: el caso, la carga uniforme hacia abajo (N/mm²), el sentido de la mala ubicación en
    las reacciones (+1, −1 o 0, ver CapCase.reaction), la fracción de la reacción que produce cortante en una sección
    (la del perfil: ACI 13.4.6.7, NSR-10 C.15.5.4) y la fuerza vertical de cada columna en su eje (column_vertical; None
    si su carga no se conoce)."""

    cap: PileCap
    case: CapCase
    load: float
    sense: float
    share: Callable[[float, float], float]
    verticals: tuple[float | None, ...]

    def reaction(self, index: int) -> float:
        return self.case.reaction(index, self.sense)

    def pile_head(self, index: int) -> tuple[float, float]:
        """La acción de la cabeza de un pilote respecto al eje de la sección (a media altura): (alrededor de X,
        alrededor de Y) = (Mx − (e − h/2)·Vy, −(My + (e − h/2)·Vx)), en N·mm."""
        cap = self.cap
        lever = cap.pile.embedment - cap.h / 2
        (vx, vy), (mx, my) = self.case.forces.shears[index], self.case.forces.moments[index]
        return mx - lever * vy, -(my + lever * vx)

    def column_head(self, index: int) -> tuple[float, float, float] | None:
        """La acción de una columna sobre el cabezal (D-143): (fuerza vertical hacia abajo, momento alrededor de X,
        alrededor de Y) con su base a h/2 + pedestal del eje de la sección; None si su carga no se conoce."""
        vertical, load = self.verticals[index], self.case.columns[index]
        if vertical is None or load is None:
            return None
        top = self.cap.h / 2 + self.cap.pedestal_height
        return vertical, load.mx - top * load.vy, -(load.my + top * load.vx)

    def column_action(self, index: int, axis: int, plane: float, outward: float) -> tuple[float, float] | None:
        """(momento respecto al plano, cortante) de una columna más allá del plano normal a x (axis = 0) o a y."""
        head = self.column_head(index)
        if head is None:
            return None
        vertical, about_x, about_y = head
        column = self.cap.columns[index]
        arm = outward * ((column.offset_x, column.offset_y)[axis] - plane)
        return -vertical * arm + outward * (about_y if axis == 0 else about_x), -vertical

    def columns_beyond(self, axis: int, plane: float, outward: float) -> list[int]:
        """Las columnas cuyo eje queda más allá del plano, del lado outward."""
        return [index for index, column in enumerate(self.cap.columns)
                if outward * ((column.offset_x, column.offset_y)[axis] - plane) > 0]

    def missing(self, axis: int, plane: float, outward: float) -> list[str]:
        """Las columnas más allá del plano sin carga conocida en el caso (cargas de los pilotes, D-143)."""
        return [self.cap.columns[index].id for index in self.columns_beyond(axis, plane, outward) if self.verticals[index] is None]

    def beyond(self, axis: int, plane: float, outward: float) -> tuple[float, float, float]:
        """Más allá de un plano vertical normal a x (axis = 0) o a y (axis = 1), del lado outward (+1 o −1): el cortante
        con la reacción interpolada, el cortante con la reacción completa y el momento respecto al plano (positivo
        tracciona la cara inferior), en N y N·mm. Un pilote cuenta si, mal ubicado del lado desfavorable (su distancia más
        la tolerancia), queda más allá: con su reacción completa, su brazo y la acción de su cabeza (su momento y el de su
        fuerza horizontal respecto al eje de la sección). Las columnas más allá (D-143), hacia abajo con su fuerza vertical
        y la acción de su base a h/2 + pedestal del eje de la sección; las de carga desconocida no cuentan (ver missing).
        El peso del cabezal, hacia abajo."""
        cap = self.cap
        tolerance, size = cap.mislocation, cap.pile.size
        shear = full = moment = 0.0
        for index, pile in enumerate(cap.piles):
            reaction = self.reaction(index)
            arm = outward * ((pile.x, pile.y)[axis] - plane) + tolerance
            shear += self.share(arm, size) * reaction
            if arm <= 0:
                continue
            full += reaction
            moment += reaction * arm
            about_x, about_y = self.pile_head(index)
            moment += outward * (about_y if axis == 0 else about_x)
        for index in self.columns_beyond(axis, plane, outward):
            action = self.column_action(index, axis, plane, outward)
            if action is None:
                continue
            moment += action[0]
            shear += action[1]
            full += action[1]
        if cap.clipped_corners:  # D-141: el peso sobre la parte del contorno más allá del plano
            area, xc, yc = beyond(cap, axis, plane, outward)
            weight = self.load * area
            return shear - weight, full - weight, moment - weight * outward * ((xc, yc)[axis] - plane)
        half, width = (cap.lx / 2, cap.ly) if axis == 0 else (cap.ly / 2, cap.lx)
        length = max(half - outward * plane, 0.0)
        weight = self.load * width * length
        return shear - weight, full - weight, moment - weight * length / 2

    def face_moments(self) -> FaceMoments:
        """Momento en las secciones de flexión de cada dirección (section_planes): las caras de las columnas (ACI 13.2.6.6 y
        13.4.6.4, NSR-10 C.15.4.1) y, con varias columnas, las secciones entre ellas (D-143). Un lado cuya columna no
        tiene carga conocida no se calcula."""
        moments: dict[str, tuple[float, ...]] = {}
        sections: dict[str, tuple[Section, ...]] = {}
        for direction, axis in AXES.items():
            values, found = [], []
            for section, outwards in section_planes(self.cap, direction):
                for outward in outwards:
                    if self.missing(axis, section.plane, outward):
                        continue
                    values.append(self.beyond(axis, section.plane, outward)[2])
                    found.append(section)
            moments[direction], sections[direction] = tuple(values), tuple(found)
        return FaceMoments(self.case.case, moments, sections)

    def unresolved(self) -> list[str]:
        """Las secciones de flexión sin ningún lado calculable (cargas de columnas desconocidas, D-143)."""
        found = []
        for direction, axis in AXES.items():
            for section, outwards in section_planes(self.cap, direction):
                if all(self.missing(axis, section.plane, outward) for outward in outwards):
                    found.append(section.note)
        return found


def column_faces_along(column: CapColumn, axis: int) -> tuple[tuple[float, float, str], tuple[float, float, str]]:
    """Las dos caras de una columna normales a x (axis = 0) o a y (axis = 1): (plano, hacia afuera, rótulo)."""
    centre, size = (column.offset_x, column.cx) if axis == 0 else (column.offset_y, column.cy)
    plus, minus = ("+X", "-X") if axis == 0 else ("+Y", "-Y")
    return (centre + size / 2, 1.0, plus), (centre - size / 2, -1.0, minus)


def section_planes(cap: PileCap, direction: str) -> list[tuple[Section, tuple[float, ...]]]:
    """Las secciones de flexión normales a la dirección de las barras, cada una con los lados de su cuerpo libre: con una
    columna, sus dos caras, hacia afuera (D-138); con varias (D-143), las caras de cada columna y secciones cada 50 mm
    fuera de las columnas, con el lado que tiene menos columnas (los dos si empatan)."""
    axis = AXES[direction]
    name = "x" if axis == 0 else "y"
    columns = cap.columns
    if len(columns) == 1:
        return [(Section(plane, label, f"Cara {label} de la columna"), (outward,))
                for plane, outward, label in column_faces_along(columns[0], axis)]
    spans = [((c.offset_x, c.cx) if axis == 0 else (c.offset_y, c.cy)) for c in columns]
    planes = [Section(plane, f"{label} {column.id}", f"Cara {label} de la columna {column.id}")
              for column in columns for plane, _, label in column_faces_along(column, axis)]
    half = (cap.lx if axis == 0 else cap.ly) / 2
    count = int(2 * half // SCAN_STEP)
    for step in range(1, count + 1):
        plane = -half + step * SCAN_STEP
        if plane >= half - _ON_PLANE:
            break
        if any(centre - size / 2 - _ON_PLANE <= plane <= centre + size / 2 + _ON_PLANE for centre, size in spans):
            continue
        planes.append(Section(plane, f"{name} = {plane:g}", f"Seccion {name} = {plane:.0f} mm"))
    return [(section, free_sides(cap, axis, section.plane)) for section in planes]


def free_sides(cap: PileCap, axis: int, plane: float, members: tuple[int, ...] | None = None) -> tuple[float, ...]:
    """Los lados del cuerpo libre de un plano normal a x (axis = 0) o a y (axis = 1): el que tiene menos columnas (de
    members, todas si es None) más allá (los dos si empatan, D-143); con una columna, el que no la tiene."""
    columns = cap.columns if members is None else tuple(cap.columns[index] for index in members)
    counts = {outward: sum(1 for column in columns if outward * ((column.offset_x, column.offset_y)[axis] - plane) > 0)
              for outward in (1.0, -1.0)}
    fewest = min(counts.values())
    return tuple(outward for outward in (1.0, -1.0) if counts[outward] == fewest)


@dataclass(frozen=True)
class CapAnalysis:
    """El análisis de un cabezal, calculado una vez (D-138): todos los casos con las reacciones de los pilotes, los casos
    mayorados con la mala ubicación del lado de la compresión (cortante y punzonamiento) y los momentos de sus secciones
    de cada caso mayorado; con las cargas de las columnas, cada caso da dos, con +ΔR (malla inferior) y −ΔR (momento
    negativo). unresolved: (caso, sección) sin ningún lado calculable (D-143)."""

    cases: tuple[CapCase, ...]
    factored: tuple[FactoredCap, ...]
    moments: tuple[FaceMoments, ...]
    unresolved: tuple[tuple[str, str], ...] = ()


def analyze(cap: PileCap, weights: UnitWeighted, share: Callable[[float, float], float]) -> CapAnalysis:
    """Las reacciones, los casos mayorados y sus momentos de sección; share es la interpolación del perfil."""
    cases = tuple(cap_cases(cap, weights))
    spread = spread_on_cap(cap)
    factored = []
    for case in cases:
        if case.load.kind != "factored":
            continue
        verticals = tuple(None if load is None else column_vertical(cap, weights, column, load)
                          for column, load in zip(cap.columns, case.columns, strict=True))
        factored.append(FactoredCap(cap, case, uniform_load(cap, weights, case.load), 1.0 if spread else 0.0, share, verticals))
    unresolved = tuple((item.case.case, note) for item in factored for note in item.unresolved())
    if not spread:
        return CapAnalysis(cases, tuple(factored), tuple(item.face_moments() for item in factored), unresolved)
    moments = []
    for item in factored:
        moments.append(replace(item.face_moments(), case=f"{item.case.case} (+ΔR)"))
        moments.append(replace(replace(item, sense=-1.0).face_moments(), case=f"{item.case.case} (−ΔR)"))
    return CapAnalysis(cases, tuple(factored), tuple(moments), unresolved)
