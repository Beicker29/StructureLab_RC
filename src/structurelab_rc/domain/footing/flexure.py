"""Flexión de zapatas aisladas con los casos mayorados (V3D.1; D-054, D-057, D-059).

La carga neta de cada caso sale de domain/footing/loads.py. El momento en
cada cara de la columna es el de la carga neta que actúa a un lado del plano vertical, en todo el ancho (ACI 13.2.6.6,
NSR-10 C.15.4.1). Positivo tracciona la cara inferior; negativo, la superior. La resistencia es la de una sección
rectangular del ancho total con la capa de esa dirección (domain/flexure_strength).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.codes.registry import Profile
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
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import Footing
from structurelab_rc.model.project import Materials

_MATS = {"bottom": "inferior", "top": "superior"}
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
    return f"{kind} malla {_MATS[mat]} (barras {direction})"


def _strength_checks(
    profile: Profile, materials: Materials, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]
) -> list[Check]:
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
                    error = blocked("Momento negativo sin malla superior: el concreto simple no esta implementado (D-059)",
                                    face=face, member=member, case=load_case)
                    checks.append(Check(name, Status.BLOCKED, (error,), clause, member=member, case=load_case, demand=demand,
                                        unit="N*mm"))
                    continue
                row = rows[mat][direction]
                strength = _strength(profile, materials, footing, row)
                if isinstance(strength, StructuredError):
                    checks.append(replace(check_from_errors(name, [strength]), clause=clause, member=member, case=load_case))
                    continue
                values = (("phi", strength.phi), ("Mn", strength.nominal), ("d", row.depth), ("As", row.area),
                          ("et", strength.state.extreme_strain))
                status = Status.PASS if strength.design >= demand else Status.FAIL
                checks.append(Check(name, status, clause=clause, demand=max(demand, 0.0), capacity=strength.design,
                                    unit="N*mm", values=values, note=f"Cara {face} de la columna", member=member,
                                    case=load_case))
    return checks


def _negative(cases: list[FaceMoments], direction: str) -> bool:
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
            if mat == "bottom" or _negative(cases, direction):
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
            if row.band is not None and (mat == "bottom" or _negative(cases, direction)):
                checks.append(_band_check(profile, materials, footing, (mat, row), cases))
    bottom = rows["bottom"]
    first = bottom[footing.bottom.first]
    second = bottom["y" if footing.bottom.first == "x" else "x"]
    measured = profile.footing.footing_depth(footing.h, footing.cover, first.diameter, second.diameter)
    minimum = profile.footing.min_depth()
    checks.append(Check("Altura minima de la zapata", Status.PASS if measured >= minimum else Status.FAIL,
                        clause=clauses["min_depth"], demand=minimum, capacity=measured, unit="mm", member=member))
    return checks


def _band_check(
    profile: Profile, materials: Materials, footing: Footing, mat_row: tuple[str, BarRow], cases: list[FaceMoments]
) -> Check:
    """Franja central de la dirección corta: As en la franja ≥ γs·As, con As el mayor entre el requerido y As,min."""
    mat, row = mat_row
    ratio = profile.footing.min_reinforcement_ratio(materials.fy)
    sign = 1.0 if mat == "bottom" else -1.0
    demand = max([sign * moment for case in cases for moment in case.moments[row.direction]], default=0.0)
    needed = required_area(profile, materials, RectangularSection(row.width, footing.h), row.depth, demand)
    name = _name("Franja central", mat, row.direction)
    clause = profile.footing.clauses()["band"]
    if needed is None:
        error = invalid_input("Ninguna cuantia alcanza el momento de la direccion corta", member=footing.id)
        return Check(name, Status.FAIL, (error,), clause, member=footing.id)
    total = max(needed, ratio * row.width * footing.h)
    beta = max(footing.lx, footing.ly) / min(footing.lx, footing.ly)
    gamma = profile.footing.band_fraction(beta)
    required = gamma * total
    return Check(name, Status.PASS if row.band_area >= required else Status.FAIL, clause=clause, demand=required,
                 capacity=row.band_area, unit="mm2", values=(("gamma s", gamma), ("As", total)), member=footing.id)


def flexure_checks(
    profile: Profile, materials: Materials, footing: Footing, factored: list[FactoredCase], bars: Sequence[RebarSpec]
) -> list[Check]:
    cases = [face_moments(footing, case) for case in factored]
    rows = {"bottom": mat_rows(footing, footing.bottom, bars)}
    if footing.top is not None:
        rows["top"] = mat_rows(footing, footing.top, bars)
    return [*_strength_checks(profile, materials, footing, rows, cases),
            *_section_checks(profile, materials, footing, rows, cases)]
