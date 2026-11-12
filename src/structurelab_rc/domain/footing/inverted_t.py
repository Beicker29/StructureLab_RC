"""Zapata combinada en T invertida (D-093): lo propio de la zarpa y de las columnas sobre la viga.

La viga larga se revisa en combined_beam (sección T volteada). Aquí, con los casos mayorados:

- Aletas: cada lado de la zarpa (±Y) es un voladizo desde la cara de la viga hasta el borde. Por unidad de longitud en
  X, con la presión de Bellos q(x, y) y la carga uniforme w de la zarpa, el relleno y las sobrecargas:

      m(x) = ∫ (q − w)·(distancia a la cara) dy          (cara → borde)
      v(x) = ∫ (q − w) dy                                  (cara + d → borde)

  Se barre X y gobierna el mayor de cada lado. Se revisan por metro la flexión y εt con la malla y, el cortante en una
  dirección con el Vc de cimentación, el mínimo de losa y la separación, y el desarrollo de las barras y desde la cara
  de la viga. Con momento negativo en una aleta (la cara superior a tracción, sin barras superiores en la zarpa), la
  flexión es de concreto simple (D-072).
- Ala a tracción de la viga: el refuerzo se reparte dentro del menor entre el ala efectiva y 1/10 de la luz (ACI
  24.3.4 con ℓn, NSR-10 C.10.6.6 con la luz); si ese ancho es menor que el ala, debe haber barras en sus zonas
  exteriores.
- Altura mínima de la zarpa, aplastamiento de cada columna sobre la viga (A2 dentro de su cara superior) y pasadores
  anclados en la altura de la viga. Sin punzonamiento: la carga de la columna la toma la viga (decisión del usuario).
"""

import math
from collections.abc import Callable
from dataclasses import replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.shear import concrete_lambda
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import (
    MomentStrength,
    RectangularSection,
    net_tensile_strain_check,
    rectangular_strength,
)
from structurelab_rc.domain.footing.combined_beam import flange_width
from structurelab_rc.domain.footing.combined_columns import (
    Cases,
    bar_development_check,
    outside_checks,
    steel_excess,
    x_development,
)
from structurelab_rc.domain.footing.connection import Support, bearing_checks, dowel_checks
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_rows
from structurelab_rc.domain.plain_strength import plain_rectangular_moment
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil

# Las aletas trabajan en la dirección secundaria (D-101).
FLEXURE = "Aleta: flexion (direccion secundaria)"
PLAIN = "Aleta: concreto simple (cara superior)"
SHEAR = "Aleta: cortante en una direccion (direccion secundaria)"
STRAIN = "Aleta: deformacion neta de traccion (direccion secundaria)"
MINIMUM = "Aleta: acero minimo (direccion secundaria)"
SPACING = "Aleta: separacion maxima (direccion secundaria)"
DEVELOPMENT = "Desarrollo barras inferiores, direccion secundaria (aletas)"
TENSION_FLANGE = "Viga T: refuerzo del ala en traccion"
DEPTH = "Altura minima de la zarpa"
STRIP = 1000.0  # mm: las aletas se revisan por metro de longitud
_SAMPLES = 64
_GOLDEN_STEPS = 100
_NEGLIGIBLE = 1.0  # N·mm/mm


def _maximize(function: Callable[[float], float], low: float, high: float) -> tuple[float, float]:
    """Máximo de una función continua en [low, high]: muestreo y sección áurea alrededor de la mejor muestra."""
    points = [low + (high - low) * index / _SAMPLES for index in range(_SAMPLES + 1)]
    values = [function(x) for x in points]
    best = max(range(len(points)), key=lambda index: values[index])
    a, b = points[max(best - 1, 0)], points[min(best + 1, _SAMPLES)]
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(_GOLDEN_STEPS):
        c, d = b - ratio * (b - a), a + ratio * (b - a)
        if function(c) >= function(d):
            b = d
        else:
            a = c
    middle = (a + b) / 2
    return max(((points[best], values[best]), (middle, function(middle))), key=lambda item: item[1])


class Flanges:
    """Cargas de las dos aletas de un caso: momento en la cara, cortante a d y momento a d, por unidad de longitud."""

    def __init__(self, footing: CombinedFooting, pressure: FactoredCase, depth: float) -> None:
        assert footing.beam is not None
        self.pressure = pressure
        self.face, self.edge, self.depth = footing.beam.width / 2, footing.ly / 2, depth
        self.half = footing.lx / 2

    def _beyond(self, x: float, side: float, at: float) -> tuple[float, float]:
        """(∫(q − w) dy, ∫(q − w)·(distancia a la sección) dy) entre la sección a `at` de la cara y el borde."""
        start = self.face + at
        if start >= self.edge:
            return 0.0, 0.0
        y0, y1 = (start, self.edge) if side > 0 else (-self.edge, -start)
        force, first = self.pressure.pressure.along_y(x, y0, y1)
        length = self.edge - start
        w = self.pressure.net_load
        lever = first - start * force if side > 0 else -start * force - first
        return force - w * length, lever - w * length**2 / 2

    def moment(self, x: float, side: float) -> float:
        return self._beyond(x, side, 0.0)[1]

    def section(self, x: float, side: float, offset: float) -> tuple[float, float]:
        """(V, M) por unidad de longitud en la sección a `offset` de la cara de la viga hacia el borde `side`: los
        diagramas de las aletas (D-095)."""
        return self._beyond(x, side, offset)

    def shear(self, x: float, side: float) -> tuple[float, float]:
        """Cortante y momento en la sección a d de la cara."""
        return self._beyond(x, side, self.depth)

    def _function(self, kind: str, side: float) -> Callable[[float], float]:
        def value(x: float) -> float:
            if kind == "shear":
                return self.shear(x, side)[0]
            return self.moment(x, side) * (-1.0 if kind == "negative" else 1.0)
        return value

    def governing(self, kind: str) -> tuple[float, float, float]:
        """(x, valor, lado) del mayor momento positivo ("moment"), negativo ("negative", con signo positivo) o cortante a
        d ("shear") de las dos aletas a lo largo de X."""
        options = []
        for side in (1.0, -1.0):
            x, value = _maximize(self._function(kind, side), -self.half, self.half)
            options.append((x, value, side))
        return max(options, key=lambda item: item[1])


def _side(side: float) -> str:
    return "+Y" if side > 0 else "-Y"


def _flexure(basis: Basis, footing: CombinedFooting, row: BarRow, per_metre: float, flanges: Flanges) -> list[Check]:
    profile, materials = basis.profile, basis.materials
    clause = profile.footing.clauses()["strength"]
    case = flanges.pressure.case
    x, moment, side = flanges.governing("moment")
    checks = []
    if moment > _NEGLIGIBLE:
        strength = rectangular_strength(profile, materials, RectangularSection(STRIP, footing.h), (SteelLayer(row.depth, per_metre),))
        note = f"Aleta {_side(side)}, cara de la viga en x = {x:.0f} mm, por metro"
        if isinstance(strength, MomentStrength):
            checks.append(Check(FLEXURE, Status.PASS if strength.design >= moment * STRIP else Status.FAIL, clause=clause,
                                demand=moment * STRIP, capacity=strength.design, unit="N*mm", member=footing.id, case=case,
                                values=(("phi", strength.phi), ("Mn", strength.nominal), ("b", STRIP), ("h", footing.h),
                                        ("d", row.depth), ("As", per_metre), ("fc", materials.fc), ("fy", materials.fy),
                                        ("a", strength.state.a)),
                                note=note))
        else:
            checks.append(replace(check_from_errors(FLEXURE, [strength]), clause=clause, member=footing.id, case=case))
    x, negative, side = flanges.governing("negative")
    if negative > _NEGLIGIBLE:
        checks.append(_plain(basis, footing, negative * STRIP, (case, f"Aleta {_side(side)}, cara de la viga en x = {x:.0f} mm")))
    return checks


def _plain(basis: Basis, footing: CombinedFooting, demand: float, location: tuple[str, str]) -> Check:
    """Momento negativo en una aleta sin barras superiores en la zarpa: concreto simple por metro (D-072)."""
    case, note = location
    plain = basis.profile.plain
    if not plain.permitted_in_foundations(basis.seismic_level):
        error = invalid_input(f"Momento negativo en la aleta sin barras superiores: {plain.clauses()['seismic']} no permite "
                              f"cimentaciones de concreto simple con nivel sismico {basis.seismic_level} (D-072)",
                              member=footing.id, case=case)
        return Check(PLAIN, Status.FAIL, (error,), plain.clauses()["seismic"], demand=demand, unit="N*mm", member=footing.id,
                     case=case, note=f"{note}, por metro")
    strength = plain_rectangular_moment(basis.profile, basis.materials, STRIP, footing.h, cast_against_soil=True)
    if isinstance(strength, StructuredError):
        return replace(check_from_errors(PLAIN, [strength]), clause=plain.clauses()["flexure"], member=footing.id, case=case)
    return Check(PLAIN, Status.PASS if strength.design >= demand else Status.FAIL, clause=plain.clauses()["flexure"],
                 demand=demand, capacity=strength.design, unit="N*mm", member=footing.id, case=case, note=f"{note}, por metro",
                 values=(("phi", strength.phi), ("Mn", strength.nominal)))


def _shear(basis: Basis, footing: CombinedFooting, row: BarRow, per_metre: float, flanges: Flanges) -> Check:
    profile, materials = basis.profile, basis.materials
    clause = profile.footing.clauses()["one_way_shear"]
    case = flanges.pressure.case
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, Check):
        return replace(lam, name=SHEAR, member=footing.id, case=case)
    x, shear, side = flanges.governing("shear")
    moment = flanges.shear(x, side)[1]
    vu, mu = max(shear, 0.0) * STRIP, abs(moment) * STRIP
    vc = profile.footing.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=STRIP, d=row.depth, h=footing.h,
                                                rho_w=per_metre / (STRIP * row.depth), vu=vu, mu=mu)
    phi = profile.shear.strength_reduction()
    return Check(SHEAR, Status.PASS if vu <= phi * vc else Status.FAIL, clause=clause, demand=vu, capacity=phi * vc, unit="N",
                 member=footing.id, case=case,
                 values=(("phi", phi), ("Vc", vc), ("bw", STRIP), ("d", row.depth), ("rho w", per_metre / (STRIP * row.depth)),
                         ("lambda", lam), ("fc", materials.fc)),
                 note=f"Aleta {_side(side)}, seccion a d de la cara de la viga en x = {x:.0f} mm, por metro")


def _tension_flange(basis: Basis, footing: CombinedFooting, bottom: BarRow) -> list[Check]:
    """Reparto del refuerzo del ala a tracción (ACI 24.3.4, NSR-10 C.10.6.6): dentro del menor entre el ala efectiva y
    1/10 de la luz; si ese ancho es menor que el ala, debe haber barras en sus zonas exteriores."""
    flexure = basis.profile.flexure
    width = flange_width(basis.profile, footing)
    if width is None:
        return []
    first, second = sorted(footing.columns, key=lambda column: column.x)
    clear = (second.x - second.cx / 2) - (first.x + first.cx / 2)
    spread = flexure.flange_tension_width(width, clear, second.x - first.x)
    values = (("bf", width), ("ancho de reparto", spread))
    clause = flexure.clauses()["flange_tension"]
    if spread >= width:
        return [Check(TENSION_FLANGE, Status.PASS, clause=clause, member=footing.id, values=values,
                      note="El ala efectiva cabe en el ancho de reparto")]
    outer = [y for y in bottom.positions if abs(y) > spread / 2]
    return [Check(TENSION_FLANGE, Status.PASS if outer else Status.FAIL, clause=clause, member=footing.id, values=values,
                  note=f"{len(outer)} barras inferiores de la direccion principal en las zonas exteriores del ala, fuera de "
                       f"{spread:.0f} mm")]


def inverted_t_checks(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> list[Check]:
    """Aletas, ala a tracción, altura de la zarpa, desarrollo de las barras x e y, aplastamiento y pasadores (D-093)."""
    assert footing.beam is not None
    profile = basis.profile
    bottom = mat_rows(footing, footing.bottom, basis.bars)
    row = bottom["y"]
    per_metre = row.bar_area * STRIP / footing.bottom.y.spacing
    checks: list[Check] = []
    largest = 0.0
    for pressure, _ in cases:
        flanges = Flanges(footing, pressure, row.depth)
        checks += _flexure(basis, footing, row, per_metre, flanges)
        checks.append(_shear(basis, footing, row, per_metre, flanges))
        largest = max(largest, flanges.governing("moment")[1])
    strength = rectangular_strength(profile, basis.materials, RectangularSection(STRIP, footing.h), (SteelLayer(row.depth, per_metre),))
    if isinstance(strength, MomentStrength):
        checks.append(replace(net_tensile_strain_check(STRAIN, profile.footing.clauses()["net_tensile_strain"], profile,
                                                       basis.materials, strength.state.extreme_strain), member=footing.id))
    checks += outside_checks(basis, footing, row, (MINIMUM, SPACING))
    cantilever = (footing.ly - footing.beam.width) / 2
    excess = steel_excess(basis, (STRIP, footing.h, row.depth), per_metre, largest * STRIP) if largest > 0 else 1.0
    checks.append(bar_development_check(basis, footing, row, (footing.bottom.y.spacing, "bottom", excess, cantilever - footing.cover),
                                        (DEVELOPMENT, "Desde la cara de la viga hasta el borde de la zarpa")))
    checks += _tension_flange(basis, footing, bottom["x"])
    checks += x_development(basis, footing, soil, (bottom["x"], top_rows(footing, basis.bars).get("x")), cases)
    first = bottom[footing.bottom.first]
    second = bottom["y" if footing.bottom.first == "x" else "x"]
    measured = profile.footing.footing_depth(footing.h, footing.cover, first.diameter, second.diameter)
    clauses = profile.footing.clauses()
    checks.append(Check(DEPTH, Status.PASS if measured >= profile.footing.min_depth() else Status.FAIL, clause=clauses["min_depth"],
                        demand=profile.footing.min_depth(), capacity=measured, unit="mm", member=footing.id))
    surface = (footing.lx, footing.beam.width, footing.total_height)
    for index, column in enumerate(footing.columns):
        support = Support(column.cx, column.cy, column.x, column.y, column.dowels, f"Columna {column.id}", surface)
        dowels, area = dowel_checks(basis, footing, support, (first, second))
        loads = [(pressure.case, loads[index].p) for pressure, loads in cases]
        checks += [*dowels, *bearing_checks(basis, footing, support, (loads, area))]
    return checks
