"""Barras del muro de contención en voladizo para el despiece (D-175): las mismas que revisa la verificación, con los
límites del perfil (ganchos estándar y empalme por traslapo con su clase) que usan las zapatas. El despiece en sí
(cortes, empalmes por longitud comercial, marcas y cartilla) es neutro, en detailing/.

Ejes del muro: x a través (de la puntera, x = −B/2, al talón, x = B/2), y a lo largo (−L/2 a L/2) y z desde la cara
inferior de la base.

- Verticales de las dos caras de la pantalla (decisión del usuario): continuas desde la malla inferior de la base hasta
  la corona, con el extremo declarado al pie (gancho hacia la puntera las de la cara del relleno, hacia el talón las de
  la cara exterior) y el gancho declarado de la corona (stem.crown_end, 90° o 180°) hacia la otra cara; sin cortes de
  barras (el corte a media altura queda para el diseño, fase B). Se empalman si pasan de la longitud comercial.
- Horizontales de cada cara de la pantalla y longitudinales de cada cara de la base: a lo largo del muro, de extremo a
  extremo menos el recubrimiento, con el extremo declarado; por dentro de las verticales y de las transversales.
- Transversales superiores e inferiores de la base: de la puntera al talón menos el recubrimiento.
- Clase del empalme (D-129, como las zapatas): con el mayor momento mayorado de la verticales de la cara del relleno
  (la pantalla) y de las transversales (el talón arriba, la puntera abajo); las de retracción, sin demanda por análisis,
  en clase B. Las barras van a su separación en el tramo útil (uniform_positions), con la de los extremos a un
  recubrimiento más medio diámetro.
"""

import math

from structurelab_rc.detailing.schedule import BarRun, Hook, Placement
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.development import BarAnchorage, lap_splice
from structurelab_rc.domain.footing.detailing import bar_hook, class_note, splice_ratio
from structurelab_rc.domain.footing.mesh import uniform_positions
from structurelab_rc.domain.retaining_wall.base import HEEL, TOE, base_moments
from structurelab_rc.domain.retaining_wall.slab import STRIP, per_strip
from structurelab_rc.domain.retaining_wall.stem import stem_moment
from structurelab_rc.domain.retaining_wall.thrust import stability_thrust, stem_thrust
from structurelab_rc.errors import StructuredError
from structurelab_rc.model.footing import BarSet
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

STEM_BACK = "pantalla vertical cara del relleno"
STEM_FRONT = "pantalla vertical cara exterior"
STEM_HORIZONTAL = "pantalla horizontal"
BASE_TOP = "base transversal superior"
BASE_BOTTOM = "base transversal inferior"
BASE_LONGITUDINAL = "base longitudinal"


def wall_concrete(wall: RetainingWall) -> float:
    """Volumen de concreto de un muro (base y pantalla en su largo), en m³."""
    assert wall.length is not None
    return (wall.base_width * wall.base_thickness + wall.stem_thickness * wall.stem_height) * wall.length / 1e9


def _run(basis: Basis, bars: BarSet, given: tuple[str, float, tuple[Hook | None, Hook | None], Placement],
         anchorage: tuple[float, float, float | None]) -> BarRun:
    """Las barras de un grupo: given = (grupo, largo exterior, ganchos, ubicación); anchorage = (recubrimiento libre,
    concreto fresco bajo la barra, As provisto/As requerido o None sin demanda por análisis) para su empalme."""
    group, length, hooks, place = given
    cover, below, ratio = anchorage
    _, diameter = per_strip(basis, bars)
    spec = next(bar for bar in basis.bars if bar.designation == bars.designation)
    count = len(place.positions)
    bar = BarAnchorage(diameter, "straight", cb=min(cover + diameter / 2, bars.spacing / 2), concrete_below=below,
                       clear_cover=cover, clear_spacing=bars.spacing - diameter)
    lap = lap_splice(basis.profile, basis.materials, bar, (1.0 if ratio is None else ratio, 0.5 if count > 1 else 1.0))
    if isinstance(lap, StructuredError):
        return BarRun(group, bars.designation, diameter, spec.mass_kg_m, count, length, hooks, note=lap.message, placement=place)
    return BarRun(group, bars.designation, diameter, spec.mass_kg_m, count, length, hooks, lap[0], note=class_note(lap[1], ratio),
                  placement=place)


def _ratio(basis: Basis, section: tuple[float, float], bars: BarSet, moment: float | None) -> float | None:
    """As provisto / As requerido por franja de 1 m con el mayor momento mayorado (D-129); None sin él."""
    if moment is None:
        return None
    thickness, cover = section
    area, diameter = per_strip(basis, bars)
    return splice_ratio(basis, (STRIP, thickness, thickness - cover - diameter / 2), area, moment)


def wall_runs(basis: Basis, wall: RetainingWall, soil: RetainingSoil) -> list[BarRun]:
    """Las barras de un muro para su cartilla y su dibujo (D-175)."""
    crown_end = wall.stem.crown_end
    assert wall.length is not None and crown_end is not None
    length, width, hb = wall.length, wall.base_width, wall.base_thickness
    stem, base = wall.stem, wall.base
    front_face = -width / 2 + wall.toe
    back_face = front_face + wall.stem_thickness
    top = hb + wall.stem_height
    db = {name: per_strip(basis, bars)[1] for name, bars in
          (("back", stem.back), ("front", stem.front), ("horizontal", stem.horizontal), ("top", base.top),
           ("bottom", base.bottom), ("longitudinal", base.longitudinal))}
    stem_cover, base_cover = wall.stem_cover, wall.base_cover
    moments = base_moments(wall, soil, stability_thrust(wall, soil), "factored")
    runs: list[BarRun] = []

    def along(bars: BarSet, diameter: float, cover: float) -> tuple[float, ...]:
        return tuple(uniform_positions(-length / 2 + cover + diameter / 2, length / 2 - cover - diameter / 2, bars.spacing))

    # Verticales: del pie, sobre las transversales inferiores, a la corona.
    foot = base_cover + db["bottom"]
    crown = top - stem_cover
    for group, bars, key, x, legs, moment in (
            (STEM_BACK, stem.back, "back", back_face - stem_cover - db["back"] / 2, (-1.0, -1.0),
             stem_moment(wall, stem_thrust(wall, soil))),
            (STEM_FRONT, stem.front, "front", front_face + stem_cover + db["front"] / 2, (1.0, 1.0), None)):
        hooks = (bar_hook(basis, db[key], bars.end), bar_hook(basis, db[key], crown_end))
        place = Placement("vertical", along(bars, db[key], stem_cover), x, (foot, crown), legs)
        ratio = _ratio(basis, (wall.stem_thickness, stem_cover), bars, moment or None)
        runs.append(_run(basis, bars, (group, crown - foot, hooks, place), (stem_cover, 0.0, ratio)))
    # Horizontales de cada cara de la pantalla, por dentro de las verticales.
    horizontal = stem.horizontal
    heights = tuple(uniform_positions(hb + stem_cover + db["horizontal"] / 2, crown - db["horizontal"] / 2, horizontal.spacing))
    span = (-length / 2 + stem_cover, length / 2 - stem_cover)
    hooks = (bar_hook(basis, db["horizontal"], horizontal.end), bar_hook(basis, db["horizontal"], horizontal.end))
    for face, x in (("cara del relleno", back_face - stem_cover - db["back"] - db["horizontal"] / 2),
                    ("cara exterior", front_face + stem_cover + db["front"] + db["horizontal"] / 2)):
        place = Placement("y", heights, x, span, vertical=True)
        runs.append(_run(basis, horizontal, (f"{STEM_HORIZONTAL} {face}", span[1] - span[0], hooks, place), (stem_cover, 0.0, None)))
    # Transversales de la base, de la puntera al talón.
    for group, bars, key, z, moment, below in (
            (BASE_TOP, base.top, "top", hb - base_cover - db["top"] / 2, moments[HEEL], hb - base_cover - db["top"] / 2),
            (BASE_BOTTOM, base.bottom, "bottom", base_cover + db["bottom"] / 2, moments[TOE], 0.0)):
        hooks = (bar_hook(basis, db[key], bars.end), bar_hook(basis, db[key], bars.end))
        place = Placement("x", along(bars, db[key], base_cover), z, (-width / 2 + base_cover, width / 2 - base_cover))
        ratio = _ratio(basis, (hb, base_cover), bars, moment)
        runs.append(_run(basis, bars, (group, width - 2 * base_cover, hooks, place), (base_cover, below, ratio)))
    # Longitudinales de cada cara de la base, por dentro de las transversales.
    longitudinal = base.longitudinal
    across = tuple(uniform_positions(-width / 2 + base_cover + db["longitudinal"] / 2, width / 2 - base_cover - db["longitudinal"] / 2,
                                     longitudinal.spacing))
    span = (-length / 2 + base_cover, length / 2 - base_cover)
    hooks = (bar_hook(basis, db["longitudinal"], longitudinal.end), bar_hook(basis, db["longitudinal"], longitudinal.end))
    for face, z in (("superior", hb - base_cover - db["top"] - db["longitudinal"] / 2),
                    ("inferior", base_cover + db["bottom"] + db["longitudinal"] / 2)):
        place = Placement("y", across, z, span)
        runs.append(_run(basis, longitudinal, (f"{BASE_LONGITUDINAL} {face}", span[1] - span[0], hooks, place),
                         (base_cover, z if face == "superior" else 0.0, None)))
    return [run for run in runs if run.count > 0 and not math.isclose(run.length, 0.0)]
