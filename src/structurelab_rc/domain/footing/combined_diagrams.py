"""Diagramas de momento y cortante de la zapata combinada y en T invertida (D-095): la envolvente de los casos mayorados
con las mismas funciones que usan las verificaciones; aquí no hay fórmulas nuevas.

- Longitudinal: M(x) y V(x) de la viga larga (combined_beam.BeamCase) en toda su longitud, con el cuerpo libre a la
  izquierda; las columnas, como cargas puntuales en su eje, hacen saltar V (y M, con su par).
- Transversal, zapata combinada: los dos voladizos de la franja de cada columna (combined_columns.strip_cantilever), de
  cada borde hasta la cara de la columna; bajo la columna no se dibuja.
- Transversal, T invertida: las dos aletas (inverted_t.Flanges) de cada borde hasta la cara de la viga, en la sección x
  que gobierna el momento de las aletas en cada caso, por metro de longitud.

M > 0 tracciona la cara inferior; V es el del cuerpo libre a la izquierda (−Y en la dirección transversal). Unidades
internas: posición en mm, M en N·mm y V en N (por metro en las aletas).

Cada envolvente trae además sus secciones críticas (D-104): las caras de las columnas (o de la viga) y las secciones a d
de ellas, y en la dirección principal las posiciones de los extremos de momento; las secciones son puntos de muestreo,
así que su máximo y su mínimo, con el caso de cada uno, son exactos.
"""

from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.combined_beam import beam_case, beam_depth, moment_sections, shear_sections
from structurelab_rc.domain.footing.combined_columns import Cases, strip_cantilever, strip_load
from structurelab_rc.domain.footing.declared import declared_envelope
from structurelab_rc.domain.footing.inverted_t import STRIP, Flanges
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil

_SAMPLES = 120  # intervalos a lo largo de la viga larga
_CANTILEVER_SAMPLES = 40  # intervalos por voladizo transversal
_JUMP = 1e-3  # mm: a cada lado del eje de una columna, para dibujar el salto de V


@dataclass(frozen=True)
class CriticalValues:
    """Una sección crítica de un diagrama: el máximo y el mínimo de M y de V entre los casos, cada uno con su caso."""

    label: str
    position: float
    moment_max: tuple[float, str]
    moment_min: tuple[float, str]
    shear_max: tuple[float, str]
    shear_min: tuple[float, str]


@dataclass(frozen=True)
class Envelope:
    """Envolvente de un diagrama: en cada posición, el máximo y el mínimo de M y de V entre los casos, y el caso de cada
    extremo global. segments agrupa las posiciones en tramos continuos (los voladizos de una franja son dos tramos)."""

    title: str
    positions: tuple[float, ...]
    moment_max: tuple[float, ...]
    moment_min: tuple[float, ...]
    shear_max: tuple[float, ...]
    shear_min: tuple[float, ...]
    segments: tuple[tuple[int, int], ...]
    marks: tuple[tuple[float, str], ...]
    extremes: tuple[tuple[str, float, float, str], ...]  # (magnitud, valor, posición, caso)
    per_metre: bool = False
    sections: tuple[CriticalValues, ...] = ()


Layout = tuple[list[tuple[float, str]], list[tuple[int, int]], bool]  # marcas, tramos y si es por metro


def _critical(samples: list[list[tuple[float, float, float]]], cases: list[str], section: tuple[float, str]) -> CriticalValues:
    """Máximo y mínimo de M y de V en una sección, que es una de las posiciones muestreadas."""
    position, label = section
    index = next(i for i, point in enumerate(samples[0]) if point[0] == position)
    values = [(own[index], case) for own, case in zip(samples, cases, strict=True)]

    def pick(key: int, largest: bool) -> tuple[float, str]:
        # Con empate gobierna el primer caso, como en los extremos de la envolvente.
        point, case = (max if largest else min)(values, key=lambda item: item[0][key])
        return point[key], case

    return CriticalValues(label, position, pick(1, True), pick(1, False), pick(2, True), pick(2, False))


def _envelope(title: str, samples: list[list[tuple[float, float, float]]], cases: list[str], layout: Layout,
              sections: list[tuple[float, str]] | None = None) -> Envelope:
    """samples[c] = [(posición, M, V)] del caso c, con las mismas posiciones en todos los casos; sections, las secciones
    críticas (posición, nombre), que deben estar entre las posiciones."""
    marks, segments, per_metre = layout
    positions = tuple(point for point, _, _ in samples[0])
    columns = list(zip(*samples, strict=True))  # por posición: los (posición, M, V) de cada caso
    moment_max = tuple(max(value[1] for value in column) for column in columns)
    moment_min = tuple(min(value[1] for value in column) for column in columns)
    shear_max = tuple(max(value[2] for value in column) for column in columns)
    shear_min = tuple(min(value[2] for value in column) for column in columns)
    extremes = []
    for name, index, pick in (("M+", 1, max), ("M-", 1, min), ("V+", 2, max), ("V-", 2, min)):
        case, point = pick(((case, point) for case, own in zip(cases, samples, strict=True) for point in own),
                           key=lambda item: item[1][index])
        extremes.append((name, point[index], point[0], case))
    return Envelope(title, positions, moment_max, moment_min, shear_max, shear_min, tuple(segments), tuple(marks),
                    tuple(extremes), per_metre, tuple(_critical(samples, cases, section) for section in sections or []))


def long_beam_envelope(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> Envelope:
    """M(x) y V(x) de la viga larga en toda su longitud, con el salto de V en el eje de cada columna; secciones críticas:
    las caras de las columnas, las secciones a d hacia cada tramo y los extremos de momento (D-104)."""
    half = footing.lx / 2
    depth = beam_depth(footing, basis.bars)
    first = beam_case(footing, soil, *cases[0])
    sections = [(section.x, section.label) for section in moment_sections(first) if section.label.startswith("cara")]
    sections += [(section.x, section.label) for section in shear_sections(first, depth)]
    points = [-half + footing.lx * index / _SAMPLES for index in range(_SAMPLES + 1)]
    for column in footing.columns:
        points += [column.x - _JUMP, column.x + _JUMP]
    points = sorted({*points, *(x for x, _ in sections)})
    samples, names = [], []
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        samples.append([(x, beam.moment(x), beam.shear(x)) for x in points])
        names.append(pressure.case)
    marks = [(column.x, column.id) for column in footing.columns]
    layout: Layout = (marks, [(0, len(points) - 1)], False)
    envelope = _envelope("Dirección principal", samples, names, layout)
    extremes = {name: position for name, _, position, _ in envelope.extremes}
    sections += [(extremes["M+"], "momento positivo máximo"), (extremes["M-"], "momento negativo máximo")]
    sections = sorted(dict.fromkeys(sections), key=lambda item: item[0])
    return _envelope("Dirección principal", samples, names, layout, sections)


def _cantilever_points(start: float, end: float) -> list[float]:
    return [start + (end - start) * index / _CANTILEVER_SAMPLES for index in range(_CANTILEVER_SAMPLES + 1)]


def strip_envelopes(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> list[Envelope]:
    """Los voladizos de la franja de cada columna (zapata combinada sin viga), del borde −Y a la cara −Y y de la cara +Y
    al borde +Y."""
    depth = mat_rows(footing, footing.bottom, basis.bars)["y"].depth
    half = footing.ly / 2
    envelopes = []
    for index, column in enumerate(footing.columns):
        low, high = column.y - column.cy / 2, column.y + column.cy / 2
        # Secciones críticas de la franja (D-104): las caras de la columna y las secciones a d hacia cada borde.
        sections = [(low, f"cara -Y de {column.id}"), (high, f"cara +Y de {column.id}")]
        sections += [(at, f"a d de la cara {name} de {column.id}") for at, name in ((low - depth, "-Y"), (high + depth, "+Y"))
                     if -half < at < half]
        left = sorted({*_cantilever_points(-half, low), *(at for at, _ in sections if at < low)}) if low > -half else []
        right = sorted({*_cantilever_points(high, half), *(at for at, _ in sections if at > high)}) if high < half else []
        sections = [section for section in sections if section[0] in left or section[0] in right]
        samples, names = [], []
        for pressure, loads in cases:
            force = column_vertical(footing, soil, column, loads[index])
            load, _ = strip_load(footing, pressure, column, (force, depth))
            own = [(y, *strip_cantilever(footing, load, y, -1.0)) for y in left]
            # A la derecha, V del cuerpo libre a la izquierda: el opuesto de la carga neta entre la sección y el borde.
            own += [(y, strip_cantilever(footing, load, y, 1.0)[0], -strip_cantilever(footing, load, y, 1.0)[1]) for y in right]
            samples.append(own)
            names.append(pressure.case)
        segments = [segment for segment in ((0, len(left) - 1), (len(left), len(left) + len(right) - 1)) if segment[1] >= segment[0]]
        marks = [(low, f"cara -Y de {column.id}"), (high, f"cara +Y de {column.id}")]  # ASCII: la fuente del PDF no tiene "−"
        envelopes.append(_envelope(f"Franja transversal de la columna {column.id}", samples, names, (marks, segments, False),
                                   sorted(sections)))
    return envelopes


def flange_envelope(basis: Basis, footing: CombinedFooting, cases: Cases) -> Envelope:
    """Las dos aletas de la T invertida, por metro, en la sección x que gobierna el momento de las aletas en cada caso."""
    assert footing.beam is not None
    depth = mat_rows(footing, footing.bottom, basis.bars)["y"].depth
    face, edge = footing.beam.width / 2, footing.ly / 2
    offsets = sorted({*_cantilever_points(0.0, edge - face), *([depth] if depth < edge - face else [])})
    left = [-(face + offset) for offset in reversed(offsets)]  # del borde −Y a la cara −Y de la viga
    right = [face + offset for offset in offsets]  # de la cara +Y de la viga al borde +Y
    samples, names = [], []
    for pressure, _ in cases:
        flanges = Flanges(footing, pressure, depth)
        x = flanges.governing("moment")[0]
        own = []
        for y in left:
            shear, moment = flanges.section(x, -1.0, -y - face)
            own.append((y, moment * STRIP, shear * STRIP))
        for y in right:
            shear, moment = flanges.section(x, 1.0, y - face)
            own.append((y, moment * STRIP, -shear * STRIP))
        samples.append(own)
        names.append(pressure.case)
    segments = [(0, len(left) - 1), (len(left), len(left) + len(right) - 1)]
    marks = [(-face, "cara -Y de la viga"), (face, "cara +Y de la viga")]
    sections = [(-face, "cara -Y de la viga"), (face, "cara +Y de la viga")]
    if depth < edge - face:
        sections += [(-(face + depth), "a d de la cara -Y de la viga"), (face + depth, "a d de la cara +Y de la viga")]
    return _envelope("Aletas de la zarpa (por metro)", samples, names, (marks, segments, True), sorted(sections))


def combined_diagrams(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> tuple[Envelope, list[Envelope]]:
    """La envolvente de la dirección principal y las de la secundaria (franjas o aletas) de la zapata, en los ejes
    declarados (D-101): la posición a lo largo de la viga ya es la coordenada global de la dirección principal; la
    transversal se convierte."""
    longitudinal = long_beam_envelope(basis, footing, soil, cases)
    transverse = [flange_envelope(basis, footing, cases)] if footing.beam is not None else strip_envelopes(basis, footing, soil, cases)
    return longitudinal, [declared_envelope(footing, envelope) for envelope in transverse]
