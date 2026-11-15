"""Cortante y punzonamiento del cabezal con los casos mayorados (D-138), como domain/footing/shear.py.

Por secciones, con la reacción interpolada de ACI 13.4.6.7 (NSR-10 C.15.5.4): una dirección a d de las caras de la
columna (ACI 13.4.6.5(a), 22.5 y 13.4.6.8(a); NSR-10 C.11.11) y dos direcciones a d/2 de la columna (ACI 13.4.6.5(b) y
22.6; NSR-10 C.11.11.2), con la acción de la cabeza de los pilotes que cuentan. Con pilotes dentro de d o d/2 de la
columna, los límites de la guía CRSI en la cara de la columna (estados límite 5 y 6, y 4). El punzonamiento de cada
pilote, aislado (P1) o de esquina (P3). La mala ubicación cuenta del lado desfavorable: el pilote se acerca a la
sección (o pasa más allá de la cara) en la tolerancia y, con las cargas de la columna, su reacción sube ΔR.
"""

import math
from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.loads import column_faces
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.pile_cap.loads import AXES, CapAnalysis, FactoredCap
from structurelab_rc.domain.shear_strength import TransferredLoad, TwoWayShear, concrete_lambda, two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter
from structurelab_rc.model.pile_cap import PileCap

ONE_WAY = "Cortante en una direccion"
FACE_ONE_WAY = "Cortante en la cara de la columna"
FACE_TWO_WAY = "Cortante en la cara de la columna (dos direcciones)"
PUNCHING = "Punzonamiento"
PILE_PUNCHING = "Punzonamiento del pilote"
PAIR_PUNCHING = "Punzonamiento de dos pilotes"
GROUP_PUNCHING = "Punzonamiento de un grupo de pilotes"
_MAX_GROUP_PILES = 16  # con más pilotes, los grupos no se enumeran (BLOCKED)
CORNER_ONE_WAY = "Cortante de esquina del pilote"
SHEAR = "Cabezal: cortante"
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_NEGLIGIBLE_FORCE = 1.0  # N
_CORNER_SIDES = 2  # una esquina pierde dos lados del perímetro


@dataclass(frozen=True)
class _Strength:
    """Lo común a las resistencias a cortante del cabezal: λ, si los pilotes están cerca (ACI 13.4.6.8), λs de dos
    direcciones y la d promedio de la malla inferior."""

    lam: float
    closely: bool
    lam_s: float
    depth: float


def _one_way(basis: Basis, item: FactoredCap, row: BarRow, strength: _Strength) -> Check | None:
    """Cortante a d de las caras con la reacción interpolada; None si las dos secciones caen fuera del cabezal."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    axis = AXES[row.direction]
    plus, minus = column_faces(cap)[row.direction]
    half = cap.lx / 2 if axis == 0 else cap.ly / 2
    phi = profile.shear.strength_reduction()
    rho = row.area / (row.width * row.depth)
    worst: tuple[float, float, float, str] | None = None
    for plane, outward, face in ((plus + row.depth, 1.0, _FACES[row.direction][0]), (minus - row.depth, -1.0, _FACES[row.direction][1])):
        if abs(plane) >= half:
            continue
        shear, _, moment = item.beyond(axis, plane, outward)
        vc = profile.pile_cap.one_way_concrete_shear(fc=materials.fc, lam=strength.lam, bw=row.width, d=row.depth, h=cap.h, rho_w=rho,
                                                     vu=abs(shear), mu=abs(moment), closely_spaced=strength.closely)
        demand, capacity = abs(shear), phi * vc
        if worst is None or demand / capacity > worst[0]:
            worst = (demand / capacity, demand, capacity, face)
    if worst is None:
        return None
    _, demand, capacity, face = worst
    return Check(f"{ONE_WAY} (barras {row.direction})", Status.PASS if demand <= capacity else Status.FAIL,
                 clause=profile.pile_cap.clauses()["one_way_shear"], member=cap.id, case=item.case.case, demand=demand,
                 capacity=capacity, unit="N", values=(("phi", phi), ("Vc", capacity / phi), ("bw", row.width), ("d", row.depth),
                                                      ("rho w", rho), ("lambda", strength.lam), ("fc", materials.fc)),
                 note=f"Seccion a d de la cara {face} de la columna, reacciones interpoladas")


def _face_one_way(basis: Basis, item: FactoredCap, row: BarRow, strength: _Strength) -> list[Check]:
    """Guía CRSI, estados límite 5 y 6: en cada cara de la columna con algún pilote a menos de d, cortante a todo el
    ancho con la reacción completa de los pilotes que, mal ubicados, quedan más allá de la cara; w es la distancia del
    más cercano más la tolerancia."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    axis = AXES[row.direction]
    phi = profile.shear.strength_reduction()
    checks = []
    for plane, outward, face in zip(column_faces(cap)[row.direction], (1.0, -1.0), _FACES[row.direction], strict=True):
        distances = [outward * ((pile.x, pile.y)[axis] - plane) for pile in cap.piles]
        near = [distance for distance in distances if distance + cap.mislocation > 0]
        if not near or min(near) >= row.depth:
            continue
        w = _clear_distance(near) + cap.mislocation
        _, shear, moment = item.beyond(axis, plane, outward)
        stress = profile.pile_cap.column_face_one_way_stress(fc=materials.fc, lam=strength.lam, d=row.depth, w=w, vu=max(shear, 0.0),
                                                             mu=max(moment, 0.0))
        capacity = phi * stress * row.width * row.depth
        checks.append(Check(f"{FACE_ONE_WAY} (barras {row.direction})", Status.PASS if shear <= capacity else Status.FAIL,
                            clause=profile.pile_cap.clauses()["column_face_one_way"], member=cap.id, case=item.case.case,
                            demand=max(shear, 0.0), capacity=capacity, unit="N",
                            values=(("phi", phi), ("vc", stress), ("w", w), ("b", row.width), ("d", row.depth), ("Mu", moment)),
                            note=f"Cara {face} de la columna"))
    return checks


def _clear_distance(distances: list[float]) -> float:
    """w de la guía CRSI sin la tolerancia: la distancia de la cara al pilote más cercano que ya está afuera (0 si todos
    los que cuentan están, mal ubicados, apenas dentro); así la tolerancia solo puede aumentar w, del lado de la menor
    capacidad, mientras la demanda cuenta los pilotes que mal ubicados quedan más allá."""
    beyond = [distance for distance in distances if distance > 0]
    return min(beyond) if beyond else 0.0


def _outside(cap: PileCap, index: int) -> float:
    """Distancia del centro de un pilote al contorno de la columna (≤ 0 si queda bajo ella), en mm."""
    column, pile = cap.column, cap.piles[index]
    return max(abs(pile.x - column.offset_x) - column.cx / 2, abs(pile.y - column.offset_y) - column.cy / 2)


def _face_two_way(basis: Basis, item: FactoredCap, strength: _Strength) -> list[Check]:
    """Guía CRSI, estado límite 4: con algún pilote a menos de d/2 de la columna, cortante en el perímetro de la cara de la
    columna, bs = 2(cx + cy), c = (cx + cy)/2 (perímetro real, decisión del usuario, D-138)."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    tolerance, depth = cap.mislocation, strength.depth
    outside = [(distance, index) for index in range(len(cap.piles)) if (distance := _outside(cap, index)) + tolerance > 0]
    if not outside or min(outside)[0] >= depth / 2:
        return []
    column = cap.column
    w = _clear_distance([distance for distance, _ in outside]) + tolerance
    shear = sum(item.reaction(index) for _, index in outside) - item.load * (cap.area - column.cx * column.cy)
    side, perimeter = (column.cx + column.cy) / 2, 2 * (column.cx + column.cy)
    stress = profile.pile_cap.column_face_two_way_stress(fc=materials.fc, lam=strength.lam, d=depth, w=w, c=side)
    phi = profile.shear.strength_reduction()
    capacity = phi * stress * perimeter * depth
    return [Check(FACE_TWO_WAY, Status.PASS if shear <= capacity else Status.FAIL, clause=profile.pile_cap.clauses()["column_face_two_way"],
                  member=cap.id, case=item.case.case, demand=max(shear, 0.0), capacity=capacity, unit="N",
                  values=(("phi", phi), ("vc", stress), ("w", w), ("bs", perimeter), ("c columna", side), ("d", depth)),
                  note=f"Pilote {cap.piles[min(outside)[1]].id} a w de la cara")]


def _closely_spaced(basis: Basis, cap: PileCap) -> bool:
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


def _column_punching(basis: Basis, item: FactoredCap, strength: _Strength) -> list[Check]:
    """Dos direcciones a d/2 de la columna con la reacción interpolada y la acción de la cabeza de los pilotes que cuentan;
    los momentos respecto al centroide del perímetro."""
    cap = item.cap
    column, depth = cap.column, strength.depth
    bounds = ((-cap.lx / 2, -cap.ly / 2), (cap.lx / 2, cap.ly / 2))
    perimeter = critical_perimeter((column.offset_x, column.offset_y), column.cx, column.cy, depth, bounds)
    if not perimeter.sides:
        return []
    half_x, half_y = (column.cx + depth) / 2, (column.cy + depth) / 2
    xc, yc = perimeter.centroid
    (x0, y0), (x1, y1) = perimeter.region
    inside = (x1 - x0) * (y1 - y0)
    force = -item.load * (cap.area - inside)  # el peso fuera del área crítica; el cabezal tiene su centroide en el origen
    along_x = item.load * inside * (x0 + x1) / 2 - xc * force
    along_y = item.load * inside * (y0 + y1) / 2 - yc * force
    lever = cap.pile.embedment - cap.h / 2
    for index, pile in enumerate(cap.piles):
        offset = max(abs(pile.x - column.offset_x) - half_x, abs(pile.y - column.offset_y) - half_y) + cap.mislocation
        portion = item.share(offset, cap.pile.size)
        if portion <= 0:
            continue
        reaction = portion * item.reaction(index)
        (vx, vy), (mx, my) = item.case.forces.shears[index], item.case.forces.moments[index]
        force += reaction
        along_x += reaction * (pile.x - xc) - portion * (my + lever * vx)
        along_y += reaction * (pile.y - yc) + portion * (mx - lever * vy)
    result = two_way_shear(basis.profile, basis.materials, perimeter, (column.cx, column.cy, strength.lam_s),
                           TransferredLoad(force, along_x, along_y))
    given = _TwoWay(PUNCHING, force, basis.profile.pile_cap.clauses()["punching"], "Columna, reacciones interpoladas")
    return [_two_way_check(item, result, given)]


def _pile_perimeters(cap: PileCap, index: int, depth: float) -> list[tuple[str, Perimeter, tuple[float, float]]]:
    """Perímetro a d/2 del pilote, recortado con el borde (P1), y, en un pilote de esquina, el que llega a los dos bordes
    (P3): el del área cargada que va de las caras interiores del pilote a la esquina más cercana."""
    pile, side = cap.piles[index], cap.pile.side
    hx, hy = cap.lx / 2, cap.ly / 2
    bounds = ((-hx, -hy), (hx, hy))
    shapes = [("P1", critical_perimeter((pile.x, pile.y), side, side, depth, bounds), (side, side))]
    if pile.x != 0 and pile.y != 0:
        sx, sy = math.copysign(1.0, pile.x), math.copysign(1.0, pile.y)
        c1, c2 = hx - abs(pile.x) + side / 2, hy - abs(pile.y) + side / 2
        shapes.append(("P3", critical_perimeter((sx * (hx - c1 / 2), sy * (hy - c2 / 2)), c1, c2, depth, bounds), (c1, c2)))
    return shapes


def _pile_punching(basis: Basis, item: FactoredCap, strength: _Strength) -> list[Check]:
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
            ratio = math.inf if check.demand is None or not check.capacity else check.demand / check.capacity
            if worst is None or ratio > worst[0]:
                worst = (ratio, check)
        if worst is not None:
            checks.append(worst[1])
    return checks


def _round_size(cap: PileCap) -> float:
    """Diámetro del pilote, o el del círculo de igual área si es cuadrado (guía CRSI: pilotes redondos o equivalentes)."""
    return cap.pile.size if cap.pile.shape == "circular" else cap.pile.size * 2 / math.sqrt(math.pi)


def _pair_punching(basis: Basis, item: FactoredCap, strength: _Strength) -> list[Check]:
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


def _groups(cap: PileCap, depth: float) -> list[_Group] | None:
    """Los grupos de 3 o más pilotes que pueden punzonar en conjunto (decisión del usuario, D-138): cada pilote se
    traslapa con otro del grupo (L < π(dp + d)/2), su perímetro, la envolvente convexa de los centros desplazada
    (dp + d)/2, b0 = perímetro de la envolvente + π(dp + d), es más corto que el de los pilotes aislados, y no alcanza el
    perímetro crítico de la columna (ahí rige su punzonamiento). None con más de 16 pilotes."""
    piles, dp = cap.piles, _round_size(cap)
    count = len(piles)
    if count > _MAX_GROUP_PILES:
        return None
    radius, single = (dp + depth) / 2, math.pi * (dp + depth)
    near = [sum(1 << j for j in range(count) if j != i and math.hypot(piles[i].x - piles[j].x, piles[i].y - piles[j].y) < single / 2)
            for i in range(count)]
    column = cap.column
    box = (column.offset_x - (column.cx + depth) / 2, column.offset_y - (column.cy + depth) / 2,
           column.offset_x + (column.cx + depth) / 2, column.offset_y + (column.cy + depth) / 2)
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
        centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        edges = list(zip(hull, hull[1:] + hull[:1], strict=True)) if len(hull) > 2 else [(hull[0], hull[-1])]  # noqa: PLR2004
        if _inside(hull, centre) or min(_segment_box_distance(a, b, box) for a, b in edges) < radius:
            continue
        xs, ys = [piles[i].x for i in members], [piles[i].y for i in members]
        sides = sorted((max(xs) - min(xs) + dp, max(ys) - min(ys) + dp))
        groups.append(_Group(members, b0, sides[1] / sides[0]))
    return groups


def _group_punching(basis: Basis, item: FactoredCap, given: tuple[_Strength, list[_Group] | None]) -> list[Check]:
    """El grupo de más de dos pilotes que gobierna en el caso: la suma de sus reacciones mayoradas sobre b0·d frente al vc
    de la norma con su β y αs = 40 (decisión del usuario, D-138)."""
    strength, groups = given
    profile, materials, cap = basis.profile, basis.materials, item.cap
    clause = profile.pile_cap.clauses()["adjacent_piles_punching"]
    if groups is None:
        error = blocked(f"Grupos de pilotes con mas de {_MAX_GROUP_PILES} pilotes: falta implementacion", member=cap.id)
        return [Check(GROUP_PUNCHING, Status.BLOCKED, (error,), clause, member=cap.id, case=item.case.case)]
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


def _corner_piles(cap: PileCap) -> list[int]:
    """El pilote más cercano a cada esquina del cabezal, si queda en el cuadrante de esa esquina."""
    hx, hy = cap.lx / 2, cap.ly / 2
    found = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        index = min(range(len(cap.piles)), key=lambda i: math.hypot(sx * hx - cap.piles[i].x, sy * hy - cap.piles[i].y))
        pile = cap.piles[index]
        if pile.x * sx > 0 and pile.y * sy > 0 and index not in found:
            found.append(index)
    return found


def _corner_one_way(basis: Basis, item: FactoredCap, strength: _Strength) -> list[Check]:
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
    return checks


def shear_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Cortante en una dirección, límites CRSI en la cara de la columna y punzonamiento de la columna y de los pilotes de
    cada caso mayorado."""
    lam = concrete_lambda(basis.profile, basis.materials)
    if isinstance(lam, StructuredError):
        return [Check(SHEAR, Status.BLOCKED, (lam,), member=cap.id)]
    bottom = mat_rows(cap, cap.bottom, basis.bars)
    depth = (bottom["x"].depth + bottom["y"].depth) / 2
    closely = _closely_spaced(basis, cap)
    strength = _Strength(lam, closely, basis.profile.pile_cap.punching_size_factor(depth, closely), depth)
    groups = _groups(cap, depth)  # la geometría de los grupos, una vez por cabezal
    checks: list[Check] = []
    for item in analysis.factored:
        for direction in ("x", "y"):
            one_way = _one_way(basis, item, bottom[direction], strength)
            checks.extend([] if one_way is None else [one_way])
            checks.extend(_face_one_way(basis, item, bottom[direction], strength))
        checks.extend([*_column_punching(basis, item, strength), *_face_two_way(basis, item, strength),
                       *_pile_punching(basis, item, strength), *_pair_punching(basis, item, strength),
                       *_group_punching(basis, item, (strength, groups)), *_corner_one_way(basis, item, strength)])
    return checks
