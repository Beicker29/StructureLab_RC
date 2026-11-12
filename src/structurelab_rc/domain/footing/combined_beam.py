"""Viga de la dirección principal ("viga larga") de una zapata combinada con los casos mayorados (D-080, V3J.2; D-081).

Como todo el cálculo de la combinada, en ejes de la viga: X a lo largo de ella (dirección principal), Y transversal
(dirección secundaria). Las verificaciones se devuelven en los ejes declarados en domain/footing/declared.py (D-101).

La zapata es rígida: la carga neta hacia arriba es la presión de Bellos y Bakas de la resultante de las dos columnas
menos las cargas uniformes (domain/footing/loads.py), integrada en todo el ancho. Cada columna baja en su eje la fuerza
vertical de `column_vertical` y el par My + (h + pedestal)·Vx, con los momentos tomados en el plano de la base, el
mismo de la resultante: así los diagramas cierran en cero en los dos extremos. Para una sección en x, con el cuerpo
libre a su izquierda:

    V(x) = ∫q dA − Σ F_c                         (columnas con x_c < x)
    M(x) = x·∫q dA − ∫x·q dA − Σ [F_c·(x − x_c) − C_c]
    T(x) = ∫y·q dA − Σ T_c,   T_c = F_c·y_c − Mx_c + (h + pedestal)·Vy_c   (D-088)

M positivo tracciona la cara inferior, como Mu de las vigas. La viga larga se revisa con el código de vigas (D-081):
una sección rectangular B × h con las barras inferiores y superiores x como capas y los estribos opcionales, y una
estación por sección crítica de cada caso (el mayor momento de las barras inferiores y el mayor de las superiores entre
las caras y los puntos con V = 0, y el cortante a d de cada cara hacia su tramo), con las verificaciones de vigas en modo
cimentación (Vc y Av,min de cimentación). Lo propio de la zapata: sin barras superiores, el momento negativo lo resiste
el concreto simple (D-072), y la separación de 3h y 450 mm (ACI 7.7.2.3, NSR-10 C.10.5.4). Mx, Vy y la posición en Y de
las columnas no cambian V ni M: producen la torsión T(x) (D-088), que cierra en cero en los dos extremos por el
equilibrio global.

En la combinada rectangular la torsión es de placa (decisión del usuario, D-118): mxy = T/B y los momentos de diseño
de las barras x son los de Wood-Armer (mechanics/plate) con mx = M/B y my = 0, por cara (Mu inferior = B·mx*,
Mu superior = B·mx*); no se revisa la torsión de vigas. En la T invertida el alma es una viga y conserva la torsión de
vigas, con Tu donde se toma el cortante (a d de la cara, ACI 9.4.4.3, NSR-10 C.11.5.2.4).

En la T invertida (D-093) la viga larga es una T con el ala abajo (la zarpa): se revisa con el código de vigas volteando
la sección (profundidades desde la cara inferior y el momento con el signo cambiado, así el ala queda arriba), con el
ala efectiva de viga aislada del perfil (ACI 6.3.2.2, NSR-10 C.8.12.4: ≤ 4bw y solo si hf ≥ 0.5bw), las barras x
inferiores que caen dentro de ella y el miembro estáticamente determinado (As,min con el ala a tracción). El peso del
alma entra como carga lineal a lo largo de X.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.deep import deep_beam_checks
from structurelab_rc.domain.beam.flexure import STRENGTH as FLEXURE_STRENGTH
from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.beam.station import checks_for, flexure_station_checks, shear_and_torsion_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import column_vertical, stem_line_load
from structurelab_rc.domain.footing.flexure import plain_principal_check
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, stirrup_diameter, top_rows
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.plate import wood_armer
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Demands, Member, Section, Station
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, BarSpacing, ReinforcementLayout

SPACING = "Direccion principal: separacion maxima"
BARS = {"bottom": "barras inferiores", "top": "barras superiores"}
_SUBDIVISIONS = 64
_BISECTION_STEPS = 200
_EDGE = 1e-6
_TOUCH = 1.0  # mm: una barra de piel a menos de esto de la capa superior se omite
_NEGLIGIBLE_TWIST = 1.0  # N·mm/mm: por debajo, la sección no lleva los datos de Wood-Armer en la nota


@dataclass(frozen=True)
class ColumnForce:
    """Fuerza vertical hacia abajo (N) y par (N·mm, positivo según My) de una columna en su eje x; half = cx/2; torque,
    su momento estático respecto al eje X, F·y − Mx + H·Vy (N·mm), el que la viga larga lleva como torsión (D-088)."""

    id: str
    x: float
    half: float
    force: float
    couple: float
    torque: float = 0.0


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
    line: float = 0.0  # carga lineal hacia abajo del alma de la T invertida, mayorada (N/mm, D-093)

    @property
    def case(self) -> str:
        return self.pressure.case

    def _left(self, x: float) -> tuple[float, float, float]:
        hx, hy = self.lx / 2, self.ly / 2
        if x <= -hx:
            return 0.0, 0.0, 0.0
        return self.pressure.net(((-hx, -hy), (x, -hy), (x, hy), (-hx, hy)))

    def _span(self, x: float) -> float:
        return min(max(x + self.lx / 2, 0.0), self.lx)

    def shear(self, x: float) -> float:
        force, _, _ = self._left(x)
        return force - self.line * self._span(x) - sum(column.force for column in self.columns if column.x < x)

    def moment(self, x: float) -> float:
        force, sx, _ = self._left(x)
        stem = self.line * self._span(x) ** 2 / 2
        return x * force - sx - stem - sum(column.force * (x - column.x) - column.couple for column in self.columns if column.x < x)

    def torque(self, x: float) -> float:
        """T(x) del cuerpo libre a la izquierda, respecto al eje X (D-088)."""
        _, _, sy = self._left(x)
        return sy - sum(column.torque for column in self.columns if column.x < x)

    def twist(self, x: float) -> float:
        """Momento torsor de placa por unidad de ancho, mxy = T(x)/B, uniforme en el ancho (decisión del usuario, D-118)."""
        return self.torque(x) / self.ly

    def plate_moments(self, x: float) -> tuple[float, float]:
        """(Mu de las barras inferiores ≥ 0, Mu de las superiores ≤ 0) en todo el ancho B por Wood-Armer (D-118), con
        mx = M/B, mxy = T/B y my = 0. Con my = 0 el mx* de Wood-Armer es el mayor posible (my solo reduce mx* en la rama
        my* < 0), así que es conservador y desacopla la dirección x de las franjas. Sin torsión: (máx(M, 0), mín(M, 0))."""
        design = wood_armer(self.moment(x) / self.ly, 0.0, self.twist(x))
        return design.bottom.x * self.ly, design.top.x * self.ly


def beam_case(footing: CombinedFooting, soil: Soil, pressure: FactoredCase, loads: tuple[FootingLoad, ...]) -> BeamCase:
    height = footing.total_height + footing.pedestal_height
    columns = []
    for column, load in zip(footing.columns, loads, strict=True):
        force = column_vertical(footing, soil, column, load)
        columns.append(ColumnForce(column.id, column.x, column.cx / 2, force, load.my + height * load.vx,
                                   force * column.y - load.mx + height * load.vy))
    columns.sort(key=lambda column: column.x)
    line = loads[0].dead_factor * stem_line_load(footing, soil)
    return BeamCase(pressure, tuple(columns), footing.lx, footing.ly, line)


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
    stirrup = stirrup_diameter(footing, bars)
    limit = footing.h - top.depth if top is not None else footing.cover + stirrup + spec.diameter_mm / 2
    inset = footing.cover + stirrup + spec.diameter_mm / 2  # por dentro del estribo, si lo hay (D-088)
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


@dataclass(frozen=True)
class TwoWayWarning:
    """Zapata ancha para revisarla en una dirección (D-091): B ≥ ℓn, la luz libre entre las caras de las columnas."""

    width: float
    clear_span: float

    @property
    def ratio(self) -> float:
        return self.width / self.clear_span


def two_way_warning(footing: CombinedFooting) -> TwoWayWarning | None:
    """Aviso si el ancho B alcanza la luz libre ℓn entre las caras de las dos columnas a lo largo de X (criterio del
    usuario, D-091): la zapata se sigue revisando en una dirección (ACI 13.3.2), pero puede trabajar en dos (13.3.4)."""
    first, second = sorted(footing.columns, key=lambda column: column.x)
    clear_span = (second.x - second.cx / 2) - (first.x + first.cx / 2)
    return TwoWayWarning(footing.ly, clear_span) if footing.ly >= clear_span else None


def flange_width(profile: Profile, footing: CombinedFooting) -> float | None:
    """Ancho efectivo del ala de la T invertida (D-093): el de viga aislada del perfil, sin pasar de la base; None si
    el ala no cuenta (hf < 0.5bw) o no hay viga."""
    if footing.beam is None:
        return None
    width = profile.flexure.isolated_flange_width(footing.beam.width, footing.h)
    return None if width is None else min(width, footing.ly)


def covered_width(profile: Profile, footing: CombinedFooting) -> float:
    """Ancho, centrado en el alma, que cubre la capa inferior de la viga de la T invertida (D-106): el declarado
    (bottom_width) o, si no, el ala efectiva del perfil (o el alma si el ala no cuenta). Fuera de él van las barras x de
    la malla de la zarpa."""
    assert footing.beam is not None
    if footing.beam.bottom_width is not None:
        return footing.beam.bottom_width
    return flange_width(profile, footing) or footing.beam.width


def spread_bottom_layer(profile: Profile, footing: CombinedFooting, bars: Sequence[RebarSpec]) -> BarLayer:
    """La capa inferior de la viga de la T con sus posiciones (D-114): si se declaró solo con sus barras (sin x), se
    reparten a igual separación en el ancho cubierto, centrado en el alma (bottom_width o el ala efectiva); en los
    extremos, al recubrimiento si ese ancho llega al borde de la base, y por dentro del estribo si el ala no cuenta.
    Con posiciones o separación declaradas, la capa no cambia."""
    beam = footing.beam
    assert beam is not None
    layer = beam.bottom_layer
    if not (isinstance(layer.bars, tuple) and layer.bars and all(isinstance(bar, str) for bar in layer.bars)):
        return layer
    names = [bar for bar in layer.bars if isinstance(bar, str)]
    db = max(next(spec.diameter_mm for spec in bars if spec.designation == name) for name in names)
    half = covered_width(profile, footing) / 2
    if half <= beam.width / 2 + _EDGE:  # solo el alma: por dentro del estribo, como en las vigas
        reach = half - footing.cover - stirrup_diameter(footing, bars) - db / 2
    else:
        reach = half - (footing.cover if half >= footing.ly / 2 - _EDGE else 0.0) - db / 2
    count = len(names)
    xs = [beam.width / 2] if count == 1 else [beam.width / 2 - reach + 2 * reach * index / (count - 1) for index in range(count)]
    return layer.model_copy(update={"bars": tuple(BarPosition(designation=name, x=x) for name, x in zip(names, xs, strict=True))})


def _bars_within(layer: BarLayer, low: float, high: float) -> BarLayer | None:
    """La capa (ya con posiciones, spread_bottom_layer) con solo las barras entre low y high (x desde la cara −Y del
    alma); None si no queda ninguna."""
    positions = ([BarPosition(designation=layer.bars.designation, x=x) for x in layer.bars.positions()]
                 if isinstance(layer.bars, BarSpacing) else [bar for bar in layer.bars if isinstance(bar, BarPosition)])
    kept = tuple(bar for bar in positions if low - _EDGE <= bar.x <= high + _EDGE)
    return layer.model_copy(update={"bars": kept}) if kept else None


def _t_beam_member(profile: Profile, footing: CombinedFooting, bars: Sequence[RebarSpec]) -> tuple[Section, ReinforcementLayout]:
    """La viga de la T invertida volteada (D-093, D-106): alma bw × H con el ala (la zarpa) arriba; x desde la cara −Y
    del alma, profundidades desde la cara inferior de la zapata. Las capas declaradas en beam (desde la cara superior,
    aquí volteadas) y las barras x de la malla de la zarpa fuera del ancho cubierto por la capa inferior; de unas y otras
    solo cuentan las que caen dentro del ala efectiva (o del alma si el ala no cuenta)."""
    beam = footing.beam
    assert beam is not None
    total, web = footing.total_height, beam.width
    width = flange_width(profile, footing)
    reach = (width if width is not None else web) / 2
    low, high = web / 2 - reach, web / 2 + reach
    layers = []
    bottom = spread_bottom_layer(profile, footing, bars)
    for layer in beam.layers:
        own = _bars_within(bottom, low, high) if layer is beam.bottom_layer else layer
        if own is not None:
            layers.append(own.model_copy(update={"depth": total - layer.depth}))
    zarpa = mat_rows(footing, footing.bottom, bars)["x"]
    outside = covered_width(profile, footing) / 2
    extra = tuple(BarPosition(designation=zarpa.designation, x=y + web / 2) for y in zarpa.positions
                  if outside + _EDGE < abs(y) <= reach + _EDGE)
    if extra:
        layers.append(BarLayer(depth=footing.h - zarpa.depth, role="flexure", bars=extra))
    layers.sort(key=lambda layer: layer.depth)
    overhang = None if width is None else (width - web) / 2
    section = Section(bw=web, h=total, cover=footing.cover, hf=None if overhang is None else footing.h,
                      overhang_x_neg=overhang, overhang_x_pos=overhang)
    return section, ReinforcementLayout(layers=tuple(layers), stirrups=beam.stirrups)


def beam_depth(footing: CombinedFooting, bars: Sequence[RebarSpec]) -> float:
    """d de las barras inferiores de la viga larga desde su cara superior: en la T invertida, la profundidad de su capa
    inferior (D-106); si no, la de las barras inferiores x de la malla."""
    if footing.beam is not None:
        return footing.beam.bottom_layer.depth
    return footing.stem_height + mat_rows(footing, footing.bottom, bars)["x"].depth


def t_beam_rows(profile: Profile, footing: CombinedFooting, bars: Sequence[RebarSpec]) -> tuple[BarRow, BarRow | None]:
    """Las barras inferiores y superiores de la viga de la T invertida como filas (D-106), para su desarrollo: la capa
    inferior y la de flexión más alta, con las posiciones respecto al eje de la viga."""
    beam = footing.beam
    assert beam is not None
    section, layout = _t_beam_member(profile, footing, bars)
    placed = placed_bars(layout, section, bars)
    total = footing.total_height

    def row(depth_from_top: float) -> BarRow:
        own = [bar for bar in placed if abs(bar.depth - (total - depth_from_top)) <= _EDGE]
        designation = own[0].designation if own else beam.bottom_layer.designations()[0]
        spec = next(bar for bar in bars if bar.designation == designation)
        positions = tuple(sorted(bar.x - beam.width / 2 for bar in own))
        depth = depth_from_top if depth_from_top > total / 2 else total - depth_from_top
        return BarRow("x", designation, spec.diameter_mm, spec.area_mm2, depth, beam.width, positions, None, ())

    flexure = [layer for layer in beam.layers if layer.role == "flexure"]
    top = min(flexure, key=lambda layer: layer.depth)
    return row(beam.bottom_layer.depth), (row(top.depth) if top is not beam.bottom_layer else None)


def long_beam_member(footing: CombinedFooting, bars: Sequence[RebarSpec], profile: Profile | None = None) -> Member:
    """La viga larga como miembro de vigas, con una estación de referencia que lleva su armado. La de la T invertida va
    volteada y es estáticamente determinada (sus fuerzas salen de la estática con la presión de Bellos, D-093)."""
    if footing.beam is not None:
        assert profile is not None
        section, layout = _t_beam_member(profile, footing, bars)
    else:
        section, layout = beam_member(footing, (mat_rows(footing, footing.bottom, bars)["x"], top_rows(footing, bars).get("x")), bars)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    return Member.model_construct(id=footing.id, type="beam", statically_determinate=True if footing.beam is not None else None,
                                  deep_beam=footing.deep_beam, length=footing.lx, section=section, stations=(placeholder,))


def _design_moments(beam: BeamCase, x: float, plate: bool) -> tuple[float, float]:
    """(Mu inferior ≥ 0, Mu superior ≤ 0) en x: los de Wood-Armer en la combinada rectangular (D-118); en la T, M."""
    if plate:
        return beam.plate_moments(x)
    moment = beam.moment(x)
    return max(moment, 0.0), min(moment, 0.0)


def critical_sections(beam: BeamCase, depth: float, plate: bool = False) -> list[CriticalSection]:
    """Las secciones de un caso: la del mayor momento de las barras inferiores y la del mayor de las superiores (caras y
    V = 0; con plate, los de Wood-Armer, D-118), si los hay, y las de cortante."""
    moments = [(_design_moments(beam, section.x, plate), section) for section in moment_sections(beam)]
    largest = max(moments, key=lambda item: item[0][0])
    smallest = min(moments, key=lambda item: item[0][1])
    chosen = ([largest[1]] if largest[0][0] > 0 else []) + ([smallest[1]] if smallest[0][1] < 0 else [])
    chosen = [_at_face_shear(beam, section, depth) for section in chosen]
    unique = {section.x: section for section in [*shear_sections(beam, depth), *chosen]}
    return sorted(unique.values(), key=lambda section: section.x)


def extreme_moments(footing: CombinedFooting, soil: Soil,
                    cases: list[tuple[FactoredCase, tuple[FootingLoad, ...]]]) -> tuple[tuple[float, float], tuple[float, float]]:
    """El mayor momento de las barras inferiores y el mayor de las superiores (este con signo positivo) de la viga larga
    en todos los casos, con su x; (0, 0) si no hay momento de ese signo. En la combinada rectangular, los de Wood-Armer
    (D-118). Las secciones de desarrollo de las barras x (D-082)."""
    positive, negative = (0.0, 0.0), (0.0, 0.0)
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        for section in moment_sections(beam):
            bottom, top = _design_moments(beam, section.x, footing.beam is None)
            if bottom > positive[0]:
                positive = (bottom, section.x)
            if -top > negative[0]:
                negative = (-top, section.x)
    return positive, negative


def moment_sign(moment: float) -> str:
    """El signo del momento (M > 0 tracciona la cara inferior) en la nota de la sección (D-095): la memoria separa por él
    la revisión del momento positivo y la del negativo."""
    return "momento negativo" if moment < 0 else "momento positivo"


def _sentence(text: str) -> str:
    """La primera letra en mayúscula, sin tocar el resto (los nombres de las columnas y los ejes)."""
    return text[:1].upper() + text[1:]


def _with_section(check: Check, label: str) -> Check:
    title = _sentence(label)
    note = title if not check.note else f"{title}: {check.note}"
    return replace(check, note=note)


def _plate_note(beam: BeamCase, x: float) -> str:
    """Los datos de Wood-Armer de la sección (D-118), en la nota de la flexión: M, T y mxy = T/B."""
    return (f"Wood-Armer (D-118): M = {beam.moment(x) / 1e6:.1f} kN*m, T = {beam.torque(x) / 1e6:.1f} kN*m, "
            f"mxy = T/B = {beam.twist(x) / 1e3:.2f} kN*m/m")


def _plate_station_checks(basis: Basis, footing: CombinedFooting, member: Member,
                          given: tuple[BeamCase, CriticalSection, bool]) -> list[Check]:
    """Combinada rectangular (D-118): la flexión con los momentos de Wood-Armer de cada cara (una estación por cara con
    momento) y el cortante de vigas una sola vez, sin torsión de vigas (la toman los momentos de placa)."""
    beam, section, has_top = given
    at = section.x if section.shear_x is None else section.shear_x
    z = section.x + footing.lx / 2
    twisted = abs(beam.twist(section.x)) > _NEGLIGIBLE_TWIST
    moments = [moment for moment in beam.plate_moments(section.x) if moment != 0] or [beam.moment(section.x)]
    checks: list[Check] = []
    for index, moment in enumerate(moments):
        label = f"{section.label}, {moment_sign(moment)}"
        station = Station.model_construct(z=z, layout=member.stations[0].layout, case=beam.case,
                                          demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=beam.shear(at), v3=0.0, tu=0.0))
        given_station = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True)
        plate = f"; {_plate_note(beam, section.x)}" if twisted else ""
        values = _plate_values(beam, section.x, moment)
        if moment < 0 and not has_top:  # sin barras superiores: concreto simple (D-072), con la sección ya en la nota
            plain = plain_principal_check(basis, footing, -moment, (label, beam.case, _sentence(label) + plate))
            rest = (*shear_and_torsion_checks(given_station), *(deep_beam_checks(given_station) if footing.deep_beam else ()))
            others = [replace(check, member=footing.id, z=z, case=beam.case) for check in rest] if index == 0 else []
            checks += [replace(plain, z=z, values=(*plain.values, *values)), *(_with_section(check, label) for check in others)]
            continue
        every = checks_for(given_station) if index == 0 else flexure_station_checks(given_station)
        for check in every:
            if plate and check.name.startswith("Flexion"):
                check = replace(check, note=f"{check.note}{plate}" if check.note else plate[2:])
            if check.name == FLEXURE_STRENGTH:  # la composición de Mu y los momentos de Wood-Armer (D-118)
                check = replace(check, values=(*check.values, *values))
            checks.append(_with_section(replace(check, member=footing.id), label))
    return checks


def _plate_values(beam: BeamCase, x: float, moment: float) -> tuple[tuple[str, float], ...]:
    """Mu = M flexión + M torsión de la sección y los momentos por unidad de ancho de Wood-Armer de las barras x
    (mx = M/B, my = 0, mxy = T/B), para la memoria y su tabla (D-118, D-119)."""
    design = wood_armer(beam.moment(x) / beam.ly, 0.0, beam.twist(x))
    return (("M flexion", beam.moment(x)), ("M torsion", moment - beam.moment(x)), ("mx", beam.moment(x) / beam.ly),
            ("my", 0.0), ("mxy", beam.twist(x)), ("mx* inf", design.bottom.x), ("mx* sup", design.top.x))


def _station_checks(basis: Basis, footing: CombinedFooting, member: Member, given: tuple[BeamCase, CriticalSection, bool]) -> list[Check]:
    if footing.beam is None:
        return _plate_station_checks(basis, footing, member, given)
    beam, section, has_top = given
    # La nota lleva el signo del momento físico (D-095); la T invertida va volteada: su momento cambia de signo (D-093).
    section = replace(section, label=f"{section.label}, {moment_sign(beam.moment(section.x))}")
    moment = beam.moment(section.x) * (-1.0 if footing.beam is not None else 1.0)
    # El cortante y la torsión, a d de la cara si la sección es una cara de columna (ACI 9.4.3.2 y 9.4.4.3).
    at = section.x if section.shear_x is None else section.shear_x
    z = section.x + footing.lx / 2
    station = Station.model_construct(z=z, layout=member.stations[0].layout, case=beam.case,
                                      demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=beam.shear(at), v3=0.0,
                                                                      tu=beam.torque(at)))
    if moment < 0 and not has_top:
        # Sin barras superiores: flexión de concreto simple (D-072) y el cortante (y la torsión) de vigas.
        flexure = plain_principal_check(basis, footing, -moment, (section.label, beam.case, _sentence(section.label)))
        given_station = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True)
        deep = deep_beam_checks(given_station) if footing.deep_beam else ()
        shear_only = [replace(check, member=footing.id, z=z, case=beam.case) for check in (*shear_and_torsion_checks(given_station), *deep)]
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
    # En la T invertida las barras superiores van en las capas de la viga (D-106): nunca es concreto simple.
    has_top = footing.beam is not None or top_rows(footing, basis.bars).get("x") is not None
    member = long_beam_member(footing, basis.bars, basis.profile)
    depth = beam_depth(footing, basis.bars)  # d de las barras inferiores desde la cara superior de la viga
    checks = []
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        for critical in critical_sections(beam, depth, plate=footing.beam is None):
            checks += _station_checks(basis, footing, member, (beam, critical, has_top))
    checks.append(_spacing_check(basis, footing, footing.bottom.x.spacing, BARS["bottom"]))
    # En la T invertida las barras superiores son de la viga: su separación la controla la fisuración de vigas (D-093).
    if footing.top is not None and footing.top.x is not None and footing.beam is None:
        checks.append(_spacing_check(basis, footing, footing.top.x.spacing, BARS["top"]))
    return checks
