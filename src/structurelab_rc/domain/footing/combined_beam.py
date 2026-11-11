"""Viga en la dirección larga de una zapata combinada con los casos mayorados (D-080, V3J.2; D-081).

La zapata es rígida: la carga neta hacia arriba es la presión de Bellos y Bakas de la resultante de las dos columnas
menos las cargas uniformes (domain/footing/loads.py), integrada en todo el ancho. Cada columna baja en su eje la fuerza
vertical de `column_vertical` y el par My + (h + pedestal)·Vx, con los momentos tomados en el plano de la base, el
mismo de la resultante: así los diagramas cierran en cero en los dos extremos. Para una sección en x, con el cuerpo
libre a su izquierda:

    V(x) = ∫q dA − Σ F_c                         (columnas con x_c < x)
    M(x) = x·∫q dA − ∫x·q dA − Σ [F_c·(x − x_c) − C_c]

M positivo tracciona la cara inferior, como Mu de las vigas. La viga larga se revisa con el código de vigas (D-081):
una sección rectangular B × h con las barras inferiores y superiores x como capas y los estribos opcionales, y una
estación por sección crítica de cada caso (el mayor momento positivo y el mayor negativo entre las caras y los puntos
con V = 0, y el cortante a d de cada cara hacia su tramo), con las verificaciones de vigas en modo cimentación (Vc y Av,min de
cimentación). Lo propio de la zapata: sin barras superiores, el momento negativo lo resiste el concreto simple
(D-072), y la separación de 3h y 450 mm (ACI 7.7.2.3, NSR-10 C.10.5.4). Mx, Vy y la posición en Y de las columnas no
cambian la viga: actúan en el sentido transversal (su torsión queda pendiente, D-080).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.shear import shear_checks
from structurelab_rc.domain.beam.station import checks_for
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.flexure import plain_check
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_row
from structurelab_rc.domain.status import Status
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Demands, Member, Section, Station
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, ReinforcementLayout

SPACING = "Viga larga: separacion maxima"
BARS = {"bottom": "barras inferiores x", "top": "barras superiores x"}
_SUBDIVISIONS = 64
_BISECTION_STEPS = 200
_EDGE = 1e-6
_TOUCH = 1.0  # mm: una barra de piel a menos de esto de la capa superior se omite


@dataclass(frozen=True)
class ColumnForce:
    """Fuerza vertical hacia abajo (N) y par (N·mm, positivo según My) de una columna en su eje x; half = cx/2."""

    id: str
    x: float
    half: float
    force: float
    couple: float


@dataclass(frozen=True)
class CriticalSection:
    """Sección crítica en x; shear_x es donde se toma el cortante si no es en x: en una cara de columna, la sección a d
    de ella (ACI 9.4.3.2 y 13.2.7.2, NSR-10 C.11.1.3 y C.15.5.2; D-082)."""

    x: float
    label: str
    shear_x: float | None = None


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


def _faces(beam: BeamCase) -> list[tuple[CriticalSection, float]]:
    """Las cuatro caras con la dirección hacia su tramo (−1 a la izquierda, +1 a la derecha)."""
    return [(CriticalSection(column.x + side * column.half, f"cara {'+' if side > 0 else '-'}X de la columna {column.id}"), side)
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
    # V es cero en un borde libre: un cambio de signo pegado a un extremo del tramo es ruido, no un extremo de M.
    return [x for x in roots if min(x - low, high - x) > _EDGE * beam.lx]


def moment_sections(beam: BeamCase) -> list[CriticalSection]:
    sections = [section for section, _ in _faces(beam)]
    for low, high, label in _regions(beam):
        sections += [CriticalSection(x, f"{label}, V = 0") for x in _zero_shear(beam, low, high)]
    return sections


def shear_sections(beam: BeamCase, depth: float) -> list[CriticalSection]:
    """A d de cada cara, hacia su tramo, si la sección queda dentro de ese tramo."""
    regions = _regions(beam)
    sections = []
    for face, side in _faces(beam):
        x = face.x + side * depth
        if any(low < x < high and (low <= face.x <= high) for low, high, _ in regions):
            sections.append(CriticalSection(x, f"a d de la {face.label}"))
    return sections


def _at_face_shear(beam: BeamCase, section: CriticalSection, depth: float) -> CriticalSection:
    """En una cara de columna, el cortante se toma en la sección a d de ella, si queda dentro del tramo."""
    for face, _ in _faces(beam):
        if abs(face.x - section.x) <= _EDGE * beam.lx:
            target = f"a d de la {face.label}"
            match = next((other for other in shear_sections(beam, depth) if other.label == target), None)
            return section if match is None else replace(section, shear_x=match.x)
    return section


def _skin_layers(footing: CombinedFooting, rows: tuple[BarRow, BarRow | None], bars: Sequence[RebarSpec]) -> list[BarLayer]:
    """Refuerzo superficial (D-083): una barra en cada cara lateral, a la separación vertical declarada desde la capa
    inferior hacia arriba, sin llegar a la capa superior (o al recubrimiento si no hay barras superiores)."""
    if footing.skin is None:
        return []
    spec = next(bar for bar in bars if bar.designation == footing.skin.designation)
    bottom, top = rows
    limit = footing.h - top.depth if top is not None else footing.cover + spec.diameter_mm / 2
    inset = footing.cover + spec.diameter_mm / 2
    layers = []
    depth = bottom.depth - footing.skin.spacing
    while depth > limit + _TOUCH:
        layers.append(BarLayer(depth=depth, role="skin", bars=(BarPosition(designation=spec.designation, x=inset),
                                                               BarPosition(designation=spec.designation, x=footing.ly - inset))))
        depth -= footing.skin.spacing
    return layers


def beam_member(footing: CombinedFooting, rows: tuple[BarRow, BarRow | None],
                bars: Sequence[RebarSpec]) -> tuple[Section, ReinforcementLayout]:
    """La viga larga como viga: sección B × h con el recubrimiento de la zapata, las barras inferiores y superiores x
    como capas (x desde la cara −Y, profundidad desde la cara superior), el refuerzo superficial y los estribos
    declarados (D-081, D-083)."""
    bottom, top = rows
    half = footing.ly / 2
    layers = [BarLayer(depth=bottom.depth, role="flexure",
                       bars=tuple(BarPosition(designation=bottom.designation, x=x + half) for x in bottom.positions))]
    if top is not None:
        layers.insert(0, BarLayer(depth=footing.h - top.depth, role="flexure",
                                  bars=tuple(BarPosition(designation=top.designation, x=x + half) for x in top.positions)))
    layers += _skin_layers(footing, rows, bars)
    return Section(bw=footing.ly, h=footing.h, cover=footing.cover), ReinforcementLayout(layers=tuple(layers), stirrups=footing.stirrups)


def critical_sections(beam: BeamCase, depth: float) -> list[CriticalSection]:
    """Las secciones de un caso: el mayor momento positivo y el mayor negativo (caras y V = 0), si los hay, y las de
    cortante."""
    moments = [(beam.moment(section.x), section) for section in moment_sections(beam)]
    largest, smallest = max(moments, key=lambda item: item[0]), min(moments, key=lambda item: item[0])
    chosen = ([largest[1]] if largest[0] > 0 else []) + ([smallest[1]] if smallest[0] < 0 else [])
    chosen = [_at_face_shear(beam, section, depth) for section in chosen]
    unique = {section.x: section for section in [*shear_sections(beam, depth), *chosen]}
    return sorted(unique.values(), key=lambda section: section.x)


def extreme_moments(footing: CombinedFooting, soil: Soil,
                    cases: list[tuple[FactoredCase, tuple[FootingLoad, ...]]]) -> tuple[tuple[float, float], tuple[float, float]]:
    """El mayor momento positivo y el mayor negativo (este con signo positivo) de la viga larga en todos los casos, con su
    x; (0, 0) si no hay momento de ese signo. Las secciones de desarrollo de las barras x (D-082)."""
    positive, negative = (0.0, 0.0), (0.0, 0.0)
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        for section in moment_sections(beam):
            moment = beam.moment(section.x)
            if moment > positive[0]:
                positive = (moment, section.x)
            if -moment > negative[0]:
                negative = (-moment, section.x)
    return positive, negative


def _with_section(check: Check, label: str) -> Check:
    note = label.capitalize() if not check.note else f"{label.capitalize()}: {check.note}"
    return replace(check, note=note)


def _station_checks(basis: Basis, footing: CombinedFooting, member: Member, given: tuple[BeamCase, CriticalSection, bool]) -> list[Check]:
    beam, section, has_top = given
    moment = beam.moment(section.x)
    shear = beam.shear(section.x if section.shear_x is None else section.shear_x)
    z = section.x + footing.lx / 2
    station = Station.model_construct(z=z, layout=member.stations[0].layout, case=beam.case,
                                      demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=shear, v3=0.0, tu=0.0))
    if moment < 0 and not has_top:
        # Sin barras superiores: flexión de concreto simple (D-072) y el cortante de vigas, que necesita acero a tracción.
        flexure = plain_check(basis, footing, "x", -moment, (section.label, beam.case, section.label.capitalize()))
        given_station = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True)
        shear_only = [replace(check, member=footing.id, z=z, case=beam.case) for check in shear_checks(given_station)]
        return [replace(flexure, z=z), *(_with_section(check, section.label) for check in shear_only)]
    checks = checks_for(StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True))
    return [_with_section(replace(check, member=footing.id), section.label) for check in checks]


def _spacing_check(basis: Basis, footing: CombinedFooting, spacing: float, bars: str) -> Check:
    maximum = basis.profile.footing.combined_max_bar_spacing(footing.h)
    return Check(f"{SPACING} ({bars})", Status.PASS if spacing <= maximum else Status.FAIL,
                 clause=basis.profile.footing.clauses()["combined_spacing"], demand=spacing, capacity=maximum, unit="mm",
                 member=footing.id)


def long_beam_checks(
    basis: Basis, footing: CombinedFooting, soil: Soil, cases: list[tuple[FactoredCase, tuple[FootingLoad, ...]]]
) -> list[Check]:
    """Las verificaciones de vigas en las secciones críticas de cada caso mayorado y la separación de las barras x."""
    bottom = mat_rows(footing, footing.bottom, basis.bars)["x"]
    top = top_row(footing, basis.bars)
    section, layout = beam_member(footing, (bottom, top), basis.bars)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    member = Member.model_construct(id=footing.id, type="beam", statically_determinate=None, length=footing.lx, section=section,
                                    stations=(placeholder,))
    checks = []
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        for critical in critical_sections(beam, bottom.depth):
            checks += _station_checks(basis, footing, member, (beam, critical, top is not None))
    checks.append(_spacing_check(basis, footing, footing.bottom.x.spacing, BARS["bottom"]))
    if footing.top is not None:
        checks.append(_spacing_check(basis, footing, footing.top.spacing, BARS["top"]))
    return checks
