from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.shear import MIN_REINFORCEMENT, SECTION, SPACING, STRENGTH
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.model.project import Materials, Member
from structurelab_rc.setup import load_engine

BARS = load_engine().bars
MATERIALS = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight")
SECTION_300X500 = {"bw": 300.0, "h": 500.0, "cover": 40.0}
BOTTOM = [{"designation": "#8", "count": 3, "depth": 440.0, "role": "flexure"}]
STIRRUPS = {"designation": "#3", "legs": 2, "spacing": 150.0, "closed": True}
DEMANDS = {"Pu_kN": 0.0, "Mu_kNm": 100.0, "Vu_kN": 120.0, "Tu_kNm": 0.0}


def _member(
    stirrups: dict[str, Any] | None = STIRRUPS,
    section: dict[str, float] = SECTION_300X500,
    layers: list[dict[str, Any]] = BOTTOM,
    **demands: float,
) -> Member:
    station = {"x": 0.0, "layout": {"layers": layers, "stirrups": stirrups}, "demands": DEMANDS | demands}
    return Member.model_validate({"id": "V", "type": "beam", "length": 6000.0, "section": section, "stations": [station]})


def _checks(member: Member, profile: str = "nsr-10", materials: Materials = MATERIALS) -> dict[str, Check]:
    checks = station_checks(PROFILES[profile], materials, member, member.stations[0], BARS)
    return {check.name: check for check in checks if check.name.startswith("Cortante")}


@pytest.mark.parametrize("profile", ["nsr-10", "aci-318-25"])
def test_a_beam_with_stirrups_passes_every_shear_check(profile: str) -> None:
    checks = _checks(_member(), profile)
    assert {name: check.status for name, check in checks.items()} == {
        STRENGTH: Status.PASS,
        SECTION: Status.PASS,
        MIN_REINFORCEMENT: Status.PASS,
        SPACING: Status.PASS,
    }
    values = dict(checks[STRENGTH].values)
    assert values["Vs"] == pytest.approx(2 * 71.0 * 420.0 * 440.0 / 150.0)
    assert checks[STRENGTH].capacity == pytest.approx(0.75 * (values["Vc"] + values["Vs"]))


def test_insufficient_strength_fails() -> None:
    assert _checks(_member(Vu_kN=400.0))[STRENGTH].status is Status.FAIL


def test_oversized_shear_fails_the_section_limit() -> None:
    # Vs = 1907 kN supera 0.66√f'c·bw·d = 461 kN: la resistencia solo cuenta Vs hasta ese límite.
    checks = _checks(_member({"designation": "#4", "legs": 4, "spacing": 50.0, "closed": True}, Vu_kN=500.0))
    assert checks[SECTION].status is Status.FAIL
    assert checks[STRENGTH].status is Status.FAIL


def test_missing_minimum_shear_reinforcement_fails() -> None:
    checks = _checks(_member(None, Vu_kN=60.0))
    assert checks[MIN_REINFORCEMENT].status is Status.FAIL
    assert checks[SPACING].status is Status.PASS


def test_minimum_thresholds_differ_between_profiles() -> None:
    # ACI exige Av,min desde φ·0.083λ√f'c·bw·d = 43.5 kN (9.6.3.1, D-031); NSR-10 desde 0.5φVc = 44.5 kN (C.11.4.6.1).
    member = _member(None, Vu_kN=44.0)
    assert _checks(member, "aci-318-25")[MIN_REINFORCEMENT].status is Status.FAIL
    assert _checks(member, "nsr-10")[MIN_REINFORCEMENT].status is Status.PASS


def test_shallow_beams_are_exempt_from_minimum_shear_reinforcement() -> None:
    shallow = {"bw": 300.0, "h": 250.0, "cover": 25.0}
    layers = [{"designation": "#5", "count": 3, "depth": 200.0, "role": "flexure"}]
    member = _member(None, shallow, layers, Mu_kNm=20.0, Vu_kN=20.0)
    assert _checks(member)[MIN_REINFORCEMENT].status is Status.PASS


def test_spacing_is_halved_for_high_steel_shear() -> None:
    checks = _checks(_member({"designation": "#4", "legs": 2, "spacing": 150.0, "closed": True}, Vu_kN=330.0))
    assert checks[SPACING].capacity == pytest.approx(440.0 / 4)
    assert checks[SPACING].status is Status.FAIL


def test_leg_spacing_across_the_width_only_limits_aci() -> None:
    member = _member(section={"bw": 900.0, "h": 500.0, "cover": 40.0})
    assert _checks(member, "aci-318-25")[SPACING].status is Status.FAIL
    assert _checks(member, "nsr-10")[SPACING].status is Status.PASS


def test_non_negligible_torsion_replaces_the_shear_checks() -> None:
    names = set(_checks(_member(Tu_kNm=10.0)))
    assert STRENGTH not in names
    assert SPACING in names


def test_axial_tension_lowers_the_torsion_threshold() -> None:
    assert STRENGTH in _checks(_member(Tu_kNm=3.0))
    assert STRENGTH not in _checks(_member(Tu_kNm=3.0, Pu_kN=-400.0))


def test_lightweight_concrete_is_blocked() -> None:
    light = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="lightweight")
    assert _checks(_member(), materials=light)[STRENGTH].status is Status.BLOCKED


def test_missing_torsion_is_incomplete() -> None:
    station = {"x": 0.0, "layout": {"layers": BOTTOM, "stirrups": STIRRUPS}, "demands": {"Pu_kN": 0.0, "Mu_kNm": 100.0, "Vu_kN": 120.0}}
    member = Member.model_validate({"id": "V", "type": "beam", "length": 6000.0, "section": SECTION_300X500, "stations": [station]})
    assert _checks(member)[STRENGTH].status is Status.INCOMPLETE


def test_stirrup_yield_is_capped_at_420_mpa() -> None:
    high = Materials(fc=28.0, fy=420.0, fyt=520.0, concrete="normalweight")
    vs = dict(_checks(_member(), materials=high)[STRENGTH].values)["Vs"]
    assert vs == pytest.approx(2 * 71.0 * 420.0 * 440.0 / 150.0)


def test_torsion_threshold_matches_hand_value() -> None:
    expected = 0.083 * 28.0**0.5 * (300.0 * 500.0) ** 2 / 1600.0
    for profile in ("aci-318-25", "nsr-10"):
        torsion = PROFILES[profile].torsion
        assert torsion.threshold_torsion(28.0, 1.0, 150000.0, 1600.0, 0.0, 150000.0) == pytest.approx(expected)
