"""V3D.3: desarrollo de las mallas, aplastamiento y pasadores de zapatas contra el oráculo independiente (D-059, D-065)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.connection import connection_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_footing_connection.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_connection_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    footing = Footing.model_validate(case["footing"])
    cases, _ = factored_cases(footing, Soil.model_validate(oracle["soil"]))
    checks = connection_checks(PROFILES[profile], Materials.model_validate(oracle["materials"]), footing, cases, BARS)
    got = {(check.name, check.case or ""): check for check in checks}
    expected = {(item["name"], item.get("case", "")): item for item in case["expected"]}
    assert set(got) == set(expected)
    tolerance = oracle["tolerance_rel"]
    for key, item in expected.items():
        check = got[key]
        assert str(check.status) == item["status"], key
        assert check.member == "Z"
        if "demand" in item:
            assert check.demand == pytest.approx(item["demand"], rel=tolerance), key
            assert check.capacity == pytest.approx(item["capacity"], rel=tolerance), key
        if "clause" in item:
            assert check.clause == item["clause"], key
