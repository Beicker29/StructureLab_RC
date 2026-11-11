"""Criterios de vigas de gran altura en una estación (D-089): límite de sección, refuerzo distribuido transversal y
longitudinal, su separación y, donde el perfil lo pide, las cortinas cerca de cada cara. La condición de viga alta la
declara el usuario (`deep_beam`); la resistencia sigue con el cálculo seccional y la memoria avisa que no considera la
distribución no lineal de deformaciones (ACI 9.9.1.2, NSR-10 C.11.7.2). Común a las vigas y a la viga larga de la
zapata combinada."""

from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.beam.shear import leg_spacing_across, shear_terms
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status

SECTION = "Viga alta: limite de seccion"
TRANSVERSE = "Viga alta: refuerzo distribuido transversal"
LONGITUDINAL = "Viga alta: refuerzo distribuido longitudinal"
SPACING = "Viga alta: separacion del refuerzo distribuido"
CURTAINS = "Viga alta: cortinas"
_SAME_DEPTH = 1e-6


def _layers(given: StationInput) -> list[tuple[float, float]]:
    """(profundidad, área) de cada capa de barras longitudinales, de arriba hacia abajo."""
    placed = placed_bars(given.station.layout, given.member.section, given.bars)
    depths = sorted({bar.depth for bar in placed})
    return [(depth, sum(bar.area for bar in placed if abs(bar.depth - depth) <= _SAME_DEPTH)) for depth in depths]


def _longitudinal(given: StationInput, required_ratio: float) -> tuple[Check, float]:
    """Cada capa intermedia frente a ratio·bw por su altura tributaria (la mitad de los saltos a sus vecinas); devuelve la
    verificación y el mayor salto vertical entre capas."""
    profile, bw = given.profile, given.member.section.bw
    layers = _layers(given)
    gaps = [lower[0] - upper[0] for upper, lower in zip(layers, layers[1:], strict=False)]
    largest = max(gaps, default=given.member.section.h)
    clause = profile.deep_beam.clauses()["longitudinal"]
    inner = layers[1:-1]
    if not inner:
        return Check(LONGITUDINAL, Status.FAIL, clause=clause, unit="mm2",
                     note="Sin capas intermedias de refuerzo distribuido entre las capas extremas"), largest
    worst: tuple[float, float, float] | None = None
    for index, (depth, area) in enumerate(inner, start=1):
        tributary = (gaps[index - 1] + gaps[index]) / 2
        required = required_ratio * bw * tributary
        if worst is None or area / required < worst[1] / worst[0]:
            worst = (required, area, depth)
    assert worst is not None
    required, area, depth = worst
    return Check(LONGITUDINAL, Status.PASS if area >= required else Status.FAIL, clause=clause, demand=required, capacity=area,
                 unit="mm2", values=(("capa", depth),), note=f"Capa que gobierna a {depth:.0f} mm de la cara superior"), largest


def deep_beam_checks(given: StationInput) -> tuple[Check, ...]:
    """Las verificaciones de viga alta de una estación de un miembro declarado alto."""
    profile, materials, member, station = given.profile, given.materials, given.member, given.station
    deep, shear = profile.deep_beam, profile.shear
    clauses = deep.clauses()
    bw = member.section.bw
    fyt = min(materials.fyt, shear.max_stirrup_yield())
    terms = shear_terms(given, shear.min_shear_reinforcement(materials.fc, bw, fyt))
    if isinstance(terms, Check):
        return (Check(SECTION, terms.status, terms.errors, clauses["section"]),)
    assert station.demands.vu is not None
    phi, d = shear.strength_reduction(), terms.d
    limit = phi * deep.section_limit(materials.fc, bw, d)
    vu = abs(station.demands.vu)
    ratio = deep.min_distributed_ratio()
    maximum = deep.max_distributed_spacing(d)
    stirrups = station.layout.stirrups
    checks = [Check(SECTION, Status.PASS if vu <= limit else Status.FAIL, clause=clauses["section"], demand=vu, capacity=limit,
                    unit="N", values=(("phi", phi), ("d", d)))]
    if stirrups is None:
        checks.append(Check(TRANSVERSE, Status.FAIL, clause=clauses["transverse"], unit="mm2/mm", note="Sin estribos"))
    else:
        checks.append(Check(TRANSVERSE, Status.PASS if terms.transverse >= ratio * bw else Status.FAIL, clause=clauses["transverse"],
                            demand=ratio * bw, capacity=terms.transverse, unit="mm2/mm"))
    longitudinal, vertical = _longitudinal(given, ratio)
    checks.append(longitudinal)
    along = stirrups.spacing if stirrups is not None else 0.0
    spacing = max(along, vertical)
    checks.append(Check(SPACING, Status.PASS if spacing <= maximum else Status.FAIL, clause=clauses["spacing"], demand=spacing,
                        capacity=maximum, unit="mm", values=(("s estribos", along), ("sd vertical", vertical))))
    curtain = deep.max_curtain_spacing(bw)
    if curtain is not None:
        across = leg_spacing_across(member, station, given.bars)
        ok = across is not None and across <= curtain
        checks.append(Check(CURTAINS, Status.PASS if ok else Status.FAIL, clause=clauses["curtains"], demand=across, capacity=curtain,
                            unit="mm", note="" if across is not None else "Sin estribos: no hay cortinas cerca de cada cara"))
    return tuple(checks)
