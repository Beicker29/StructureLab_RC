"""Verificación a flexión de vigas por estación, con Pn = Pu (D-024), en los dos ejes (D-046)."""

import math
from collections.abc import Callable, Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.geometry import flexure_points, placed_bars, section_polygon
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import flexure_phi, material_models, net_tensile_strain_check
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import FlexureState, SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.section import SectionState, SteelPoint, biaxial_state, section_state
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Demands, Materials, Member, Section, Station
from structurelab_rc.model.reinforcement import ReinforcementLayout

STRENGTH = "Flexion: resistencia"
NET_TENSILE_STRAIN = "Flexion: deformacion neta de traccion (M3)"
NET_TENSILE_STRAIN_M2 = "Flexion: deformacion neta de traccion (M2)"
NET_TENSILE_STRAIN_BIAXIAL = "Flexion: deformacion neta de traccion (biaxial)"
MIN_REINFORCEMENT = "Flexion: acero minimo (M3)"
MIN_REINFORCEMENT_M2 = "Flexion: acero minimo (M2)"
CRACK_SPACING = "Flexion: separacion por fisuracion"
SKIN = "Flexion: refuerzo superficial"
# d de As,min, del cortante y de la torsión: no menor que 0.8h (D-043).
MIN_DEPTH_RATIO = 0.8
_BISECTION_STEPS = 200
_RELATIVE_TOLERANCE = 1e-12
_SAME_LAYER = 1e-6  # mm


def steel_layers(layout: ReinforcementLayout, bars: Sequence[RebarSpec]) -> tuple[SteelLayer, ...] | StructuredError:
    """Capas de flexión con su área total; la profundidad sigue medida desde la fibra superior (D-027)."""
    areas = {bar.designation: bar.area_mm2 for bar in bars}
    layers = []
    for layer in layout.layers:
        if layer.role != "flexure":
            continue
        names = layer.designations()
        missing = [name for name in names if name not in areas]
        if missing:
            return invalid_input(f"La barra '{missing[0]}' no esta en el catalogo")
        layers.append(SteelLayer(layer.depth, sum(areas[name] for name in names)))
    return tuple(layers)


def nominal_flexure(
    profile: Profile, materials: Materials, section: Section, layers: tuple[SteelLayer, ...], demands: Demands
) -> FlexureState | StructuredError:
    """Estado nominal con la cara comprimida que indica el signo de Mu y la carga axial Pn = Pu.

    Lanza NoEquilibrium si la sección no puede equilibrar Pu.
    """
    if demands.mu is None or demands.pu is None:
        return incomplete("La flexion requiere Mu y Pu")
    models = material_models(profile, materials)
    if isinstance(models, StructuredError):
        return models
    top_in_compression = demands.mu >= 0
    # Con bf = bw el valor de hf no afecta el resultado.
    bf = section.bw if section.bf is None else section.bf
    hf = section.h / 2 if section.hf is None else section.hf
    strips = compression_strips(section.bw, section.h, bf, hf, flange_in_compression=top_in_compression)
    from_face = tuple(layer if top_in_compression else SteelLayer(section.h - layer.depth, layer.area) for layer in layers)
    return flexure_state(strips, from_face, *models, demands.pu)


def section_states(given: StationInput) -> tuple[SectionState, SectionState] | StructuredError:
    """Estado biaxial en la dirección de (Mu, M2) y estado uniaxial de M2 solo, con la sección completa (D-046).

    Lanza NoEquilibrium si la sección no puede equilibrar Pu.
    """
    demands, section = given.station.demands, given.member.section
    if demands.mu is None or demands.m2 is None or demands.pu is None:
        return incomplete("La flexion requiere Mu, M2 y Pu")
    models = material_models(given.profile, given.materials)
    if isinstance(models, StructuredError):
        return models
    polygon = section_polygon(section)
    points = flexure_points(given.station.layout, section, given.bars)
    biaxial = biaxial_state(polygon, points, models, demands.pu, (demands.mu, demands.m2))
    weak = section_state(polygon, points, models, demands.pu, 0.0 if demands.m2 >= 0 else math.pi)
    return biaxial, weak


def _counts_for_minimum(depth: float, strain: float, height: float) -> bool:
    """Acero que cuenta como As de tracción para As,min y su excepción (D-025 ajustada por D-081): a tracción y del lado
    en tracción de la sección, más allá de la mitad de la altura medida desde la cara comprimida. Con c pequeño, las
    barras cercanas a la cara comprimida quedan a tracción, pero no son el refuerzo de tracción por flexión."""
    return strain > 0 and depth > height / 2


def _analysis_area(provided: float, demand: float, design: Callable[[float], float]) -> float | None:
    """As a tracción requerido por análisis (ACI 9.6.1.3, NSR-10 C.10.5.3): el acero a tracción del estado nominal
    escalado por k hasta φMn(k) = |Mu|, por bisección; None si el provisto no alcanza el momento (la excepción no
    aplica). design(k) es φMn con el acero a tracción multiplicado por k."""
    if design(1.0) < demand:
        return None
    low, high = 0.0, 1.0
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2
        low, high = (middle, high) if design(middle) < demand else (low, middle)
        if high - low <= _RELATIVE_TOLERANCE:
            break
    return high * provided


def _min_check(profile: Profile, name: str, demand: tuple[float, float], provided: float, design: Callable[[float], float]) -> Check:
    """As ≥ As,min, o As ≥ 4/3 del requerido por análisis si es menor (D-022 resuelta por D-081)."""
    required, moment = demand
    clauses = profile.flexure.clauses()
    clause = f"{clauses['min_reinforcement']} y {clauses['min_reinforcement_exception']}"
    if provided >= required:
        return Check(name, Status.PASS, clause=clause, demand=required, capacity=provided, unit="mm2", values=(("As,min", required),))
    analysis = _analysis_area(provided, moment, design)
    if analysis is None:
        return Check(name, Status.FAIL, clause=clause, demand=required, capacity=provided, unit="mm2", values=(("As,min", required),),
                     note="As < As,min y el acero provisto no alcanza el momento: no aplica la excepcion")
    effective = profile.flexure.effective_min_reinforcement(required, analysis)
    return Check(name, Status.PASS if provided >= effective else Status.FAIL, clause=clause, demand=effective, capacity=provided,
                 unit="mm2", values=(("As,min", required), ("As analisis", analysis)),
                 note=f"Excepcion de {clauses['min_reinforcement_exception']}: 4/3 del As requerido por analisis")


def _strong_design(profile: Profile, materials: Materials, member: Member, layers: tuple[SteelLayer, ...],
                   given: tuple[FlexureState, Demands]) -> Callable[[float], float]:
    """φMn del eje fuerte con las capas a tracción del estado nominal multiplicadas por k."""
    state, demands = given
    tension = [_counts_for_minimum(layer.depth, layer.strain, member.section.h) for layer in state.layers]

    def design(k: float) -> float:
        scaled = tuple(SteelLayer(layer.depth, layer.area * k) if pulled else layer for layer, pulled in zip(layers, tension, strict=True))
        try:
            result = nominal_flexure(profile, materials, member.section, scaled, demands)
        except NoEquilibrium:
            return 0.0
        if isinstance(result, StructuredError):
            return 0.0
        return flexure_phi(profile, materials, result.extreme_strain) * abs(result.nominal_moment)

    return design


def _min_reinforcement(
    profile: Profile, materials: Materials, member: Member, state: FlexureState, given: tuple[float, Callable[[float], float]]
) -> Check:
    mu, design = given
    clause = profile.flexure.clauses()["min_reinforcement"]
    if mu == 0:
        return Check(MIN_REINFORCEMENT, Status.PASS, clause=clause, note="Sin momento no se requiere refuerzo a traccion")
    section = member.section
    bw = section.bw
    if section.bf is not None and mu < 0:
        if member.statically_determinate is None:
            return check_from_errors(MIN_REINFORCEMENT, [incomplete("Falta declarar si el miembro es isostatico (ala a traccion)")])
        if member.statically_determinate:
            bw = profile.flexure.determinate_flange_width(section.bw, section.bf)
    # Cuenta todo el acero a tracción en el estado nominal (D-025); d es su centroide, no menor que 0.8h (D-043).
    tension = [layer for layer in state.layers if _counts_for_minimum(layer.depth, layer.strain, section.h)]
    provided = sum(layer.area for layer in tension)
    centroid = sum(layer.depth * layer.area for layer in tension) / provided if provided else 0.0
    depth = max(centroid, MIN_DEPTH_RATIO * section.h)
    required = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, bw, depth)
    return _min_check(profile, MIN_REINFORCEMENT, (required, abs(mu)), provided, design)


def _weak_design(given: StationInput, weak: SectionState) -> Callable[[float], float]:
    """φMn del eje débil (M2 solo) con las barras a tracción del estado multiplicadas por k."""
    demands, section = given.station.demands, given.member.section
    assert demands.pu is not None and demands.m2 is not None
    models = material_models(given.profile, given.materials)
    polygon = section_polygon(section)
    points = flexure_points(given.station.layout, section, given.bars)
    tension = [_counts_for_minimum(bar.depth, bar.strain, section.flange_width) for bar in weak.bars]
    angle = 0.0 if demands.m2 >= 0 else math.pi

    def design(k: float) -> float:
        if isinstance(models, StructuredError):
            return 0.0
        scaled = tuple(SteelPoint(point.x, point.y, point.area * k) if pulled else point
                       for point, pulled in zip(points, tension, strict=True))
        try:
            state = section_state(polygon, scaled, models, demands.pu or 0.0, angle)
        except NoEquilibrium:
            return 0.0
        return flexure_phi(given.profile, given.materials, state.extreme_strain) * math.hypot(state.mn3, state.mn2)

    return design


def _weak_min_reinforcement(given: StationInput, weak: SectionState, m2: float) -> Check:
    """As,min del eje débil: ancho h y d del estado girado, no menor que 0.8 veces el ancho total (D-046)."""
    profile, materials, member = given.profile, given.materials, given.member
    clause = profile.flexure.clauses()["min_reinforcement"]
    if m2 == 0:
        return Check(MIN_REINFORCEMENT_M2, Status.PASS, clause=clause, note="Sin M2 no se requiere refuerzo a traccion")
    section = member.section
    tension = [bar for bar in weak.bars if _counts_for_minimum(bar.depth, bar.strain, section.flange_width)]
    provided = sum(bar.area for bar in tension)
    centroid = sum(bar.depth * bar.area for bar in tension) / provided if provided else 0.0
    depth = max(centroid, MIN_DEPTH_RATIO * section.flange_width)
    required = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, section.h, depth)
    return _min_check(profile, MIN_REINFORCEMENT_M2, (required, abs(m2)), provided, _weak_design(given, weak))


def _face_gaps(depths: list[float], start: float, end: float) -> float:
    """Mayor separación a lo largo de una cara lateral: de la capa en tracción (start) a las barras de piel y de la
    última al límite h/2 (end)."""
    ordered = sorted(depths, key=lambda depth: abs(depth - start))
    points = [start, *ordered, end]
    return max(abs(b - a) for a, b in zip(points, points[1:], strict=False))


def skin_check(given: StationInput) -> Check | None:
    """Refuerzo superficial (ACI 9.7.2.3, NSR-10 C.10.6.7; D-083): con h mayor que el límite del perfil, barras de piel en
    las dos caras laterales dentro de h/2 desde la cara en tracción; en cada cara, la mayor separación entre la capa en
    tracción, las barras de piel y el límite h/2 no excede el control de agrietamiento con cc a la cara lateral. None si
    no aplica (h menor o sin caras laterales libres)."""
    profile, materials, section = given.profile, given.materials, given.member.section
    if not given.side_faces or section.h <= profile.flexure.skin_reinforcement_depth():
        return None
    clause = profile.flexure.clauses()["skin"]
    mu = given.station.demands.mu or 0.0
    if mu == 0:
        return Check(SKIN, Status.PASS, clause=clause, note="Sin momento no hay cara en traccion")
    placed = placed_bars(given.station.layout, section, given.bars)
    bottom = mu > 0
    flexure = [bar.depth for bar in placed if bar.role == "flexure"]
    start = max(flexure) if bottom else min(flexure)
    half = section.h / 2
    in_zone = [bar for bar in placed if bar.role == "skin" and (bar.depth >= half if bottom else bar.depth <= half)]
    worst: tuple[float, float, float, str] | None = None  # razón, s, s máx, cara
    for name, own in (("izquierda", [bar for bar in in_zone if bar.x <= section.bw / 2]),
                      ("derecha", [bar for bar in in_zone if bar.x > section.bw / 2])):
        if not own:
            error = invalid_input(f"Falta el refuerzo superficial en la cara lateral {name} (h > "
                                  f"{profile.flexure.skin_reinforcement_depth():.0f} mm)")
            return Check(SKIN, Status.FAIL, (error,), clause)
        cc = min(min(bar.x, section.bw - bar.x) - bar.diameter / 2 for bar in own)
        limit = profile.flexure.crack_control_spacing(materials.fy, cc)
        gap = _face_gaps([bar.depth for bar in own], start, half)
        if worst is None or gap / limit > worst[0]:
            worst = (gap / limit, gap, limit, name)
    assert worst is not None
    _, gap, limit, name = worst
    return Check(SKIN, Status.PASS if gap <= limit else Status.FAIL, clause=clause, demand=gap, capacity=limit, unit="mm",
                 note=f"Gobierna la cara lateral {name}; zona de h/2 desde la cara {'inferior' if bottom else 'superior'}")


def _crack_check(given: StationInput, mu: float) -> Check:
    """Separación de las barras de flexión de la capa más cercana a la cara en tracción frente al control de
    agrietamiento del perfil (ACI 24.3.2, NSR-10 C.10.6.4), con fs = (2/3)·fy. Con una sola barra en esa capa, s es
    el ancho de la cara en tracción (NSR-10 C.10.6.4; en ACI, la misma lectura, D-081)."""
    profile, materials, section = given.profile, given.materials, given.member.section
    clause = profile.flexure.clauses()["crack_spacing"]
    if mu == 0:
        return Check(CRACK_SPACING, Status.PASS, clause=clause, note="Sin momento no hay cara en traccion")
    flexure = [bar for bar in placed_bars(given.station.layout, section, given.bars) if bar.role == "flexure"]
    bottom = mu > 0
    extreme = max(bar.depth for bar in flexure) if bottom else min(bar.depth for bar in flexure)
    layer = [bar for bar in flexure if abs(bar.depth - extreme) <= _SAME_LAYER]
    cc = min((section.h - bar.depth if bottom else bar.depth) - bar.diameter / 2 for bar in layer)
    positions = sorted(bar.x for bar in layer)
    if len(positions) == 1:
        spacing = section.bw if bottom else section.flange_width
        note = "Una sola barra en la capa: s = ancho de la cara en traccion"
    else:
        spacing = max(b - a for a, b in zip(positions, positions[1:], strict=False))
        note = f"Cara {'inferior' if bottom else 'superior'} en traccion"
    limit = profile.flexure.crack_control_spacing(materials.fy, cc)
    return Check(CRACK_SPACING, Status.PASS if spacing <= limit else Status.FAIL, clause=clause, demand=spacing, capacity=limit,
                 unit="mm", values=(("cc", cc), ("barras", float(len(positions)))), note=note)


def _strain_check(name: str, profile: Profile, materials: Materials, strain: float | None) -> Check:
    return net_tensile_strain_check(name, profile.flexure.clauses()["net_tensile_strain"], profile, materials, strain)


def _biaxial_checks(given: StationInput) -> tuple[Check, ...]:
    """Resistencia biaxial, εt del eje débil y del estado biaxial, y As,min del eje débil."""
    profile, materials, demands = given.profile, given.materials, given.station.demands
    clause = profile.flexure.clauses()["strength"]
    try:
        states = section_states(given)
    except NoEquilibrium as error:
        return (Check(STRENGTH, Status.FAIL, clause=clause, note=str(error)),)
    if isinstance(states, StructuredError):
        return (check_from_errors(STRENGTH, [states]),)
    biaxial, weak = states
    assert demands.mu is not None and demands.m2 is not None
    phi = flexure_phi(profile, materials, biaxial.extreme_strain)
    demand = math.hypot(demands.mu, demands.m2)
    capacity = phi * math.hypot(biaxial.mn3, biaxial.mn2)
    values = (("phi", phi), ("Mn3", biaxial.mn3), ("Mn2", biaxial.mn2), ("theta", math.degrees(biaxial.theta)),
              ("c", biaxial.c), ("et", biaxial.extreme_strain))
    strength = Check(STRENGTH, Status.PASS if capacity >= demand else Status.FAIL, clause=clause,
                     demand=demand, capacity=capacity, unit="N*mm", values=values)
    moments = demands.mu != 0 or demands.m2 != 0
    return (
        strength,
        _strain_check(NET_TENSILE_STRAIN_M2, profile, materials, weak.extreme_strain if demands.m2 != 0 else None),
        _strain_check(NET_TENSILE_STRAIN_BIAXIAL, profile, materials, biaxial.extreme_strain if moments else None),
        _weak_min_reinforcement(given, weak, demands.m2),
    )


def flexure_checks(
    profile: Profile, materials: Materials, member: Member, station: Station, bars: Sequence[RebarSpec]
) -> tuple[Check, ...]:
    """Verificaciones a flexión de una estación dentro del alcance de viga, en los dos ejes (D-046)."""
    demands = station.demands
    if demands.mu is None or demands.pu is None:
        return (check_from_errors(STRENGTH, [incomplete("La flexion requiere Mu y Pu")]),)
    layers = steel_layers(station.layout, bars)
    if isinstance(layers, StructuredError):
        return (check_from_errors(STRENGTH, [layers]),)
    try:
        state = nominal_flexure(profile, materials, member.section, layers, demands)
    except NoEquilibrium as error:
        return (Check(STRENGTH, Status.FAIL, clause=profile.flexure.clauses()["strength"], note=str(error)),)
    if isinstance(state, StructuredError):
        return (check_from_errors(STRENGTH, [state]),)
    strong_strain = _strain_check(NET_TENSILE_STRAIN, profile, materials, state.extreme_strain if demands.mu != 0 else None)
    if demands.mu == 0:
        strong_strain = _strain_check(NET_TENSILE_STRAIN, profile, materials, None)
    design = _strong_design(profile, materials, member, layers, (state, demands))
    strong_minimum = _min_reinforcement(profile, materials, member, state, (demands.mu, design))
    given = StationInput(profile, materials, member, station, bars)
    return (*_biaxial_checks(given), strong_strain, strong_minimum, _crack_check(given, demands.mu))
