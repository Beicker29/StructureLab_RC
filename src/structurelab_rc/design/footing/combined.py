"""Diseño de una zapata combinada rectangular de dos columnas (v3 Fase 3B, D-107).

El diseño no tiene fórmulas propias: propone zapatas y las aprueba con la verificación de la combinada
(`domain/footing/checks.combined_footing_checks`). Para proponer barras usa los momentos de la viga larga y de las franjas
de `domain/footing` y el As requerido de `design/bars`.

- Ubicación: el centroide de la base coincide con la resultante de las fuerzas de las columnas en el caso de servicio
  sin sismo de mayor carga (D+L), con los momentos y los cortantes llevados a la base, como en `combined_resultant`:
  así ese caso no tiene excentricidad. Un voladizo máximo declarado (columna de lindero) puede impedirlo: la base se
  corre lo necesario y queda excéntrica.
- Largo: el menor que cubre las dos columnas con esa ubicación, al paso de la planta; luego los mayores (la primera
  solución y _EXTRA_LENGTHS más, la heurística de D-069). Ancho: el menor, al paso, que cumple la revisión geotécnica.
- Espesor: el menor con solución, por bisección, y los mayores mientras el concreto solo no alcance el mejor costo.
- Refuerzo: cada grupo (barras inferiores y superiores x de la viga larga, continuas y sin cortes; band de cada
  columna; malla inferior y fuera de las franjas; barras superiores y; refuerzo superficial; pasadores de cada columna)
  empieza en su opción más liviana y, si una verificación suya falla, pasa a la más liviana que corrige esa falla: más
  área, menor diámetro (desarrollo), más luz libre o menor separación. Las fallas de cortante, punzonamiento, torsión o
  deformación unitaria piden más espesor; sin estribos (D-107).
- f'c: se repite para cada resistencia de la lista y gana la de menor costo.
"""

import math
import re
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES, Profile
from structurelab_rc.design.bars import Spread, bar_count, bar_options
from structurelab_rc.design.footing.typologies import load_input, soil_input
from structurelab_rc.design.stirrups import StirrupFrame, stirrup_options
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.deep import CURTAINS as DEEP_CURTAINS
from structurelab_rc.domain.beam.deep import LONGITUDINAL as DEEP_LONGITUDINAL
from structurelab_rc.domain.beam.deep import SECTION as DEEP_SECTION
from structurelab_rc.domain.beam.deep import SPACING as DEEP_SPACING
from structurelab_rc.domain.beam.deep import TRANSVERSE as DEEP_TRANSVERSE
from structurelab_rc.domain.beam.flexure import SKIN
from structurelab_rc.domain.beam.shear import MIN_REINFORCEMENT as SHEAR_MINIMUM
from structurelab_rc.domain.beam.shear import SECTION as SHEAR_SECTION
from structurelab_rc.domain.beam.shear import SPACING as SHEAR_SPACING
from structurelab_rc.domain.beam.shear import STRENGTH as SHEAR_STRENGTH
from structurelab_rc.domain.beam.torsion import DETAILING as TORSION_DETAILING
from structurelab_rc.domain.beam.torsion import LONGITUDINAL as TORSION_LONGITUDINAL
from structurelab_rc.domain.beam.torsion import MIN_TRANSVERSE as TORSION_MIN_TRANSVERSE
from structurelab_rc.domain.beam.torsion import SECTION as TORSION_SECTION
from structurelab_rc.domain.beam.torsion import TRANSVERSE as TORSION_TRANSVERSE
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.checks import combined_footing_checks
from structurelab_rc.domain.footing.combined_beam import SPACING as LONG_SPACING
from structurelab_rc.domain.footing.combined_beam import beam_member, extreme_moments
from structurelab_rc.domain.footing.combined_columns import (
    PLATE_PLAIN,
    PLATE_SHEAR,
    band_row,
    band_top_row,
    outside_twist,
    strip_demands,
    strip_limits,
    strip_moments,
    strip_twist,
    transverse_bottom,
    transverse_top,
)
from structurelab_rc.domain.footing.inverted_t import DEPTH as T_DEPTH
from structurelab_rc.domain.footing.inverted_t import DEVELOPMENT as T_DEVELOPMENT
from structurelab_rc.domain.footing.inverted_t import DEVELOPMENT_TOP as T_DEVELOPMENT_TOP
from structurelab_rc.domain.footing.inverted_t import FLEXURE as T_FLEXURE
from structurelab_rc.domain.footing.inverted_t import FLEXURE_TOP as T_FLEXURE_TOP
from structurelab_rc.domain.footing.inverted_t import MINIMUM as T_MINIMUM
from structurelab_rc.domain.footing.inverted_t import PLAIN as T_PLAIN
from structurelab_rc.domain.footing.inverted_t import SHEAR as T_SHEAR
from structurelab_rc.domain.footing.inverted_t import SPACING as T_SPACING
from structurelab_rc.domain.footing.inverted_t import STRAIN as T_STRAIN
from structurelab_rc.domain.footing.inverted_t import TENSION_FLANGE as T_TENSION_FLANGE
from structurelab_rc.domain.footing.inverted_t import Flanges
from structurelab_rc.domain.footing.loads import FactoredCase, combined_factored_cases
from structurelab_rc.domain.footing.mesh import mat_rows, top_rows, uniform_positions
from structurelab_rc.domain.footing.service import combined_service_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.design import CombinedDesign, CombinedDesignColumn, CombinedDesignProject
from structurelab_rc.model.footing import FootingLoad
from structurelab_rc.model.project import Materials, Project

FOOTING_ID = "ZC1"
_EXTRA_LENGTHS = 2  # largos mayores que se exploran después del primero con solución
_ROUNDS = 60  # ajustes del refuerzo por espesor
_DOWELS_MIN = 4
_DOWEL_COUNTS = 6  # cantidades por designación de pasadores, desde la mínima
_SKIN_MIN_SPACING = 100.0  # mm
_TOUCH = 1.0  # mm: una barra de piel a menos de esto de la capa superior se omite (como combined_beam)
_MM3_PER_M3 = 1e9
_SOIL = ("Presion admisible del suelo", "Contacto con el suelo", "Deslizamiento", "Volcamiento")
_THICKNESS = ("Cortante", "Punzonamiento", "Torsion", "Flexion: deformacion neta")
# demanda = área requerida y capacidad = área provista: la proporción que falta
_SCALED = (TORSION_LONGITUDINAL, DEEP_TRANSVERSE, DEEP_LONGITUDINAL)
_STIRRUP_CHECKS = (SHEAR_STRENGTH, SHEAR_MINIMUM, SHEAR_SPACING, TORSION_TRANSVERSE, TORSION_MIN_TRANSVERSE)
Cases = list[tuple[FactoredCase, tuple[FootingLoad, ...]]]
_COLUMN = re.compile(r"columna (\S+?)(?=[\s,):]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Context:
    """Lo que no cambia durante la búsqueda."""

    project: CombinedDesignProject
    profile: Profile
    bars: Sequence[RebarSpec]

    @property
    def design(self) -> CombinedDesign:
        return self.project.combined_design

    def materials(self, fc: float) -> Materials:
        m = self.project.materials
        return Materials(fc=fc, fy=m.fy, fyt=m.fyt, concrete=m.concrete, coating=m.coating, max_aggregate=m.max_aggregate)

    def basis(self, fc: float) -> Basis:
        return Basis(self.profile, self.materials(fc), self.bars, self.project.seismic.level)

    def spec(self, designation: str) -> RebarSpec:
        return next(bar for bar in self.bars if bar.designation == designation)

    def axes(self) -> tuple[str, str]:
        """(eje global de la dirección principal, eje global transversal)."""
        return ("x", "y") if self.project.principal_direction == "x" else ("y", "x")


@dataclass(frozen=True)
class Geometry:
    """Largo (dirección principal) y ancho de la base, espesor (mm; el de la zarpa en la T) y centroide de la base en ejes
    globales (mm); beam, en la T invertida (D-113), el ancho del alma y el alto total de la viga (mm)."""

    length: float
    width: float
    h: float
    center: tuple[float, float]
    beam: tuple[float, float] | None = None

    @property
    def total_height(self) -> float:
        return self.h if self.beam is None else self.beam[1]


@dataclass
class Group:
    """Opciones de un grupo de refuerzo de menor a mayor peso y las fallas que ya se vieron: la opción vigente es la más
    liviana que ninguna falla descarta (None mientras optional y sin fallas)."""

    options: list[dict[str, Any]]
    optional: bool = False
    failures: list[tuple[str, dict[str, Any], float]] = field(default_factory=list)

    def current(self) -> dict[str, Any] | None:
        if self.optional:
            return None
        return next((option for option in self.options if not any(_ruled_out(option, *seen) for seen in self.failures)), None)

    def tighten(self, kinds: set[str], ratio: float = 1.0) -> None:
        """Las fallas de la opción vigente (todas las de una ronda) descartan las opciones que las repetirían; ratio > 1
        (área requerida sobre provista, si la falla la da) descarta además las que no llegan a esa proporción."""
        now = self.current()
        if now is None:
            self.optional = False
            return
        self.failures += [(kind, now, ratio if kind == "area" else 1.0) for kind in sorted(kinds)]


_Option = dict[str, Any]
# Tipos de falla que una opción repite si no mejora el mismo dato de la que falló.
_SAME_OR_WORSE: dict[str, Callable[[_Option, _Option], bool]] = {
    "legs": lambda option, failed: option["_legs"] <= failed["_legs"],
    # At/s lo toma la rama exterior del estribo cerrado: no crece con más ramas. El At/s requerido baja con un estribo
    # más delgado (Ao crece): solo se descartan las de igual o mayor diámetro.
    "outer_leg": lambda option, failed: option["_leg"] <= failed["_leg"] and option["_diameter"] >= failed["_diameter"],
    "development": lambda option, failed: option["_diameter"] >= failed["_diameter"] and option["_spacing"] <= failed["_spacing"],
    "min_spacing": lambda option, failed: option["_clear"] <= failed["_clear"],
    "max_spacing": lambda option, failed: option["_spacing"] >= failed["_spacing"],
    "diameter": lambda option, failed: option["_diameter"] <= failed["_diameter"],
    # Torsión: barra en cada esquina (a no más de un diámetro); la fallida también, por si el estribo real difiere.
    "corners": lambda option, failed: option["_corner"] > option["_diameter"] or option is failed,
}


def _ruled_out(option: dict[str, Any], kind: str, failed: dict[str, Any], ratio: float = 1.0) -> bool:
    """Si la opción repetiría la falla de failed: con menos o igual área (resistencia, mínimos), con diámetro mayor o
    igual y separación menor o igual (desarrollo: ld crece con db y decrece con cb), con menos o igual luz libre
    (separación mínima) o con mayor o igual separación (separaciones máximas y fisuración). El área se compara total
    (resistencia, en el ancho del grupo) y por metro (cuantías de retracción): se descarta la que no mejora ninguna."""
    if kind in _SAME_OR_WORSE:
        return _SAME_OR_WORSE[kind](option, failed)
    if ratio > 1.0:
        return option["_area"] < failed["_area"] * ratio and option["_per_m"] < failed["_per_m"] * ratio
    return option["_area"] <= failed["_area"] and option["_per_m"] <= failed["_per_m"]


@dataclass(frozen=True)
class CombinedSolution:
    """Zapata aprobada: geometría, refuerzo en el formato de entrada (ejes de la viga) y su costo."""

    fc: float
    geometry: Geometry
    reinforcement: dict[str, Any]
    cost: float
    concrete: float
    steel: float
    data: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class FcOption:
    fc: float
    solution: CombinedSolution | None
    failure: str | None


@dataclass(frozen=True)
class CombinedDesignResult:
    best: CombinedSolution | None
    options: tuple[FcOption, ...]
    placement: str  # el caso que ubica la base (D-108)


def placement_loads(ctx: Context) -> tuple[FootingLoad, FootingLoad]:
    """Las cargas de las dos columnas en el caso que ubica la base (D-108): placement_case si se declara; si no, el caso
    de servicio sin sismo de mayor carga total (D-107)."""
    first, second = ctx.project.columns
    pairs = [(load, next(other for other in second.loads if other.case == load.case and other.kind == load.kind))
             for load in first.loads if load.kind == "service" and not load.seismic]
    chosen = ctx.design.placement_case
    if chosen is not None:
        return next(pair for pair in pairs if pair[0].case == chosen)
    return max(pairs, key=lambda pair: pair[0].p + pair[1].p)


def _footing_data(ctx: Context, geometry: Geometry, reinforcement: dict[str, Any]) -> dict[str, Any]:
    """La zapata en el formato de entrada, en ejes globales con la dirección principal declarada; reinforcement va en
    ejes de la viga (x a lo largo de ella) y se escribe en los globales (D-094)."""
    design = ctx.design
    principal, _ = ctx.axes()
    swap = principal == "y"
    lx, ly = (geometry.width, geometry.length) if swap else (geometry.length, geometry.width)
    columns = []
    for column in ctx.project.columns:
        item: dict[str, Any] = {"id": column.id, "cx": column.cx, "cy": column.cy,
                                "x": round(column.x - geometry.center[0], 6), "y": round(column.y - geometry.center[1], 6)}
        if column.id in reinforcement["dowels"]:
            item["dowels"] = reinforcement["dowels"][column.id]
        if column.id in reinforcement["bands"]:
            item["band"] = reinforcement["bands"][column.id]
        if reinforcement.get("band_tops", {}).get(column.id) is not None:  # band superior (D-119)
            item["band_top"] = reinforcement["band_tops"][column.id]
        item["loads"] = [load_input(load) for load in column.loads]
        columns.append(item)
    data: dict[str, Any] = {
        "id": FOOTING_ID, "principal_direction": principal, "lx": lx, "ly": ly, "h": geometry.h, "cover": design.cover,
        "min_steel_exception": design.min_steel_exception,
        "fill_height": design.fill_height, "pedestal_height": design.pedestal_height,
        "surcharge_dead_kNm2": design.surcharge_dead, "surcharge_live_kNm2": design.surcharge_live, "columns": columns,
        "bottom": _declared({"first": "x", "end": design.end, "x": reinforcement["bottom_x"], "y": reinforcement["bottom_y"]}, swap),
    }
    if geometry.beam is not None:  # T invertida (D-106, D-113): el refuerzo de la viga va en beam
        data["bottom"] = _declared({"first": "y", "end": design.end, "x": reinforcement["mat_x"], "y": reinforcement["bottom_y"]}, swap)
        if reinforcement.get("top_y") is not None:  # malla superior de la zarpa (D-114)
            data["top"] = _declared({"end": design.end, "y": reinforcement["top_y"]}, swap)
        data["beam"] = _beam_data(ctx, geometry, reinforcement)
        data["deep_beam"] = _is_deep(ctx, geometry)
        return data
    top = {key: reinforcement[f"top_{key}"] for key in ("x", "y") if reinforcement.get(f"top_{key}") is not None}
    if top:
        data["top"] = _declared({**({"first": "x"} if len(top) == len(("x", "y")) else {}), "end": design.end, **top}, swap)
    if reinforcement.get("skin") is not None:
        data["skin"] = reinforcement["skin"]
    if reinforcement.get("stirrups") is not None:
        data["stirrups"] = reinforcement["stirrups"]
    return data


def _stirrup_diameter(ctx: Context) -> float:
    """Diámetro con que se colocan las capas de la viga de la T: el mayor de stirrup_bars (las posiciones no cambian con
    el estribo elegido y quedan por dentro de cualquiera de ellos); 0 sin estribos."""
    return max((ctx.spec(name).diameter_mm for name in ctx.design.stirrup_bars), default=0.0)


def bottom_layer(ctx: Context, geometry: Geometry, bar_set: dict[str, Any], aleta_db: float) -> tuple[float, list[float]]:
    """(profundidad, posiciones x desde la cara −Y del alma) de la capa inferior de la viga de la T (D-106): en el alma
    por dentro del estribo y, si el ala cuenta, a cada lado sobre la zarpa hasta el ancho cubierto (al recubrimiento si
    llega al borde), a la misma separación, sobre las barras y de las aletas."""
    assert geometry.beam is not None
    web, height = geometry.beam
    cover, db, spacing = ctx.design.cover, ctx.spec(bar_set["designation"]).diameter_mm, bar_set["spacing"]
    half = covered(ctx, geometry) / 2
    inner = cover + _stirrup_diameter(ctx) + db / 2
    xs = list(uniform_positions(inner, web - inner, spacing))
    reach = half - (cover if half >= geometry.width / 2 else 0.0) - db / 2
    if reach > web / 2 + db / 2:
        outside = uniform_positions(web / 2 + db / 2, reach, spacing)
        xs += [web / 2 + y for y in outside] + [web / 2 - y for y in outside]
    return height - cover - aleta_db - db / 2, sorted(xs)


def covered(ctx: Context, geometry: Geometry) -> float:
    """Ancho que cubre la capa inferior de la viga de la T (mm): el ala efectiva de viga aislada del perfil (≤ 4bw, si la
    zarpa tiene al menos 0.5bw; si no, el alma), sin pasar de la base (D-093, D-106)."""
    assert geometry.beam is not None
    web = geometry.beam[0]
    flange = ctx.profile.flexure.isolated_flange_width(web, geometry.h)
    return min(flange if flange is not None else web, geometry.width)


def _beam_data(ctx: Context, geometry: Geometry, reinforcement: dict[str, Any]) -> dict[str, Any]:
    """La viga de la T en el formato de entrada (D-106): capa superior por dentro de los estribos, capa inferior repartida
    en el ancho cubierto (sobre las barras y de las aletas) y piel en las dos caras, con x desde la cara −Y del alma."""
    assert geometry.beam is not None
    design = ctx.design
    web, height = geometry.beam
    cover, stirrup = design.cover, _stirrup_diameter(ctx)
    top, bottom = reinforcement["top_x"], reinforcement["bottom_x"]
    top_db = ctx.spec(top["designation"]).diameter_mm
    aleta_db = ctx.spec(reinforcement["bottom_y"]["designation"]).diameter_mm
    inset = cover + stirrup + top_db / 2
    top_depth = inset
    bottom_depth, xs = bottom_layer(ctx, geometry, bottom, aleta_db)
    top_bars = [{"designation": top["designation"], "x": round(x, 3)} for x in uniform_positions(inset, web - inset, top["spacing"])]
    bottom_bars = [{"designation": bottom["designation"], "x": round(x, 3)} for x in xs]
    layers: list[dict[str, Any]] = [{"depth": round(top_depth, 3), "role": "flexure", "bars": top_bars},
                                    {"depth": round(bottom_depth, 3), "role": "flexure", "bars": bottom_bars}]
    skin = reinforcement.get("skin")
    if skin is not None:
        skin_db = ctx.spec(skin["designation"]).diameter_mm
        side = cover + stirrup + skin_db / 2
        depth = bottom_depth - skin["spacing"]
        while depth > top_depth + _TOUCH:
            layers.append({"depth": round(depth, 3), "role": "skin",
                           "bars": [{"designation": skin["designation"], "x": round(side, 3)},
                                    {"designation": skin["designation"], "x": round(web - side, 3)}]})
            depth -= skin["spacing"]
    layers.sort(key=lambda layer: layer["depth"])
    beam: dict[str, Any] = {"width": web, "height": height, "end": design.end, "layers": layers}
    if reinforcement.get("stirrups") is not None:
        beam["stirrups"] = reinforcement["stirrups"]
    return beam


def _is_deep(ctx: Context, geometry: Geometry) -> bool:
    """Viga de gran altura si la luz libre entre las caras de las columnas sobre el alto es ≤ 4 (ACI 9.9.1.1, NSR-10
    C.10.7.1): el diseño la declara deep_beam y se revisa con D-089 (D-109)."""
    principal, _ = ctx.axes()
    spans = sorted((_coordinate(column, principal) for column in ctx.project.columns), key=lambda item: item[0])
    clear = (spans[1][0] - spans[1][1] / 2) - (spans[0][0] + spans[0][1] / 2)
    return clear / geometry.total_height <= ctx.profile.deep_beam.max_span_to_depth()


def _declared(mat: dict[str, Any], swap: bool) -> dict[str, Any]:
    """Una malla en ejes de la viga escrita en los ejes globales: con la dirección principal en Y, x e y se intercambian."""
    if not swap:
        return mat
    turned = {key: value for key, value in mat.items() if key not in ("x", "y", "first")}
    turned.update({{"x": "y", "y": "x"}[key]: mat[key] for key in ("x", "y") if key in mat})
    if "first" in mat:
        turned["first"] = {"x": "y", "y": "x"}[mat["first"]]
    return turned


def _footing(ctx: Context, geometry: Geometry, reinforcement: dict[str, Any]) -> CombinedFooting | None:
    try:
        return CombinedFooting.model_validate(_footing_data(ctx, geometry, reinforcement))
    except ValidationError:
        return None


def _placeholder(ctx: Context) -> dict[str, Any]:
    """Refuerzo provisional para las revisiones que no dependen de él (suelo y demandas)."""
    bars = {"designation": ctx.design.bars[0], "spacing": ctx.design.spacing_step * 4}
    return {"bottom_x": bars, "bottom_y": bars, "top_x": bars if ctx.design.shape == "inverted_t" else None, "top_y": None,
            "mat_x": bars, "bands": {}, "dowels": {}, "skin": None, "stirrups": None}


def placement(ctx: Context, h: float, beam: tuple[float, float] | None = None) -> tuple[float, float]:
    """La resultante del caso que ubica la base (`placement_loads`), en ejes globales (mm): con el centroide en ella el
    momento de ese caso en la base se anula, como en `combined_resultant` (xr·Σv = Σ(v·x + My + H·Vx) y
    yr·Σv = Σ(v·y − Mx + H·Vy), con v la fuerza vertical de la columna y H = h + pedestal)."""
    loads = placement_loads(ctx)
    span = sum(abs(column.x) + abs(column.y) + column.cx + column.cy for column in ctx.project.columns)
    big = 4 * span + 4 * ctx.design.plan_step
    provisional = _footing(ctx, Geometry(big, big, h, (0.0, 0.0), None if beam is None else (big / 2, beam[1])), _placeholder(ctx))
    assert provisional is not None
    height = (h if beam is None else beam[1]) + ctx.design.pedestal_height
    total = sx = sy = 0.0
    for column, load in zip(ctx.project.columns, loads, strict=True):
        model = next(item for item in provisional.columns if item.id == column.id)
        vertical = column_vertical(provisional, ctx.project.soil, model, load)
        total += vertical
        sx += vertical * column.x + load.my + height * load.vx
        sy += vertical * column.y - load.mx + height * load.vy
    return sx / total, sy / total


def _coordinate(column: CombinedDesignColumn, axis: str) -> tuple[float, float]:
    """(posición, dimensión) de la columna a lo largo del eje global."""
    return (column.x, column.cx) if axis == "x" else (column.y, column.cy)


def geometry_for(ctx: Context, h: float, extra: int, beam: tuple[float, float] | None = None) -> Geometry | None:
    """La base de largo mínimo (más extra pasos) centrada en la resultante a lo largo de la dirección principal, salvo
    que un voladizo máximo lo impida, y con el ancho mínimo que cubre las columnas; None si el largo pasa de plan_max."""
    design = ctx.design
    step = design.plan_step
    principal, transverse = ctx.axes()
    resultant = dict(zip(("x", "y"), placement(ctx, h, beam), strict=True))
    spans = [_coordinate(column, principal) for column in ctx.project.columns]
    start_face, end_face = min(s - c / 2 for s, c in spans), max(s + c / 2 for s, c in spans)
    center = resultant[principal]
    length = math.ceil(round(2 * max(center - start_face, end_face - center) / step, 9)) * step + extra * step
    low, high = center - length / 2, center + length / 2
    if design.max_cantilever_start is not None and start_face - low > design.max_cantilever_start:
        low = start_face - design.max_cantilever_start
        high = max(low + length, end_face)
    if design.max_cantilever_end is not None and high - end_face > design.max_cantilever_end:
        high = end_face + design.max_cantilever_end
        low = high - length
        if design.max_cantilever_start is not None:
            low = max(low, start_face - design.max_cantilever_start)
    length = high - low
    if length > design.plan_max or low > start_face or high < end_face:
        return None
    sides = [_coordinate(column, transverse) for column in ctx.project.columns]
    cross = resultant[transverse]
    width = math.ceil(round(2 * max(abs(t - cross) + c / 2 for t, c in sides) / step, 9)) * step
    middle = (low + high) / 2
    center_xy = (middle, cross) if principal == "x" else (cross, middle)
    if beam is not None:  # el alma cubre las columnas y la base, el alma
        width = max(width, math.ceil(round((beam[0] + 2 * design.cover) / step, 9)) * step)
    return Geometry(length, width, h, center_xy, beam)


def _soil_ok(ctx: Context, geometry: Geometry) -> bool:
    footing = _footing(ctx, geometry, _placeholder(ctx))
    if footing is None:
        return False
    soil = ctx.project.soil
    service = combined_service_checks(ctx.profile, footing, soil)
    return all(check.status is Status.PASS for check in service) and not combined_factored_cases(footing, soil)[1]


def width_for(ctx: Context, geometry: Geometry) -> Geometry | None:
    """El menor ancho, al paso de la planta, con el que la base cumple la revisión geotécnica (presión, contacto,
    deslizamiento y volcamiento) y el equilibrio de los casos mayorados; None hasta plan_max."""
    design = ctx.design
    soil = ctx.project.soil
    loads = placement_loads(ctx)
    needed = (loads[0].p + loads[1].p) / soil.allowable_pressure / geometry.length
    width = max(geometry.width, math.ceil(round(needed / design.plan_step, 9)) * design.plan_step)
    while width <= design.plan_max:
        candidate = replace(geometry, width=width)
        if _soil_ok(ctx, candidate):
            return candidate
        width += design.plan_step
    return None


def _options(raw: list[tuple[float, dict[str, Any]]], ctx: Context, spread: Spread) -> list[dict[str, Any]]:
    """Las opciones de bar_options con lo que las restricciones comparan: área total, diámetro, luz libre, separación y
    la distancia de la barra extrema a la esquina (con el recubrimiento de spread; _cornered la corrige)."""
    options = []
    for _, bar_set in raw:
        spec = ctx.spec(bar_set["designation"])
        count = bar_count(spread, spec.diameter_mm, bar_set["spacing"])
        options.append({**bar_set, "_area": count * spec.area_mm2, "_diameter": spec.diameter_mm,
                        "_clear": bar_set["spacing"] - spec.diameter_mm, "_spacing": bar_set["spacing"],
                        "_per_m": spec.area_mm2 / bar_set["spacing"]})
    return _cornered(options, spread.width, spread.cover)


def _cornered(options: list[dict[str, Any]], width: float, inset: float) -> list[dict[str, Any]]:
    """_corner de cada opción: lo que queda entre la barra extrema y la posición de esquina con las barras centradas a su
    separación en width − 2·inset − db, como las coloca domain/footing/mesh (inset: recubrimiento y estribo lateral)."""
    for option in options:
        span = width - 2 * inset - option["_diameter"]
        count = math.floor(span / option["_spacing"] + 1e-6) if span > 0 else 0
        option["_corner"] = max(span - count * option["_spacing"], 0.0) / 2
    return options


def _bar_group(given: tuple[Context, Materials], spread: Spread, depth_of: Callable[[float], float],
               moment: float, compression: float | None = None) -> list[dict[str, Any]]:
    """Opciones de un grupo de barras que ya cumplen los límites del perfil que la verificación revisa en él: el acero
    mínimo de losa en todo el grupo y, si hay momento (viga larga y franjas, revisadas como vigas, D-081 y D-082), el
    As,min de vigas (con la excepción de 4/3 solo si se declara, D-123; con el ancho del alma) y la separación de
    control de fisuración con el recubrimiento. compression es el ancho a compresión de la T, si difiere del de reparto
    (D-113)."""
    ctx, materials = given
    profile = ctx.profile
    specs = [ctx.spec(designation) for designation in ctx.design.bars]
    minimum = profile.footing.min_reinforcement_ratio(materials.fy) * spread.width * spread.h
    if moment > 0:
        depth = depth_of(specs[0].diameter_mm)
        web = min(spread.width, compression or spread.width)
        beam = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, web, depth)
        if ctx.design.min_steel_exception:  # D-123: la excepción de 4/3 del As requerido, si se declara
            section = RectangularSection(compression or spread.width, spread.h)
            beam = profile.flexure.effective_min_reinforcement(beam, required_area(profile, materials, section, depth, moment) or 0.0)
        minimum = max(minimum, beam)
        crack = math.floor(profile.flexure.crack_control_spacing(materials.fy, ctx.design.cover) / spread.step) * spread.step
        spread = replace(spread, max_spacing=min(spread.max_spacing, crack))
    if compression is not None:  # el As requerido se calcula con el ancho de compresión, no con el de reparto
        return _options(_compressed_options(given, spread, depth_of, (moment, minimum, compression)), ctx, spread)
    return _options(bar_options((profile, materials, specs), spread, depth_of, (moment, minimum)), ctx, spread)


def _compressed_options(given: tuple[Context, Materials], spread: Spread, depth_of: Callable[[float], float],
                        demand: tuple[float, float, float]) -> list[tuple[float, dict[str, Any]]]:
    """bar_options con el As requerido de la sección de ancho compression y las barras repartidas en spread.width;
    demand es (Mu, As mínimo, ancho a compresión)."""
    ctx, materials = given
    profile = ctx.profile
    specs = [ctx.spec(designation) for designation in ctx.design.bars]
    moment, minimum, compression = demand
    options: list[tuple[float, dict[str, Any]]] = []
    for spec in specs:
        needed = required_area(profile, materials, RectangularSection(compression, spread.h), depth_of(spec.diameter_mm), moment)
        if needed is None:
            continue
        options += bar_options((profile, materials, [spec]), spread, depth_of, (0.0, max(needed, minimum)))
    return sorted(options, key=lambda option: option[0])


def _strip_moments(ctx: Context, footing: CombinedFooting, cases: Cases, depth: float) -> list[list[float]]:
    """Los momentos de diseño de la franja de cada columna en todos los casos (D-082, D-095), con la altura efectiva dada:
    los de Wood-Armer con la torsión de placa (D-118)."""
    soil = ctx.project.soil
    result = []
    for index, column in enumerate(footing.columns):
        moments = []
        limits = strip_limits(footing, column, depth)
        for pressure, loads in cases:
            force = column_vertical(footing, soil, column, loads[index])
            twist = strip_twist(footing, soil, (pressure, loads), limits)
            for _, moment, _, _ in strip_demands(footing, pressure, column, (force, depth))[0]:
                moments += strip_moments(moment, limits[1] - limits[0], twist)
        result.append(moments)
    return result


def _outside_twist(ctx: Context, footing: CombinedFooting, cases: Cases, depth: float) -> float:
    """El mayor |mxy| fuera de las franjas en todos los casos (N·mm/mm, D-118): el momento por unidad de largo de las
    barras y inferiores y superiores allí."""
    zones = [strip_limits(footing, column, depth) for column in footing.columns]
    return max((outside_twist(footing, ctx.project.soil, given, zones)[1] for given in cases), default=0.0)


def _t_groups(ctx: Context, fc: float, geometry: Geometry) -> dict[str, Group] | None:
    """Los grupos de la T invertida (D-113): capas inferior (en el ancho cubierto, con el alma a compresión) y superior
    (en el alma, con el ala a compresión) de la viga, barras x de la zarpa fuera del ancho cubierto, barras y de las
    aletas (con su mayor momento por unidad de largo), piel, estribos y pasadores."""
    assert geometry.beam is not None
    footing = _footing(ctx, geometry, _placeholder(ctx))
    if footing is None:
        return None
    design, profile = ctx.design, ctx.profile
    materials = ctx.materials(fc)
    soil = ctx.project.soil
    cases, failures = combined_factored_cases(footing, soil)
    if failures:
        return None
    web, height = geometry.beam
    h, cover, step = geometry.h, design.cover, design.spacing_step
    long_spacing = math.floor(profile.footing.combined_max_bar_spacing(h) / step) * step
    slab_spacing = math.floor(profile.footing.max_bar_spacing(h) / step) * step
    positive, negative = extreme_moments(footing, soil, cases)
    first = ctx.spec(design.bars[0]).diameter_mm
    stirrup = _stirrup_diameter(ctx)
    width = covered(ctx, geometry)
    flange = max(Flanges(footing, pressure, h - cover - first / 2).governing("moment")[1] for pressure, _ in cases)
    hogging = max(Flanges(footing, pressure, h - cover - first / 2).governing("negative")[1] for pressure, _ in cases)
    top = Spread(web, height, cover + stirrup, step, long_spacing)
    bottom = Spread(width, height, cover if width >= geometry.width else 0.0, step, long_spacing)
    groups = {
        "top_x": Group(_bar_group((ctx, materials), top, lambda db: height - cover - stirrup - db / 2, negative[0], width)),
        "bottom_x": Group(_placed(ctx, geometry, _bar_group((ctx, materials), bottom, lambda db: height - cover - first - db / 2,
                                                            positive[0], web), first)),
        "mat_x": Group(_bar_group((ctx, materials), Spread(geometry.width, h, cover, step, long_spacing),
                                  lambda db: h - cover - first - db / 2, 0.0)),
        "bottom_y": Group(_bar_group((ctx, materials), Spread(geometry.length, h, cover, step, slab_spacing),
                                     lambda db: h - cover - db / 2, max(flange, 0.0) * geometry.length)),
        # Malla superior de la zarpa (D-114): las barras y que toman el momento negativo de las aletas, solo si el concreto
        # simple no alcanza o no se permite (D-072); d desde la cara inferior.
        "top_y": Group(_bar_group((ctx, materials), Spread(geometry.length, h, cover, step, slab_spacing),
                                  lambda db: h - cover - db / 2, max(hogging, 0.0) * geometry.length), optional=True),
        "skin": Group(_skin_options(ctx, height), optional=height <= profile.flexure.skin_reinforcement_depth()),
    }
    for column in footing.columns:
        groups[f"dowels:{column.id}"] = Group(_dowel_options(ctx, column.cx * column.cy))
    if design.stirrup_bars:
        along_max = profile.shear.max_spacing(0.0, materials.fc, web, height - cover - first)
        frame = StirrupFrame(web, height, cover, step, along_max)
        groups["stirrups"] = Group(stirrup_options([ctx.spec(name) for name in design.stirrup_bars], frame), optional=True)
    return groups


def _placed(ctx: Context, geometry: Geometry, options: list[dict[str, Any]], aleta_db: float) -> list[dict[str, Any]]:
    """Las opciones de la capa inferior de la T con el área y el peso de las barras que de verdad coloca bottom_layer
    (en el alma por dentro del estribo y en el ala), para que las fallas descarten con el área real."""
    placed = []
    for option in options:
        spec = ctx.spec(option["designation"])
        count = len(bottom_layer(ctx, geometry, option, aleta_db)[1])
        placed.append({**option, "_area": count * spec.area_mm2, "_mass": count * spec.mass_kg_m})
    assert geometry.beam is not None  # las esquinas de torsión son las del alma, por dentro del estribo
    _cornered(placed, geometry.beam[0], ctx.design.cover + _stirrup_diameter(ctx))
    return sorted(placed, key=lambda option: option["_mass"])


def _groups(ctx: Context, fc: float, geometry: Geometry) -> dict[str, Group] | None:
    """Los grupos de refuerzo con sus opciones para la geometría, a partir de los momentos de la viga larga y de las
    franjas con un refuerzo provisional (no dependen de él, salvo la altura efectiva de las franjas)."""
    if geometry.beam is not None:
        return _t_groups(ctx, fc, geometry)
    footing = _footing(ctx, geometry, _placeholder(ctx))
    if footing is None:
        return None
    design, profile = ctx.design, ctx.profile
    materials = ctx.materials(fc)
    cases, failures = combined_factored_cases(footing, ctx.project.soil)
    if failures:
        return None
    h, cover, step = geometry.h, design.cover, design.spacing_step
    long_spacing = math.floor(profile.footing.combined_max_bar_spacing(h) / step) * step
    slab_spacing = math.floor(profile.footing.max_bar_spacing(h) / step) * step
    positive, negative = extreme_moments(footing, ctx.project.soil, cases)
    along = Spread(geometry.width, h, cover, step, long_spacing)  # barras x: repartidas en el ancho
    across = Spread(geometry.length, h, cover, step, slab_spacing)  # barras y: repartidas en el largo
    first = ctx.spec(design.bars[0]).diameter_mm

    def outer(db: float) -> float:  # barras x, las más cercanas a su cara
        return h - cover - db / 2

    def inner(db: float) -> float:  # barras y, sobre las x
        return h - cover - first - db / 2

    plain = profile.plain.permitted_in_foundations(ctx.project.seismic.level)
    lateral = cover + _stirrup_diameter(ctx)  # los estribos encierran las barras x por los lados (mesh)
    twist = _outside_twist(ctx, footing, cases, inner(first))  # torsión de placa fuera de las franjas (D-118)
    groups = {"bottom_x": Group(_cornered(_bar_group((ctx, materials), along, outer, positive[0]), geometry.width, lateral)),
              "bottom_y": Group(_bar_group((ctx, materials), across, inner, twist * geometry.length)),
              "top_x": Group(_cornered(_bar_group((ctx, materials), along, outer, negative[0]), geometry.width, lateral),
                             optional=plain or negative[0] <= 0)}
    strips = _strip_moments(ctx, footing, cases, inner(first))
    for column, moments in zip(footing.columns, strips, strict=True):
        low, high = strip_limits(footing, column, inner(first))
        strip = Spread(high - low, h, 0.0, step, slab_spacing)
        groups[f"band:{column.id}"] = Group(_bar_group((ctx, materials), strip, inner, max(max(moments, default=0.0), 0.0)))
        # Band superior (D-119): las barras superiores de la franja, para su momento negativo de Wood-Armer; solo si una
        # falla de la franja lo pide (mientras tanto, top.y o concreto simple).
        groups[f"band_top:{column.id}"] = Group(_bar_group((ctx, materials), strip, lambda db: h - cover - db / 2,
                                                           max(-min(moments, default=0.0), 0.0)), optional=True)
        groups[f"dowels:{column.id}"] = Group(_dowel_options(ctx, column.cx * column.cy))
    negative_strip = max((-min(moments, default=0.0) for moments in strips), default=0.0)
    hogging = max(negative_strip, twist * geometry.length, 0.0)
    groups["top_y"] = Group(_bar_group((ctx, materials), across, inner, hogging), optional=plain or hogging <= 0)
    groups["skin"] = Group(_skin_options(ctx, h), optional=h <= profile.flexure.skin_reinforcement_depth())
    if design.stirrup_bars:
        depth = outer(first)
        along_max = profile.shear.max_spacing(0.0, materials.fc, geometry.width, depth)
        frame = StirrupFrame(geometry.width, h, cover, step, along_max)
        groups["stirrups"] = Group(stirrup_options([ctx.spec(name) for name in design.stirrup_bars], frame), optional=True)
    return groups


def _dowel_options(ctx: Context, area: float) -> list[dict[str, Any]]:
    """Pasadores de menor a mayor peso: para cada designación, desde el número par (al menos 4) que cubre 0.005Ag, y
    _DOWEL_COUNTS más; el anclaje y el exceso de aplastamiento los decide la verificación."""
    required = ctx.profile.footing.dowel_min_ratio() * area
    options = []
    for designation in ctx.design.dowel_bars:
        spec = ctx.spec(designation)
        count = max(_DOWELS_MIN, math.ceil(required / spec.area_mm2))
        count += count % 2
        for extra in range(_DOWEL_COUNTS):
            bars = count + 2 * extra
            options.append({"designation": designation, "count": bars, "_area": bars * spec.area_mm2, "_diameter": spec.diameter_mm,
                            "_clear": 0.0, "_spacing": 0.0, "_per_m": bars * spec.area_mm2, "_mass": bars * spec.mass_kg_m})
    return sorted(options, key=lambda option: option["_mass"])


def _skin_options(ctx: Context, h: float) -> list[dict[str, Any]]:
    """Refuerzo superficial de menor a mayor peso por unidad de altura: cada designación a separaciones desde la de
    control de fisuración con el recubrimiento a la cara lateral (la que revisa el perfil, D-083) o h/2 si es menor."""
    step = ctx.design.spacing_step
    crack = ctx.profile.flexure.crack_control_spacing(ctx.project.materials.fy, ctx.design.cover)
    options = []
    for designation in ctx.design.bars:
        spec = ctx.spec(designation)
        spacing = math.floor(min(crack, h / 2) / step) * step
        while spacing >= _SKIN_MIN_SPACING:
            options.append({"designation": designation, "spacing": spacing, "_area": spec.area_mm2 / spacing,
                            "_diameter": spec.diameter_mm, "_clear": spacing, "_spacing": spacing, "_per_m": spec.area_mm2 / spacing,
                            "_mass": spec.mass_kg_m / spacing})
            spacing -= step
    return sorted(options, key=lambda option: option["_mass"])


def classify(check: Check) -> tuple[str, str]:
    """(grupo, tipo de corrección) de una verificación que no cumple. Los grupos son los de _groups, "soil" (la planta)
    y "h" (el espesor); el tipo dice qué corrige la falla: "area", "development" (menor diámetro), "min_spacing" (más
    luz libre) o "max_spacing" (menor separación)."""
    name, note = check.name, check.note
    found = _COLUMN.search(name) or _COLUMN.search(note)
    column = found.group(1) if found else ""
    principal = "principal" in name
    fields = {"column": column, "axis": "x" if principal else "y",
              "transfer": "bottom_x" if principal else f"band:{column}",
              "bottom": "bottom_x" if principal else (f"band:{column}" if column and "band" in name else "bottom_y")}
    if name == TORSION_DETAILING:
        return _torsion_detailing(note)
    group = next((template for test, template in _RULES if test(name, note)), "h").format(**fields)
    return group, _stirrup_kind(check) or _kind(name)


def _torsion_detailing(note: str) -> tuple[str, str]:
    """La distribución del refuerzo longitudinal de torsión (domain/beam/torsion): capas separadas en altura, más niveles
    de piel; barras delgadas, piel de mayor diámetro; una fila superior o inferior con barras muy separadas o sin
    esquinas, menor separación en esa capa. Se corrige el primer problema de la nota; los demás, en las rondas siguientes."""
    if "en altura" in note:
        return "skin", "max_spacing"
    if "diametro menor" in note:
        return "skin", "diameter"
    row = "top_x" if note.find("capa superior") >= 0 else "bottom_x"
    first = note.find("capa superior" if row == "top_x" else "capa inferior")
    return row, "corners" if note[first:].split(";")[0].endswith("esquinas") else "max_spacing"


def _stirrup_kind(check: Check) -> str | None:
    """Fallas de estribos que no corrige más Av/s: la separación de las ramas a lo ancho (faltan ramas) y la rama
    exterior a torsión (At/s > Ab/s: barra mayor o separación menor)."""
    values = dict(check.values)
    if check.name == TORSION_TRANSVERSE:
        at, outer = values.get("At/s"), values.get("At/s rama exterior")
        return "outer_leg" if at is not None and outer is not None and at > outer else None
    if check.name != SHEAR_SPACING:
        return None
    across, limit = values.get("across"), values.get("across_max")
    if across is not None and limit is not None and across > limit and (check.capacity is None or (check.demand or 0.0) <= check.capacity):
        return "legs"
    return None


def _kind(name: str) -> str:
    lowered = name.lower()
    if name.startswith("Desarrollo") or "anclaje" in lowered:
        return "development"
    if name.startswith("Separacion minima"):
        return "min_spacing"
    if "separacion" in lowered or name == SKIN:
        return "max_spacing"
    return "area"


_BARS = ("Retraccion", "Separacion minima", "Desarrollo", "Direccion")
# (prueba sobre el nombre y la nota, grupo): la primera que se cumple; sin ninguna, el espesor.
_RULES: tuple[tuple[Callable[[str, str], bool], str], ...] = (
    (lambda name, note: name in _SOIL, "soil"),
    # Torsión de placa fuera de las franjas sin barras superiores y (D-118): las pide; su cortante, espesor (D-119).
    (lambda name, note: name == PLATE_PLAIN, "top_y"),
    (lambda name, note: name == PLATE_SHEAR, "h"),
    # El band superior de cada columna (D-119): su desarrollo, separación y retracción.
    (lambda name, note: "band superior" in name, "band_top:{column}"),
    # D-110: el cortante y la torsión transversal de la viga larga los toman los estribos; Aℓ, la piel (D-090).
    (lambda name, note: name in _STIRRUP_CHECKS and not note.startswith("Franja transversal"), "stirrups"),
    (lambda name, note: name in (TORSION_LONGITUDINAL, TORSION_DETAILING), "skin"),
    (lambda name, note: name.startswith(("Pasadores", "Aplastamiento")), "dowels:{column}"),
    (lambda name, note: name == SKIN, "skin"),
    (lambda name, note: name.startswith(_THICKNESS), "h"),
    # D-120: la parte negativa de γf·Msc la toman las barras superiores en bslab: en Y, el band superior de la columna.
    (lambda name, note: name.startswith("Transferencia de momento") and "parte negativa" in name and "principal" in name, "top_x"),
    (lambda name, note: name.startswith("Transferencia de momento") and "parte negativa" in name, "band_top:{column}"),
    (lambda name, note: name.startswith("Transferencia de momento"), "{transfer}"),
    # El momento negativo de la franja lo toma su band superior (D-119), no top.y en todo el largo.
    (lambda name, note: note.startswith("Franja transversal") and "momento negativo" in note, "band_top:{column}"),
    (lambda name, note: note.startswith("Franja transversal"), "band:{column}"),
    (lambda name, note: name.startswith("Flexion") and "momento negativo" in note, "top_x"),
    (lambda name, note: name.startswith("Flexion"), "bottom_x"),
    (lambda name, note: name.startswith(_BARS) and "superiores" in name, "top_{axis}"),
    (lambda name, note: name.startswith(_BARS), "{bottom}"),
)


# T invertida (D-113): las aletas y la zarpa, el alma, la viga alta y las barras x de la zarpa.
_T_GROUPS = {
    T_FLEXURE: "bottom_y", T_MINIMUM: "bottom_y", T_SPACING: "bottom_y", T_DEVELOPMENT: "bottom_y",
    T_STRAIN: "zarpa", T_SHEAR: "zarpa", T_DEPTH: "zarpa", T_TENSION_FLANGE: "bottom_x",
    # El momento negativo de las aletas: barras superiores en la zarpa antes que más espesor (D-114, D-117).
    T_PLAIN: "top_y", T_FLEXURE_TOP: "top_y", T_DEVELOPMENT_TOP: "top_y",
    f"{LONG_SPACING} (barras inferiores)": "mat_x",
    SHEAR_SECTION: "web", TORSION_SECTION: "web", DEEP_SECTION: "web",
    DEEP_TRANSVERSE: "stirrups", DEEP_LONGITUDINAL: "skin", DEEP_CURTAINS: "skin", DEEP_SPACING: "skin",
}


def classify_t(check: Check) -> tuple[str, str]:
    """(grupo, tipo) de una falla de la T invertida: lo propio de la T y, si no, lo mismo que la rectangular (la viga larga
    con bottom_x y top_x como sus capas inferior y superior)."""
    group = _T_GROUPS.get(check.name)
    if check.name.startswith("Separacion minima (capa") and check.name.endswith("de la viga)"):  # domain/footing/spacing
        return ("top_x" if "capa superior" in check.name else "bottom_x"), "min_spacing"
    if check.name == TORSION_DETAILING:  # la viga de la T se revisa volteada: su capa "superior" es la inferior (D-093)
        found, kind = _torsion_detailing(check.note)
        return {"top_x": "bottom_x", "bottom_x": "top_x"}.get(found, found), kind
    if group is None:
        return classify(check)
    if check.name == DEEP_SPACING:  # la separación de los estribos o la vertical de la piel, la que exceda (D-089)
        values = dict(check.values)
        limit = check.capacity or 0.0
        group = "stirrups" if values.get("s estribos", 0.0) > limit >= values.get("sd vertical", 0.0) else "skin"
    kind = "max_spacing" if check.name in (T_SPACING, DEEP_SPACING, f"{LONG_SPACING} (barras inferiores)") else _kind(check.name)
    return group, kind


def _reinforcement(ctx: Context, groups: dict[str, Group]) -> dict[str, Any] | None:
    chosen = {name: group.current() for name, group in groups.items()}
    required = [name for name, group in groups.items() if not group.optional]
    if any(chosen[name] is None for name in required):
        return None  # un grupo agotó sus opciones

    def clean(option: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if option is None else {key: value for key, value in option.items() if not key.startswith("_")}

    ids = [column.id for column in ctx.project.columns]
    if "mat_x" in groups:  # T invertida
        return {"top_x": clean(chosen["top_x"]), "bottom_x": clean(chosen["bottom_x"]), "mat_x": clean(chosen["mat_x"]),
                "bottom_y": clean(chosen["bottom_y"]), "top_y": clean(chosen.get("top_y")), "skin": clean(chosen["skin"]),
                "stirrups": clean(chosen.get("stirrups")), "bands": {},
                "dowels": {column: clean(chosen[f"dowels:{column}"]) for column in ids}}
    return {"bottom_x": clean(chosen["bottom_x"]), "bottom_y": clean(chosen["bottom_y"]), "top_x": clean(chosen["top_x"]),
            "top_y": clean(chosen["top_y"]), "skin": clean(chosen["skin"]), "stirrups": clean(chosen.get("stirrups")),
            "bands": {column: clean(chosen[f"band:{column}"]) for column in ids},
            "band_tops": {column: clean(chosen[f"band_top:{column}"]) for column in ids},
            "dowels": {column: clean(chosen[f"dowels:{column}"]) for column in ids}}


def reinforce(ctx: Context, fc: float, geometry: Geometry) -> CombinedSolution | str:
    """El refuerzo de menor peso que aprueba la verificación con esta geometría; "soil" si la planta no cumple el suelo,
    "width" si un grupo transversal agotó sus opciones por desarrollo (lo arregla un ancho mayor, D-110), en la T "zarpa"
    o "web" si fallan las aletas o las dimensiones del alma (D-113) o si las capas de la viga no caben en ella (D-117), y
    "h" si falta espesor o alto de viga (o otro grupo agotó sus opciones)."""
    groups = _groups(ctx, fc, geometry)
    if groups is None:
        return "soil"
    basis = ctx.basis(fc)
    for _ in range(_ROUNDS):
        reinforcement = _reinforcement(ctx, groups)
        footing = None if reinforcement is None else _footing(ctx, geometry, reinforcement)
        if reinforcement is None or footing is None:
            if geometry.beam is not None and _exhausted(groups, ("top_x", "bottom_x")):
                return "web"  # las capas de la viga no caben en el alma: un alma más ancha (D-117)
            return "width" if _needs_width(groups) else "h"
        failures = [check for check in combined_footing_checks(basis, footing, ctx.project.soil) if check.status is not Status.PASS]
        if not failures:
            solution = priced(ctx, fc, geometry, reinforcement)
            return solution if _valid(ctx, solution) else "h"
        sort = classify_t if geometry.beam is not None else classify
        wanted = {sort(check) for check in failures}
        targets = {group for group, _ in wanted}
        signal = next((name for name in ("soil", "zarpa", "web", "h") if name in targets), None)
        if signal is not None or not targets <= groups.keys():
            return signal or "h"
        ratios = {sort(check)[0]: max(check.demand / check.capacity, 1.0) for check in failures
                  if check.name in _SCALED and check.demand and check.capacity}
        for target in sorted(targets):
            groups[target].tighten({kind for group, kind in wanted if group == target}, ratios.get(target, 1.0))
    return "h"


def _valid(ctx: Context, solution: CombinedSolution) -> bool:
    """La solución pasa además la validación de entrada del proyecto que verifica run (barras dentro del estribo o del
    ala, catálogo, separaciones declaradas): el diseño no entrega un proyecto que la memoria rechace."""
    project = Project.model_validate(designed_project(ctx, solution))
    return validate_project(project, ctx.bars).status is Status.PASS


def _exhausted(groups: dict[str, Group], names: tuple[str, ...]) -> bool:
    """Si alguno de esos grupos obligatorios se quedó sin opciones (o no tuvo ninguna)."""
    return any(name in groups and not groups[name].optional and groups[name].current() is None for name in names)


def _needs_width(groups: dict[str, Group]) -> bool:
    """Si un grupo de barras transversales (band o barras y) se agotó con fallas de desarrollo: su largo disponible
    crece con el ancho de la base, no con el espesor."""
    return any(group.current() is None and not group.optional and any(kind == "development" for kind, _, _ in group.failures)
               for name, group in groups.items() if name.startswith(("band:", "band_top:", "bottom_y", "top_y")))


def priced(ctx: Context, fc: float, geometry: Geometry, reinforcement: dict[str, Any]) -> CombinedSolution:
    """Costo, concreto (m³) y acero (kg) de la zapata: barras rectas de borde a borde menos el recubrimiento, con las
    posiciones de la verificación (domain/footing/mesh), y pasadores hasta la malla inferior, como en D-069."""
    if geometry.beam is not None:
        return _priced_t(ctx, fc, geometry, reinforcement)
    footing = _footing(ctx, geometry, reinforcement)
    assert footing is not None
    design = ctx.design
    basis = ctx.basis(fc)
    long_bar, cross_bar = (footing.lx - 2 * design.cover) / 1000, (footing.ly - 2 * design.cover) / 1000  # m, ejes de la viga
    rows = mat_rows(footing, footing.bottom, ctx.bars)
    tops = top_rows(footing, ctx.bars)

    def mass(designation: str, count: int, length: float) -> float:
        return count * ctx.spec(designation).mass_kg_m * length

    steel = mass(rows["x"].designation, len(rows["x"].positions), long_bar)
    steel += mass(rows["y"].designation, len(transverse_bottom(footing, rows["y"]).positions), cross_bar)
    for column in footing.columns:
        band = band_row(footing, column, rows["y"], basis)
        if band is not None:
            steel += mass(band.designation, len(band.positions), cross_bar)
        band_top = band_top_row(footing, column, rows["y"].depth, ctx.bars)  # band superior (D-119)
        if band_top is not None:
            steel += mass(band_top.designation, len(band_top.positions), cross_bar)
        if column.dowels is not None:
            steel += mass(column.dowels.designation, column.dowels.count, (footing.h - design.cover) / 1000)
    if "x" in tops:
        steel += mass(tops["x"].designation, len(tops["x"].positions), long_bar)
    across = transverse_top(footing, tops.get("y"), rows["y"].depth)  # top.y fuera de las zonas de band superior
    if across is not None:
        steel += mass(across.designation, len(across.positions), cross_bar)
    if footing.skin is not None:  # una barra en cada cara lateral por nivel (domain/footing/combined_beam)
        _, layout = beam_member(footing, (rows["x"], tops.get("x")), ctx.bars)
        levels = sum(1 for layer in layout.layers if layer.role == "skin")
        steel += mass(footing.skin.designation, 2 * levels, long_bar)
    if footing.stirrups is not None:
        stirrups = footing.stirrups
        count = math.floor((footing.lx - 2 * design.cover) / stirrups.spacing + 1e-6) + 1
        perimeter = (stirrups.legs * (footing.h - 2 * design.cover) + 2 * (footing.ly - 2 * design.cover)) / 1000
        steel += mass(stirrups.designation, count, perimeter)
    concrete = (footing.lx * footing.ly * footing.h + footing.column_area * footing.pedestal_height) / _MM3_PER_M3
    cost = concrete * design.prices.concrete(fc) + steel * design.prices.steel_per_kg
    return CombinedSolution(fc, geometry, reinforcement, cost, concrete, steel, _footing_data(ctx, geometry, reinforcement))


def _priced_t(ctx: Context, fc: float, geometry: Geometry, reinforcement: dict[str, Any]) -> CombinedSolution:
    """Costo de la T invertida (D-113): zarpa, alma y pedestales; barras rectas de borde a borde menos el recubrimiento
    (las x de la zarpa solo fuera del ancho cubierto), capas de la viga, estribos y pasadores hasta la capa inferior."""
    assert geometry.beam is not None
    footing = _footing(ctx, geometry, reinforcement)
    assert footing is not None and footing.beam is not None
    design = ctx.design
    web, height = geometry.beam
    long_bar, cross_bar = (footing.lx - 2 * design.cover) / 1000, (footing.ly - 2 * design.cover) / 1000

    def mass(designation: str, count: int, length: float) -> float:
        return count * ctx.spec(designation).mass_kg_m * length

    rows = mat_rows(footing, footing.bottom, ctx.bars)
    half = covered(ctx, geometry) / 2
    steel = mass(rows["x"].designation, sum(1 for y in rows["x"].positions if abs(y) > half + 1e-6), long_bar)
    steel += mass(rows["y"].designation, len(rows["y"].positions), cross_bar)
    top = top_rows(footing, ctx.bars).get("y")  # malla superior de la zarpa (D-114)
    if top is not None:
        steel += mass(top.designation, len(top.positions), cross_bar)
    for layer in _beam_data(ctx, geometry, reinforcement)["layers"]:
        steel += sum(mass(bar["designation"], 1, long_bar) for bar in layer["bars"])
    for column in footing.columns:
        if column.dowels is not None:
            steel += mass(column.dowels.designation, column.dowels.count, (height - design.cover) / 1000)
    if footing.beam.stirrups is not None:
        stirrups = footing.beam.stirrups
        count = math.floor((footing.lx - 2 * design.cover) / stirrups.spacing + 1e-6) + 1
        perimeter = (stirrups.legs * (height - 2 * design.cover) + 2 * (web - 2 * design.cover)) / 1000
        steel += mass(stirrups.designation, count, perimeter)
    concrete = (footing.lx * footing.ly * footing.h + web * footing.lx * (height - footing.h)
                + footing.column_area * footing.pedestal_height) / _MM3_PER_M3
    cost = concrete * design.prices.concrete(fc) + steel * design.prices.steel_per_kg
    return CombinedSolution(fc, geometry, reinforcement, cost, concrete, steel, _footing_data(ctx, geometry, reinforcement))


def _concrete_floor(ctx: Context, fc: float, geometry: Geometry) -> float:
    """Cota inferior del costo con esta geometría: solo el concreto (en la T, con el alma)."""
    columns = sum(column.cx * column.cy for column in ctx.project.columns)
    stem = 0.0 if geometry.beam is None else geometry.beam[0] * geometry.length * (geometry.beam[1] - geometry.h)
    volume = (geometry.length * geometry.width * geometry.h + stem + columns * ctx.design.pedestal_height) / _MM3_PER_M3
    return volume * ctx.design.prices.concrete(fc)


def _with_height(geometry: Geometry, value: float) -> Geometry:
    """La geometría con otro valor de la variable que recorre la búsqueda: el espesor o, en la T, el alto de la viga."""
    return replace(geometry, h=value) if geometry.beam is None else replace(geometry, beam=(geometry.beam[0], value))


def web_minimum(ctx: Context, height: float) -> float:
    """Ancho mínimo del alma de la T (D-109): cubre las columnas respecto a la resultante transversal, más web_margin a
    cada lado, al paso web_step."""
    design = ctx.design
    assert design.web_margin is not None and design.web_step is not None
    _, transverse = ctx.axes()
    cross = dict(zip(("x", "y"), placement(ctx, design.h_min, (0.0, height)), strict=True))[transverse]
    sides = [_coordinate(column, transverse) for column in ctx.project.columns]
    needed = max(2 * abs(t - cross) + c for t, c in sides) + 2 * design.web_margin
    return math.ceil(round(needed / design.web_step, 9)) * design.web_step


def _at_beam_height(ctx: Context, fc: float, extra: int, height: float) -> CombinedSolution | str:
    """T invertida (D-113): con este alto de viga, la zarpa desde h_min y el alma desde la mínima; la zarpa crece si fallan
    las aletas y el alma si fallan las dimensiones de la sección."""
    design = ctx.design
    assert design.web_step is not None
    zarpa, web = design.h_min, web_minimum(ctx, height)
    while True:
        result = _sized(ctx, fc, geometry_for(ctx, zarpa, extra, (web, height)))
        if result == "zarpa" and zarpa + design.h_step <= min(design.h_max, height - design.h_step):
            zarpa += design.h_step
        elif result == "web" and isinstance(result, str):
            footing_width = geometry_for(ctx, zarpa, extra, (web + design.web_step, height))
            if footing_width is None or web + design.web_step + 2 * design.cover > design.plan_max:
                return "h"
            web += design.web_step
        else:
            return "h" if result in ("zarpa", "web") else result


def _at_height(ctx: Context, fc: float, extra: int, h: float) -> CombinedSolution | str:
    """Solución de menor peso de refuerzo con este espesor (en la T, este alto de viga) y este largo, con el ancho mínimo
    del suelo o, si las barras transversales no se desarrollan, el siguiente que lo permita; "plan" si el largo no cabe,
    "soil" si el ancho no alcanza para el suelo, "h" si falta espesor."""
    if ctx.design.shape == "inverted_t":
        return _at_beam_height(ctx, fc, extra, h)
    return _sized(ctx, fc, geometry_for(ctx, h, extra))


def _sized(ctx: Context, fc: float, geometry: Geometry | None) -> CombinedSolution | str:
    if geometry is None:
        return "plan"
    sized = width_for(ctx, geometry)
    if sized is None:
        return "soil"
    result = reinforce(ctx, fc, sized)
    while result == "width" and sized.width + ctx.design.plan_step <= ctx.design.plan_max:
        sized = replace(sized, width=sized.width + ctx.design.plan_step)  # más largo de desarrollo transversal
        result = reinforce(ctx, fc, sized)
    return "h" if result == "width" else result


def _heights(ctx: Context) -> list[float]:
    """Los valores que recorre la búsqueda: los espesores o, en la T invertida, los altos de la viga."""
    design = ctx.design
    low, step, high = design.h_min, design.h_step, design.h_max
    if design.shape == "inverted_t":
        assert design.beam_h_min is not None and design.beam_h_step is not None and design.beam_h_max is not None
        low, step, high = design.beam_h_min, design.beam_h_step, design.beam_h_max
    count = int(round((high - low) / step)) + 1
    return [low + index * step for index in range(max(count, 1))]


def _for_length(ctx: Context, fc: float, extra: int) -> CombinedSolution | str:
    """La solución de menor costo con este largo: el menor espesor con solución, por bisección, y los mayores mientras el
    concreto solo no alcance el mejor costo (el ancho mínimo no decrece con el espesor). "plan" si el largo no cabe y
    "h" si no hay solución hasta h_max."""
    heights = _heights(ctx)
    first = _at_height(ctx, fc, extra, heights[0])
    if first == "plan":
        return "plan"
    best: CombinedSolution | None = first if isinstance(first, CombinedSolution) else None
    lowest = 0
    if best is None:
        low, high = 1, len(heights) - 1
        while low <= high:
            middle = (low + high) // 2
            result = _at_height(ctx, fc, extra, heights[middle])
            if isinstance(result, CombinedSolution):
                best, lowest, high = result, middle, middle - 1
            elif result == "soil":
                high = middle - 1
            else:
                low = middle + 1
    if best is None:
        return "h"
    for h in heights[lowest + 1 :]:
        if _concrete_floor(ctx, fc, _with_height(best.geometry, h)) >= best.cost:
            break
        result = _at_height(ctx, fc, extra, h)
        if isinstance(result, CombinedSolution) and result.cost < best.cost:
            best = result
    return best


_FAILURES = {"plan": "el largo necesario pasa de plan_max o no cabe con los voladizos maximos",
             "soil": "ningun ancho hasta plan_max cumple la revision geotecnica",
             "h": "ningun espesor hasta h_max aprueba la verificacion estructural"}


def design_for_fc(ctx: Context, fc: float) -> FcOption:
    """La zapata de menor costo con este f'c entre el largo mínimo con solución y los _EXTRA_LENGTHS siguientes."""
    best: CombinedSolution | None = None
    failure = "h"
    extra, remaining = 0, None
    while remaining is None or remaining > 0:
        result = _for_length(ctx, fc, extra)
        if result == "plan":
            failure = "plan" if best is None and extra == 0 else failure
            break
        if isinstance(result, CombinedSolution):
            best = result if best is None or result.cost < best.cost else best
        else:
            failure = result
        if best is not None:
            remaining = _EXTRA_LENGTHS if remaining is None else remaining - 1
        extra += 1
    return FcOption(fc, best, None if best is not None else _FAILURES[failure])


def _fc_in_worker(task: tuple[CombinedDesignProject, tuple[RebarSpec, ...], float]) -> FcOption:
    """Un f'c en un proceso del pool: el perfil (módulos) no se copia entre procesos, se toma del registro."""
    project, bars, fc = task
    return design_for_fc(Context(project, PROFILES[project.profile], bars), fc)


def design_combined(ctx: Context, workers: int = 1) -> CombinedDesignResult:
    """La zapata de menor costo entre los f'c de la lista (D-107); workers reparte los f'c entre procesos (no cambia el
    resultado)."""
    fcs = list(ctx.design.fc_options)
    if workers > 1 and len(fcs) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(fcs))) as pool:
            options = tuple(pool.map(_fc_in_worker, [(ctx.project, tuple(ctx.bars), fc) for fc in fcs]))
    else:
        options = tuple(design_for_fc(ctx, fc) for fc in fcs)
    solved = [option.solution for option in options if option.solution is not None]
    return CombinedDesignResult(min(solved, key=lambda solution: solution.cost) if solved else None, options,
                                placement_loads(ctx)[0].case)


def _placement_note(ctx: Context) -> str:
    """El caso que ubica la base y cómo se eligió, para la memoria y el resumen (D-108)."""
    case = placement_loads(ctx)[0].case
    how = "declarado en placement_case" if ctx.design.placement_case is not None else "de servicio sin sismo de mayor carga"
    return f"'{case}' ({how})"


def designed_project(ctx: Context, solution: CombinedSolution) -> dict[str, Any]:
    """Proyecto de verificación (formato de entrada) con la zapata diseñada."""
    project = ctx.project
    materials = project.materials
    g = solution.geometry
    shape = ""
    if g.beam is not None:  # T invertida (D-113)
        deep = ", de gran altura (deep_beam, D-089: sin puntal-tensor)" if solution.data.get("deep_beam") else ""
        shape = f" en T invertida con viga de {g.beam[0]:g} × {g.beam[1]:g} mm{deep}"
    return {
        "description": f"{project.description} Diseño de la zapata combinada (D-107){shape}: {g.length:g} × {g.width:g} × {g.h:g} mm, "
                       f"f'c = {solution.fc:g} MPa, centroide de la base en ({g.center[0]:.1f}, {g.center[1]:.1f}) mm de los "
                       f"ejes de las columnas, sobre la resultante del caso {_placement_note(ctx)}, costo {solution.cost:.2f}.",
        "profile": project.profile,
        "seismic": project.seismic.model_dump(),
        "materials": {"fc": solution.fc, "fy": materials.fy, "fyt": materials.fyt, "concrete": materials.concrete,
                      "coating": materials.coating,
                      **({} if materials.max_aggregate is None else {"max_aggregate": materials.max_aggregate})},
        "soil": soil_input(project.soil),
        "combined_footings": [solution.data],
    }
