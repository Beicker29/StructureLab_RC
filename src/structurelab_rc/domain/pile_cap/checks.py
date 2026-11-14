"""Verificaciones de un cabezal sobre pilotes (D-138).

- Geometría: empotramiento, borde y tolerancia de mala ubicación mínimos del perfil (ACI 13.4.6.3 y 13.4.1.4; NSR-10 no
  los fija) y la altura mínima sobre el refuerzo inferior (ACI 13.4.6.2, NSR-10 C.15.7).
- Revisiones geotécnicas con los casos de servicio, como las de las zapatas: presión admisible de cada pilote a
  compresión (con +10 % en ACI al considerar la mala ubicación) y a tracción, deslizamiento (carga lateral), capacidad
  del grupo con su eficiencia y, sin sismo, la excentricidad máxima declarada; las capacidades del suelo suben con sismo.
- Flexión en las caras de la columna con las reacciones de los pilotes concentradas en su centro (ACI 13.4.6.4), con el
  brazo aumentado por la tolerancia del lado desfavorable, el peso del cabezal hacia abajo y la acción de la cabeza de
  cada pilote (su momento y el de su fuerza horizontal respecto al eje de la sección). Las mallas se revisan con
  domain/footing/flexure.py: el As mínimo es la interpretación de la guía CRSI (4.5) y no se admite concreto simple.
- Cortante por secciones con la reacción interpolada de 13.4.6.7 (NSR-10 C.15.5.4): una dirección a d de las caras y dos
  direcciones a d/2 de la columna; los límites de la guía CRSI en la cara de la columna cuando hay pilotes dentro de d
  (estados límite 5 y 6) o de d/2 (estado límite 4), y el punzonamiento de cada pilote, aislado (P1) o de esquina (P3).
- Desarrollo, pasadores y aplastamiento: los de la zapata (domain/footing/connection.py).
"""

import math
from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.connection import column_connection_checks
from structurelab_rc.domain.footing.flexure import FaceMoments, SectionRules, Values, mat_flexure_checks
from structurelab_rc.domain.footing.loads import column_faces, uniform_load
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.footing.spacing import footing_min_spacing_checks
from structurelab_rc.domain.pile_cap.reactions import CapCase, cap_cases, spread_on_cap
from structurelab_rc.domain.shear_strength import TransferredLoad, TwoWayShear, concrete_lambda, two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, incomplete, invalid_input
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter
from structurelab_rc.model.footing import UnitWeighted
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil

PILE_COMPRESSION = "Presion admisible del pilote: compresion"
PILE_TENSION = "Presion admisible del pilote: traccion"
PILE_LATERAL = "Deslizamiento del pilote"
GROUP = "Capacidad del grupo de pilotes"
ECCENTRICITY = "Excentricidad en servicio"
UNRESISTED = "Pilotes: momento no resistido"
EMBEDMENT = "Cabezal: empotramiento del pilote"
EDGE = "Cabezal: borde del pilote"
MISLOCATION = "Cabezal: tolerancia de mala ubicacion"
STRUCTURAL = "Cabezal: verificacion estructural"
ONE_WAY = "Cortante en una direccion"
FACE_ONE_WAY = "Cortante en la cara de la columna"
FACE_TWO_WAY = "Cortante en la cara de la columna (dos direcciones)"
PUNCHING = "Punzonamiento"
PILE_PUNCHING = "Punzonamiento del pilote"
_AXES = {"x": 0, "y": 1}
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_NEGLIGIBLE_FORCE = 1.0  # N
_NEGLIGIBLE_MOMENT = 1e3  # N·mm


def _geometry_checks(basis: Basis, cap: PileCap) -> list[Check]:
    """Empotramiento, borde y tolerancia mínimos del perfil; NSR-10 no los fija (D-138)."""
    rules, member = basis.profile.pile_cap, cap.id
    clauses = rules.clauses()
    checks = []
    embedment = rules.min_embedment()
    if embedment is not None:
        checks.append(Check(EMBEDMENT, Status.PASS if cap.pile.embedment >= embedment else Status.FAIL, clause=clauses["embedment"],
                            member=member, demand=embedment, capacity=cap.pile.embedment, unit="mm"))
    edge = rules.min_edge_distance()
    if edge is not None:
        distance, pile = min((min(cap.lx / 2 - abs(pile.x), cap.ly / 2 - abs(pile.y)) - cap.pile.size / 2, pile.id) for pile in cap.piles)
        checks.append(Check(EDGE, Status.PASS if distance >= edge else Status.FAIL, clause=clauses["edge"], member=member, demand=edge,
                            capacity=distance, unit="mm", note=f"Pilote {pile}"))
    tolerance = rules.min_mislocation()
    if tolerance is not None:
        checks.append(Check(MISLOCATION, Status.PASS if cap.mislocation >= tolerance else Status.FAIL, clause=clauses["mislocation"],
                            member=member, demand=tolerance, capacity=cap.mislocation, unit="mm"))
    return checks


def _pile_checks(basis: Basis, cap: PileCap, case: CapCase, soil: PileCapSoil) -> list[Check]:
    """Un caso de servicio, como las revisiones geotécnicas de las zapatas: presión admisible de cada pilote a compresión
    y a tracción, deslizamiento (carga lateral de cada pilote) y capacidad del grupo, con las capacidades del suelo
    aumentadas en los casos con sismo; en ACI, la compresión con +10 % al considerar la mala ubicación."""
    rules, member = basis.profile.pile_cap, cap.id
    spread = spread_on_cap(cap)
    seismic = soil.factor(case.load.seismic)
    mislocation = rules.mislocation_capacity_factor() if spread and cap.mislocation > 0 else 1.0
    clause = rules.clauses()["pile_capacity"]
    forces = case.forces
    count = range(len(cap.piles))
    reaction, index = max((case.adverse(index, spread), index) for index in count)
    capacity = mislocation * seismic * soil.pile_capacity_compression
    values = (("R pilote", forces.reactions[index]), ("delta R", forces.spread[index] if spread else 0.0),
              ("Qa", soil.pile_capacity_compression), ("factor mala ubicacion", mislocation), ("factor sismo", seismic))
    checks = [Check(PILE_COMPRESSION, Status.PASS if reaction <= capacity else Status.FAIL, clause=clause, member=member,
                    case=case.case, demand=max(reaction, 0.0), capacity=capacity, unit="N", values=values,
                    note=f"Pilote {cap.piles[index].id}")]
    pull, index = min((forces.reactions[index] - (forces.spread[index] if spread else 0.0), index) for index in count)
    where = (member, case.case, f"Pilote {cap.piles[index].id}")
    if pull < -_NEGLIGIBLE_FORCE:
        tension = None if soil.pile_capacity_tension is None else seismic * soil.pile_capacity_tension
        checks.append(_optional_capacity(PILE_TENSION, (-pull, tension, "pile_capacity_tension_kN"), clause, where))
    lateral, index = max((math.hypot(*forces.shears[index]), index) for index in count)
    if lateral > _NEGLIGIBLE_FORCE:
        capacity_h = None if soil.pile_capacity_lateral is None else seismic * soil.pile_capacity_lateral
        checks.append(_optional_capacity(PILE_LATERAL, (lateral, capacity_h, "pile_capacity_lateral_kN"), clause,
                                         (member, case.case, f"Pilote {cap.piles[index].id}")))
    group = soil.group_efficiency * len(cap.piles) * seismic * soil.pile_capacity_compression
    checks.append(Check(GROUP, Status.PASS if case.total <= group else Status.FAIL, clause=clause, member=member, case=case.case,
                        demand=max(case.total, 0.0), capacity=group, unit="N",
                        values=(("eficiencia", soil.group_efficiency), ("pilotes", float(len(cap.piles))), ("factor sismo", seismic))))
    if not case.load.seismic:
        checks.append(_eccentricity(cap, case, soil))
    return checks


def _eccentricity(cap: PileCap, case: CapCase, soil: PileCapSoil) -> Check:
    """Combinaciones de servicio sin sismo (D+L): la resultante vertical de las reacciones respecto al centroide del grupo
    no pasa de la excentricidad máxima declarada (decisión del usuario, D-138)."""
    reactions, n = case.forces.reactions, len(cap.piles)
    total = sum(reactions)
    xc, yc = sum(pile.x for pile in cap.piles) / n, sum(pile.y for pile in cap.piles) / n
    if total <= 0:
        error = invalid_input("La resultante de servicio no comprime el grupo de pilotes", member=cap.id, case=case.case)
        return Check(ECCENTRICITY, Status.FAIL, (error,), "D-138", member=cap.id, case=case.case, unit="mm")
    ex = sum(r * pile.x for r, pile in zip(reactions, cap.piles, strict=True)) / total - xc
    ey = sum(r * pile.y for r, pile in zip(reactions, cap.piles, strict=True)) / total - yc
    e = math.hypot(ex, ey)
    return Check(ECCENTRICITY, Status.PASS if e <= soil.max_eccentricity else Status.FAIL, clause="D-138", member=cap.id,
                 case=case.case, demand=e, capacity=soil.max_eccentricity, unit="mm", values=(("ex", ex), ("ey", ey)),
                 note="Resultante vertical respecto al centroide del grupo de pilotes")


def _optional_capacity(name: str, given: tuple[float, float | None, str], clause: str, where: tuple[str, str, str]) -> Check:
    """Una demanda frente a una capacidad opcional: sin ella, INCOMPLETE (no se supone)."""
    demand, capacity, field = given
    member, case, note = where
    if capacity is None:
        error = incomplete(f"Falta soil.{field}: un pilote la necesita en este caso (no se supone)", member=member, case=case)
        return Check(name, Status.INCOMPLETE, (error,), clause, member=member, case=case, demand=demand, unit="N", note=note)
    return Check(name, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=member, case=case, demand=demand,
                 capacity=capacity, unit="N", note=note)


def _unresisted(cap: PileCap, case: CapCase) -> list[Check]:
    if case.unresisted <= _NEGLIGIBLE_MOMENT:
        return []
    error = incomplete("Los pilotes estan alineados y no resisten el momento de la columna en la direccion normal a su eje: "
                       "requiere vigas de amarre o pilotes que tomen momento (no se suponen)", member=cap.id, case=case.case)
    return [Check(UNRESISTED, Status.INCOMPLETE, (error,), "D-138", member=cap.id, case=case.case, demand=case.unresisted, unit="N*mm")]


@dataclass(frozen=True)
class _Context:
    """Lo común a las solicitaciones de un caso mayorado: la base de cálculo, el cabezal, el caso, la carga uniforme hacia
    abajo (N/mm²) y si la mala ubicación aumenta las reacciones."""

    basis: Basis
    cap: PileCap
    case: CapCase
    load: float
    spread: bool

    def beyond(self, axis: int, plane: float, outward: float) -> tuple[float, float, float]:
        """Más allá de un plano vertical normal a x (axis = 0) o a y (axis = 1), del lado outward (+1 o −1): el cortante
        con la reacción interpolada (13.4.6.7), el cortante con la reacción completa de los pilotes cuyo centro está más
        allá y el momento respecto al plano (positivo tracciona la cara inferior), en N y N·mm. El brazo de cada pilote
        crece con la tolerancia; la acción de su cabeza cuenta si su centro está más allá; el peso, hacia abajo."""
        cap, case = self.cap, self.case
        tolerance, size, lever = cap.mislocation, cap.pile.size, cap.pile.embedment - cap.h / 2
        share = self.basis.profile.pile_cap.reaction_share
        shear = full = moment = 0.0
        for index, pile in enumerate(cap.piles):
            reaction = case.adverse(index, self.spread)
            distance = outward * ((pile.x, pile.y)[axis] - plane)
            if distance + tolerance > 0:
                moment += reaction * (distance + tolerance)
            if distance > 0:
                full += reaction
                (vx, vy), (mx, my) = case.forces.shears[index], case.forces.moments[index]
                moment += -outward * (my + lever * vx) if axis == 0 else outward * (mx - lever * vy)
            shear += share(distance + tolerance, size) * reaction
        half, width = (cap.lx / 2, cap.ly) if axis == 0 else (cap.ly / 2, cap.lx)
        length = max(half - outward * plane, 0.0)
        weight = self.load * width * length
        return shear - weight, full - weight, moment - weight * length / 2

    def face_moments(self) -> FaceMoments:
        """Momento en cada cara de la columna (ACI 13.2.6.6 y 13.4.6.4, NSR-10 C.15.4.1)."""
        faces = column_faces(self.cap)
        return FaceMoments(self.case.case, {direction: (self.beyond(_AXES[direction], plus, 1.0)[2],
                                                        self.beyond(_AXES[direction], minus, -1.0)[2])
                                            for direction, (plus, minus) in faces.items()})


def cap_rules(basis: Basis, cap: PileCap) -> SectionRules:
    """Flexión de las mallas del cabezal: As mínimo con la interpretación de la guía CRSI (4.5) de ACI 9.6.1 y 24.4
    (NSR-10 C.10.5 y C.7.12), As = máx(As análisis, mín(As,min, 4/3·As análisis), mín(As,min, ρt·b·h)) con As,min =
    máx(0.25√f'c, 1.4)·b·d/fy; altura mínima del cabezal y sin concreto simple (ACI 14.1.4, NSR-10 C.22.2.1)."""
    profile, materials = basis.profile, basis.materials
    clauses = profile.pile_cap.clauses()
    ratio = profile.footing.shrinkage_temperature_ratio(materials.fy)

    def minimum(mat: str, row: BarRow, demand: float) -> tuple[float, Values, str]:
        minimum_area = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, row.width, row.depth)
        analysis = required_area(profile, materials, RectangularSection(row.width, cap.h), row.depth, max(demand, 0.0))
        shrinkage = min(minimum_area, ratio * row.width * cap.h)
        if analysis is None:  # ninguna cuantía alcanza el momento: la flexión no cumple y el mínimo es As,min
            return minimum_area, (("As,min", minimum_area), ("rho t", ratio)), clauses["min_reinforcement"]
        required = max(analysis, profile.flexure.effective_min_reinforcement(minimum_area, analysis), shrinkage)
        return required, (("As analisis", analysis), ("As,min", minimum_area), ("rho t", ratio)), clauses["min_reinforcement"]

    return SectionRules(minimum, (profile.pile_cap.min_depth(), clauses["min_depth"]), clauses["plain"])


def _one_way(context: _Context, row: BarRow, given: tuple[float, bool]) -> Check | None:
    """Cortante en una dirección a d de las caras, con la reacción interpolada (ACI 13.4.6.5(a) y 13.4.6.7, NSR-10
    C.15.5.4); None si las dos secciones caen fuera del cabezal."""
    profile, materials, cap = context.basis.profile, context.basis.materials, context.cap
    lam, closely = given
    axis = _AXES[row.direction]
    plus, minus = column_faces(cap)[row.direction]
    half = cap.lx / 2 if axis == 0 else cap.ly / 2
    phi = profile.shear.strength_reduction()
    rho = row.area / (row.width * row.depth)
    worst: tuple[float, float, float, str] | None = None
    for plane, outward, face in ((plus + row.depth, 1.0, _FACES[row.direction][0]), (minus - row.depth, -1.0, _FACES[row.direction][1])):
        if abs(plane) >= half:
            continue
        shear, _, moment = context.beyond(axis, plane, outward)
        vc = profile.pile_cap.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=row.width, d=row.depth, h=cap.h, rho_w=rho,
                                                     vu=abs(shear), mu=abs(moment), closely_spaced=closely)
        demand, capacity = abs(shear), phi * vc
        if worst is None or demand / capacity > worst[0]:
            worst = (demand / capacity, demand, capacity, face)
    if worst is None:
        return None
    _, demand, capacity, face = worst
    return Check(f"{ONE_WAY} (barras {row.direction})", Status.PASS if demand <= capacity else Status.FAIL,
                 clause=profile.pile_cap.clauses()["one_way_shear"], member=cap.id, case=context.case.case, demand=demand,
                 capacity=capacity, unit="N", values=(("phi", phi), ("Vc", capacity / phi), ("bw", row.width), ("d", row.depth),
                                                      ("rho w", rho), ("lambda", lam), ("fc", materials.fc)),
                 note=f"Seccion a d de la cara {face} de la columna, reacciones interpoladas")


def _face_one_way(context: _Context, row: BarRow, lam: float) -> list[Check]:
    """Guía CRSI, estados límite 5 y 6: cortante a todo el ancho en cada cara de la columna con algún pilote a menos de d
    de ella, con la reacción completa de los pilotes más allá y w la distancia al más cercano más la tolerancia."""
    profile, materials, cap = context.basis.profile, context.basis.materials, context.cap
    axis = _AXES[row.direction]
    phi = profile.shear.strength_reduction()
    checks = []
    for plane, outward, face in zip(column_faces(cap)[row.direction], (1.0, -1.0), _FACES[row.direction], strict=True):
        distances = [outward * ((pile.x, pile.y)[axis] - plane) for pile in cap.piles]
        near = [distance for distance in distances if distance > 0]
        if not near or min(near) >= row.depth:
            continue
        w = min(near) + cap.mislocation
        _, shear, moment = context.beyond(axis, plane, outward)
        stress = profile.pile_cap.column_face_one_way_stress(fc=materials.fc, lam=lam, d=row.depth, w=w, vu=max(shear, 0.0),
                                                             mu=max(moment, 0.0))
        capacity = phi * stress * row.width * row.depth
        checks.append(Check(f"{FACE_ONE_WAY} (barras {row.direction})", Status.PASS if shear <= capacity else Status.FAIL,
                            clause=profile.pile_cap.clauses()["column_face_one_way"], member=cap.id, case=context.case.case,
                            demand=max(shear, 0.0), capacity=capacity, unit="N",
                            values=(("phi", phi), ("vc", stress), ("w", w), ("b", row.width), ("d", row.depth),
                                    ("Mu", moment)), note=f"Cara {face} de la columna"))
    return checks


def _outside(cap: PileCap, index: int) -> float:
    """Distancia del centro de un pilote al contorno de la columna (≤ 0 si queda bajo ella), en mm."""
    column, pile = cap.column, cap.piles[index]
    return max(abs(pile.x - column.offset_x) - column.cx / 2, abs(pile.y - column.offset_y) - column.cy / 2)


def _face_two_way(context: _Context, depth: float, lam: float) -> list[Check]:
    """Guía CRSI, estado límite 4: con algún pilote a menos de d/2 de la columna, cortante en el perímetro de la cara de la
    columna, bs = 2(cx + cy), c = (cx + cy)/2 (perímetro real, decisión del usuario, D-138)."""
    profile, materials, cap = context.basis.profile, context.basis.materials, context.cap
    distances = [(_outside(cap, index), index) for index in range(len(cap.piles))]
    outside = [(distance, index) for distance, index in distances if distance > 0]
    if not outside or min(outside)[0] >= depth / 2:
        return []
    column = cap.column
    w = min(outside)[0] + cap.mislocation
    shear = sum(context.case.adverse(index, context.spread) for _, index in outside) - context.load * (cap.area - column.cx * column.cy)
    side, perimeter = (column.cx + column.cy) / 2, 2 * (column.cx + column.cy)
    stress = profile.pile_cap.column_face_two_way_stress(fc=materials.fc, lam=lam, d=depth, w=w, c=side)
    phi = profile.shear.strength_reduction()
    capacity = phi * stress * perimeter * depth
    return [Check(FACE_TWO_WAY, Status.PASS if shear <= capacity else Status.FAIL, clause=profile.pile_cap.clauses()["column_face_two_way"],
                  member=cap.id, case=context.case.case, demand=max(shear, 0.0), capacity=capacity, unit="N",
                  values=(("phi", phi), ("vc", stress), ("w", w), ("bs", perimeter), ("c columna", side), ("d", depth)),
                  note=f"Pilote {cap.piles[min(outside)[1]].id} a w de la cara")]


def _closely_spaced(basis: Basis, cap: PileCap) -> bool:
    """Si cada pilote tiene otro a la separación límite del perfil o menos (ACI 13.4.6.8; NSR-10 no la tiene)."""
    limit = basis.profile.pile_cap.closely_spaced_limit()
    if limit is None or len(cap.piles) < 2:  # noqa: PLR2004 - un grupo necesita al menos dos pilotes
        return False
    nearest = [min(math.hypot(a.x - b.x, a.y - b.y) for b in cap.piles if b is not a) for a in cap.piles]
    return max(nearest) <= limit * cap.pile.size


def _two_way_check(context: _Context, result: TwoWayShear | StructuredError, given: tuple[str, float, str, str]) -> Check:
    name, force, clause, note = given
    cap, case = context.cap, context.case.case
    if isinstance(result, StructuredError):
        return Check(name, Status.BLOCKED, (result,), clause, member=cap.id, case=case, note=note)
    xc, yc = result.perimeter.centroid
    values: Values = (("Vu", force), ("b0", result.perimeter.length), ("d", result.perimeter.depth), ("alpha s", result.alpha_s),
                      ("vuv", result.vuv), ("xc", xc), ("yc", yc))
    return Check(name, Status.PASS if result.vu <= result.phi_vc else Status.FAIL, clause=clause, member=cap.id, case=case,
                 demand=result.vu, capacity=result.phi_vc, unit="MPa", values=values, note=note)


def _column_punching(context: _Context, depth: float, lam_s: float) -> list[Check]:
    """Dos direcciones a d/2 de la columna con la reacción interpolada (ACI 13.4.6.5(b) y 13.4.6.7, NSR-10 C.15.5.4) y la
    acción de la cabeza de los pilotes que cuentan; los momentos respecto al centroide del perímetro."""
    basis, cap = context.basis, context.cap
    column = cap.column
    bounds = ((-cap.lx / 2, -cap.ly / 2), (cap.lx / 2, cap.ly / 2))
    perimeter = critical_perimeter((column.offset_x, column.offset_y), column.cx, column.cy, depth, bounds)
    if not perimeter.sides:
        return []
    half_x, half_y = (column.cx + depth) / 2, (column.cy + depth) / 2
    xc, yc = perimeter.centroid
    (x0, y0), (x1, y1) = perimeter.region
    inside = (x1 - x0) * (y1 - y0)
    # El peso fuera del área crítica, hacia abajo (el cabezal tiene su centroide en el origen).
    force = -context.load * (cap.area - inside)
    along_x = context.load * inside * (x0 + x1) / 2 - xc * force
    along_y = context.load * inside * (y0 + y1) / 2 - yc * force
    lever = cap.pile.embedment - cap.h / 2
    share = basis.profile.pile_cap.reaction_share
    for index, pile in enumerate(cap.piles):
        offset = max(abs(pile.x - column.offset_x) - half_x, abs(pile.y - column.offset_y) - half_y) + cap.mislocation
        portion = share(offset, cap.pile.size)
        if portion <= 0:
            continue
        reaction = portion * context.case.adverse(index, context.spread)
        (vx, vy), (mx, my) = context.case.forces.shears[index], context.case.forces.moments[index]
        force += reaction
        along_x += reaction * (pile.x - xc) - portion * (my + lever * vx)
        along_y += reaction * (pile.y - yc) + portion * (mx - lever * vy)
    load = TransferredLoad(force, along_x, along_y)
    result = two_way_shear(basis.profile, basis.materials, perimeter, (column.cx, column.cy, lam_s), load)
    clause = basis.profile.pile_cap.clauses()["punching"]
    return [_two_way_check(context, result, (PUNCHING, force, clause, "Columna, reacciones interpoladas"))]


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
        centre = (sx * (hx - c1 / 2), sy * (hy - c2 / 2))
        shapes.append(("P3", critical_perimeter(centre, c1, c2, depth, bounds), (c1, c2)))
    return shapes


def _pile_punching(context: _Context, depth: float, lam_s: float) -> list[Check]:
    """Punzonamiento de cada pilote a compresión con su reacción (guía CRSI, P1 y P3): gobierna el perímetro de mayor razón.
    Un perímetro que pierde más de dos lados contra los bordes (cabezal angosto) no forma el mecanismo y no se revisa: ahí
    gobierna el cortante a todo el ancho."""
    basis, cap = context.basis, context.cap
    clause = basis.profile.pile_cap.clauses()["pile_punching"]
    checks = []
    for index, pile in enumerate(cap.piles):
        force = context.case.adverse(index, context.spread)
        if force <= _NEGLIGIBLE_FORCE:
            continue
        worst: tuple[float, Check] | None = None
        for label, perimeter, (c1, c2) in _pile_perimeters(cap, index, depth):
            if not perimeter.sides or perimeter.outside > 2:  # noqa: PLR2004 - una esquina pierde dos lados
                continue
            result = two_way_shear(basis.profile, basis.materials, perimeter, (c1, c2, lam_s), TransferredLoad(force, 0.0, 0.0))
            check = _two_way_check(context, result, (PILE_PUNCHING, force, clause, f"Pilote {pile.id} ({label})"))
            ratio = math.inf if check.demand is None or not check.capacity else check.demand / check.capacity
            if worst is None or ratio > worst[0]:
                worst = (ratio, check)
        if worst is not None:
            checks.append(worst[1])
    return checks


def _contexts(basis: Basis, cap: PileCap, cases: list[CapCase], weights: UnitWeighted) -> list[_Context]:
    spread = spread_on_cap(cap)
    return [_Context(basis, cap, case, uniform_load(cap, weights, case.load), spread) for case in cases if case.load.kind == "factored"]


def cap_face_moments(basis: Basis, cap: PileCap, weights: UnitWeighted) -> list[FaceMoments]:
    """Los momentos en las caras de la columna de cada caso mayorado (para la envolvente del despiece, D-129)."""
    return [context.face_moments() for context in _contexts(basis, cap, cap_cases(cap, weights), weights)]


def _structural_checks(basis: Basis, cap: PileCap, cases: list[CapCase], weights: UnitWeighted) -> list[Check]:
    """Casos mayorados: flexión, cortante, punzonamiento, desarrollo, pasadores y aplastamiento."""
    contexts = _contexts(basis, cap, cases, weights)
    if not contexts:
        error = incomplete("El cabezal no tiene casos mayorados", member=cap.id)
        return [Check(STRUCTURAL, Status.INCOMPLETE, (error,), member=cap.id)]
    factored = [context.case for context in contexts]
    moments = [context.face_moments() for context in contexts]
    rules = cap_rules(basis, cap)
    checks = [*mat_flexure_checks(basis, cap, moments, rules), *footing_min_spacing_checks(basis, cap)]
    lam = concrete_lambda(basis.profile, basis.materials)
    if isinstance(lam, StructuredError):
        checks.append(Check(STRUCTURAL, Status.BLOCKED, (lam,), member=cap.id))
    else:
        bottom = mat_rows(cap, cap.bottom, basis.bars)
        depth = (bottom["x"].depth + bottom["y"].depth) / 2
        closely = _closely_spaced(basis, cap)
        lam_s = basis.profile.pile_cap.punching_size_factor(depth, closely)
        for context in contexts:
            for direction in ("x", "y"):
                one_way = _one_way(context, bottom[direction], (lam, closely))
                checks.extend([] if one_way is None else [one_way])
                checks.extend(_face_one_way(context, bottom[direction], lam))
            checks.extend([*_column_punching(context, depth, lam_s), *_face_two_way(context, depth, lam),
                           *_pile_punching(context, depth, lam_s)])
    loads = [(case.case, case.column) for case in factored]
    return [*checks, *column_connection_checks(basis, cap, (moments, rules), loads)]


def pile_cap_checks(basis: Basis, cap: PileCap, soil: PileCapSoil) -> list[Check]:
    """Todas las verificaciones del cabezal: geometría, revisiones geotécnicas con los casos de servicio y estructura con
    los mayorados."""
    cases = cap_cases(cap, soil)
    service = [check for case in cases if case.load.kind == "service" for check in _pile_checks(basis, cap, case, soil)]
    unresisted = [check for case in cases for check in _unresisted(cap, case)]
    return [*_geometry_checks(basis, cap), *service, *unresisted, *_structural_checks(basis, cap, cases, soil)]
