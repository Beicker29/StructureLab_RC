"""Barras de cada zapata para el despiece (v3 Fase 4A, D-125): las mismas filas de barras que revisa la verificación, con
los límites del perfil (ganchos estándar y de estribo, empalme por traslapo con su clase y empalme a compresión de los
pasadores). El despiece en sí (cortes, empalmes por longitud comercial, marcas y cartilla) es neutro, en detailing/.

Reglas propias del despiece:
- Las barras de las mallas van de borde a borde menos el recubrimiento; con `end: hook`, gancho estándar de 90° en los
  dos extremos.
- La clase del empalme sale del As provisto sobre el requerido: en las barras x de la combinada, con el mayor momento de su
  cara (el lado conservador: el empalme puede caer en cualquier parte); en las demás barras no se calcula el As requerido
  en la zona del empalme y el empalme es clase B. La fracción empalmada es la mitad (empalmes escalonados en detailing/)
  si hay más de una barra.
- Pasadores: rectos hasta la malla inferior con gancho de 90° al pie, el pedestal y, encima, el empalme a compresión del
  propio pasador (las barras de la columna no están en el modelo).
- Estribos cerrados con ganchos de 135°: con más de dos ramas, estribos cerrados anidados de dos ramas cada uno.

Cada corrida lleva su ubicación (Placement) para el dibujo (D-126): las mismas posiciones que revisa la verificación.
Los pasadores se dibujan en dos esquinas de la columna, a un recubrimiento de sus caras (esquemático: la disposición de
los pasadores no está en el modelo).
"""

import math
from collections.abc import Sequence
from dataclasses import replace

from structurelab_rc.detailing.schedule import BarRun, Hook, Placement
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.development import BarAnchorage, lap_splice
from structurelab_rc.domain.footing.combined_beam import beam_member, covered_width, extreme_moments
from structurelab_rc.domain.footing.combined_columns import (
    band_row,
    band_top_row,
    steel_excess,
    transverse_bottom,
    transverse_top,
)
from structurelab_rc.domain.footing.connection import bar_anchorage
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_rows
from structurelab_rc.errors import StructuredError
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedColumn, CombinedFooting
from structurelab_rc.model.footing import Column, Dowels, Footing, Soil
from structurelab_rc.model.project import Section
from structurelab_rc.model.reinforcement import ReinforcementLayout, Stirrups

_CLASS_B_NOTE = "sin el As requerido en la zona del empalme"


def _spec(bars: Sequence[RebarSpec], designation: str) -> RebarSpec:
    return next(bar for bar in bars if bar.designation == designation)


def _hook(basis: Basis, db: float) -> Hook:
    detailing = basis.profile.detailing
    return Hook(90, detailing.hook_bend_diameter(db), detailing.hook_extension(db, 90))


def _hooks(basis: Basis, db: float, end: str) -> tuple[Hook | None, Hook | None]:
    hook = _hook(basis, db) if end == "hook" else None
    return hook, hook


def _row_run(basis: Basis, row: BarRow, given: tuple[str, float, tuple[Hook | None, Hook | None]],
             anchorage: tuple[float, bool, tuple[float, float], float | None]) -> BarRun | None:
    """Las barras de una fila: given = (grupo, largo exterior, ganchos); anchorage = (separación, malla inferior, (h,
    recubrimiento), As provisto/As requerido o None si no se calcula)."""
    group, length, hooks = given
    spacing, bottom, footing, ratio = anchorage
    count = len(row.positions)
    if count == 0:
        return None
    # depth se mide desde la cara opuesta a la fila: abajo, z = h − d; arriba, z = d.
    place = Placement(row.direction, row.positions, footing[0] - row.depth if bottom else row.depth, (-length / 2, length / 2))
    bar = bar_anchorage(row, ("straight", spacing, bottom), footing, 1.0)
    lap = lap_splice(basis.profile, basis.materials, bar, (1.0 if ratio is None else ratio, 0.5 if count > 1 else 1.0))
    spec = _spec(basis.bars, row.designation)
    if isinstance(lap, StructuredError):
        return BarRun(group, row.designation, spec.diameter_mm, spec.mass_kg_m, count, length, hooks, note=lap.message,
                      placement=place)
    note = f"empalme clase {lap[1]}" + (f": {_CLASS_B_NOTE}" if ratio is None else "")
    return BarRun(group, row.designation, spec.diameter_mm, spec.mass_kg_m, count, length, hooks, lap[0], note=note,
                  placement=place)


def _dowel_run(basis: Basis, dowels: Dowels | None, embed: float, pedestal: float, column: str) -> BarRun | None:
    """Pasadores de una columna: tramo vertical (empotramiento hasta la malla inferior, pedestal y empalme a compresión)
    con gancho de 90° al pie. Sin ubicación: la agrega _placed_dowels."""
    if dowels is None:
        return None
    spec = _spec(basis.bars, dowels.designation)
    materials = basis.materials
    lap = basis.profile.detailing.compression_lap_length(materials.fy, materials.fc, spec.diameter_mm)
    note = f"columna {column}: empotramiento {embed:.0f} mm + pedestal {pedestal:.0f} mm + empalme a compresión"
    if lap is None:
        return BarRun("pasadores", dowels.designation, spec.diameter_mm, spec.mass_kg_m, dowels.count, embed + pedestal,
                      (_hook(basis, spec.diameter_mm), None),
                      note=f"columna {column}: el perfil no define el empalme a compresión con este fy; sin la parte de la columna")
    return BarRun("pasadores", dowels.designation, spec.diameter_mm, spec.mass_kg_m, dowels.count, embed + pedestal + lap,
                  (_hook(basis, spec.diameter_mm), None), note=f"{note} {lap:.0f} mm")


def _placed_dowels(run: BarRun | None, column: Column | CombinedColumn, top_embed: tuple[float, float], cover: float) -> BarRun | None:
    """Los pasadores con su ubicación: el pie a embed bajo la cara superior top de la zapata (en la T, de la viga) y dos
    esquinas de la columna a un recubrimiento de sus caras (esquemático)."""
    if run is None:
        return None
    top, embed = top_embed
    centre = (column.offset_x, column.offset_y) if isinstance(column, Column) else (column.x, column.y)
    foot = top - embed
    return replace(run, placement=Placement("z", centre, foot, (foot, foot + run.length),
                                            (column.cx / 2 - cover, column.cy / 2 - cover)))


def _stirrup_runs(basis: Basis, stirrups: Stirrups | None, frame: tuple[float, float, float], along: float) -> list[BarRun]:
    """Estribos cerrados de una viga de ancho × alto × recubrimiento, repartidos en el largo along: los de dos ramas
    anidados para las ramas que haya."""
    if stirrups is None:
        return []
    width, height, cover = frame
    spec = _spec(basis.bars, stirrups.designation)
    db = spec.diameter_mm
    detailing = basis.profile.detailing
    extension = detailing.stirrup_hook_extension(db, 135)
    if extension is None:
        return [BarRun("estribos", stirrups.designation, db, spec.mass_kg_m, 0, 0.0,
                       note="el perfil no define el gancho de 135° para esta barra")]
    hook = Hook(135, detailing.stirrup_bend_diameter(db), extension)
    count = math.floor((along - 2 * cover) / stirrups.spacing + 1e-6) + 1
    outer_width, outer_height = width - 2 * cover, height - 2 * cover
    gap = (outer_width - db) / max(stirrups.legs - 1, 1)
    stations = tuple(-along / 2 + cover + index * stirrups.spacing for index in range(count))
    place = Placement("estribo", stations, cover, (-along / 2, along / 2))
    runs = []
    for pair in range(max(stirrups.legs // 2, 1)):
        closed = (outer_width - 2 * pair * gap, outer_height)
        runs.append(BarRun("estribos", stirrups.designation, db, spec.mass_kg_m, count, 0.0, (hook, hook), stirrup=closed,
                           note=f"{stirrups.legs} ramas c/{stirrups.spacing:.0f} mm", placement=place))
    return runs


def footing_runs(basis: Basis, footing: Footing) -> list[BarRun]:
    """Zapata aislada: malla inferior, malla superior si la hay y pasadores."""
    h, cover = footing.h, footing.cover
    runs = []
    for name, mat in (("inferior", footing.bottom), ("superior", footing.top)):
        if mat is None:
            continue
        for direction, row in mat_rows(footing, mat, basis.bars).items():
            bar_set = getattr(mat, direction)
            length = (footing.lx if direction == "x" else footing.ly) - 2 * cover
            spacing = min(bar_set.spacing, bar_set.band_spacing or bar_set.spacing)
            run = _row_run(basis, row, (f"malla {name} {direction}", length, _hooks(basis, row.diameter, mat.end)),
                           (spacing, name == "inferior", (h, cover), None))
            if run is not None:
                runs.append(run)
    rows = mat_rows(footing, footing.bottom, basis.bars)
    embed = h - cover - rows["x"].diameter - rows["y"].diameter
    dowels = _placed_dowels(_dowel_run(basis, footing.column.dowels, embed, footing.pedestal_height, footing.id),
                            footing.column, (h, embed), cover)
    return [*runs, *([] if dowels is None else [dowels])]


def _x_ratio(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, BarRow | None]) -> tuple[float | None, float | None]:
    """As provisto/As requerido de las barras x inferiores y superiores con el mayor momento de su cara (D-125)."""
    cases, failures = combined_factored_cases(footing, soil)
    if failures or not cases:
        return None, None
    positive, negative = extreme_moments(footing, soil, cases)
    ratios: list[float | None] = []
    for row, (moment, _) in zip(rows, (positive, negative), strict=True):
        if row is None or moment <= 0:
            ratios.append(None if row is None else math.inf)
            continue
        excess = steel_excess(basis, (footing.ly, footing.h, row.depth), row.area, moment, footing.min_steel_exception)
        ratios.append(1 / excess if excess > 0 else math.inf)
    return ratios[0], ratios[1]


def combined_runs(basis: Basis, footing: CombinedFooting, soil: Soil) -> list[BarRun]:
    """Zapata combinada rectangular o T invertida: mallas, band y band superior, barras superiores, piel o capas de la
    viga, estribos y pasadores."""
    if footing.beam is not None:
        return _t_runs(basis, footing)
    h, cover, bars = footing.h, footing.cover, basis.bars
    along, across = footing.lx - 2 * cover, footing.ly - 2 * cover
    bottom, tops = mat_rows(footing, footing.bottom, bars), top_rows(footing, bars)
    ratio_bottom, ratio_top = _x_ratio(basis, footing, soil, (bottom["x"], tops.get("x")))
    geometry = (h, cover)
    runs: list[BarRun | None] = [
        _row_run(basis, bottom["x"], ("malla inferior x", along, _hooks(basis, bottom["x"].diameter, footing.bottom.end)),
                 (footing.bottom.x.spacing, True, geometry, ratio_bottom)),
        _row_run(basis, transverse_bottom(footing, bottom["y"]),
                 ("malla inferior y", across, _hooks(basis, bottom["y"].diameter, footing.bottom.end)),
                 (footing.bottom.y.spacing, True, geometry, None)),
    ]
    for column in footing.columns:
        band = band_row(footing, column, bottom["y"], basis)
        if band is not None and column.band is not None:
            runs.append(_row_run(basis, band, (f"band columna {column.id}", across, _hooks(basis, band.diameter, footing.bottom.end)),
                                 (column.band.spacing, True, geometry, None)))
    if footing.top is not None:
        end = footing.top.end
        if "x" in tops and footing.top.x is not None:
            runs.append(_row_run(basis, tops["x"], ("barras superiores x", along, _hooks(basis, tops["x"].diameter, end)),
                                 (footing.top.x.spacing, False, geometry, ratio_top)))
        across_top = transverse_top(footing, tops.get("y"), bottom["y"].depth)
        if across_top is not None and footing.top.y is not None:
            runs.append(_row_run(basis, across_top, ("barras superiores y", across, _hooks(basis, across_top.diameter, end)),
                                 (footing.top.y.spacing, False, geometry, None)))
    for column in footing.columns:
        band_top = band_top_row(footing, column, bottom["y"].depth, bars)
        if band_top is not None and column.band_top is not None:
            end = footing.top.end if footing.top is not None else footing.bottom.end
            runs.append(_row_run(basis, band_top, (f"band superior columna {column.id}", across, _hooks(basis, band_top.diameter, end)),
                                 (column.band_top.spacing, False, geometry, None)))
    if footing.skin is not None:
        section, layout = beam_member(footing, (bottom["x"], tops.get("x")), bars)
        skin = [bar for bar in placed_bars(layout, section, bars) if bar.role == "skin"]
        depths = sorted({round(bar.depth, 1) for bar in skin})
        spec = _spec(bars, footing.skin.designation)
        for depth in depths:  # una corrida por nivel, para el dibujo; la cartilla las reúne en una marca
            ys = tuple(bar.x - footing.ly / 2 for bar in skin if round(bar.depth, 1) == depth)
            runs.append(BarRun("piel", spec.designation, spec.diameter_mm, spec.mass_kg_m, len(ys), along,
                               note=f"{len(depths)} niveles en cada cara lateral",
                               placement=Placement("x", ys, h - depth, (-along / 2, along / 2))))
    runs += _stirrup_runs(basis, footing.stirrups, (footing.ly, h, cover), footing.lx)
    embed = h - cover - bottom["x"].diameter - bottom["y"].diameter
    runs += [_placed_dowels(_dowel_run(basis, column.dowels, embed, footing.pedestal_height, column.id), column, (h, embed), cover)
             for column in footing.columns]
    return [run for run in runs if run is not None]


def _layer_run(basis: Basis, bar: tuple[str, RebarSpec, int, tuple[Hook | None, Hook | None]],
               layer: tuple[list[float], float, float, float], length: float) -> BarRun:
    """Las barras de una capa de la viga de la T con su empalme (clase B: sin el As requerido en la zona del empalme):
    layer = (posiciones x, profundidad desde la cara superior, alto de la viga, recubrimiento libre con el estribo)."""
    name, spec, count, hooks = bar
    xs, depth, height, clear = layer
    db = spec.diameter_mm
    gaps = [b - a for a, b in zip(xs, xs[1:], strict=False)]
    spacing = min(gaps) if gaps else 2 * (clear + db / 2)
    anchorage = BarAnchorage(db, "straight", cb=min(clear + db / 2, spacing / 2), concrete_below=height - depth,
                             clear_cover=clear, clear_spacing=spacing - db)
    lap = lap_splice(basis.profile, basis.materials, anchorage, (1.0, 0.5 if count > 1 else 1.0))
    if isinstance(lap, StructuredError):
        return BarRun(name, spec.designation, db, spec.mass_kg_m, count, length, hooks, note=lap.message)
    return BarRun(name, spec.designation, db, spec.mass_kg_m, count, length, hooks, lap[0],
                  note=f"empalme clase {lap[1]}: {_CLASS_B_NOTE}")


def _t_runs(basis: Basis, footing: CombinedFooting) -> list[BarRun]:
    """T invertida: capas de la viga (barras longitudinales), estribos, malla de la zarpa (las barras x fuera del ancho
    que cubre la capa inferior de la viga), malla superior de la zarpa si la hay y pasadores anclados en la viga."""
    beam = footing.beam
    assert beam is not None
    h, cover, bars = footing.h, footing.cover, basis.bars
    along, across = footing.lx - 2 * cover, footing.ly - 2 * cover
    section = Section(bw=beam.width, h=beam.height, cover=cover)
    placed = placed_bars(ReinforcementLayout(layers=beam.layers, stirrups=beam.stirrups), section, bars)
    groups: dict[tuple[str, float, str], list[float]] = {}
    for bar in placed:
        groups.setdefault((bar.role, round(bar.depth, 1), bar.designation), []).append(bar.x)
    stirrup = 0.0 if beam.stirrups is None else _spec(bars, beam.stirrups.designation).diameter_mm
    runs: list[BarRun | None] = []
    for (role, depth, designation), xs in groups.items():
        spec = _spec(bars, designation)
        name = "piel de la viga" if role == "skin" else f"viga, capa a {depth:.0f} mm"
        hooks = _hooks(basis, spec.diameter_mm, beam.end) if role == "flexure" else (None, None)
        run = _layer_run(basis, (name, spec, len(xs), hooks), (sorted(xs), depth, beam.height, cover + stirrup), along)
        ys = tuple(x - beam.width / 2 for x in sorted(xs))
        runs.append(replace(run, placement=Placement("x", ys, beam.height - depth, (-along / 2, along / 2))))
    runs += _stirrup_runs(basis, beam.stirrups, (beam.width, beam.height, cover), footing.lx)
    rows = mat_rows(footing, footing.bottom, bars)
    half = covered_width(basis.profile, footing) / 2
    outside = BarRow(**{**rows["x"].__dict__, "positions": tuple(y for y in rows["x"].positions if abs(y) > half + 1e-6)})
    geometry = (h, cover)
    runs.append(_row_run(basis, outside, ("zarpa, malla inferior x", along, _hooks(basis, outside.diameter, footing.bottom.end)),
                         (footing.bottom.x.spacing, True, geometry, None)))
    runs.append(_row_run(basis, rows["y"], ("zarpa, malla inferior y (aletas)", across,
                                            _hooks(basis, rows["y"].diameter, footing.bottom.end)),
                         (footing.bottom.y.spacing, True, geometry, None)))
    if footing.top is not None:
        for direction, row in top_rows(footing, bars).items():
            bar_set = getattr(footing.top, direction)
            length = along if direction == "x" else across
            runs.append(_row_run(basis, row, (f"zarpa, malla superior {direction}", length,
                                              _hooks(basis, row.diameter, footing.top.end)),
                                 (bar_set.spacing, False, geometry, None)))
    embed = footing.total_height - cover - rows["y"].diameter
    runs += [_placed_dowels(_dowel_run(basis, column.dowels, embed, footing.pedestal_height, column.id), column,
                            (footing.total_height, embed), cover) for column in footing.columns]
    return [run for run in runs if run is not None]
