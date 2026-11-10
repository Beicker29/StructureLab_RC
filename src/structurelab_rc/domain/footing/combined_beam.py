"""Viga en la dirección larga de una zapata combinada con los casos mayorados (D-080, V3J.2).

La zapata es rígida: la carga neta hacia arriba es la presión de Bellos y Bakas de la resultante de las dos columnas
menos las cargas uniformes (domain/footing/loads.py), integrada en todo el ancho. Cada columna baja en su eje la fuerza
vertical de `column_vertical` y el par My + (h + pedestal)·Vx, con los momentos tomados en el plano de la base, el
mismo de la resultante: así los diagramas cierran en cero en los dos extremos. Para una sección en x, con el cuerpo
libre a su izquierda:

    V(x) = ∫q dA − Σ F_c                         (columnas con x_c < x)
    M(x) = x·∫q dA − ∫x·q dA − Σ [F_c·(x − x_c) − C_c]

M positivo tracciona la cara inferior (barras inferiores x); negativo, la superior (barras superiores x o, sin ellas,
concreto simple, D-072). Los momentos se revisan en las cuatro caras de las columnas y en los extremos de cada tramo
(donde V = 0); el cortante, a d de cada cara, hacia el tramo, sin estribos (Vu ≤ φVc). El acero mínimo es el de vigas
con su excepción de 4/3 (ACI 9.6.1.2 y 9.6.1.3, NSR-10 C.10.5.1 y C.10.5.3), la separación máxima la de
`combined_max_bar_spacing` del perfil y la sección es la rectangular del ancho total. Mx, Vy y la posición en Y de
las columnas no cambian la viga: actúan en el sentido transversal.
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
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.flexure import plain_check
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_row
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Materials

FLEXURE = "Viga larga: flexion"
SHEAR = "Viga larga: cortante en una direccion"
MIN_REINFORCEMENT = "Viga larga: acero minimo"
STRAIN = "Viga larga: deformacion neta de traccion"
SPACING = "Viga larga: separacion maxima"
BARS = {"bottom": "barras inferiores x", "top": "barras superiores x"}
_NEGLIGIBLE = 1e-6  # N·mm
_SUBDIVISIONS = 64
_BISECTION_STEPS = 200


@dataclass(frozen=True)
class ColumnForce:
    """Fuerza vertical hacia abajo (N) y par (N·mm, positivo según My) de una columna en su eje x; half = cx/2."""

    id: str
    x: float
    half: float
    force: float
    couple: float


@dataclass(frozen=True)
class Section:
    x: float
    label: str


@dataclass(frozen=True)
class BeamCase:
    """Un caso mayorado de la viga larga: la carga neta del suelo y las dos columnas ordenadas por x."""

    pressure: FactoredCase
    columns: tuple[ColumnForce, ...]
    lx: float
    ly: float

    @property
    def case(self) -> str:
        return self.pressure.case

    def _left(self, x: float) -> tuple[float, float]:
        hx, hy = self.lx / 2, self.ly / 2
        if x <= -hx:
            return 0.0, 0.0
        force, sx, _ = self.pressure.net(((-hx, -hy), (x, -hy), (x, hy), (-hx, hy)))
        return force, sx

    def shear(self, x: float) -> float:
        force, _ = self._left(x)
        return force - sum(column.force for column in self.columns if column.x < x)

    def moment(self, x: float) -> float:
        force, sx = self._left(x)
        return x * force - sx - sum(column.force * (x - column.x) - column.couple for column in self.columns if column.x < x)


def beam_case(footing: CombinedFooting, soil: Soil, pressure: FactoredCase, loads: tuple[FootingLoad, ...]) -> BeamCase:
    height = footing.h + footing.pedestal_height
    columns = sorted((ColumnForce(column.id, column.x, column.cx / 2, column_vertical(footing, soil, column, load),
                                  load.my + height * load.vx)
                      for column, load in zip(footing.columns, loads, strict=True)), key=lambda column: column.x)
    return BeamCase(pressure, tuple(columns), footing.lx, footing.ly)


def _regions(beam: BeamCase) -> list[tuple[float, float, str]]:
    """Los tres tramos sin columna: voladizo −X, entre columnas y voladizo +X."""
    first, second = beam.columns
    return [(-beam.lx / 2, first.x - first.half, "voladizo -X"), (first.x + first.half, second.x - second.half, "entre columnas"),
            (second.x + second.half, beam.lx / 2, "voladizo +X")]


def _faces(beam: BeamCase) -> list[tuple[Section, float]]:
    """Las cuatro caras con la dirección hacia su tramo (−1 a la izquierda, +1 a la derecha)."""
    return [(Section(column.x + side * column.half, f"cara {'+' if side > 0 else '-'}X de la columna {column.id}"), side)
            for column in beam.columns for side in (-1.0, 1.0)]


def _zero_shear(beam: BeamCase, low: float, high: float) -> list[float]:
    """Las x del tramo donde V cambia de signo (extremos de M), por muestreo y bisección."""
    if high - low <= 0:
        return []
    step = (high - low) / _SUBDIVISIONS
    points = [low + index * step for index in range(_SUBDIVISIONS + 1)]
    roots = []
    for a, b in zip(points, points[1:], strict=False):
        va, vb = beam.shear(a), beam.shear(b)
        if va == 0 and a > low:
            roots.append(a)
            continue
        if va * vb >= 0:
            continue
        for _ in range(_BISECTION_STEPS):
            middle = (a + b) / 2
            if beam.shear(middle) * va > 0:
                a = middle
            else:
                b = middle
            if b - a <= 1e-9 * beam.lx:
                break
        roots.append((a + b) / 2)
    return roots


def moment_sections(beam: BeamCase) -> list[Section]:
    sections = [section for section, _ in _faces(beam)]
    for low, high, label in _regions(beam):
        sections += [Section(x, f"{label}, V = 0") for x in _zero_shear(beam, low, high)]
    return sections


def shear_sections(beam: BeamCase, depth: float) -> list[Section]:
    """A d de cada cara, hacia su tramo, si la sección queda dentro de ese tramo."""
    regions = _regions(beam)
    sections = []
    for face, side in _faces(beam):
        x = face.x + side * depth
        if any(low < x < high and (low <= face.x <= high) for low, high, _ in regions):
            sections.append(Section(x, f"a d de la {face.label}"))
    return sections


def _strength(profile: Profile, materials: Materials, footing: CombinedFooting, row: BarRow) -> MomentStrength | StructuredError:
    return rectangular_strength(profile, materials, RectangularSection(row.width, footing.h), (SteelLayer(row.depth, row.area),))


def _flexure_check(basis: Basis, footing: CombinedFooting, row: BarRow, demand: tuple[float, Section, str], bars: str) -> Check:
    profile, materials = basis.profile, basis.materials
    moment, section, case = demand
    name = f"{FLEXURE} ({bars})"
    clause = profile.flexure.clauses()["strength"]
    strength = _strength(profile, materials, footing, row)
    if isinstance(strength, StructuredError):
        return replace(check_from_errors(name, [strength]), clause=clause, member=footing.id, case=case)
    values = (("phi", strength.phi), ("Mn", strength.nominal), ("d", row.depth), ("As", row.area),
              ("et", strength.state.extreme_strain), ("x", section.x))
    return Check(name, Status.PASS if strength.design >= moment else Status.FAIL, clause=clause, demand=moment,
                 capacity=strength.design, unit="N*mm", values=values, note=section.label.capitalize(), member=footing.id, case=case)


def _shear_check(basis: Basis, footing: CombinedFooting, rows: tuple[BarRow, BarRow | None], beam: BeamCase) -> Check:
    profile, materials = basis.profile, basis.materials
    bottom, top = rows
    clause = profile.footing.clauses()["one_way_shear"]
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return replace(check_from_errors(SHEAR, [lam]), clause=clause, member=footing.id, case=beam.case)
    phi = profile.shear.strength_reduction()
    depth = bottom.depth
    worst: tuple[float, float, float, Section] | None = None  # razón, Vu, φVc, sección
    for section in shear_sections(beam, depth):
        shear, moment = abs(beam.shear(section.x)), beam.moment(section.x)
        tension = bottom.area if moment >= 0 else (top.area if top is not None else 0.0)
        vc = profile.footing.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=footing.ly, d=depth, h=footing.h,
                                                    rho_w=tension / (footing.ly * depth), vu=shear, mu=abs(moment))
        if worst is None or shear / (phi * vc) > worst[0]:
            worst = (shear / (phi * vc), shear, phi * vc, section)
    if worst is None:
        return Check(SHEAR, Status.PASS, clause=clause, member=footing.id, case=beam.case,
                     note="Ninguna seccion a d de las caras queda dentro de la zapata")
    _, demand, capacity, section = worst
    return Check(SHEAR, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, demand=demand, capacity=capacity,
                 unit="N", values=(("phi", phi), ("Vc", capacity / phi), ("d", depth), ("x", section.x)),
                 note=f"Seccion {section.label}; sin estribos", member=footing.id, case=beam.case)


def _min_check(basis: Basis, footing: CombinedFooting, row: BarRow, demand: float, bars: str) -> Check:
    """As de vigas, o 4/3 del requerido por el mayor momento si es menor (las barras son continuas: el mismo As en
    todas las secciones)."""
    profile, materials = basis.profile, basis.materials
    clauses = profile.flexure.clauses()
    as_min = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, row.width, row.depth)
    analysis = required_area(profile, materials, RectangularSection(row.width, footing.h), row.depth, demand)
    required = as_min if analysis is None else profile.flexure.effective_min_reinforcement(as_min, analysis)
    values: tuple[tuple[str, float], ...] = (("As,min", as_min), ("d", row.depth))
    note = ""
    if analysis is not None:
        values += (("As analisis", analysis),)
        if required < as_min:
            note = f"Excepcion de {clauses['min_reinforcement_exception']}: 4/3 del As requerido por analisis"
    return Check(f"{MIN_REINFORCEMENT} ({bars})", Status.PASS if row.area >= required else Status.FAIL,
                 clause=f"{clauses['min_reinforcement']} y {clauses['min_reinforcement_exception']}", demand=required,
                 capacity=row.area, unit="mm2", values=values, note=note, member=footing.id)


def _section_checks(basis: Basis, footing: CombinedFooting, row: BarRow, demand: float, bars: str) -> list[Check]:
    """εt, acero mínimo y separación de una capa de barras x con momento de su signo."""
    profile, materials = basis.profile, basis.materials
    strength = _strength(profile, materials, footing, row)
    checks = []
    if isinstance(strength, MomentStrength):
        checks.append(replace(net_tensile_strain_check(f"{STRAIN} ({bars})", profile.flexure.clauses()["net_tensile_strain"],
                                                       profile, materials, strength.state.extreme_strain), member=footing.id))
    checks.append(_min_check(basis, footing, row, demand, bars))
    spacing = footing.bottom.x.spacing if bars == BARS["bottom"] else footing.top.spacing if footing.top else 0.0
    clear_cover = footing.h - row.depth - row.diameter / 2  # de la superficie de la barra a la cara en tracción
    maximum = profile.footing.combined_max_bar_spacing(footing.h, materials.fy, clear_cover)
    checks.append(Check(f"{SPACING} ({bars})", Status.PASS if spacing <= maximum else Status.FAIL,
                        clause=profile.footing.clauses()["combined_spacing"], demand=spacing, capacity=maximum, unit="mm",
                        values=(("cc", clear_cover),), member=footing.id))
    return checks


def long_beam_checks(
    basis: Basis, footing: CombinedFooting, soil: Soil, cases: list[tuple[FactoredCase, tuple[FootingLoad, ...]]]
) -> list[Check]:
    """Flexión y cortante de cada caso mayorado y las verificaciones de sección de las barras x."""
    bottom = mat_rows(footing, footing.bottom, basis.bars)["x"]
    top = top_row(footing, basis.bars)
    checks = []
    positive_max = negative_max = 0.0
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        moments = [(beam.moment(section.x), section) for section in moment_sections(beam)]
        positive, at_positive = max(moments, key=lambda item: item[0])
        negative, at_negative = min(moments, key=lambda item: item[0])
        positive, negative = max(positive, 0.0), max(-negative, 0.0)
        positive_max, negative_max = max(positive_max, positive), max(negative_max, negative)
        checks.append(_flexure_check(basis, footing, bottom, (positive, at_positive, beam.case), BARS["bottom"]))
        if negative > _NEGLIGIBLE:
            if top is None:
                checks.append(plain_check(basis, footing, "x", negative,
                                          (at_negative.label, beam.case, at_negative.label.capitalize())))
            else:
                checks.append(_flexure_check(basis, footing, top, (negative, at_negative, beam.case), BARS["top"]))
        checks.append(_shear_check(basis, footing, (bottom, top), beam))
    if positive_max > _NEGLIGIBLE:
        checks += _section_checks(basis, footing, bottom, positive_max, BARS["bottom"])
    if top is not None and negative_max > _NEGLIGIBLE:
        checks += _section_checks(basis, footing, top, negative_max, BARS["top"])
    return checks
