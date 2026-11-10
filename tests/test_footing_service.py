"""V3C: verificación geotécnica de zapatas contra el oráculo independiente (D-052)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.base import base_resultant
from structurelab_rc.domain.footing.service import BEARING, CONTACT, service_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.model.footing import Footing, Soil

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MAT = {"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 150.0}, "y": {"designation": "#5", "spacing": 150.0}}


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_footing_service.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


def _footing(case: dict[str, Any], kind: str = "service") -> Footing:
    load = {"case": "S", "kind": kind, **case["load"]}
    return Footing.model_validate({"id": "Z", **case["footing"], "bottom": MAT, "top": None, "loads": [load]})


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_service_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    soil = Soil.model_validate(oracle["soil"])
    footing = _footing(case)
    expected = case["expected"]
    tolerance = oracle["tolerance_rel"]

    resultant = base_resultant(footing, soil, footing.loads[0])
    assert resultant.n / 1e3 == pytest.approx(expected["N_kN"], rel=tolerance)
    assert resultant.mx / 1e6 == pytest.approx(expected["Mx_base_kNm"], rel=tolerance, abs=1e-9)
    assert resultant.my / 1e6 == pytest.approx(expected["My_base_kNm"], rel=tolerance, abs=1e-9)

    checks = {check.name: check for check in service_checks(PROFILES[profile], footing, soil)}
    bearing, contact = checks[BEARING], checks[CONTACT]
    assert str(bearing.status) == expected["bearing"]
    assert str(contact.status) == expected["contact"]
    assert bearing.clause == oracle["bearing_clause"]
    assert (bearing.member, bearing.case) == ("Z", "S")
    if not expected["equilibrium"]:
        assert "Sin equilibrio" in bearing.errors[0].message
        return
    values = dict(bearing.values)
    assert values["ex"] == pytest.approx(expected["ex_mm"], rel=tolerance, abs=1e-9)
    assert values["ey"] == pytest.approx(expected["ey_mm"], rel=tolerance, abs=1e-9)
    assert bearing.demand is not None
    assert bearing.demand * 1e3 == pytest.approx(expected["pmax_kPa"], rel=tolerance)
    assert bearing.capacity is not None
    assert bearing.capacity * 1e3 == pytest.approx(expected["capacity_kPa"], rel=tolerance)
    corners = [values[f"p esquina {name}"] * 1e3 for name in ("-x-y", "+x-y", "+x+y", "-x+y")]
    assert corners == pytest.approx(expected["corners_kPa"], rel=tolerance, abs=1e-6)
    assert contact.capacity == pytest.approx(expected["contact_fraction"], rel=tolerance)


def test_factored_cases_are_not_checked_for_bearing() -> None:
    """El contacto y la presión admisible se verifican solo con los casos de servicio (D-052, punto 5)."""
    oracle = _oracle("nsr_10")
    footing = _footing(oracle["cases"][0], kind="factored")

    checks = service_checks(PROFILES["nsr-10"], footing, Soil.model_validate(oracle["soil"]))

    assert [(check.name, check.status) for check in checks] == [(BEARING, Status.INCOMPLETE)]
    assert "no tiene casos de servicio" in checks[0].errors[0].message
