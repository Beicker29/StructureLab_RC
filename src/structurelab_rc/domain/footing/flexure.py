"""Flexión de zapatas aisladas con los casos mayorados (V3D.1; D-054, D-057, D-059).

La carga neta de cada caso sale de domain/footing/loads.py. El momento en
cada cara de la columna es el de la carga neta que actúa a un lado del plano vertical, en todo el ancho (ACI 13.2.6.6,
NSR-10 C.15.4.1). Positivo tracciona la cara inferior; negativo, la superior. La resistencia es la de una sección
rectangular del ancho total con la capa de esa dirección (domain/flexure_strength). Sin malla superior, el momento
negativo lo resiste el concreto simple (domain/plain_strength), si el perfil lo permite con el nivel sísmico (D-072).
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import (
    MomentStrength,
    RectangularSection,
    net_tensile_strain_check,
    rectangular_strength,
    required_area,
)
from structurelab_rc.domain.footing.loads import FactoredCase, column_faces
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.plain_strength import plain_rectangular_moment
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.footing import Footing, FootingBase, FootingBody
from structurelab_rc.model.project import Materials

MAT_NAMES = {"bottom": "inferior", "top": "superior"}
PLAIN = "Flexion concreto simple"
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_AXES = {"x": 0, "y": 1}
_NEGLIGIBLE = 1e-6  # N·mm
_BAND_TOLERANCE = 1e-6  # mm


@dataclass(frozen=True)
class Section:
    """Una sección de flexión normal a la dirección de las barras: su coordenada (plane, en mm), su rótulo (la cara, en
    los errores) y la nota de su verificación."""

    plane: float
    label: str
    note: str


@dataclass(frozen=True)
class FaceMoments:
    """Momentos de la carga neta por dirección de las barras en sus secciones: en la zapata, las caras de la columna,
    {"x": (+X, −X), "y": (+Y, −Y)} (sections None); en el cabezal, las secciones de sections, en el mismo orden (D-143)."""

    case: str
    moments: dict[str, tuple[float, ...]]
    sections: dict[str, tuple[Section, ...]] | None = None


Values = tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class SectionRules:
    """Lo que cambia entre la zapata y el cabezal en la flexión de las mallas (D-138): minimum da, para (malla, fila,
    momento de diseño de esa malla), el As que debe proveerse, sus valores y su numeral; min_depth, la altura mínima y
    su numeral; plain_forbidden, el numeral que prohíbe el concreto simple (None si el perfil lo permite)."""

    minimum: Callable[[str, BarRow, float], tuple[float, Values, str]]
    min_depth: tuple[float, str]
    plain_forbidden: str | None = None
    row_at: Callable[[BarRow, float], BarRow] | None = None  # la fila en la sección de cada cara (contorno recortado, D-141)


def footing_rules(profile: Profile, materials: Materials, footing: FootingBody) -> SectionRules:
    """Zapata aislada: As,min = cuantía mínima·b·h (ACI 8.6.1.1, NSR-10 C.10.5.4) y la altura mínima de la zapata."""
    clauses = profile.footing.clauses()
    ratio = profile.footing.min_reinforcement_ratio(materials.fy)

    def minimum(mat: str, row: BarRow, demand: float) -> tuple[float, Values, str]:
        return ratio * row.width * footing.h, (("cuantia minima", ratio),), clauses["min_reinforcement"]

    return SectionRules(minimum, (profile.footing.min_depth(), clauses["min_depth"]))


def design_moment(cases: list[FaceMoments], mat: str, direction: str) -> float:
    """Mayor momento que tracciona la malla en esa dirección: positivo para la inferior, negativo (con signo positivo)
    para la superior; 0 si ninguno."""
    sign = 1.0 if mat == "bottom" else -1.0
    return max([sign * moment for case in cases for moment in case.moments[direction]], default=0.0)


def face_moments(footing: Footing, case: FactoredCase) -> FaceMoments:
    """Momento de la carga neta a un lado de cada cara de la columna, en todo el ancho (ACI 13.2.6.6, NSR-10 C.15.4.1)."""
    faces = column_faces(footing)
    moments: dict[str, tuple[float, ...]] = {direction: (case.beyond(footing, _AXES[direction], plus, 1.0)[1],
                           case.beyond(footing, _AXES[direction], minus, -1.0)[1])
               for direction, (plus, minus) in faces.items()}
    return FaceMoments(case.case, moments)


def face_sections(footing: FootingBody, direction: str) -> tuple[Section, Section]:
    """Las dos caras de la columna de una zapata aislada como secciones (+ y −)."""
    assert isinstance(footing, Footing)
    plus, minus = column_faces(footing)[direction]
    positive, negative = _FACES[direction]
    return Section(plus, positive, f"Cara {positive} de la columna"), Section(minus, negative, f"Cara {negative} de la columna")


def _strength(profile: Profile, materials: Materials, footing: FootingBody, row: BarRow) -> MomentStrength | StructuredError:
    return rectangular_strength(profile, materials, RectangularSection(row.width, footing.h), (SteelLayer(row.depth, row.area),))


def _name(kind: str, mat: str, direction: str) -> str:
    return f"{kind} malla {MAT_NAMES[mat]} (barras {direction})"


def plain_check(basis: Basis, footing: FootingBase, direction: str, demand: float, location: tuple[str, str, str]) -> Check:
    """Momento negativo sin malla superior: concreto simple en todo el ancho, espesor h − 50 mm (D-072). location es la
    cara (o sección), el caso y la nota que describe la sección."""
    return _plain_concrete(basis, footing, (direction, None, None), demand, location)


def plain_principal_check(basis: Basis, footing: FootingBase, demand: float, location: tuple[str, str, str]) -> Check:
    """El momento negativo de la viga de una zapata combinada (dirección principal, D-101) sin barras superiores en esa
    dirección: concreto simple en todo el ancho (D-072)."""
    return _plain_concrete(basis, footing, ("x", None, "direccion principal"), demand, location)


def plain_strip_check(basis: Basis, footing: FootingBase, demand: float, location: tuple[str, str, str], width: float) -> Check:
    """El momento negativo de la franja transversal de una zapata combinada (dirección secundaria), sin barras
    superiores en esa dirección: concreto simple en el ancho de la franja (D-072, D-095)."""
    return _plain_concrete(basis, footing, ("y", width, "direccion secundaria"), demand, location)


def _plain_concrete(basis: Basis, footing: FootingBase, section: tuple[str, float | None, str | None], demand: float,
                    location: tuple[str, str, str]) -> Check:
    direction, width, bars = section
    face, load_case, note = location
    plain = basis.profile.plain
    name = f"{PLAIN} (cara superior, {bars or f'barras {direction}'})"
    clause = plain.clauses()["flexure"]
    member = footing.id
    if not plain.permitted_in_foundations(basis.seismic_level):
        error = invalid_input(f"Momento negativo sin malla superior: {plain.clauses()['seismic']} no permite cimentaciones de "
                              f"concreto simple con nivel sismico {basis.seismic_level}; requiere malla superior (D-072)",
                              face=face, member=member, case=load_case)
        return Check(name, Status.FAIL, (error,), plain.clauses()["seismic"], demand=demand, unit="N*mm", member=member,
                     case=load_case, note=note)
    if width is None:
        width = footing.ly if direction == "x" else footing.lx
    strength = plain_rectangular_moment(basis.profile, basis.materials, width, footing.h, cast_against_soil=True)
    if isinstance(strength, StructuredError):
        return replace(check_from_errors(name, [strength]), clause=clause, member=member, case=load_case)
    values = (("phi", strength.phi), ("Mn", strength.nominal), ("b", width), ("h calculo", strength.thickness),
              ("Sm", strength.modulus), ("fc", basis.materials.fc))
    return Check(name, Status.PASS if strength.design >= demand else Status.FAIL, clause=clause, demand=demand,
                 capacity=strength.design, unit="N*mm", values=values, note=note, member=member,
                 case=load_case)


def _strength_checks(basis: Basis, footing: FootingBody, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments],
                     rules: SectionRules) -> list[Check]:
    profile, materials = basis.profile, basis.materials
    clause = profile.footing.clauses()["strength"]
    checks = []
    for case in cases:
        for direction in ("x", "y"):
            sections = case.sections[direction] if case.sections is not None else face_sections(footing, direction)
            if not sections:  # ninguna sección calculable (cabezal sin las cargas de sus columnas, D-143)
                continue
            for mat, sign in (("bottom", 1.0), ("top", -1.0)):
                demand, face, index = max((sign * moment, section.label, index)
                                          for index, (moment, section) in enumerate(zip(case.moments[direction], sections, strict=True)))
                section = sections[index]
                if mat == "top" and demand <= _NEGLIGIBLE:
                    continue
                name = _name("Flexion", mat, direction)
                member, load_case = footing.id, case.case
                if mat not in rows and rules.plain_forbidden is not None:
                    # El cabezal no admite concreto simple (ACI 14.1.4, NSR-10 C.22.2.1): sin malla superior no cumple.
                    error = invalid_input("Momento negativo sin malla superior: el concreto simple no se permite aqui",
                                          face=face, member=member, case=load_case)
                    checks.append(Check(name, Status.FAIL, (error,), rules.plain_forbidden, demand=demand, unit="N*mm",
                                        member=member, case=load_case, note=section.note))
                    continue
                where = (face, load_case, section.note)
                if mat not in rows:
                    checks.append(plain_check(basis, footing, direction, demand, where))
                    continue
                if mat == "top" and rules.plain_forbidden is None:
                    # Concreto simple primero (decisión del usuario, D-140): si resiste el momento negativo, la malla superior
                    # no se exige; si no alcanza (o el nivel sísmico no lo permite), se revisa la malla.
                    plain = plain_check(basis, footing, direction, demand, where)
                    if plain.status is Status.PASS:
                        checks.append(plain)
                        continue
                row = rows[mat][direction]
                if rules.row_at is not None:
                    row = rules.row_at(row, section.plane)
                strength = _strength(profile, materials, footing, row)
                if isinstance(strength, StructuredError):
                    checks.append(replace(check_from_errors(name, [strength]), clause=clause, member=member, case=load_case))
                    continue
                beta1 = profile.strength_assumptions.beta1(materials.fc)
                # Los datos de la resistencia, sin el procedimiento (D-097).
                values = (("phi", strength.phi), ("Mn", strength.nominal), ("b", row.width), ("h", footing.h), ("d", row.depth),
                          ("As", row.area), ("fc", materials.fc), ("fy", materials.fy),
                          *((("beta1", beta1),) if beta1 is not None else ()), ("a", strength.state.a), ("c", strength.state.c),
                          ("et", strength.state.extreme_strain))
                status = Status.PASS if strength.design >= demand else Status.FAIL
                checks.append(Check(name, status, clause=clause, demand=max(demand, 0.0), capacity=strength.design,
                                    unit="N*mm", values=values, note=section.note, member=member, case=load_case))
    return checks


def has_negative_moment(cases: list[FaceMoments], direction: str) -> bool:
    return any(moment < -_NEGLIGIBLE for case in cases for moment in case.moments[direction])


def plain_resists(basis: Basis, width: float, h: float, demand: float) -> bool:
    """Si el concreto simple resiste un momento negativo (D-140): el nivel sísmico lo permite (D-072) y φMn del concreto
    simple en el ancho b y el espesor h (menos 50 mm contra el suelo) alcanza la demanda. Entonces las barras superiores
    no se exigen."""
    if demand <= _NEGLIGIBLE:
        return True
    if not basis.profile.plain.permitted_in_foundations(basis.seismic_level):
        return False
    strength = plain_rectangular_moment(basis.profile, basis.materials, width, h, cast_against_soil=True)
    return not isinstance(strength, StructuredError) and strength.design >= demand


def top_needed(basis: Basis, footing: FootingBody, given: tuple[list[FaceMoments], SectionRules], direction: str) -> bool:
    """Si la malla superior de una dirección se exige (D-140): hay momento negativo y el concreto simple no lo resiste,
    porque el elemento no lo admite (cabezal), el nivel sísmico no lo permite (D-072) o su φMn no alcanza."""
    cases, rules = given
    if not has_negative_moment(cases, direction):
        return False
    if rules.plain_forbidden is not None:
        return True
    width = footing.ly if direction == "x" else footing.lx
    return not plain_resists(basis, width, footing.h, design_moment(cases, "top", direction))


def _section_checks(basis: Basis, footing: FootingBody, rows: dict[str, dict[str, BarRow]],
                    given: tuple[list[FaceMoments], SectionRules]) -> list[Check]:
    """Verificaciones que no dependen del caso: εt, As,min, separación, franja γs y altura mínima. Las de la malla superior
    que dependen del momento negativo, solo si se exige (D-140)."""
    profile, materials = basis.profile, basis.materials
    cases, rules = given
    clauses = profile.footing.clauses()
    checks = []
    member = footing.id
    max_spacing = profile.footing.max_bar_spacing(footing.h)
    for mat, mat_rows_ in rows.items():
        bar_sets = {"x": getattr(footing, mat).x, "y": getattr(footing, mat).y}
        for direction, row in mat_rows_.items():
            strength = _strength(profile, materials, footing, row)
            if isinstance(strength, MomentStrength):
                checks.append(replace(net_tensile_strain_check(_name("Deformacion neta de traccion", mat, direction),
                                                               clauses["net_tensile_strain"], profile, materials,
                                                               strength.state.extreme_strain), member=member))
            needed = mat == "bottom" or top_needed(basis, footing, given, direction)
            if needed:
                required, values, clause = rules.minimum(mat, row, design_moment(cases, mat, direction))
                checks.append(Check(_name("Acero minimo", mat, direction), Status.PASS if row.area >= required else Status.FAIL,
                                    clause=clause, demand=required, capacity=row.area, unit="mm2", values=values, member=member))
            spacings = [bar_sets[direction].spacing]
            if bar_sets[direction].band_spacing is not None:
                spacings.append(bar_sets[direction].band_spacing)
            largest = max(spacings)
            checks.append(Check(_name("Separacion maxima", mat, direction), Status.PASS if largest <= max_spacing else Status.FAIL,
                                clause=clauses["spacing"], demand=largest, capacity=max_spacing, unit="mm", member=member))
            if row.band is not None and needed:
                checks.extend(_band_checks(profile, materials, footing, (mat, row), (cases, rules)))
    bottom = rows["bottom"]
    first = bottom[footing.bottom.first]
    second = bottom["y" if footing.bottom.first == "x" else "x"]
    measured = profile.footing.footing_depth(footing.h, footing.bottom_face_cover, first.diameter, second.diameter)
    minimum, clause = rules.min_depth
    checks.append(Check("Altura minima", Status.PASS if measured >= minimum else Status.FAIL,
                        clause=clause, demand=minimum, capacity=measured, unit="mm", member=member))
    return checks


def required_mat_area(
    profile: Profile, materials: Materials, footing: FootingBody, mat_row: tuple[str, BarRow],
    given: tuple[list[FaceMoments], SectionRules | None]
) -> float | None:
    """As requerido de una dirección de una malla: el mayor entre el de flexión de los casos mayorados (momento positivo
    para la inferior, negativo para la superior) y el mínimo de las reglas (las de la zapata si son None); None si
    ninguna cuantía alcanza el momento."""
    mat, row = mat_row
    cases, rules = given
    demand = design_moment(cases, mat, row.direction)
    needed = required_area(profile, materials, RectangularSection(row.width, footing.h), row.depth, demand)
    if needed is None:
        return None
    rules = rules or footing_rules(profile, materials, footing)
    return max(needed, rules.minimum(mat, row, demand)[0])


def _band_fills_width(footing: FootingBody, row: BarRow) -> bool:
    """Si la franja central cubre todo el rango útil de las barras (ancho menos los recubrimientos y una barra): entre ella
    y el borde no cabe ninguna barra (D-142)."""
    assert row.band is not None
    half = row.width / 2 - footing.cover - row.diameter / 2
    return row.band[0] <= -half + _BAND_TOLERANCE and row.band[1] >= half - _BAND_TOLERANCE


def _band_checks(
    profile: Profile, materials: Materials, footing: FootingBody, mat_row: tuple[str, BarRow],
    given: tuple[list[FaceMoments], SectionRules]
) -> list[Check]:
    """Franja central de la dirección corta (ACI 13.3.3.3(b), NSR-10 C.15.4.4.2): As en la franja ≥ γs·As y fuera de
    ella ≥ (1 − γs)·As (D-087), con As el mayor entre el requerido y As,min. Si fuera de la franja no cabe ninguna barra,
    todo As va en ella con reparto uniforme (D-142)."""
    mat, row = mat_row
    total = required_mat_area(profile, materials, footing, mat_row, given)
    name = _name("Franja central", mat, row.direction)
    outside_name = _name("Fuera de la franja central", mat, row.direction)
    clause = profile.footing.clauses()["band"]
    if total is None:
        error = invalid_input("Ninguna cuantia alcanza el momento de la direccion corta", member=footing.id)
        return [Check(name, Status.FAIL, (error,), clause, member=footing.id)]
    if _band_fills_width(footing, row):
        # D-142: fuera de la franja no cabe ninguna barra; todo el refuerzo va en ella, con reparto uniforme.
        return [Check(name, Status.PASS if row.band_area >= total else Status.FAIL, clause=clause, demand=total,
                      capacity=row.band_area, unit="mm2", values=(("As", total),), member=footing.id,
                      note="Sin espacio para barras fuera de la franja: todo el refuerzo va en ella (D-142)")]
    beta = max(footing.lx, footing.ly) / min(footing.lx, footing.ly)
    gamma = profile.footing.band_fraction(beta)
    required, outside = gamma * total, (1 - gamma) * total
    values = (("gamma s", gamma), ("As", total))
    return [Check(name, Status.PASS if row.band_area >= required else Status.FAIL, clause=clause, demand=required,
                  capacity=row.band_area, unit="mm2", values=values, member=footing.id),
            Check(outside_name, Status.PASS if row.area - row.band_area >= outside else Status.FAIL, clause=clause, demand=outside,
                  capacity=row.area - row.band_area, unit="mm2", values=values, member=footing.id)]


def flexure_checks(basis: Basis, footing: Footing, factored: list[FactoredCase]) -> list[Check]:
    cases = [face_moments(footing, case) for case in factored]
    return mat_flexure_checks(basis, footing, cases, footing_rules(basis.profile, basis.materials, footing))


def mat_flexure_checks(basis: Basis, footing: FootingBody, cases: list[FaceMoments], rules: SectionRules) -> list[Check]:
    """Flexión de las mallas con los momentos en las caras de la columna de cada caso, ya calculados: los de la presión
    del suelo en la zapata o los de las reacciones de los pilotes en el cabezal (D-138)."""
    rows = {"bottom": mat_rows(footing, footing.bottom, basis.bars)}
    if footing.top is not None:
        rows["top"] = mat_rows(footing, footing.top, basis.bars)
    return [*_strength_checks(basis, footing, rows, cases, rules),
            *_section_checks(basis, footing, rows, (cases, rules))]
