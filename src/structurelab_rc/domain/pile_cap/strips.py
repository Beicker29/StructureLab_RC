"""Franja de cada columna de un cabezal de varias columnas (decisión del usuario, D-143), como las franjas transversales
de la zapata combinada (D-080, D-082).

La dirección principal es la de mayor separación entre los ejes de las columnas (X si empatan); la franja de cada
columna va en la otra (la secundaria), con ancho igual a su lado en la principal más d/2 a cada lado (recortado con el
cabezal), en voladizo desde las dos caras de la columna normales a la secundaria hasta el borde. Su carga, en cada caso
mayorado, es la reacción de los pilotes cuyo centro queda más allá de la cara, con la fracción de ACI 13.4.6.7 (NSR-10
C.15.5.4) según la distancia de su centro al borde de la franja (completa a dpile/2 adentro, nula a dpile/2 afuera),
con su brazo más la tolerancia de mala ubicación y la acción de su cabeza, menos el peso sobre la franja. Resisten las
barras de la dirección secundaria que caen en la franja:
- flexión en la cara con el código de vigas en modo cimentación (resistencia, εt, As mínimo y separación; sin refuerzo
  superficial: las caras de la franja quedan dentro del concreto, D-083); con momento negativo y sin barras superiores en
  la franja, no cumple: el cabezal no admite concreto simple;
- cortante a d de la cara con la reacción interpolada también a lo largo, con el Vc del cabezal (ACI 13.4.6.5 y
  13.4.6.8, NSR-10 C.11.11).
Si otra columna queda en la franja más allá de una cara, ese voladizo no se revisa (BLOCKED, falta implementación).
"""

from dataclasses import replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.station import flexure_station_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.pile_cap.loads import AXES, CapAnalysis, FactoredCap
from structurelab_rc.domain.pile_cap.shear import closely_spaced
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.model.pile_cap import CapColumn, PileCap
from structurelab_rc.model.project import Demands, Member, Section, Station
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, ReinforcementLayout

STRIP = "Franja de la columna"
STRIP_SHEAR = "Franja de la columna: cortante"
_TOLERANCE = 1e-6  # mm
_NEGLIGIBLE_MOMENT = 1e3  # N·mm


def directions(cap: PileCap) -> tuple[str, str]:
    """(principal, secundaria): la principal es la de mayor separación entre los ejes de las columnas."""
    xs, ys = [column.offset_x for column in cap.columns], [column.offset_y for column in cap.columns]
    return ("x", "y") if max(xs) - min(xs) >= max(ys) - min(ys) else ("y", "x")


def strip_limits(cap: PileCap, column: CapColumn, depth: float) -> tuple[float, float]:
    """El ancho de la franja a lo largo de la dirección principal: el lado de la columna más d/2 a cada lado, recortado
    con el cabezal."""
    principal, _ = directions(cap)
    centre, size, half = ((column.offset_x, column.cx, cap.lx / 2) if principal == "x" else (column.offset_y, column.cy, cap.ly / 2))
    return max(centre - size / 2 - depth / 2, -half), min(centre + size / 2 + depth / 2, half)


def _across(cap: PileCap, item: FactoredCap, limits: tuple[float, float], position: float) -> float:
    """Fracción de la reacción de un pilote que carga la franja según la distancia de su centro al borde (13.4.6.7)."""
    inside = min(position - limits[0], limits[1] - position)
    return item.share(inside, cap.pile.size)


def _demands(item: FactoredCap, column: CapColumn, given: tuple[tuple[float, float], float, float], depth: float) -> tuple[float, float]:
    """Momento en la cara (plane, outward) y cortante a d de ella, de la franja de ancho limits, en N·mm y N."""
    limits, plane, outward = given
    cap = item.cap
    principal, secondary = directions(cap)
    along, across = AXES[secondary], AXES[principal]
    tolerance, size, lever = cap.mislocation, cap.pile.size, cap.pile.embedment - cap.h / 2
    moment = shear = 0.0
    for index, pile in enumerate(cap.piles):
        position = (pile.x, pile.y)
        portion = _across(cap, item, limits, position[across])
        if portion <= 0:
            continue
        reaction = portion * item.reaction(index)
        arm = outward * (position[along] - plane) + tolerance
        shear += item.share(arm - depth, size) * reaction
        if arm <= 0:
            continue
        moment += reaction * arm
        (vx, vy), (mx, my) = item.case.forces.shears[index], item.case.forces.moments[index]
        moment += portion * (-outward * (my + lever * vx) if along == 0 else outward * (mx - lever * vy))
    half = (cap.lx if along == 0 else cap.ly) / 2
    length = max(half - outward * plane, 0.0)
    width = limits[1] - limits[0]
    moment -= item.load * width * length * length / 2
    shear -= item.load * width * max(length - depth, 0.0)
    return moment, shear


def _blocking(cap: PileCap, column: CapColumn, limits: tuple[float, float], given: tuple[float, float]) -> str | None:
    """La otra columna que queda en la franja más allá de la cara, si la hay."""
    plane, outward = given
    principal, secondary = directions(cap)
    for other in cap.columns:
        if other is column:
            continue
        position = (other.offset_x, other.offset_y)
        if limits[0] < position[AXES[principal]] < limits[1] and outward * (position[AXES[secondary]] - plane) > 0:
            return other.id
    return None


def _member(cap: PileCap, limits: tuple[float, float], rows: tuple[BarRow, BarRow | None]) -> Member:
    """La franja como viga: ancho de franja × h, con las barras inferiores y superiores de la dirección secundaria que
    caen en ella (x desde el borde de la franja, profundidad desde la cara superior)."""
    bottom, top = rows
    x0, x1 = limits
    layers = []
    for row, depth in ((bottom, bottom.depth), (top, None if top is None else cap.h - top.depth)):
        if row is None or depth is None:
            continue
        inside = [position for position in row.positions if x0 - _TOLERANCE <= position <= x1 + _TOLERANCE]
        if inside:
            layers.append(BarLayer(depth=depth, role="flexure",
                                   bars=tuple(BarPosition(designation=row.designation, x=position - x0) for position in inside)))
    layout = ReinforcementLayout(layers=tuple(layers), stirrups=None)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    return Member.model_construct(id=cap.id, type="beam", min_steel_exception=False, statically_determinate=None,
                                  length=cap.ly if directions(cap)[1] == "y" else cap.lx,
                                  section=Section(bw=x1 - x0, h=cap.h, cover=cap.cover), stations=(placeholder,))


def _inside_area(row: BarRow | None, limits: tuple[float, float]) -> float:
    if row is None:
        return 0.0
    return sum(row.bar_area for position in row.positions if limits[0] - _TOLERANCE <= position <= limits[1] + _TOLERANCE)


def _face_checks(basis: Basis, item: FactoredCap, column: CapColumn, given: tuple[tuple[float, float], float, float, str],
                 rows: tuple[BarRow, BarRow | None]) -> list[Check]:
    limits, plane, outward, label = given
    cap = item.cap
    bottom, top = rows
    note = f"{STRIP} {column.id}, cara {label}"
    moment, shear = _demands(item, column, (limits, plane, outward), bottom.depth)
    width = limits[1] - limits[0]
    checks: list[Check] = []
    if moment < -_NEGLIGIBLE_MOMENT and _inside_area(top, limits) <= 0:
        clause = basis.profile.pile_cap.clauses()["plain"]
        error = invalid_input("Momento negativo en la franja sin barras superiores: el concreto simple no se permite aqui",
                              member=cap.id, case=item.case.case)
        checks.append(Check(f"{STRIP}: flexion", Status.FAIL, (error,), clause, member=cap.id, case=item.case.case,
                            demand=-moment, unit="N*mm", note=note))
    else:
        member = _member(cap, limits, rows)
        station = Station.model_construct(z=0.0, layout=member.stations[0].layout, case=item.case.case,
                                          demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=0.0, v3=0.0, tu=0.0))
        given_input = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False)
        checks += [replace(check, note=f"{note}: {check.note}" if check.note else note, member=cap.id, case=item.case.case, z=None)
                   for check in flexure_station_checks(given_input)]
    checks.append(_shear_check(basis, item, (shear, moment), (width, bottom, limits), note))
    return checks


def _shear_check(basis: Basis, item: FactoredCap, demand: tuple[float, float], section: tuple[float, BarRow, tuple[float, float]],
                 note: str) -> Check:
    profile, materials, cap = basis.profile, basis.materials, item.cap
    shear, moment = demand
    width, bottom, limits = section
    clause = profile.pile_cap.clauses()["one_way_shear"]
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return Check(STRIP_SHEAR, Status.BLOCKED, (lam,), clause, member=cap.id, case=item.case.case, note=note)
    rho = _inside_area(bottom, limits) / (width * bottom.depth)
    closely = closely_spaced(basis, cap)
    vc = profile.pile_cap.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=width, d=bottom.depth, h=cap.h, rho_w=rho,
                                                 vu=abs(shear), mu=abs(moment), closely_spaced=closely)
    phi = profile.shear.strength_reduction()
    capacity = phi * vc
    return Check(STRIP_SHEAR, Status.PASS if abs(shear) <= capacity else Status.FAIL, clause=clause, member=cap.id,
                 case=item.case.case, demand=abs(shear), capacity=capacity, unit="N",
                 values=(("phi", phi), ("Vc", vc), ("bw", width), ("d", bottom.depth), ("rho w", rho)),
                 note=f"{note}, seccion a d de la cara, reacciones interpoladas")


def strip_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Las franjas de las columnas de un cabezal de varias columnas en cada caso mayorado (con +ΔR y −ΔR con las cargas
    de las columnas); [] con una columna (rige la franja central γs, D-138)."""
    if len(cap.columns) < 2:  # noqa: PLR2004 - varias columnas
        return []
    _, secondary = directions(cap)
    bottom = mat_rows(cap, cap.bottom, basis.bars)[secondary]
    top = None if cap.top is None else mat_rows(cap, cap.top, basis.bars)[secondary]
    checks = []
    items = [*analysis.factored, *(replace(item, sense=-1.0) for item in analysis.factored if item.sense)]
    for column in cap.columns:
        limits = strip_limits(cap, column, bottom.depth)
        centre, size = (column.offset_x, column.cx) if secondary == "x" else (column.offset_y, column.cy)
        plus, minus = ("+X", "-X") if secondary == "x" else ("+Y", "-Y")
        for plane, outward, label in ((centre + size / 2, 1.0, plus), (centre - size / 2, -1.0, minus)):
            other = _blocking(cap, column, limits, (plane, outward))
            if other is not None:
                error = blocked(f"La columna {other} queda en la franja de la columna {column.id} mas alla de su cara {label}: "
                                "falta implementacion", member=cap.id)
                checks.append(Check(f"{STRIP}: flexion", Status.BLOCKED, (error,), member=cap.id,
                                    note=f"{STRIP} {column.id}, cara {label}"))
                continue
            for item in items:
                checks += _face_checks(basis, item, column, (limits, plane, outward, label), (bottom, top))
    return checks


def unresolved_checks(cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Las secciones de flexión que no se pudieron calcular porque faltan las cargas de las columnas (D-143)."""
    return [Check("Flexion: secciones", Status.INCOMPLETE,
                  (incomplete(f"{note}: faltan las cargas de las columnas de los dos lados; no se reparten (D-143)",
                              member=cap.id, case=case),), member=cap.id, case=case, note=note)
            for case, note in analysis.unresolved]
