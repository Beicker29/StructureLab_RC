"""Flexión de zapatas aisladas con los casos mayorados (V3D.1; D-054, D-057, D-059).

La carga neta de cada caso sale de domain/footing/loads.py. El momento en
cada cara de la columna es el de la carga neta que actúa a un lado del plano vertical, en todo el ancho (ACI 13.2.6.6,
NSR-10 C.15.4.1). Positivo tracciona la cara inferior; negativo, la superior. La resistencia es la de una sección
rectangular del ancho total con la capa de esa dirección (domain/flexure_strength). Sin malla superior, el momento
negativo lo resiste el concreto simple (domain/plain_strength), si el perfil lo permite con el nivel sísmico (D-072).
"""

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
from structurelab_rc.model.footing import Footing, FootingBase
from structurelab_rc.model.project import Materials

MAT_NAMES = {"bottom": "inferior", "top": "superior"}
PLAIN = "Flexion concreto simple"
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_AXES = {"x": 0, "y": 1}
_NEGLIGIBLE = 1e-6  # N·mm


@dataclass(frozen=True)
class FaceMoments:
    """Momentos de la carga neta en las caras de la columna, por dirección de las barras: {"x": (+X, −X), "y": (+Y, −Y)}."""

    case: str
    moments: dict[str, tuple[float, float]]


def face_moments(footing: Footing, case: FactoredCase) -> FaceMoments:
    """Momento de la carga neta a un lado de cada cara de la columna, en todo el ancho (ACI 13.2.6.6, NSR-10 C.15.4.1)."""
    faces = column_faces(footing)
    moments = {direction: (case.beyond(footing, _AXES[direction], plus, 1.0)[1],
                           case.beyond(footing, _AXES[direction], minus, -1.0)[1])
               for direction, (plus, minus) in faces.items()}
    return FaceMoments(case.case, moments)


def _strength(profile: Profile, materials: Materials, footing: Footing, row: BarRow) -> MomentStrength | StructuredError:
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


def _strength_checks(basis: Basis, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]) -> list[Check]:
    profile, materials = basis.profile, basis.materials
    clause = profile.footing.clauses()["strength"]
    checks = []
    for case in cases:
        for direction in ("x", "y"):
            positive, negative = _FACES[direction]
            plus, minus = case.moments[direction]
            for mat, sign in (("bottom", 1.0), ("top", -1.0)):
                demand, face = max((sign * plus, positive), (sign * minus, negative))
                if mat == "top" and demand <= _NEGLIGIBLE:
                    continue
                name = _name("Flexion", mat, direction)
                member, load_case = footing.id, case.case
                if mat not in rows:
                    checks.append(plain_check(basis, footing, direction, demand, (face, load_case, f"Cara {face} de la columna")))
                    continue
                row = rows[mat][direction]
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
                                    unit="N*mm", values=values, note=f"Cara {face} de la columna", member=member,
                                    case=load_case))
    return checks


def has_negative_moment(cases: list[FaceMoments], direction: str) -> bool:
    return any(min(case.moments[direction]) < -_NEGLIGIBLE for case in cases)


def _section_checks(
    profile: Profile, materials: Materials, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]
) -> list[Check]:
    """Verificaciones que no dependen del caso: εt, As,min, separación, franja γs y altura mínima."""
    clauses = profile.footing.clauses()
    checks = []
    member = footing.id
    ratio = profile.footing.min_reinforcement_ratio(materials.fy)
    max_spacing = profile.footing.max_bar_spacing(footing.h)
    for mat, mat_rows_ in rows.items():
        bar_sets = {"x": getattr(footing, mat).x, "y": getattr(footing, mat).y}
        for direction, row in mat_rows_.items():
            strength = _strength(profile, materials, footing, row)
            if isinstance(strength, MomentStrength):
                checks.append(replace(net_tensile_strain_check(_name("Deformacion neta de traccion", mat, direction),
                                                               clauses["net_tensile_strain"], profile, materials,
                                                               strength.state.extreme_strain), member=member))
            if mat == "bottom" or has_negative_moment(cases, direction):
                required = ratio * row.width * footing.h
                checks.append(Check(_name("Acero minimo", mat, direction), Status.PASS if row.area >= required else Status.FAIL,
                                    clause=clauses["min_reinforcement"], demand=required, capacity=row.area, unit="mm2",
                                    values=(("cuantia minima", ratio),), member=member))
            spacings = [bar_sets[direction].spacing]
            if bar_sets[direction].band_spacing is not None:
                spacings.append(bar_sets[direction].band_spacing)
            largest = max(spacings)
            checks.append(Check(_name("Separacion maxima", mat, direction), Status.PASS if largest <= max_spacing else Status.FAIL,
                                clause=clauses["spacing"], demand=largest, capacity=max_spacing, unit="mm", member=member))
            if row.band is not None and (mat == "bottom" or has_negative_moment(cases, direction)):
                checks.extend(_band_checks(profile, materials, footing, (mat, row), cases))
    bottom = rows["bottom"]
    first = bottom[footing.bottom.first]
    second = bottom["y" if footing.bottom.first == "x" else "x"]
    measured = profile.footing.footing_depth(footing.h, footing.cover, first.diameter, second.diameter)
    minimum = profile.footing.min_depth()
    checks.append(Check("Altura minima de la zapata", Status.PASS if measured >= minimum else Status.FAIL,
                        clause=clauses["min_depth"], demand=minimum, capacity=measured, unit="mm", member=member))
    return checks


def required_mat_area(
    profile: Profile, materials: Materials, footing: Footing, mat_row: tuple[str, BarRow], cases: list[FaceMoments]
) -> float | None:
    """As requerido de una dirección de una malla: el mayor entre el de flexión de los casos mayorados (momento positivo
    para la inferior, negativo para la superior) y As,min; None si ninguna cuantía alcanza el momento."""
    mat, row = mat_row
    sign = 1.0 if mat == "bottom" else -1.0
    demand = max([sign * moment for case in cases for moment in case.moments[row.direction]], default=0.0)
    needed = required_area(profile, materials, RectangularSection(row.width, footing.h), row.depth, demand)
    if needed is None:
        return None
    return max(needed, profile.footing.min_reinforcement_ratio(materials.fy) * row.width * footing.h)


def _band_checks(
    profile: Profile, materials: Materials, footing: Footing, mat_row: tuple[str, BarRow], cases: list[FaceMoments]
) -> list[Check]:
    """Franja central de la dirección corta (ACI 13.3.3.3(b), NSR-10 C.15.4.4.2): As en la franja ≥ γs·As y fuera de
    ella ≥ (1 − γs)·As (D-087), con As el mayor entre el requerido y As,min."""
    mat, row = mat_row
    total = required_mat_area(profile, materials, footing, mat_row, cases)
    name = _name("Franja central", mat, row.direction)
    outside_name = _name("Fuera de la franja central", mat, row.direction)
    clause = profile.footing.clauses()["band"]
    if total is None:
        error = invalid_input("Ninguna cuantia alcanza el momento de la direccion corta", member=footing.id)
        return [Check(name, Status.FAIL, (error,), clause, member=footing.id)]
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
    rows = {"bottom": mat_rows(footing, footing.bottom, basis.bars)}
    if footing.top is not None:
        rows["top"] = mat_rows(footing, footing.top, basis.bars)
    return [*_strength_checks(basis, footing, rows, cases),
            *_section_checks(basis.profile, basis.materials, footing, rows, cases)]
