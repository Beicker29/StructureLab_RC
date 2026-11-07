"""V3D.1: flexión de zapatas contra el oráculo independiente (D-059, D-061)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.flexure_strength import MomentStrength, RectangularSection, rectangular_strength, required_area
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_footing_flexure.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


def _key(check: Check) -> tuple[str, str]:
    return check.name, check.case or ""


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_flexure_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    footing = Footing.model_validate(case["footing"])
    cases, failures = factored_cases(footing, Soil.model_validate(oracle["soil"]))
    checks = [*failures, *flexure_checks(PROFILES[profile], Materials.model_validate(oracle["materials"]), footing, cases, BARS)]
    got = {_key(check): check for check in checks}
    expected = {(item["name"], item.get("case", "")): item for item in case["expected"]["checks"]}
    assert set(got) == set(expected)
    tolerance = oracle["tolerance_rel"]
    for key, item in expected.items():
        check = got[key]
        assert str(check.status) == item["status"], key
        assert check.member == "Z"
        if "demand_Nmm" in item:
            assert check.demand == pytest.approx(item["demand_Nmm"], rel=tolerance), key
        if "capacity_Nmm" in item:
            assert check.capacity == pytest.approx(item["capacity_Nmm"], rel=tolerance), key
        if "demand" in item:
            assert check.demand == pytest.approx(item["demand"], rel=tolerance), key
        if "capacity" in item:
            assert check.capacity == pytest.approx(item["capacity"], rel=tolerance), key
        if key[0].startswith("Flexion"):
            assert check.clause == oracle["clauses"]["strength"]
        if key[0].startswith("Franja"):
            assert check.clause == oracle["clauses"]["band"]


def test_band_spacing_places_bars_in_the_central_band() -> None:
    """Con band_spacing, la franja (lado corto, centrada en la columna) lleva su separación y fuera rige spacing."""
    data = _oracle("nsr_10")["cases"][1]["footing"]
    data = {**data, "bottom": {**data["bottom"], "y": {"designation": "#5", "spacing": 300.0, "band_spacing": 125.0}}}
    rows = mat_rows(Footing.model_validate(data), Footing.model_validate(data).bottom, BARS)
    row = rows["y"]
    assert row.band == (350.0 - 1100.0, 350.0 + 1100.0)
    inner = row.band_positions
    assert all(-750.0 - 1e-6 <= x <= 1450.0 + 1e-6 for x in inner)
    assert [round(b - a, 6) for a, b in zip(inner, inner[1:], strict=False)] == [125.0] * (len(inner) - 1)
    outside = [x for x in row.positions if x not in inner]
    assert outside and all(abs(abs(x - near) % 300.0) < 1e-6 or abs(abs(x - near) % 300.0 - 300.0) < 1e-6
                           for x in outside for near in (inner[0] if x < inner[0] else inner[-1],))
    assert len(inner) == 18  # ⌊2200/125⌋ + 1


def test_band_spacing_only_in_short_direction() -> None:
    data = _oracle("nsr_10")["cases"][1]["footing"]
    wrong = {**data, "bottom": {**data["bottom"], "x": {"designation": "#6", "spacing": 200.0, "band_spacing": 100.0}}}
    with pytest.raises(ValueError, match="band_spacing"):
        Footing.model_validate(wrong)


def test_required_area_reaches_the_moment() -> None:
    profile, materials = PROFILES["nsr-10"], Materials.model_validate(_oracle("nsr_10")["materials"])
    section = RectangularSection(2200.0, 600.0)
    area = required_area(profile, materials, section, 500.0, 4.0e8)
    assert area is not None
    strength = rectangular_strength(profile, materials, section, (SteelLayer(500.0, area),))
    assert isinstance(strength, MomentStrength)
    assert strength.design == pytest.approx(4.0e8, rel=1e-9)
    assert required_area(profile, materials, section, 500.0, 0.0) == 0.0
