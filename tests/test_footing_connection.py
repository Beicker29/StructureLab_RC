"""V3D.3 y V3H: desarrollo de las mallas (con ψe, ψcc y refuerzo en exceso), aplastamiento y pasadores de zapatas contra
el oráculo independiente (D-059, D-065, D-071)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
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
    materials = Materials.model_validate({**oracle["materials"], "coating": case["coating"]})
    checks = connection_checks(Basis(PROFILES[profile], materials, BARS, case["seismic_level"]), footing, cases)
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
        if "psi_e" in item:
            values = dict(check.values)
            assert values["psi e"] == item["psi_e"], key
            assert values["factor exceso"] == pytest.approx(item["excess_applied"], rel=tolerance), key
            assert values.get("psi cc") == item.get("psi_cc"), key
            if item["excess_ratio"] < 1.0:
                assert values["As,req/As,sum"] == pytest.approx(item["excess_ratio"], rel=tolerance), key
            if item["excess_ratio"] < 1.0 and item["excess_applied"] == 1.0:
                assert "no aplicado" in check.note, key


def test_coating_is_required() -> None:
    with pytest.raises(ValueError, match="coating"):
        Materials.model_validate({"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"})


def test_aci_rejects_the_excess_factor_on_hooks() -> None:
    """25.4.10.2(d): el factor de refuerzo en exceso no se permite en ganchos; NSR-10 sí lo permite (C.12.5.3(d))."""
    aci, nsr = PROFILES["aci-318-25"].development, PROFILES["nsr-10"].development
    assert not aci.excess_factor_permitted("hook", "ordinary")
    assert nsr.excess_factor_permitted("hook", "DMI")
    assert not nsr.excess_factor_permitted("compression", "DMI")
    with pytest.raises(ValueError, match="25.4.10.2"):
        aci.hook_development_length(fy=420.0, fc=28.0, lam=1.0, db=25.4, psi_e=1.0, psi_cc=1.0, excess=0.5)
