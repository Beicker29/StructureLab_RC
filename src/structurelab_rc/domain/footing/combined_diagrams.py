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
"""

from dataclasses import dataclass

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.combined_beam import beam_case
from structurelab_rc.domain.footing.combined_columns import Cases, strip_cantilever, strip_load
from structurelab_rc.domain.footing.inverted_t import STRIP, Flanges
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil

_SAMPLES = 120  # intervalos a lo largo de la viga larga
_CANTILEVER_SAMPLES = 40  # intervalos por voladizo transversal
_JUMP = 1e-3  # mm: a cada lado del eje de una columna, para dibujar el salto de V


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


Layout = tuple[list[tuple[float, str]], list[tuple[int, int]], bool]  # marcas, tramos y si es por metro


def _envelope(title: str, samples: list[list[tuple[float, float, float]]], cases: list[str], layout: Layout) -> Envelope:
    """samples[c] = [(posición, M, V)] del caso c, con las mismas posiciones en todos los casos."""
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
                    tuple(extremes), per_metre)


def long_beam_envelope(footing: CombinedFooting, soil: Soil, cases: Cases) -> Envelope:
    """M(x) y V(x) de la viga larga en toda su longitud, con el salto de V en el eje de cada columna."""
    half = footing.lx / 2
    points = [-half + footing.lx * index / _SAMPLES for index in range(_SAMPLES + 1)]
    for column in footing.columns:
        points += [column.x - _JUMP, column.x + _JUMP]
    points.sort()
    samples, names = [], []
    for pressure, loads in cases:
        beam = beam_case(footing, soil, pressure, loads)
        samples.append([(x, beam.moment(x), beam.shear(x)) for x in points])
        names.append(pressure.case)
    marks = [(column.x, column.id) for column in footing.columns]
    return _envelope("Viga en la dirección larga", samples, names, (marks, [(0, len(points) - 1)], False))


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
        left = _cantilever_points(-half, low) if low > -half else []
        right = _cantilever_points(high, half) if high < half else []
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
        envelopes.append(_envelope(f"Franja transversal de la columna {column.id}", samples, names, (marks, segments, False)))
    return envelopes


def flange_envelope(basis: Basis, footing: CombinedFooting, cases: Cases) -> Envelope:
    """Las dos aletas de la T invertida, por metro, en la sección x que gobierna el momento de las aletas en cada caso."""
    assert footing.beam is not None
    depth = mat_rows(footing, footing.bottom, basis.bars)["y"].depth
    face, edge = footing.beam.width / 2, footing.ly / 2
    offsets = _cantilever_points(0.0, edge - face)
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
    return _envelope("Aletas de la zarpa (por metro)", samples, names, (marks, segments, True))


def combined_diagrams(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> tuple[Envelope, list[Envelope]]:
    """La envolvente longitudinal y las transversales (franjas o aletas) de la zapata."""
    longitudinal = long_beam_envelope(footing, soil, cases)
    transverse = [flange_envelope(basis, footing, cases)] if footing.beam is not None else strip_envelopes(basis, footing, soil, cases)
    return longitudinal, transverse
