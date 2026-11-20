"""Cortante y punzonamiento del cabezal con los casos mayorados (D-138), como domain/footing/shear.py.

Por secciones, con la reacción interpolada de ACI 13.4.6.7 (NSR-10 C.15.5.4): una dirección a d de las caras de cada
columna (ACI 13.4.6.5(a), 22.5 y 13.4.6.8(a); NSR-10 C.11.11) y dos direcciones a d/2 de cada columna y del perímetro
común de las que se traslapan (ACI 13.4.6.5(b) y 22.6; NSR-10 C.11.11.2), con la acción de la cabeza de los pilotes que
cuentan. Con pilotes dentro de d o d/2 de una columna, los límites de la guía CRSI en su cara (estados límite 5 y 6, y 4).
El punzonamiento de cada pilote, aislado (P1) o de esquina (P3), de dos pilotes (P2) y de grupos, y el cortante de esquina
(P4). La mala ubicación cuenta del lado desfavorable: el pilote se acerca a la sección (o pasa más allá de la cara) en la
tolerancia y, con las cargas de las columnas, su reacción sube ΔR. Con varias columnas, cada cuerpo libre es el del lado
con menos columnas (los dos si empatan, gobierna el mayor; D-143, D-145).
"""

import math
from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.pile_cap.loads import AXES, CapAnalysis, FactoredCap, column_faces_along, free_sides
from structurelab_rc.domain.pile_cap.outline import centroid, parallel_chord, section_row
from structurelab_rc.domain.pile_cap.outline import inside as region_inside
from structurelab_rc.domain.shear_strength import TransferredLoad, TwoWayShear, concrete_lambda, two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, incomplete
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter, polygon_perimeter
from structurelab_rc.model.pile_cap import CapColumn, PileCap

ONE_WAY = "Cortante en una direccion"
FACE_ONE_WAY = "Cortante en la cara de la columna"
FACE_TWO_WAY = "Cortante en la cara de la columna (dos direcciones)"
PUNCHING = "Punzonamiento"
PILE_PUNCHING = "Punzonamiento del pilote"
PAIR_PUNCHING = "Punzonamiento de dos pilotes"
GROUP_PUNCHING = "Punzonamiento de un grupo de pilotes"
CORNER_ONE_WAY = "Cortante de esquina del pilote"
SHEAR = "Cabezal: cortante"
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_NEGLIGIBLE_FORCE = 1.0  # N
_CORNER_SIDES = 2  # una esquina pierde dos lados del perímetro


@dataclass(frozen=True)
class CapStrength:
    """Lo común a las resistencias a cortante del cabezal: λ, si los pilotes están cerca (ACI 13.4.6.8), λs de dos
    direcciones y la d promedio de la malla inferior."""

    lam: float
    closely: bool
    lam_s: float
    depth: float


def _column_name(cap: PileCap, column: CapColumn) -> str:
    return "la columna" if len(cap.columns) == 1 else f"la columna {column.id}"


def _inside_column(cap: PileCap, axis: int, plane: float) -> bool:
    """Si el plano corta alguna columna (sus caras no cuentan)."""
    for column in cap.columns:
        centre, size = (column.offset_x, column.cx) if axis == 0 else (column.offset_y, column.cy)
        if centre - size / 2 < plane < centre + size / 2:
            return True
    return False


def _incomplete(name: str, item: FactoredCap, missing: list[str], clause: str, note: str) -> Check:
    error = incomplete(f"Faltan las cargas de las columnas {', '.join(sorted(set(missing)))} en el caso; no se reparten (D-143)",
                       member=item.cap.id, case=item.case.case)
    return Check(name, Status.INCOMPLETE, (error,), clause, member=item.cap.id, case=item.case.case, note=note)


def _one_way(basis: Basis, item: FactoredCap, row: BarRow, strength: CapStrength) -> list[Check]:
    """Cortante a d de las caras de cada columna con la reacción interpolada; gobierna la sección de mayor razón. La
    sección que cae fuera del cabezal o corta otra columna no se revisa; su cuerpo libre es el lado con menos columnas
    (D-143)."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    axis = AXES[row.direction]
    half = cap.lx / 2 if axis == 0 else cap.ly / 2
    phi = profile.shear.strength_reduction()
    clause = profile.pile_cap.clauses()["one_way_shear"]
    name = f"{ONE_WAY} (barras {row.direction})"
    full_row = row
    worst: tuple[float, float, float, str, float, float] | None = None
    missing: list[str] = []
    for column in cap.columns:
        for face, outward_face, label in column_faces_along(column, AXES[row.direction]):
            plane = face + outward_face * row.depth
            if abs(plane) >= half or _inside_column(cap, axis, plane):
                continue
            section = section_row(cap, full_row, plane) if cap.clipped_corners else full_row  # D-141: ancho real
            if section.width <= 0:  # la sección no corta el contorno
                continue
            rho = section.area / (section.width * section.depth)
            for outward in free_sides(cap, axis, plane):
                lacking = item.missing(axis, plane, outward)
                if lacking:
                    missing += lacking
                    continue
                shear, _, moment = item.beyond(axis, plane, outward)
                vc = profile.pile_cap.one_way_concrete_shear(fc=materials.fc, lam=strength.lam, bw=section.width, d=section.depth,
                                                             h=cap.h, rho_w=rho, vu=abs(shear), mu=abs(moment),
                                                             closely_spaced=strength.closely)
                demand, capacity = abs(shear), phi * vc
                where = f"{label} de {_column_name(cap, column)}"
                if worst is None or demand / capacity > worst[0]:
                    worst = (demand / capacity, demand, capacity, where, section.width, rho)
    if worst is None:
        return [_incomplete(name, item, missing, clause, "Secciones a d de las caras")] if missing else []
    _, demand, capacity, where, width, rho = worst
    return [Check(name, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=cap.id, case=item.case.case,
                  demand=demand, capacity=capacity, unit="N",
                  values=(("phi", phi), ("Vc", capacity / phi), ("bw", width), ("d", row.depth), ("rho w", rho),
                          ("lambda", strength.lam), ("fc", materials.fc)),
                  note=f"Seccion a d de la cara {where}, reacciones interpoladas")]


def _face_one_way(basis: Basis, item: FactoredCap, row: BarRow, strength: CapStrength) -> list[Check]:
    """Guía CRSI, estados límite 5 y 6: en cada cara de cada columna con algún pilote a menos de d, cortante a todo el
    ancho con la reacción completa de los pilotes que, mal ubicados, quedan más allá de la cara (y las columnas de ese
    lado, D-143); w es la distancia del más cercano más la tolerancia."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    axis = AXES[row.direction]
    phi = profile.shear.strength_reduction()
    clause = profile.pile_cap.clauses()["column_face_one_way"]
    name = f"{FACE_ONE_WAY} (barras {row.direction})"
    checks = []
    for column in cap.columns:
        for plane, outward, label in column_faces_along(column, AXES[row.direction]):
            distances = [outward * ((pile.x, pile.y)[axis] - plane) for pile in cap.piles]
            near = [distance for distance in distances if distance + cap.mislocation > 0]
            if not near or min(near) >= row.depth:
                continue
            note = f"Cara {label} de {_column_name(cap, column)}"
            # La regla de cuerpo libre de D-143 (lado con menos columnas, el mayor si empatan; D-145).
            sides = [side for side in free_sides(cap, axis, plane) if not item.missing(axis, plane, side)]
            if not sides:
                lacking = [name for side in free_sides(cap, axis, plane) for name in item.missing(axis, plane, side)]
                checks.append(_incomplete(name, item, lacking, clause, note))
                continue
            w = _clear_distance(near) + cap.mislocation
            section = section_row(cap, row, plane) if cap.clipped_corners else row  # D-141: el ancho real en la cara
            _, shear, moment = max((item.beyond(axis, plane, side) for side in sides), key=lambda value: value[1])
            stress = profile.pile_cap.column_face_one_way_stress(fc=materials.fc, lam=strength.lam, d=row.depth, w=w,
                                                                 vu=max(shear, 0.0), mu=max(moment, 0.0))
            capacity = phi * stress * section.width * row.depth
            checks.append(Check(name, Status.PASS if shear <= capacity else Status.FAIL, clause=clause, member=cap.id,
                                case=item.case.case, demand=max(shear, 0.0), capacity=capacity, unit="N",
                                values=(("phi", phi), ("vc", stress), ("w", w), ("b", section.width), ("d", row.depth),
                                        ("Mu", moment)), note=note))
    return checks


def _clear_distance(distances: list[float]) -> float:
    """w de la guía CRSI sin la tolerancia: la distancia de la cara al pilote más cercano que ya está afuera (0 si todos
    los que cuentan están, mal ubicados, apenas dentro); así la tolerancia solo puede aumentar w, del lado de la menor
    capacidad, mientras la demanda cuenta los pilotes que mal ubicados quedan más allá."""
    beyond = [distance for distance in distances if distance > 0]
    return min(beyond) if beyond else 0.0


def _outside(cap: PileCap, column: CapColumn, index: int) -> float:
    """Distancia del centro de un pilote al contorno de una columna (≤ 0 si queda bajo ella), en mm."""
    pile = cap.piles[index]
    return max(abs(pile.x - column.offset_x) - column.cx / 2, abs(pile.y - column.offset_y) - column.cy / 2)


def _face_two_way(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Guía CRSI, estado límite 4: con algún pilote a menos de d/2 de una columna, cortante en el perímetro de su cara,
    bs = 2(cx + cy), c = (cx + cy)/2 (perímetro real, decisión del usuario, D-138). La fuerza que lo atraviesa es la de
    los pilotes de afuera menos el peso de afuera (y las otras columnas, D-143) o la de la columna más el peso bajo ella
    menos los pilotes de adentro: el lado con menos columnas, el mayor si empatan."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    tolerance, depth = cap.mislocation, strength.depth
    clause = profile.pile_cap.clauses()["column_face_two_way"]
    checks = []
    for number, column in enumerate(cap.columns):
        outside = [(distance, index) for index in range(len(cap.piles)) if (distance := _outside(cap, column, index)) + tolerance > 0]
        if not outside or min(outside)[0] >= depth / 2:
            continue
        note = f"Pilote {cap.piles[min(outside)[1]].id} a w de la cara" + ("" if len(cap.columns) == 1 else f" de la columna {column.id}")
        counted = {index for _, index in outside}
        others = [index for index in range(len(cap.columns)) if index != number]
        sides: list[float | None] = []
        if len(others) <= 1:  # afuera: los pilotes de afuera, menos el peso y las otras columnas
            if any(item.verticals[index] is None for index in others):
                sides.append(None)
            else:
                sides.append(sum(item.reaction(index) for index in counted) - item.load * (cap.area - column.area)
                             - sum(item.verticals[index] or 0.0 for index in others))
        if others:  # adentro: la columna más el peso bajo ella, menos los pilotes de adentro
            vertical = item.verticals[number]
            sides.append(None if vertical is None else vertical + item.load * column.area
                         - sum(item.reaction(index) for index in range(len(cap.piles)) if index not in counted))
        known = [value for value in sides if value is not None]
        if not known:
            checks.append(_incomplete(FACE_TWO_WAY, item, [column.id, *(cap.columns[i].id for i in others)], clause, note))
            continue
        shear = max(known)
        w = _clear_distance([distance for distance, _ in outside]) + tolerance
        side, perimeter = (column.cx + column.cy) / 2, 2 * (column.cx + column.cy)
        stress = profile.pile_cap.column_face_two_way_stress(fc=materials.fc, lam=strength.lam, d=depth, w=w, c=side)
        phi = profile.shear.strength_reduction()
        capacity = phi * stress * perimeter * depth
        checks.append(Check(FACE_TWO_WAY, Status.PASS if shear <= capacity else Status.FAIL, clause=clause, member=cap.id,
                            case=item.case.case, demand=max(shear, 0.0), capacity=capacity, unit="N",
                            values=(("phi", phi), ("vc", stress), ("w", w), ("bs", perimeter), ("c columna", side), ("d", depth)),
                            note=note))
    return checks


def closely_spaced(basis: Basis, cap: PileCap) -> bool:
    """Si cada pilote tiene otro a la separación límite del perfil o menos (ACI 13.4.6.8; NSR-10 no la tiene)."""
    limit = basis.profile.pile_cap.closely_spaced_limit()
    if limit is None or len(cap.piles) == 1:
        return False
    nearest = [min(math.hypot(a.x - b.x, a.y - b.y) for b in cap.piles if b is not a) for a in cap.piles]
    return max(nearest) <= limit * cap.pile.size


@dataclass(frozen=True)
class _TwoWay:
    """Una revisión de dos direcciones: su nombre, la fuerza que atraviesa el perímetro, su numeral y su nota."""

    name: str
    force: float
    clause: str
    note: str


def _two_way_check(item: FactoredCap, result: TwoWayShear | StructuredError, given: _TwoWay) -> Check:
    cap, case = item.cap, item.case.case
    if isinstance(result, StructuredError):
        return Check(given.name, Status.BLOCKED, (result,), given.clause, member=cap.id, case=case, note=given.note)
    xc, yc = result.perimeter.centroid
    values = (("Vu", given.force), ("b0", result.perimeter.length), ("d", result.perimeter.depth), ("alpha s", result.alpha_s),
              ("vuv", result.vuv), ("xc", xc), ("yc", yc))
    return Check(given.name, Status.PASS if result.vu <= result.phi_vc else Status.FAIL, clause=given.clause, member=cap.id, case=case,
                 demand=result.vu, capacity=result.phi_vc, unit="MPa", values=values, note=given.note)


@dataclass(frozen=True)
class _Loaded:
    """Un área cargada de punzonamiento: una columna o, si sus perímetros se traslapan, la caja que contiene varias
    (perímetro común, D-143): su centro, su tamaño, las columnas que contiene y la nota de sus verificaciones."""

    centre: tuple[float, float]
    size: tuple[float, float]
    columns: tuple[int, ...]
    note: str


def _loaded_areas(cap: PileCap, depth: float) -> list[_Loaded]:
    """Cada columna y, con varias, cada grupo conectado de columnas cuyos perímetros a d/2 se traslapan, con la caja que
    las contiene (ACI R13.2.7.2, NSR-10 CR15.5.2, como D-086 en la zapata combinada)."""
    columns = cap.columns
    if len(columns) == 1:
        column = columns[0]
        return [_Loaded((column.offset_x, column.offset_y), (column.cx, column.cy), (0,), "Columna, reacciones interpoladas")]
    areas = [_Loaded((c.offset_x, c.offset_y), (c.cx, c.cy), (i,), f"Columna {c.id}, reacciones interpoladas")
             for i, c in enumerate(columns)]
    count = len(columns)

    def overlap(a: CapColumn, b: CapColumn) -> bool:
        return (abs(a.offset_x - b.offset_x) < (a.cx + b.cx) / 2 + depth) and (abs(a.offset_y - b.offset_y) < (a.cy + b.cy) / 2 + depth)

    seen: set[int] = set()
    for first in range(count):
        if first in seen:
            continue
        group, frontier = {first}, [first]
        while frontier:
            current = frontier.pop()
            for other in range(count):
                if other not in group and overlap(columns[current], columns[other]):
                    group.add(other)
                    frontier.append(other)
        seen |= group
        if len(group) < 2:  # noqa: PLR2004 - un perímetro común
            continue
        members = tuple(sorted(group))
        left = min(columns[i].offset_x - columns[i].cx / 2 for i in members)
        right = max(columns[i].offset_x + columns[i].cx / 2 for i in members)
        low = min(columns[i].offset_y - columns[i].cy / 2 for i in members)
        high = max(columns[i].offset_y + columns[i].cy / 2 for i in members)
        names = ", ".join(columns[i].id for i in members)
        areas.append(_Loaded(((left + right) / 2, (low + high) / 2), (right - left, high - low), members,
                             f"Columnas {names} (perimetro comun), reacciones interpoladas"))
    return areas


_Sums = list[float]  # [fuerza, momento en x, momento en y] respecto al centroide del perímetro


def _add_piles(item: FactoredCap, area: _Loaded, depth: float, given: tuple[_Sums, tuple[float, float], bool]) -> None:
    """Suma los pilotes con la fracción de su reacción que produce cortante en el perímetro (outside) o el resto."""
    sums, (xc, yc), outside = given
    cap = item.cap
    (cx, cy), (sx, sy) = area.centre, area.size
    half_x, half_y = (sx + depth) / 2, (sy + depth) / 2
    for index, pile in enumerate(cap.piles):
        offset = max(abs(pile.x - cx) - half_x, abs(pile.y - cy) - half_y) + cap.mislocation
        portion = item.share(offset, cap.pile.size)
        portion = portion if outside else 1.0 - portion
        if portion <= 0:
            continue
        reaction = portion * item.reaction(index)
        about_x, about_y = item.pile_head(index)
        sums[0] += reaction
        sums[1] += reaction * (pile.x - xc) + portion * about_y
        sums[2] += reaction * (pile.y - yc) + portion * about_x


def _add_columns(item: FactoredCap, indices: list[int], sums: _Sums, centre: tuple[float, float]) -> list[str]:
    """Resta las columnas (hacia abajo, con la acción de su base); devuelve las que no tienen carga (vacía si todas)."""
    cap, (xc, yc) = item.cap, centre
    missing = [cap.columns[index].id for index in indices if item.column_head(index) is None]
    if missing:
        return missing
    for index in indices:
        head = item.column_head(index)
        assert head is not None
        vertical, about_x, about_y = head
        column = cap.columns[index]
        sums[0] -= vertical
        sums[1] += -vertical * (column.offset_x - xc) + about_y
        sums[2] += -vertical * (column.offset_y - yc) + about_x
    return []


def _transferred(item: FactoredCap, area: _Loaded, perimeter: Perimeter, depth: float) -> tuple[list[TransferredLoad | None], list[str]]:
    """La carga que atraviesa el perímetro, desde el lado con menos columnas (los dos si empatan, D-143): afuera, los
    pilotes con la fracción de su reacción que produce cortante, el peso de afuera y las columnas de afuera; adentro, las
    columnas del área, el peso de adentro y el resto de las reacciones, con el signo cambiado. Momentos respecto al
    centroide del perímetro; None si falta la carga de alguna columna del lado."""
    cap = item.cap
    (cx, cy), (sx, sy) = area.centre, area.size
    half_x, half_y = (sx + depth) / 2, (sy + depth) / 2
    xc, yc = perimeter.centroid
    (x0, y0), (x1, y1) = perimeter.region
    if cap.clipped_corners:
        total, total_x, total_y = centroid(cap)
        inside, inside_x, inside_y = region_inside(cap, ((cx - half_x, cy - half_y), (cx + half_x, cy + half_y)))
    else:
        total, total_x, total_y = cap.area, 0.0, 0.0
        inside, inside_x, inside_y = (x1 - x0) * (y1 - y0), (x0 + x1) / 2, (y0 + y1) / 2
    within = list(area.columns)
    outer = [index for index in range(len(cap.columns)) if index not in within]
    results: list[TransferredLoad | None] = []
    lacking: list[str] = []
    if len(outer) <= len(within):  # afuera
        force = -item.load * (total - inside)  # el peso fuera del área crítica
        sums = [force, -item.load * (total * total_x - inside * inside_x) - xc * force,
                -item.load * (total * total_y - inside * inside_y) - yc * force]
        _add_piles(item, area, depth, (sums, (xc, yc), True))
        missing = _add_columns(item, outer, sums, (xc, yc))
        lacking += missing
        results.append(None if missing else TransferredLoad(sums[0], sums[1], sums[2]))
    if len(within) <= len(outer):  # adentro, con el signo cambiado
        sums = [-item.load * inside, -item.load * inside * (inside_x - xc), -item.load * inside * (inside_y - yc)]
        _add_piles(item, area, depth, (sums, (xc, yc), False))
        missing = _add_columns(item, within, sums, (xc, yc))
        lacking += missing
        results.append(None if missing else TransferredLoad(-sums[0], -sums[1], -sums[2]))
    return results, lacking


def _column_punching(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Dos direcciones a d/2 de cada columna (y del perímetro común de las que se traslapan, D-143) con la reacción
    interpolada y la acción de la cabeza de los pilotes que cuentan; los momentos respecto al centroide del perímetro.
    Gobierna el lado de mayor razón si se revisan los dos."""
    cap, depth = item.cap, strength.depth
    clause = basis.profile.pile_cap.clauses()["punching"]
    bounds = ((-cap.lx / 2, -cap.ly / 2), (cap.lx / 2, cap.ly / 2))
    checks = []
    for area in _loaded_areas(cap, depth):
        if cap.clipped_corners:  # D-141: el perímetro recortado con el contorno
            perimeter = polygon_perimeter(area.centre, area.size[0], area.size[1], depth, cap.outline)
        else:
            perimeter = critical_perimeter(area.centre, area.size[0], area.size[1], depth, bounds)
        if not perimeter.sides:
            continue
        loads, lacking = _transferred(item, area, perimeter, depth)
        known = [load for load in loads if load is not None]
        if not known:
            checks.append(_incomplete(PUNCHING, item, lacking, clause, area.note))
            continue
        worst: Check | None = None
        for load in known:
            result = two_way_shear(basis.profile, basis.materials, perimeter, (area.size[0], area.size[1], strength.lam_s), load)
            check = _two_way_check(item, result, _TwoWay(PUNCHING, load.force, clause, area.note))
            if worst is None or check_ratio(check) > check_ratio(worst):
                worst = check
        assert worst is not None
        checks.append(worst)
    return checks


def check_ratio(check: Check) -> float:
    """La razón demanda/capacidad para elegir la revisión que gobierna (infinita sin capacidad si no cumple)."""
    if check.demand is None or not check.capacity:
        return math.inf if check.status is not Status.PASS else 0.0
    return check.demand / check.capacity


def _pile_perimeters(cap: PileCap, index: int, depth: float) -> list[tuple[str, Perimeter, tuple[float, float]]]:
    """Perímetro a d/2 del pilote, recortado con el borde (P1), y, en un pilote de esquina, el que llega a los dos bordes
    (P3): el del área cargada que va de las caras interiores del pilote a la esquina más cercana."""
    pile, side = cap.piles[index], cap.pile.side
    hx, hy = cap.lx / 2, cap.ly / 2
    bounds = ((-hx, -hy), (hx, hy))
    if cap.clipped_corners:
        shapes = [("P1", polygon_perimeter((pile.x, pile.y), side, side, depth, cap.outline), (side, side))]
    else:
        shapes = [("P1", critical_perimeter((pile.x, pile.y), side, side, depth, bounds), (side, side))]
    clipped = {clip.corner for clip in cap.clipped_corners}
    if pile.x != 0 and pile.y != 0 and _corner_key(pile.x, pile.y) not in clipped:  # P3 solo en esquinas sin recortar
        sx, sy = math.copysign(1.0, pile.x), math.copysign(1.0, pile.y)
        c1, c2 = hx - abs(pile.x) + side / 2, hy - abs(pile.y) + side / 2
        shapes.append(("P3", critical_perimeter((sx * (hx - c1 / 2), sy * (hy - c2 / 2)), c1, c2, depth, bounds), (c1, c2)))
    return shapes


def _pile_punching(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Punzonamiento de cada pilote a compresión con su reacción: gobierna el perímetro de mayor razón. Un perímetro que
    pierde más de dos lados contra los bordes (cabezal angosto) no forma el mecanismo y no se revisa: ahí gobierna el
    cortante a todo el ancho."""
    cap = item.cap
    clause = basis.profile.pile_cap.clauses()["pile_punching"]
    checks = []
    for index, pile in enumerate(cap.piles):
        force = item.reaction(index)
        if force <= _NEGLIGIBLE_FORCE:
            continue
        worst: tuple[float, Check] | None = None
        for label, perimeter, (c1, c2) in _pile_perimeters(cap, index, strength.depth):
            if not perimeter.sides or perimeter.outside > _CORNER_SIDES:
                continue
            result = two_way_shear(basis.profile, basis.materials, perimeter, (c1, c2, strength.lam_s), TransferredLoad(force, 0.0, 0.0))
            check = _two_way_check(item, result, _TwoWay(PILE_PUNCHING, force, clause, f"Pilote {pile.id} ({label})"))
            ratio = check_ratio(check)
            if worst is None or ratio > worst[0]:
                worst = (ratio, check)
        if worst is not None:
            checks.append(worst[1])
    return checks


def _round_size(cap: PileCap) -> float:
    """Diámetro del pilote, o el del círculo de igual área si es cuadrado (guía CRSI: pilotes redondos o equivalentes)."""
    return cap.pile.size if cap.pile.shape == "circular" else cap.pile.size * 2 / math.sqrt(math.pi)


def _pair_punching(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Guía CRSI, estado límite P2: dos pilotes vecinos a compresión cuya falla conjunta es más corta que las dos aisladas,
    L < π(dp + d)/2: b0 = π(dp + d) + 2L con la suma de sus reacciones, frente al vc de la norma con β = (L + dp)/dp y
    αs = 40 (decisiones del usuario, D-138)."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    dp, d = _round_size(cap), strength.depth
    phi = profile.shear.strength_reduction()
    clause = profile.pile_cap.clauses()["adjacent_piles_punching"]
    checks = []
    for first in range(len(cap.piles)):
        for second in range(first + 1, len(cap.piles)):
            a, b = cap.piles[first], cap.piles[second]
            spacing = math.hypot(a.x - b.x, a.y - b.y)
            force = item.reaction(first) + item.reaction(second)
            if spacing >= math.pi * (dp + d) / 2 or min(item.reaction(first), item.reaction(second)) <= _NEGLIGIBLE_FORCE:
                continue
            b0 = math.pi * (dp + d) + 2 * spacing
            vc = profile.shear.punching_concrete_stress(fc=materials.fc, lam=strength.lam, lam_s=strength.lam_s,
                                                        beta=(spacing + dp) / dp, alpha_s=40.0, d=d, b0=b0)
            demand, capacity = force / (b0 * d), phi * vc
            checks.append(Check(PAIR_PUNCHING, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=cap.id,
                                case=item.case.case, demand=demand, capacity=capacity, unit="MPa",
                                values=(("Vu", force), ("b0", b0), ("d", d), ("L", spacing), ("dp", dp)),
                                note=f"Pilotes {a.id} y {b.id} (P2)"))
    return checks


def _hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Envolvente convexa (cadena monótona), en orden antihorario; dos puntos si son colineales."""
    ordered = sorted(set(points))
    if len(ordered) <= 2:  # noqa: PLR2004 - un segmento
        return ordered

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:  # noqa: PLR2004
            lower.pop()
        lower.append(point)
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:  # noqa: PLR2004
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _perimeter_length(hull: list[tuple[float, float]]) -> float:
    if len(hull) == 2:  # noqa: PLR2004 - un segmento: ida y vuelta
        return 2 * math.dist(*hull)
    return sum(math.dist(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull)))


def _segment_box_distance(a: tuple[float, float], b: tuple[float, float], box: tuple[float, float, float, float]) -> float:
    """Distancia de un segmento a un rectángulo (x0, y0, x1, y1); 0 si se tocan. Muestrea el segmento con la proyección
    exacta de cada punto: la distancia a un rectángulo es convexa a lo largo del segmento (búsqueda ternaria)."""
    x0, y0, x1, y1 = box

    def at(t: float) -> float:
        x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))

    low, high = 0.0, 1.0
    for _ in range(60):
        left, right = low + (high - low) / 3, high - (high - low) / 3
        if at(left) <= at(right):
            high = right
        else:
            low = left
    return at((low + high) / 2)


def _inside(hull: list[tuple[float, float]], point: tuple[float, float]) -> bool:
    if len(hull) < 3:  # noqa: PLR2004
        return False
    signs = [(hull[(i + 1) % len(hull)][0] - hull[i][0]) * (point[1] - hull[i][1])
             - (hull[(i + 1) % len(hull)][1] - hull[i][1]) * (point[0] - hull[i][0]) for i in range(len(hull))]
    return all(sign >= 0 for sign in signs)


@dataclass(frozen=True)
class _Group:
    """Un grupo de pilotes que punzona en conjunto: sus índices, b0 y β."""

    members: tuple[int, ...]
    b0: float
    beta: float


def _groups(cap: PileCap, depth: float) -> list[_Group]:
    """Los grupos de 3 o más pilotes que pueden punzonar en conjunto (decisión del usuario, D-138): cada pilote se
    traslapa con otro del grupo (L < π(dp + d)/2), su perímetro, la envolvente convexa de los centros desplazada
    (dp + d)/2, b0 = perímetro de la envolvente + π(dp + d), es más corto que el de los pilotes aislados, y no alcanza el
    perímetro crítico de ninguna columna (ahí rige su punzonamiento). El cabezal tiene a lo más 16 pilotes (D-152): los
    subconjuntos se enumeran todos."""
    piles, dp = cap.piles, _round_size(cap)
    count = len(piles)
    radius, single = (dp + depth) / 2, math.pi * (dp + depth)
    near = [sum(1 << j for j in range(count) if j != i and math.hypot(piles[i].x - piles[j].x, piles[i].y - piles[j].y) < single / 2)
            for i in range(count)]
    boxes = [(column.offset_x - (column.cx + depth) / 2, column.offset_y - (column.cy + depth) / 2,
              column.offset_x + (column.cx + depth) / 2, column.offset_y + (column.cy + depth) / 2) for column in cap.columns]
    groups = []
    for mask in range(1, 1 << count):
        members = tuple(i for i in range(count) if mask >> i & 1)
        if len(members) < 3:  # noqa: PLR2004 - los pares son P2
            continue
        reached, frontier = 1 << members[0], 1 << members[0]
        while frontier:
            index = (frontier & -frontier).bit_length() - 1
            frontier &= frontier - 1
            new = near[index] & mask & ~reached
            reached |= new
            frontier |= new
        if reached != mask:
            continue
        hull = _hull([(piles[i].x, piles[i].y) for i in members])
        b0 = _perimeter_length(hull) + single
        if b0 >= len(members) * single:
            continue
        edges = list(zip(hull, hull[1:] + hull[:1], strict=True)) if len(hull) > 2 else [(hull[0], hull[-1])]  # noqa: PLR2004
        if any(_inside(hull, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
               or min(_segment_box_distance(a, b, box) for a, b in edges) < radius for box in boxes):
            continue
        xs, ys = [piles[i].x for i in members], [piles[i].y for i in members]
        sides = sorted((max(xs) - min(xs) + dp, max(ys) - min(ys) + dp))
        groups.append(_Group(members, b0, sides[1] / sides[0]))
    return groups


def _group_punching(basis: Basis, item: FactoredCap, given: tuple[CapStrength, list[_Group]]) -> list[Check]:
    """El grupo de más de dos pilotes que gobierna en el caso: la suma de sus reacciones mayoradas sobre b0·d frente al vc
    de la norma con su β y αs = 40 (decisión del usuario, D-138)."""
    strength, groups = given
    profile, materials, cap = basis.profile, basis.materials, item.cap
    clause = profile.pile_cap.clauses()["adjacent_piles_punching"]
    phi, d = profile.shear.strength_reduction(), strength.depth
    worst: tuple[float, Check] | None = None
    for group in groups:
        reactions = [item.reaction(index) for index in group.members]
        if min(reactions) <= _NEGLIGIBLE_FORCE:
            continue
        force = sum(reactions)
        vc = profile.shear.punching_concrete_stress(fc=materials.fc, lam=strength.lam, lam_s=strength.lam_s, beta=group.beta,
                                                    alpha_s=40.0, d=d, b0=group.b0)
        demand, capacity = force / (group.b0 * d), phi * vc
        names = ", ".join(cap.piles[index].id for index in group.members)
        check = Check(GROUP_PUNCHING, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=cap.id,
                      case=item.case.case, demand=demand, capacity=capacity, unit="MPa",
                      values=(("Vu", force), ("b0", group.b0), ("d", d), ("pilotes", float(len(group.members)))),
                      note=f"Pilotes {names}")
        if worst is None or demand / capacity > worst[0]:
            worst = (demand / capacity, check)
    return [] if worst is None else [worst[1]]


def _corner_key(x: float, y: float) -> str:
    return f"{'+' if x > 0 else '-'}x{'+' if y > 0 else '-'}y"


def _corner_piles(cap: PileCap) -> list[int]:
    """El pilote más cercano a cada esquina sin recortar del cabezal, si queda en el cuadrante de esa esquina."""
    hx, hy = cap.lx / 2, cap.ly / 2
    clipped = {clip.corner for clip in cap.clipped_corners}
    found = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        if _corner_key(sx, sy) in clipped:
            continue
        index = min(range(len(cap.piles)), key=lambda i: math.hypot(sx * hx - cap.piles[i].x, sy * hy - cap.piles[i].y))
        pile = cap.piles[index]
        if pile.x * sx > 0 and pile.y * sy > 0 and index not in found:
            found.append(index)
    return found


def _corner_one_way(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Guía CRSI, estado límite P4: sección a 45° que corta la esquina a d de la cara del pilote de esquina, con su
    reacción; su longitud b = 2s, s = (Ex + Ey)/√2 + dp/2 + d (d ≤ 330 mm solo aquí; proyección sobre la diagonal,
    decisión del usuario, D-138), frente a φ·0.166λ√f'c·b·d. Si la sección no cabe en la esquina, no se revisa."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    rules = profile.pile_cap
    dp, d = _round_size(cap), strength.depth
    phi = profile.shear.strength_reduction()
    stress = rules.corner_one_way_stress(fc=materials.fc, lam=strength.lam)
    checks = []
    for index in _corner_piles(cap):
        pile, force = cap.piles[index], item.reaction(index)
        if force <= _NEGLIGIBLE_FORCE:
            continue
        ex, ey = cap.lx / 2 - abs(pile.x), cap.ly / 2 - abs(pile.y)
        reach = (ex + ey) / math.sqrt(2) + dp / 2 + min(d, rules.corner_depth_limit())
        if reach * math.sqrt(2) > min(cap.lx, cap.ly):
            continue
        width = 2 * reach
        capacity = phi * stress * width * d
        checks.append(Check(CORNER_ONE_WAY, Status.PASS if force <= capacity else Status.FAIL, clause=rules.clauses()["corner_one_way"],
                            member=cap.id, case=item.case.case, demand=force, capacity=capacity, unit="N",
                            values=(("phi", phi), ("vc", stress), ("b", width), ("d", d), ("Ex", ex), ("Ey", ey), ("dp", dp)),
                            note=f"Pilote {pile.id} (P4)"))
    return [*checks, *_clip_one_way(basis, item, strength)]


def _clip_one_way(basis: Basis, item: FactoredCap, strength: CapStrength) -> list[Check]:
    """Cortante de esquina (P4) en una esquina recortada (D-141): la sección paralela al recorte, a dp/2 + d (d ≤ 330 mm)
    del centro del pilote más cercano al recorte hacia adentro, con la longitud de esa recta dentro del contorno y su reacción."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    rules = profile.pile_cap
    dp, d = _round_size(cap), strength.depth
    phi = profile.shear.strength_reduction()
    stress = rules.corner_one_way_stress(fc=materials.fc, lam=strength.lam)
    outline, checks = cap.outline, []
    for clip in cap.clipped_corners:
        sx, sy = (1.0 if clip.corner[0] == "+" else -1.0), (1.0 if clip.corner[2] == "+" else -1.0)
        ends = {(sx * cap.lx / 2, sy * (cap.ly / 2 - clip.along_y)), (sx * (cap.lx / 2 - clip.along_x), sy * cap.ly / 2)}
        edge = next((outline[i], outline[(i + 1) % len(outline)]) for i in range(len(outline))
                    if {outline[i], outline[(i + 1) % len(outline)]} == ends)
        middle = ((edge[0][0] + edge[1][0]) / 2, (edge[0][1] + edge[1][1]) / 2)
        # El pilote más cercano al recorte, aunque no quede en el cuadrante de la esquina (el del vértice en un cabezal de
        # tres pilotes sirve a los dos recortes).
        index = min(range(len(cap.piles)), key=lambda i: math.hypot(cap.piles[i].x - middle[0], cap.piles[i].y - middle[1]))
        pile, force = cap.piles[index], item.reaction(index)
        if force <= _NEGLIGIBLE_FORCE:
            continue
        (ax, ay), (bx, by) = edge
        distance = abs((bx - ax) * (ay - pile.y) - (ax - pile.x) * (by - ay)) / math.hypot(bx - ax, by - ay)
        width = parallel_chord(cap, edge, distance + dp / 2 + min(d, rules.corner_depth_limit()))
        if width <= 0:
            continue
        capacity = phi * stress * width * d
        checks.append(Check(CORNER_ONE_WAY, Status.PASS if force <= capacity else Status.FAIL, clause=rules.clauses()["corner_one_way"],
                            member=cap.id, case=item.case.case, demand=force, capacity=capacity, unit="N",
                            values=(("phi", phi), ("vc", stress), ("b", width), ("d", d), ("dp", dp)),
                            note=f"Pilote {pile.id} (P4, esquina recortada {clip.corner})"))
    return checks


def cap_strength(basis: Basis, cap: PileCap) -> CapStrength | StructuredError:
    """λ, si los pilotes están cerca (13.4.6.8), λs de dos direcciones y la d promedio de la malla inferior: lo común a
    los cortantes del cabezal y de sus franjas (una sola fuente)."""
    lam = concrete_lambda(basis.profile, basis.materials)
    if isinstance(lam, StructuredError):
        return lam
    bottom = mat_rows(cap, cap.bottom, basis.bars)
    depth = (bottom["x"].depth + bottom["y"].depth) / 2
    closely = closely_spaced(basis, cap)
    return CapStrength(lam, closely, basis.profile.pile_cap.punching_size_factor(depth, closely), depth)


def shear_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Cortante en una dirección, límites CRSI en la cara de las columnas y punzonamiento de las columnas y de los pilotes
    de cada caso mayorado."""
    strength = cap_strength(basis, cap)
    if isinstance(strength, StructuredError):
        return [Check(SHEAR, Status.BLOCKED, (strength,), member=cap.id)]
    bottom = mat_rows(cap, cap.bottom, basis.bars)
    depth = strength.depth
    groups = _groups(cap, depth)  # la geometría de los grupos, una vez por cabezal
    checks: list[Check] = []
    for item in analysis.factored:
        for direction in ("x", "y"):
            checks.extend(_one_way(basis, item, bottom[direction], strength))
            checks.extend(_face_one_way(basis, item, bottom[direction], strength))
        checks.extend([*_column_punching(basis, item, strength), *_face_two_way(basis, item, strength),
                       *_pile_punching(basis, item, strength), *_pair_punching(basis, item, strength),
                       *_group_punching(basis, item, (strength, groups)), *_corner_one_way(basis, item, strength)])
    return checks
