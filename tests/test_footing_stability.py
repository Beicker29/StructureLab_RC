"""V3G: deslizamiento y volcamiento de zapatas contra el oráculo independiente (D-070)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.earth_pressure import passive_force
from structurelab_rc.model.footing import Footing, Soil

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MAT = {"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 150.0}, "y": {"designation": "#5", "spacing": 150.0}}


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_footing_stability.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


def _footing(case: dict[str, Any]) -> Footing:
    load = {"case": "S", "kind": "service", **case["load"]}
    return Footing.model_validate({"id": "Z", **case["footing"], "bottom": MAT, "top": None, "loads": [load]})


def _checks(profile: str, footing: Footing, soil: Soil) -> dict[str, Any]:
    return {check.name: check for check in service_checks(PROFILES[profile], footing, soil)}


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_stability_matches_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    tolerance = oracle["tolerance_rel"]
    expected = case["expected"]
    checks = _checks(profile, _footing(case), Soil.model_validate(oracle["soil"]))
    sliding, overturning = checks[SLIDING], checks[OVERTURNING]
    assert str(sliding.status) == expected["sliding"]
    assert str(overturning.status) == expected["overturning"]
    assert sliding.clause == overturning.clause == oracle["stability_clause"]
    assert (sliding.member, sliding.case) == ("Z", "S")
    if not expected["equilibrium"]:
        assert "Sin equilibrio" in sliding.errors[0].message
        return
    values = dict(sliding.values)
    assert values["Pp x"] / 1e3 == pytest.approx(expected["Pp_x_kN"], rel=tolerance)
    assert values["Pp y"] / 1e3 == pytest.approx(expected["Pp_y_kN"], rel=tolerance)
    assert sliding.demand / 1e3 == pytest.approx(expected["sliding_demand_kN"], rel=tolerance, abs=1e-9)
    assert sliding.capacity / 1e3 == pytest.approx(expected["R_kN"], rel=tolerance)
    assert sliding.note.removeprefix("Gobierna ").removeprefix("el ") in expected["sliding_governing"]
    assert overturning.demand / 1e6 == pytest.approx(expected["overturning_demand_kNm"], rel=tolerance, abs=1e-9)
    assert overturning.capacity / 1e6 == pytest.approx(expected["Mr_kNm"], rel=tolerance)
    assert overturning.note.removeprefix("Gobierna el volcamiento en el ") in expected["overturning_governing"]


def test_passive_force_closed_form() -> None:
    """Kp = 3, γ = 18 kN/m³, de 1 m a 1.5 m, c = 10 kPa: ½·3·18·(1.5² − 1²) + 2·10·√3·0.5 = 33.75 + 17.3205 kN/m."""
    force = passive_force(3.0, 18e-6, 1000.0, 500.0, 10e-3)
    assert force == pytest.approx(33.75 + 10 * 3**0.5)


def test_seismic_flag_only_changes_the_required_factor() -> None:
    oracle = _oracle("nsr_10")
    case = next(case for case in oracle["cases"] if case["id"] == "sismo-cumple")
    soil = Soil.model_validate(oracle["soil"])
    seismic = _checks("nsr-10", _footing(case), soil)[SLIDING]
    plain = _checks("nsr-10", _footing({**case, "load": {**case["load"], "seismic": False}}), soil)[SLIDING]
    assert (seismic.status, plain.status) == (Status.PASS, Status.FAIL)
    assert seismic.capacity == plain.capacity
    assert dict(seismic.values)["FS requerido"] == soil.sliding_safety_factor_seismic
    assert dict(plain.values)["FS requerido"] == soil.sliding_safety_factor


def test_passive_factor_defaults_to_one_half() -> None:
    data = {key: value for key, value in _oracle("nsr_10")["soil"].items() if key != "passive_factor"}
    assert Soil.model_validate(data).passive_factor == 0.5


@pytest.mark.parametrize("field", ["friction_coefficient", "adhesion_kPa", "passive_coefficient", "cohesion_kPa",
                                   "sliding_safety_factor", "sliding_safety_factor_seismic", "overturning_safety_factor",
                                   "overturning_safety_factor_seismic"])
def test_stability_data_is_required(field: str) -> None:
    data = {key: value for key, value in _oracle("nsr_10")["soil"].items() if key != field}
    with pytest.raises(ValueError, match=field):
        Soil.model_validate(data)
