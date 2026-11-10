"""V3J.1: zapatas combinadas, modelo, entrada y revisión geotécnica contra el oráculo independiente (D-080)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.checks import COMBINED_STRUCTURAL
from structurelab_rc.domain.footing.service import BEARING, CONTACT, combined_service_checks
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import run_project
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_combined_service.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
         for case in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_combined_geotechnical_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    tolerance = oracle["tolerance_rel"]
    footing = CombinedFooting.model_validate(case["footing"])
    checks = combined_service_checks(PROFILES[profile], footing, Soil.model_validate(oracle["soil"]))
    for name, expected in case["expected"].items():
        own = {check.name: check for check in checks if check.case == name}
        bearing = own[BEARING]
        values = dict(bearing.values)
        assert values["N"] / 1e3 == pytest.approx(expected["N_kN"], rel=tolerance)
        assert values["Mx base"] / 1e6 == pytest.approx(expected["Mx_base_kNm"], rel=tolerance, abs=1e-9)
        assert values["My base"] / 1e6 == pytest.approx(expected["My_base_kNm"], rel=tolerance, abs=1e-9)
        if not expected["equilibrium"]:
            assert {str(own[key].status) for key in (BEARING, CONTACT, SLIDING, OVERTURNING)} == {"FAIL"}
            assert "Sin equilibrio" in bearing.errors[0].message
            continue
        assert str(bearing.status) == expected["bearing"]
        assert bearing.demand is not None and bearing.capacity is not None
        assert bearing.demand * 1e3 == pytest.approx(expected["pmax_kPa"], rel=tolerance)
        assert bearing.capacity * 1e3 == pytest.approx(expected["capacity_kPa"], rel=tolerance)
        corners = [values[f"p esquina {key}"] * 1e3 for key in ("-x-y", "+x-y", "+x+y", "-x+y")]
        assert corners == pytest.approx(expected["corners_kPa"], rel=tolerance, abs=1e-6)
        assert str(own[CONTACT].status) == expected["contact"]
        assert own[CONTACT].capacity == pytest.approx(expected["contact_fraction"], rel=tolerance)
        assert str(own[SLIDING].status) == expected["sliding"]
        assert own[SLIDING].demand / 1e3 == pytest.approx(expected["sliding_demand_kN"], rel=tolerance, abs=1e-9)
        assert own[SLIDING].capacity / 1e3 == pytest.approx(expected["sliding_capacity_kN"], rel=tolerance)
        assert str(own[OVERTURNING].status) == expected["overturning"]
        assert own[OVERTURNING].demand / 1e6 == pytest.approx(expected["overturning_demand_kNm"], rel=tolerance, abs=1e-9)
        assert own[OVERTURNING].capacity / 1e6 == pytest.approx(expected["overturning_capacity_kNm"], rel=tolerance)


def _footing(**changes: Any) -> dict[str, Any]:
    footing = json.loads(json.dumps(_oracle("nsr_10")["cases"][0]["footing"]))
    footing.update(changes)
    return footing


@pytest.mark.parametrize(("change", "message"), [
    ({"lx": 4000.0}, "se sale de la base"),
    ({"columns": "traslapo"}, "se traslapan"),
    ({"columns": "casos distintos"}, "mismos casos de carga"),
    ({"columns": "una sola"}, "at least 2"),
])
def test_combined_footing_input_is_validated(change: dict[str, Any], message: str) -> None:
    footing = _footing()
    columns = footing["columns"]
    if change.get("columns") == "traslapo":
        columns[1]["x"] = columns[0]["x"] + 200.0
    elif change.get("columns") == "casos distintos":
        columns[1]["loads"][0]["case"] = "otro"
    elif change.get("columns") == "una sola":
        footing["columns"] = columns[:1]
    else:
        footing.update(change)
    with pytest.raises(ValueError, match=message):
        CombinedFooting.model_validate(footing)


def test_project_with_a_combined_footing_is_blocked_until_the_structural_checks(tmp_path: Path) -> None:
    """Mientras falten V3J.2 y V3J.3, la zapata combinada queda BLOCKED: nunca PASS sin estar completa."""
    oracle = _oracle("nsr_10")
    project = {"description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
               "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
               "soil": oracle["soil"], "combined_footings": [oracle["cases"][0]["footing"]]}
    path = tmp_path / "combinada.json"
    path.write_text(json.dumps(project), encoding="utf-8")
    _, checks = run_project(path)
    by_name = {check.name: check for check in checks}
    assert by_name["Validacion de entrada"].status is Status.PASS
    assert by_name[BEARING].status is Status.PASS
    assert by_name[COMBINED_STRUCTURAL].status is Status.BLOCKED
