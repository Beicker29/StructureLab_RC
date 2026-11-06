import math
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import STRENGTH as FLEXURE_STRENGTH
from structurelab_rc.domain.beam.shear import SPACING
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.beam.torsion import (
    DETAILING,
    LONGITUDINAL,
    MIN_TRANSVERSE,
    SECTION,
    THRESHOLD,
    TRANSVERSE,
    gross_torsion_section,
)
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.model.project import Materials, Member, Section
from structurelab_rc.setup import load_engine

BARS = load_engine().bars
MATERIALS = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight")
SECTION_300X500 = {"bw": 300.0, "h": 500.0, "cover": 40.0}
TOP = {"bars": ["#5", "#5", "#5"], "depth": 60.0, "role": "flexure"}
BOTTOM = {"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}
TORSION_BARS = {"bars": ["#6", "#6"], "depth": 250.0, "role": "torsion"}
STIRRUPS = {"designation": "#4", "legs": 2, "spacing": 100.0, "closed": True}
DEMANDS = {"Pu_kN": 0.0, "Mu_kNm": 100.0, "Vu_kN": 120.0, "Tu_kNm": 20.0}
TORSION_NAMES = {THRESHOLD, SECTION, TRANSVERSE, MIN_TRANSVERSE, LONGITUDINAL, SPACING, DETAILING}


def _member(
    layers: list[dict[str, Any]] | None = None,
    stirrups: dict[str, Any] | None = STIRRUPS,
    section: dict[str, Any] = SECTION_300X500,
    **demands: float,
) -> Member:
    layout = {"layers": layers if layers is not None else [TOP, BOTTOM, TORSION_BARS], "stirrups": stirrups}
    station = {"x": 0.0, "layout": layout, "demands": DEMANDS | demands}
    return Member.model_validate({"id": "V", "type": "beam", "length": 6000.0, "section": section, "stations": [station]})


def _checks(member: Member, profile: str = "nsr-10") -> dict[str, Check]:
    return {check.name: check for check in station_checks(PROFILES[profile], MATERIALS, member, member.stations[0], BARS)}


@pytest.mark.parametrize("profile", ["nsr-10", "aci-318-25"])
def test_a_beam_designed_for_torsion_passes(profile: str) -> None:
    checks = _checks(_member(), profile)
    assert {name: checks[name].status for name in TORSION_NAMES} == dict.fromkeys(TORSION_NAMES, Status.PASS)


def test_hand_values_for_the_reference_beam() -> None:
    # Estribo #4 (12.7 mm) con recubrimiento de 40 mm en una sección de 300 × 500 mm.
    x1, y1 = 300.0 - 80.0 - 12.7, 500.0 - 80.0 - 12.7
    aoh, ph = x1 * y1, 2 * (x1 + y1)
    at_s = 20e6 / (0.75 * 2 * 0.85 * aoh * 420.0)
    checks = _checks(_member())
    values = dict(checks[TRANSVERSE].values)
    assert values["At/s"] == pytest.approx(at_s)
    assert values["At/s rama exterior"] == pytest.approx(129.0 / 100.0)
    al = 20e6 * ph / (0.75 * 2 * 0.85 * aoh * 420.0)
    al_min = 0.42 * math.sqrt(28.0) * 150000.0 / 420.0 - at_s * ph
    assert checks[LONGITUDINAL].demand == pytest.approx(max(al, al_min))
    assert checks[LONGITUDINAL].capacity == pytest.approx(2 * 284.0)
    assert checks[SPACING].capacity == pytest.approx(ph / 8)


def test_torsion_bars_do_not_count_as_flexural_steel() -> None:
    with_torsion = dict(_checks(_member())[FLEXURE_STRENGTH].values)["Mn"]
    without = dict(_checks(_member([TOP, BOTTOM]))[FLEXURE_STRENGTH].values)["Mn"]
    assert with_torsion == pytest.approx(without)


def test_missing_torsion_bars_fail_the_longitudinal_check() -> None:
    assert _checks(_member([TOP, BOTTOM]))[LONGITUDINAL].status is Status.FAIL


def test_open_stirrups_fail_the_transverse_check() -> None:
    check = _checks(_member(stirrups=STIRRUPS | {"closed": False}))[TRANSVERSE]
    assert check.status is Status.FAIL
    assert "cerrados" in check.note


def test_no_stirrups_fail_when_torsion_matters() -> None:
    checks = _checks(_member(stirrups=None))
    assert checks[TRANSVERSE].status is Status.FAIL


def test_interior_legs_do_not_resist_torsion() -> None:
    # Cuatro ramas #3 cada 60 mm suman n·Ab/s = 4.73 mm²/mm, pero la rama exterior solo da 1.18 < At/s requerido.
    stirrups = {"designation": "#3", "legs": 4, "spacing": 60.0, "closed": True}
    check = _checks(_member(stirrups=stirrups, Tu_kNm=60.0, Vu_kN=60.0))[TRANSVERSE]
    values = dict(check.values)
    assert values["Av/s"] + 2 * values["At/s"] <= check.capacity  # type: ignore[operator]
    assert values["At/s"] > values["At/s rama exterior"]
    assert check.status is Status.FAIL


def test_thin_torsion_bars_fail_the_detailing() -> None:
    thin = TORSION_BARS | {"bars": ["#3", "#3", "#3", "#3"]}
    check = _checks(_member([TOP, BOTTOM, thin], stirrups=STIRRUPS | {"spacing": 150.0}))[DETAILING]
    assert check.status is Status.FAIL
    assert "diametro" in check.note


def test_corner_bars_can_be_flexural_bars() -> None:
    # Opción A (D-035): las esquinas se cumplen con cualquier barra longitudinal.
    assert _checks(_member())[DETAILING].status is Status.PASS
    single_top = TOP | {"bars": ["#5"]}
    assert _checks(_member([single_top, BOTTOM, TORSION_BARS]))[DETAILING].status is Status.FAIL


def test_tall_gaps_between_layers_fail_the_detailing() -> None:
    tall = {"bw": 300.0, "h": 900.0, "cover": 40.0}
    bottom = BOTTOM | {"depth": 840.0}
    check = _checks(_member([TOP, bottom], section=tall, Tu_kNm=40.0))[DETAILING]
    assert check.status is Status.FAIL
    assert "altura" in check.note


def test_oversized_section_fails_the_combined_limit() -> None:
    assert _checks(_member(Tu_kNm=80.0, Vu_kN=250.0))[SECTION].status is Status.FAIL


def test_minimum_bar_diameter_has_a_10_mm_floor() -> None:
    for profile in ("aci-318-25", "nsr-10"):
        torsion = PROFILES[profile].torsion
        assert torsion.min_longitudinal_diameter(100.0) == pytest.approx(10.0)
        assert torsion.min_longitudinal_diameter(300.0) == pytest.approx(0.042 * 300.0)


def test_both_profiles_require_the_same_longitudinal_steel_at_45_degrees() -> None:
    aci, nsr = _checks(_member(), "aci-318-25")[LONGITUDINAL], _checks(_member(), "nsr-10")[LONGITUDINAL]
    assert aci.demand == pytest.approx(nsr.demand)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        # T: el saliente se limita a 4hf = 400 mm (menor que h − hf = 500 mm); las alas aumentan Acp²/pcp.
        ({"bw": 300.0, "h": 600.0, "bf": 1500.0, "hf": 100.0, "flange_sides": 2}, (260000.0, 3400.0)),
        # L: un solo saliente, limitado a 480 mm aunque el ala mida 500 mm.
        ({"bw": 300.0, "h": 600.0, "bf": 800.0, "hf": 120.0, "flange_sides": 1}, (237600.0, 2760.0)),
        # Ala delgada: con alas Acp²/pcp baja, así que se ignoran.
        ({"bw": 300.0, "h": 700.0, "bf": 1500.0, "hf": 60.0, "flange_sides": 2}, (210000.0, 2000.0)),
    ],
)
@pytest.mark.parametrize("profile", ["nsr-10", "aci-318-25"])
def test_gross_torsion_section_uses_the_effective_flange(profile: str, section: dict[str, Any], expected: tuple[float, float]) -> None:
    acp, pcp = gross_torsion_section(PROFILES[profile], Section.model_validate(section | {"cover": 40.0}))
    assert (acp, pcp) == pytest.approx(expected)


def test_minimum_longitudinal_steel_governs_for_small_torsion() -> None:
    x1, y1 = 300.0 - 80.0 - 12.7, 500.0 - 80.0 - 12.7
    aoh, ph = x1 * y1, 2 * (x1 + y1)
    at_s = 6e6 / (0.75 * 2 * 0.85 * aoh * 420.0)
    al_min = 0.42 * math.sqrt(28.0) * 150000.0 / 420.0 - at_s * ph
    for profile in ("nsr-10", "aci-318-25"):
        check = _checks(_member(Tu_kNm=6.0), profile)[LONGITUDINAL]
        assert check.demand == pytest.approx(al_min)


@pytest.mark.parametrize("profile", ["nsr-10", "aci-318-25"])
def test_minimum_longitudinal_steel_floors_at_s(profile: str) -> None:
    # At/s = 0.1 < 0.175·bw/fyt = 0.125 mm²/mm: se usa 0.125 (NSR-10 C.11-24; en ACI 9.6.4.3 rige la opción (b)).
    expected = 0.42 * math.sqrt(28.0) * 150000.0 / 420.0 - 0.125 * 1229.2
    assert PROFILES[profile].torsion.min_longitudinal(28.0, 150000.0, 420.0, 0.1, 1229.2, 420.0, 300.0) == pytest.approx(expected)


def test_torsion_yield_strengths_are_capped_at_420_mpa() -> None:
    high = Materials(fc=28.0, fy=520.0, fyt=520.0, concrete="normalweight")
    member = _member()
    capped = station_checks(PROFILES["nsr-10"], high, member, member.stations[0], BARS)
    longitudinal = next(check for check in capped if check.name == LONGITUDINAL)
    assert longitudinal.demand == pytest.approx(_checks(member)[LONGITUDINAL].demand)


def test_zero_torsion_never_triggers_the_torsion_checks() -> None:
    # Con Pu = −300 kN el factor de carga axial del umbral es negativo y φTth = 0; con Tu = 0 no hay torsión que verificar.
    names = set(_checks(_member(Tu_kNm=0.0, Pu_kN=-300.0, Mu_kNm=5.0, Vu_kN=20.0)))
    assert THRESHOLD not in names
    assert TRANSVERSE not in names
