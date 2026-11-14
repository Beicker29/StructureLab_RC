"""Cabezales sobre pilotes (D-138): contra el oráculo independiente y reglas propias de cada perfil."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.pile_cap.checks import cap_face_moments, pile_cap_checks
from structurelab_rc.domain.pile_cap.reactions import cap_cases
from structurelab_rc.domain.status import Status
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_pile_cap.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, index, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for index, case in enumerate(_oracle(folder)["cases"])]


def _setup(profile: str, index: int) -> tuple[dict[str, Any], dict[str, Any], Basis, PileCap, PileCapSoil]:
    oracle = _oracle(FOLDERS[profile])
    case = oracle["cases"][index]
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, "")
    return oracle, case, basis, PileCap.model_validate(case["cap"]), PileCapSoil.model_validate(case["soil"])


@pytest.mark.parametrize(("profile", "index"), CASES)
def test_reactions_and_face_moments_match_oracle(profile: str, index: int) -> None:
    oracle, case, basis, cap, weights = _setup(profile, index)
    tolerance = oracle["tolerance_rel"]
    got = {item.case: item for item in cap_cases(cap, weights)}
    for expected in case["reactions"]:
        forces = got[expected["case"]].forces
        assert forces.reactions == pytest.approx(expected["R"], rel=tolerance), expected["case"]
        assert forces.spread == pytest.approx(expected["dR"], rel=tolerance, abs=1e-9), expected["case"]
    moments = {(item.case, direction): pair for item in cap_face_moments(basis, cap, weights) for direction, pair in item.moments.items()}
    for expected in case["moments"]:
        pair = moments[(expected["case"], expected["direction"])]
        assert pair == pytest.approx((expected["plus"], expected["minus"]), rel=tolerance, abs=1.0), expected


@pytest.mark.parametrize(("profile", "index"), CASES)
def test_checks_match_oracle(profile: str, index: int) -> None:
    oracle, case, basis, cap, weights = _setup(profile, index)
    tolerance = oracle["tolerance_rel"]
    checks = pile_cap_checks(basis, cap, weights)
    for expected in case["minimum"]:
        check = next(item for item in checks if item.name == f"Acero minimo malla inferior (barras {expected['direction']})")
        assert (check.demand, check.capacity) == pytest.approx((expected["required"], expected["provided"]), rel=tolerance)
    names = {item["name"] for item in case["checks"]}
    for name, load_case in {(item["name"], item["case"]) for item in case["checks"]}:
        wanted = sorted((item["demand"], item["capacity"]) for item in case["checks"] if (item["name"], item["case"]) == (name, load_case))
        found = sorted((item.demand or 0.0, item.capacity or 0.0) for item in checks if (item.name, item.case) == (name, load_case))
        assert len(found) == len(wanted), (name, load_case)
        flat = [value for pair in found for value in pair]
        assert flat == pytest.approx([value for pair in wanted for value in pair], rel=tolerance), (name, load_case)
    # El oráculo cubre todas las verificaciones de esos tipos que el programa produce.
    for check in checks:
        if check.name in names and check.name != "Punzonamiento del pilote":
            assert any((item["name"], item["case"]) == (check.name, check.case) for item in case["checks"]), (check.name, check.case)


def _cap(index: int = 0, **changes: Any) -> dict[str, Any]:
    case: dict[str, Any] = _oracle("aci_318_25")["cases"][index]["cap"]
    return {**case, **changes}


def test_aci_mislocation_below_75_mm_fails_and_nsr_does_not_check_it() -> None:
    oracle = _oracle("aci_318_25")
    weights = PileCapSoil.model_validate(oracle["cases"][0]["soil"])
    cap = PileCap.model_validate(_cap(mislocation_mm=50.0))
    for profile, expected in (("aci-318-25", Status.FAIL), ("nsr-10", None)):
        basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, "")
        found = [check for check in pile_cap_checks(basis, cap, weights) if check.name == "Cabezal: tolerancia de mala ubicacion"]
        assert [check.status for check in found] == ([] if expected is None else [expected])


def test_missing_tension_capacity_is_incomplete() -> None:
    oracle = _oracle("nsr_10")
    loads = [{**load, "P_kN": 50.0, "My_kNm": 600.0} for load in _cap()["loads"]]
    cap = PileCap.model_validate(_cap(loads=loads))
    basis = Basis(PROFILES["nsr-10"], Materials.model_validate(oracle["materials"]), BARS, "")
    soil = PileCapSoil.model_validate({**oracle["cases"][0]["soil"], "pile_capacity_tension_kN": None})
    tension = [check for check in pile_cap_checks(basis, cap, soil) if check.name == "Presion admisible del pilote: traccion"]
    assert tension and all(check.status is Status.INCOMPLETE for check in tension)


def test_negative_moment_without_top_mat_fails() -> None:
    """El cabezal no admite concreto simple (ACI 14.1.4, NSR-10 C.22.2.1)."""
    oracle = _oracle("aci_318_25")
    cap = PileCap.model_validate(_cap(1, top=None))  # B: el peso fuera de las caras X da momento negativo
    basis = Basis(PROFILES["aci-318-25"], Materials.model_validate(oracle["materials"]), BARS, "")
    plain = [check for check in pile_cap_checks(basis, cap, PileCapSoil.model_validate(oracle["cases"][0]["soil"]))
             if check.name.startswith("Flexion malla superior")]
    assert plain and all(check.status is Status.FAIL and check.clause == "14.1.4" for check in plain)


@pytest.mark.parametrize(("changes", "message"), [
    ({"bottom_cover": 75.0}, "bottom_cover debe ser mayor que el empotramiento"),
    ({"loads": []}, "necesita las cargas de la columna"),
    ({"reactions_include_weight": True}, "solo se declara con las cargas de los pilotes"),
    ({"piles": [{"id": "P1", "x": 1000.0, "y": 0.0}]}, "queda fuera del cabezal"),
])
def test_invalid_caps_are_rejected(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        PileCap.model_validate(_cap(**changes))
