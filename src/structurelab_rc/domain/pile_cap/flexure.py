"""Flexión de las mallas del cabezal (D-138), con domain/footing/flexure.py y los momentos de cara del análisis
(domain/pile_cap/loads.py): las reglas propias del cabezal son su As mínimo (interpretación de la guía CRSI, 4.5), su
altura mínima y que no admite concreto simple (ACI 14.1.4, NSR-10 C.22.2.1)."""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.flexure import SectionRules, Values, mat_flexure_checks
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.pile_cap.loads import CapAnalysis
from structurelab_rc.domain.status import Status
from structurelab_rc.model.pile_cap import PileCap


def cap_rules(basis: Basis, cap: PileCap) -> SectionRules:
    """As mínimo de la guía CRSI (4.5) con ACI 9.6.1 y 24.4 (NSR-10 C.10.5 y C.7.12): en la malla inferior, As =
    máx(As análisis, mín(As,min, 4/3·As análisis), mín(As,min, ρt·b·h)), con As,min = máx(0.25√f'c, 1.4)·b·d/fy; en la
    superior, solo el de flexión, máx(As análisis, mín(As,min, 4/3·As análisis)): la retracción ρt·b·h se revisa con las
    dos mallas sumadas (decisión del usuario, D-140; ACI R24.4.3.2, NSR-10 CR7.12.2). Altura mínima del cabezal; sin
    concreto simple."""
    profile, materials = basis.profile, basis.materials
    clauses = profile.pile_cap.clauses()
    ratio = profile.footing.shrinkage_temperature_ratio(materials.fy)

    def minimum(mat: str, row: BarRow, demand: float) -> tuple[float, Values, str]:
        minimum_area = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, row.width, row.depth)
        analysis = required_area(profile, materials, RectangularSection(row.width, cap.h), row.depth, max(demand, 0.0))
        if analysis is None:  # ninguna cuantía alcanza el momento: la flexión no cumple y el mínimo es As,min
            return minimum_area, (("As,min", minimum_area), ("rho t", ratio)), clauses["min_reinforcement"]
        flexural = max(analysis, profile.flexure.effective_min_reinforcement(minimum_area, analysis))
        if mat == "top":
            return flexural, (("As analisis", analysis), ("As,min", minimum_area)), clauses["min_reinforcement"]
        required = max(flexural, min(minimum_area, ratio * row.width * cap.h))
        return required, (("As analisis", analysis), ("As,min", minimum_area), ("rho t", ratio)), clauses["min_reinforcement"]

    return SectionRules(minimum, (profile.pile_cap.min_depth(), clauses["min_depth"]), clauses["plain"])


SHRINKAGE = "Retraccion y temperatura: cuantia"


def shrinkage_checks(basis: Basis, cap: PileCap) -> list[Check]:
    """Retracción y temperatura (ACI 24.4.3.2, NSR-10 C.7.12.2.1): en cada dirección, la malla inferior más la superior
    suman al menos ρt·b·h (D-140)."""
    profile = basis.profile
    ratio = profile.footing.shrinkage_temperature_ratio(basis.materials.fy)
    bottom = mat_rows(cap, cap.bottom, basis.bars)
    top = {} if cap.top is None else mat_rows(cap, cap.top, basis.bars)
    checks = []
    for direction, row in bottom.items():
        required = ratio * row.width * cap.h
        provided = row.area + (top[direction].area if direction in top else 0.0)
        checks.append(Check(f"{SHRINKAGE} (barras {direction})", Status.PASS if provided >= required else Status.FAIL,
                            clause=profile.footing.clauses()["shrinkage_temperature"], member=cap.id, demand=required,
                            capacity=provided, unit="mm2", values=(("cuantia minima", ratio), ("b", row.width), ("h", cap.h)),
                            note="Malla inferior y superior sumadas"))
    return checks


def flexure_checks(basis: Basis, cap: PileCap, analysis: CapAnalysis) -> list[Check]:
    """Resistencia, deformación neta, As mínimo, separación, franja central, altura mínima y retracción de las mallas."""
    return [*mat_flexure_checks(basis, cap, list(analysis.moments), cap_rules(basis, cap)), *shrinkage_checks(basis, cap)]
