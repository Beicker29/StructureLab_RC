"""Torsión de vigas macizas por estación: umbral, y verificación combinada con el cortante si Tu ≥ φTth."""

from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.beam.geometry import inside_web, interior_limits, placed_bars
from structurelab_rc.domain.beam.shear import SPACING, ShearTerms, concrete_lambda, leg_spacing_across, shear_terms
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Section, Station

THRESHOLD = "Torsion: umbral"
SECTION = "Torsion: dimensiones de la seccion"
TRANSVERSE = "Torsion: refuerzo transversal"
MIN_TRANSVERSE = "Torsion: refuerzo transversal minimo"
LONGITUDINAL = "Torsion: refuerzo longitudinal"
DETAILING = "Torsion: distribucion del refuerzo longitudinal"
_CORNER_BARS = 2


def gross_torsion_section(profile: Profile, section: Section) -> tuple[float, float]:
    """Acp y pcp con el saliente efectivo del ala; las alas se ignoran si reducen Acp²/pcp (ACI 9.2.4.4, NSR-10 C.11.5.1.1)."""
    web = (section.bw * section.h, 2 * (section.bw + section.h))
    if section.hf is None:
        return web
    limit = profile.torsion.effective_overhang(section.h, section.hf)
    overhangs = min(section.overhang_x_neg or 0.0, limit) + min(section.overhang_x_pos or 0.0, limit)
    flanged = (section.bw * section.h + overhangs * section.hf, 2 * (section.bw + overhangs + section.h))
    return max(web, flanged, key=lambda geometry: geometry[0] ** 2 / geometry[1])


def threshold_check(profile: Profile, materials: Materials, member: Member, station: Station) -> Check | None:
    """Umbral φTth; None si Tu es despreciable y el cortante se verifica solo."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, Check):
        return lam
    demands, section, torsion = station.demands, member.section, profile.torsion
    assert demands.tu is not None and demands.pu is not None
    acp, pcp = gross_torsion_section(profile, section)
    limit = torsion.strength_reduction() * torsion.threshold_torsion(materials.fc, lam, acp, pcp, demands.pu, section.area)
    # Sin torsión no hay nada que verificar, aunque la tracción axial lleve el umbral a cero.
    if demands.tu == 0 or abs(demands.tu) < limit:
        return None
    return Check(THRESHOLD, Status.PASS, clause=torsion.clauses()["threshold"], values=(("Tu", abs(demands.tu)), ("phi Tth", limit)),
                 note="Tu >= phi Tth: se verifica la torsion combinada con el cortante")


def _longitudinal_detailing(profile: Profile, member: Member, station: Station, bars: Sequence[RebarSpec]) -> Check:
    """Barra en cada esquina y separación ≤ 300 mm con todas las capas; diámetro mínimo en las de torsión (D-034, D-035)."""
    torsion, section, layout = profile.torsion, member.section, station.layout
    assert layout.stirrups is not None
    specs = {bar.designation: bar for bar in bars}
    # Solo cuentan las barras dentro de los estribos cerrados, es decir, en el alma (ACI 9.7.5.1, NSR-10 C.11.5.6.2).
    placed = [bar for bar in placed_bars(layout, section, bars) if inside_web(bar, section)]
    depths = sorted({bar.depth for bar in placed})
    limit = torsion.max_longitudinal_spacing()
    problems = []
    for depth in (depths[0], depths[-1]):
        row = sorted((bar for bar in placed if bar.depth == depth), key=lambda bar: bar.x)
        left_corner = interior_limits(section, layout, specs, row[0].diameter)[0]
        right_corner = interior_limits(section, layout, specs, row[-1].diameter)[1]
        # Una barra ocupa la esquina si su centro está a no más de un diámetro de la posición de esquina.
        if len(row) < _CORNER_BARS or row[0].x - left_corner > row[0].diameter or right_corner - row[-1].x > row[-1].diameter:
            problems.append(f"la capa a {depth:.0f} mm no tiene barras en ambas esquinas")
        if any(second.x - first.x > limit for first, second in zip(row, row[1:], strict=False)):
            problems.append(f"la capa a {depth:.0f} mm separa sus barras mas de {limit:.0f} mm")
    gaps = [lower - upper for upper, lower in zip(depths, depths[1:], strict=False)]
    if gaps and max(gaps) > limit:
        problems.append(f"hay capas separadas {max(gaps):.0f} mm en altura")
    minimum = torsion.min_longitudinal_diameter(layout.stirrups.spacing)
    thin = [bar for bar in placed if bar.role == "torsion" and bar.diameter < minimum]
    if thin:
        problems.append(f"barras de torsion con diametro menor que {minimum:.1f} mm")
    clause = torsion.clauses()["detailing"]
    return Check(DETAILING, Status.FAIL if problems else Status.PASS, clause=clause, note="; ".join(problems))


def _checks(given: StationInput, terms: ShearTerms) -> list[Check]:
    profile, materials, member, station, bars = given.profile, given.materials, given.member, given.station, given.bars
    torsion, shear, section, stirrups = profile.torsion, profile.shear, member.section, station.layout.stirrups
    demands = station.demands
    assert stirrups is not None and demands.vu is not None and demands.tu is not None
    specs = {bar.designation: bar for bar in bars}
    stirrup = specs[stirrups.designation]
    clauses = torsion.clauses()
    x1 = section.bw - 2 * section.cover - stirrup.diameter_mm
    y1 = section.h - 2 * section.cover - stirrup.diameter_mm
    aoh, ph = x1 * y1, 2 * (x1 + y1)
    a0 = 0.85 * aoh
    vu, tu, phi = abs(demands.vu), abs(demands.tu), shear.strength_reduction()
    fyt = min(materials.fyt, torsion.max_yield())
    fy = min(materials.fy, torsion.max_yield())
    at_s = torsion.required_transverse(tu, a0, fyt)
    av_s = max(vu / phi - terms.vc, 0.0) / (fyt * terms.d)
    outer_leg = stirrup.area_mm2 / stirrups.spacing
    transverse_ok = stirrups.closed and av_s + 2 * at_s <= terms.transverse and at_s <= outer_leg
    stress = torsion.combined_stress(vu, tu, section.bw, terms.d, ph, aoh)
    stress_limit = torsion.combined_stress_limit(terms.vc, materials.fc, section.bw, terms.d)
    acp, _ = gross_torsion_section(profile, section)
    al_required = max(
        torsion.required_longitudinal(tu, at_s, a0, ph, fyt, fy),
        torsion.min_longitudinal(materials.fc, acp, fy, at_s, ph, fyt, section.bw),
    )
    al_provided = sum(bar.area for bar in placed_bars(station.layout, section, bars) if bar.role == "torsion")
    minimum = torsion.min_transverse(materials.fc, section.bw, fyt)
    required_vs = max(vu / phi - terms.vc, 0.0)
    along = min(torsion.max_spacing(ph), shear.max_spacing(required_vs, materials.fc, section.bw, terms.d))
    across_limit = shear.max_leg_spacing_across(required_vs, materials.fc, section.bw, terms.d)
    across = leg_spacing_across(member, station, bars) or 0.0
    spacing_ok = stirrups.spacing <= along and (across_limit is None or across <= across_limit)
    return [
        Check(SECTION, Status.PASS if stress <= stress_limit else Status.FAIL, clause=clauses["section"],
              demand=stress, capacity=stress_limit, unit="MPa"),
        Check(TRANSVERSE, Status.PASS if transverse_ok else Status.FAIL, clause=clauses["transverse"],
              demand=av_s + 2 * at_s, capacity=terms.transverse, unit="mm2/mm",
              values=(("Av/s", av_s), ("At/s", at_s), ("At/s rama exterior", outer_leg), ("Vc", terms.vc)),
              note="" if stirrups.closed else "La torsion requiere estribos cerrados"),
        Check(MIN_TRANSVERSE, Status.PASS if terms.transverse >= minimum else Status.FAIL, clause=clauses["min_transverse"],
              demand=minimum, capacity=terms.transverse, unit="mm2/mm"),
        Check(LONGITUDINAL, Status.PASS if al_provided >= al_required else Status.FAIL, clause=clauses["longitudinal"],
              demand=al_required, capacity=al_provided, unit="mm2", values=(("Aoh", aoh), ("ph", ph))),
        Check(SPACING, Status.PASS if spacing_ok else Status.FAIL, clause=f"{shear.clauses()['spacing']} y {clauses['spacing']}",
              demand=stirrups.spacing, capacity=along, unit="mm"),
        _longitudinal_detailing(profile, member, station, bars),
    ]


def torsion_checks(given: StationInput) -> tuple[Check, ...]:
    """Verificación combinada de torsión y cortante en una estación con Tu ≥ φTth."""
    profile, materials = given.profile, given.materials
    if given.station.layout.stirrups is None:
        clause = profile.torsion.clauses()["transverse"]
        return (Check(TRANSVERSE, Status.FAIL, clause=clause, note="La torsion requiere estribos cerrados y no hay estribos"),)
    fyt = min(materials.fyt, profile.torsion.max_yield())
    terms = shear_terms(given, profile.torsion.min_transverse(materials.fc, given.member.section.bw, fyt))
    if isinstance(terms, Check):
        return (terms,)
    return tuple(_checks(given, terms))
