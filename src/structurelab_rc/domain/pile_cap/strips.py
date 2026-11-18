"""Franja de cada columna de un cabezal de varias columnas (decisiones del usuario, D-143 y D-145), como las franjas
transversales de la zapata combinada (D-080, D-082), analizada por secciones de cuerpo libre dentro de su ancho.

Dirección de las franjas: con las columnas alineadas a lo largo de X (todas con la misma y), las franjas van en Y; a lo
largo de Y, en X; si no están alineadas, en las dos direcciones (D-145). La franja de una columna en una dirección tiene
el ancho de su lado en la otra más d/2 a cada lado (recortado con el cabezal), con d el de las barras de esa dirección.

Secciones a lo largo de la franja (D-145): las caras de las columnas que tocan la franja y secciones cada 50 mm fuera
de ellas, con el mismo cuerpo libre de la flexión a todo el ancho (domain/pile_cap/loads.py, D-143): el lado con menos
columnas de la franja (los dos si empatan). De ese lado entran los pilotes con la fracción de ACI 13.4.6.7 (NSR-10
C.15.5.4) según la distancia de su centro al borde de la franja (completa a dpile/2 adentro, nula a dpile/2 afuera), con
su brazo más la tolerancia de mala ubicación y la acción de su cabeza; las columnas de la franja, completas, con su fuerza
vertical y la acción de su base; y el peso sobre la franja. Con las columnas alineadas, son los voladizos desde las caras
de D-143. Resisten las barras de la dirección de la franja que caen en ella:
- flexión en la sección de mayor momento positivo (malla inferior) y en la de mayor negativo (superior), con el código de
  vigas en modo cimentación (resistencia y εt) y el As mínimo del cabezal (D-140) en el ancho de la franja; la separación
  es la de las mallas del cabezal (3h y 450 mm) y no hay refuerzo superficial (las caras de la franja quedan dentro del
  concreto, D-083); con momento negativo y sin barras superiores en la franja, no cumple: el cabezal no admite concreto
  simple;
- cortante a d de las caras de sus columnas, con la reacción interpolada también a lo largo y el Vc del cabezal
  (ACI 13.4.6.5 y 13.4.6.8, NSR-10 C.11.11); gobierna la sección de mayor razón.
Una sección cuyo lado necesita la carga de una columna desconocida (cargas de los pilotes) no se calcula de ese lado; si no
queda ninguna sección, la franja queda INCOMPLETE.
"""

from dataclasses import dataclass, replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.flexure import NET_TENSILE_STRAIN
from structurelab_rc.domain.beam.flexure import STRENGTH as FLEXURE_STRENGTH
from structurelab_rc.domain.beam.station import flexure_station_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.flexure import Section
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, positions_within
from structurelab_rc.domain.pile_cap.flexure import cap_rules
from structurelab_rc.domain.pile_cap.loads import AXES, SCAN_STEP, CapAnalysis, FactoredCap, column_faces_along, free_sides
from structurelab_rc.domain.pile_cap.shear import cap_strength
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, incomplete, invalid_input
from structurelab_rc.model.pile_cap import CapColumn, PileCap
from structurelab_rc.model.project import Demands, Member, Station
from structurelab_rc.model.project import Section as BeamSection
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, ReinforcementLayout

STRIP = "Franja de la columna"
STRIP_SHEAR = "Franja de la columna: cortante"
# De la viga, la resistencia y εt, con el nombre de la franja (un solo prefijo para sus revisiones).
_BEAM_CHECKS = {FLEXURE_STRENGTH: f"{STRIP}: resistencia", NET_TENSILE_STRAIN: f"{STRIP}: deformacion neta de traccion"}
_TOLERANCE = 1e-6  # mm
_NEGLIGIBLE_MOMENT = 1e3  # N·mm
_ALIGNED = 1e-6  # mm


@dataclass(frozen=True)
class Strip:
    """La franja de una columna en una dirección (along, la de sus barras): su ancho en la otra (limits), las columnas
    que la tocan y las barras inferiores y superiores de esa dirección."""

    column: int
    along: str
    limits: tuple[float, float]
    members: tuple[int, ...]
    rows: tuple[BarRow, BarRow | None]

    @property
    def width(self) -> float:
        return self.limits[1] - self.limits[0]

    @property
    def across(self) -> int:
        return 1 - AXES[self.along]


def strip_directions(cap: PileCap) -> list[str]:
    """Las direcciones de las franjas (D-145): la perpendicular a la línea de las columnas si están alineadas a lo largo
    de X o de Y; si no, las dos."""
    xs, ys = [column.offset_x for column in cap.columns], [column.offset_y for column in cap.columns]
    if max(ys) - min(ys) <= _ALIGNED:
        return ["y"]
    if max(xs) - min(xs) <= _ALIGNED:
        return ["x"]
    return ["x", "y"]


def strips(cap: PileCap, basis: Basis) -> list[Strip]:
    """Las franjas de todas las columnas en sus direcciones."""
    found = []
    for along in strip_directions(cap):
        bottom = mat_rows(cap, cap.bottom, basis.bars)[along]
        top = None if cap.top is None else mat_rows(cap, cap.top, basis.bars)[along]
        across = 1 - AXES[along]
        half = (cap.lx, cap.ly)[across] / 2
        for index, column in enumerate(cap.columns):
            centre, size = (column.offset_x, column.cx) if across == 0 else (column.offset_y, column.cy)
            limits = (max(centre - size / 2 - bottom.depth / 2, -half), min(centre + size / 2 + bottom.depth / 2, half))
            # Una columna cuenta en la franja si la toca, con toda su carga (decisión del usuario, D-145).
            members = tuple(i for i, other in enumerate(cap.columns)
                            if _overlaps(_span(other, across), limits))
            found.append(Strip(index, along, limits, members, (bottom, top)))
    return found


def _span(column: CapColumn, axis: int) -> tuple[float, float]:
    """(centro, lado) de una columna a lo largo de x (axis = 0) o de y."""
    return (column.offset_x, column.cx) if axis == 0 else (column.offset_y, column.cy)


def _overlaps(span: tuple[float, float], limits: tuple[float, float]) -> bool:
    centre, size = span
    return centre - size / 2 < limits[1] - _TOLERANCE and centre + size / 2 > limits[0] + _TOLERANCE


def _spans(cap: PileCap, strip: Strip) -> list[tuple[float, float]]:
    """(centro, lado) a lo largo de la franja de cada columna de la franja."""
    return [_span(cap.columns[index], AXES[strip.along]) for index in strip.members]


def _sections(cap: PileCap, strip: Strip) -> list[Section]:
    """Las caras de las columnas de la franja y secciones cada 50 mm fuera de ellas, a lo largo de la franja."""
    axis = AXES[strip.along]
    name = strip.along
    sections = [Section(plane, label, f"cara {label} de la columna {cap.columns[index].id}")
                for index in strip.members for plane, _, label in column_faces_along(cap.columns[index], axis)]
    half = (cap.lx, cap.ly)[axis] / 2
    step = 1
    while (plane := -half + step * SCAN_STEP) < half - _TOLERANCE:
        if not any(centre - size / 2 - _TOLERANCE <= plane <= centre + size / 2 + _TOLERANCE for centre, size in _spans(cap, strip)):
            sections.append(Section(plane, f"{name} = {plane:g}", f"seccion {name} = {plane:.0f} mm"))
        step += 1
    return sections


def _action(item: FactoredCap, strip: Strip, plane: float, outward: float) -> tuple[float, float] | None:
    """(momento respecto al plano, cortante con la reacción interpolada a lo largo) de lo que queda más allá del plano
    dentro de la franja; None si falta la carga de una columna de la franja más allá."""
    cap = item.cap
    along, across = AXES[strip.along], strip.across
    tolerance, size = cap.mislocation, cap.pile.size
    moment = shear = 0.0
    for index, pile in enumerate(cap.piles):
        position = (pile.x, pile.y)
        # La tolerancia del lado desfavorable acerca el pilote a la franja (decisión del usuario, D-145).
        inside = min(position[across] - strip.limits[0], strip.limits[1] - position[across]) + tolerance
        portion = item.share(inside, size)
        if portion <= 0:
            continue
        reaction = portion * item.reaction(index)
        arm = outward * (position[along] - plane) + tolerance
        shear += item.share(arm, size) * reaction
        if arm <= 0:
            continue
        about_x, about_y = item.pile_head(index)
        moment += reaction * arm + portion * outward * (about_y if along == 0 else about_x)
    beyond = item.columns_beyond(along, plane, outward)
    for index in strip.members:
        if index not in beyond:
            continue
        action = item.column_action(index, along, plane, outward)
        if action is None:
            return None
        moment += action[0]
        shear += action[1]
    half = (cap.lx, cap.ly)[along] / 2
    length = max(half - outward * plane, 0.0)
    return moment - item.load * strip.width * length * length / 2, shear - item.load * strip.width * length


def _member(cap: PileCap, strip: Strip) -> Member:
    """La franja como viga: ancho de franja × h, con las barras inferiores y superiores de su dirección que caen en ella
    (x desde el borde de la franja, profundidad desde la cara superior)."""
    bottom, top = strip.rows
    x0, x1 = strip.limits
    layers = []
    for row, depth in ((bottom, bottom.depth), (top, None if top is None else cap.h - top.depth)):
        if row is None or depth is None:
            continue
        inside = positions_within(row, strip.limits)
        if inside:
            layers.append(BarLayer(depth=depth, role="flexure",
                                   bars=tuple(BarPosition(designation=row.designation, x=position - x0) for position in inside)))
    layout = ReinforcementLayout(layers=tuple(layers), stirrups=None)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    return Member.model_construct(id=cap.id, type="beam", min_steel_exception=False, statically_determinate=None,
                                  length=(cap.lx, cap.ly)[AXES[strip.along]],
                                  section=BeamSection(bw=x1 - x0, h=cap.h, cover=cap.cover), stations=(placeholder,))


def _flexure_checks(basis: Basis, item: FactoredCap, strip: Strip, given: tuple[float, str]) -> list[Check]:
    """Resistencia y εt (código de vigas) y As mínimo del cabezal de la sección con el momento dado."""
    moment, note = given
    cap = item.cap
    bottom, top = strip.rows
    if moment < 0 and (top is None or not positions_within(top, strip.limits)):
        error = invalid_input("Momento negativo en la franja sin barras superiores: el concreto simple no se permite aqui",
                              member=cap.id, case=item.case.case)
        return [Check(f"{STRIP}: flexion", Status.FAIL, (error,), basis.profile.pile_cap.clauses()["plain"], member=cap.id,
                      case=item.case.case, demand=-moment, unit="N*mm", note=note)]
    member = _member(cap, strip)
    station = Station.model_construct(z=0.0, layout=member.stations[0].layout, case=item.case.case,
                                      demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=0.0, v3=0.0, tu=0.0))
    given_input = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False)
    # De la viga, la resistencia y εt; el As mínimo es el del cabezal (D-140) y la separación, la de sus mallas (D-143).
    checks = [replace(check, name=_BEAM_CHECKS[check.name], note=f"{note}: {check.note}" if check.note else note, member=cap.id,
                      case=item.case.case, z=None)
              for check in flexure_station_checks(given_input) if check.name in _BEAM_CHECKS]
    mat, row = ("bottom", bottom) if moment >= 0 else ("top", top)
    assert row is not None
    section = replace(row, width=strip.width, positions=positions_within(row, strip.limits), band=None, band_positions=())
    required, values, clause = cap_rules(basis, cap).minimum(mat, section, abs(moment))
    checks.append(Check(f"{STRIP}: acero minimo", Status.PASS if section.area >= required else Status.FAIL, clause=clause,
                        member=cap.id, case=item.case.case, demand=required, capacity=section.area, unit="mm2",
                        values=(*values, ("b", section.width)), note=note))
    return checks


def _shear_check(basis: Basis, item: FactoredCap, strip: Strip, title: str) -> Check | None:
    """Cortante a d de las caras de las columnas de la franja (sin las secciones que caen en una columna o fuera del
    cabezal); gobierna la de mayor razón. None si no hay ninguna sección."""
    profile, materials, cap = basis.profile, basis.materials, item.cap
    clause = profile.pile_cap.clauses()["one_way_shear"]
    strength = cap_strength(basis, cap)
    if isinstance(strength, StructuredError):
        return Check(STRIP_SHEAR, Status.BLOCKED, (strength,), clause, member=cap.id, case=item.case.case, note=title)
    bottom = strip.rows[0]
    rho = len(positions_within(bottom, strip.limits)) * bottom.bar_area / (strip.width * bottom.depth)
    phi = profile.shear.strength_reduction()
    axis = AXES[strip.along]
    half = (cap.lx, cap.ly)[axis] / 2
    worst: tuple[float, float, float, float, str] | None = None
    for index in strip.members:
        for face, outward_face, label in column_faces_along(cap.columns[index], axis):
            plane = face + outward_face * bottom.depth
            if abs(plane) >= half or any(c - size / 2 < plane < c + size / 2 for c, size in _spans(cap, strip)):
                continue
            for outward in free_sides(cap, axis, plane, strip.members):
                action = _action(item, strip, plane, outward)
                if action is None:
                    continue
                moment, shear = action
                vc = profile.pile_cap.one_way_concrete_shear(fc=materials.fc, lam=strength.lam, bw=strip.width, d=bottom.depth,
                                                             h=cap.h, rho_w=rho, vu=abs(shear), mu=abs(moment),
                                                             closely_spaced=strength.closely)
                if worst is None or abs(shear) / (phi * vc) > worst[0]:
                    worst = (abs(shear) / (phi * vc), abs(shear), phi * vc, vc, f"cara {label} de la columna {cap.columns[index].id}")
    if worst is None:
        return None
    _, demand, capacity, vc, where = worst
    return Check(STRIP_SHEAR, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=cap.id,
                 case=item.case.case, demand=demand, capacity=capacity, unit="N",
                 values=(("phi", phi), ("Vc", vc), ("bw", strip.width), ("d", bottom.depth), ("rho w", rho)),
                 note=f"{title}, seccion a d de la {where}, reacciones interpoladas")


def _strip_case(basis: Basis, item: FactoredCap, strip: Strip) -> list[Check]:
    cap = item.cap
    title = f"{STRIP} {cap.columns[strip.column].id} (barras {strip.along})"
    values: list[tuple[float, Section]] = []
    missing = False
    for section in _sections(cap, strip):
        for outward in free_sides(cap, AXES[strip.along], section.plane, strip.members):
            action = _action(item, strip, section.plane, outward)
            if action is None:
                missing = True
                continue
            values.append((action[0], section))
    clause = basis.profile.footing.clauses()["strength"]
    if not values:
        error = incomplete(f"{title}: faltan las cargas de sus columnas; no se reparten (D-143)", member=cap.id, case=item.case.case)
        return [Check(f"{STRIP}: flexion", Status.INCOMPLETE, (error,), clause, member=cap.id, case=item.case.case, note=title)]
    checks = []
    positive = max(values, key=lambda value: value[0])
    if positive[0] > _NEGLIGIBLE_MOMENT:
        checks += _flexure_checks(basis, item, strip, (positive[0], f"{title}, {positive[1].note}"))
    negative = min(values, key=lambda value: value[0])
    if negative[0] < -_NEGLIGIBLE_MOMENT:
        checks += _flexure_checks(basis, item, strip, (negative[0], f"{title}, {negative[1].note}"))
    # El cortante con +ΔR, como el del cabezal; la flexión con +ΔR y −ΔR (D-145).
    shear = _shear_check(basis, item, strip, title) if item.sense >= 0 else None
    checks += [] if shear is None else [shear]
    if missing:
        error = incomplete(f"{title}: secciones sin las cargas de sus columnas de un lado; no se reparten (D-143)",
                           member=cap.id, case=item.case.case)
        checks.append(Check(f"{STRIP}: secciones", Status.INCOMPLETE, (error,), clause, member=cap.id, case=item.case.case, note=title))
    return checks


def strip_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Las franjas de las columnas de un cabezal de varias columnas en cada caso mayorado (con +ΔR y −ΔR con las cargas
    de las columnas); [] con una columna (rige la franja central γs, D-138)."""
    if len(cap.columns) < 2:  # noqa: PLR2004 - varias columnas
        return []
    items = [*analysis.factored, *(replace(item, sense=-1.0) for item in analysis.factored if item.sense)]
    return [check for strip in strips(cap, basis) for item in items for check in _strip_case(basis, item, strip)]


def unresolved_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Las secciones de flexión que no se pudieron calcular porque faltan las cargas de las columnas (D-143)."""
    clause = basis.profile.footing.clauses()["strength"]
    return [Check("Flexion: secciones", Status.INCOMPLETE,
                  (incomplete(f"{note}: faltan las cargas de las columnas de los dos lados; no se reparten (D-143)",
                              member=cap.id, case=case),), clause, member=cap.id, case=case, note=note)
            for case, note in analysis.unresolved]
