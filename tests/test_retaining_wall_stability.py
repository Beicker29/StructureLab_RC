"""Estabilidad y presiones del muro en voladizo (D-173, fase A, etapa 2) contra el oráculo independiente
tests/oracles/<perfil>/derived_wall_stability.json, y el ejemplo 2 del manual ACI MNL-17(21) contra sus números."""

import json
from pathlib import Path
from typing import Any

import pytest
from wall_inputs import basis, internal_soil, wall

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.service import BEARING, CONTACT
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.retaining_wall.checks import THRUST, retaining_wall_checks
from structurelab_rc.domain.retaining_wall.stability import stability_checks
from structurelab_rc.domain.retaining_wall.thrust import stability_thrust
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci_318_25": "aci-318-25", "nsr_10": "nsr-10"}
KN_M = 1e3  # kN/m → N por franja de 1 m (las revisiones se reportan por franja de 1 m)
KNM_M = 1e6  # kN·m/m → N·mm por franja de 1 m
KPA = 1e-3  # kPa = 1e-3 MPa


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_wall_stability.json").read_text(encoding="utf-8"))
    return data


def _checks(folder: str, item: dict[str, Any]) -> dict[str, Check]:
    own = RetainingWall.model_validate(wall(**item["wall"], cases=[item["case"]]))
    soil = RetainingSoil.model_validate(internal_soil(**item["soil"]))
    return {check.name: check for check in stability_checks(PROFILES[FOLDERS[folder]], own, soil, stability_thrust(own, soil))}


def _value(check: Check, name: str) -> float:
    return dict(check.values)[name]


CASES = [(folder, item["id"]) for folder in FOLDERS for item in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("folder", "case_id"), CASES)
def test_stability_matches_the_oracle(folder: str, case_id: str) -> None:
    oracle = _oracle(folder)
    item = next(case for case in oracle["cases"] if case["id"] == case_id)
    expected, tolerance = item["expected"], oracle["tolerance_rel"]
    checks = _checks(folder, item)
    bearing, contact, sliding, overturning = (checks[name] for name in (BEARING, CONTACT, SLIDING, OVERTURNING))

    def close(actual: float, value: float, scale: float) -> None:
        assert actual == pytest.approx(value * scale, rel=tolerance, abs=1e-9)

    close(_value(bearing, "N"), expected["N_kN"], KN_M)
    close(_value(bearing, "H"), expected["H_kN"], KN_M)
    close(_value(bearing, "Mr"), expected["Mr_kNm"], KNM_M)
    close(_value(bearing, "Mo"), expected["Mo_kNm"], KNM_M)
    statuses = tuple(str(check.status) for check in (bearing, contact, sliding, overturning))
    assert statuses == (expected["bearing"], expected["contact_status"], expected["sliding"], expected["overturning"])
    if not expected["equilibrium"]:
        assert all("Sin equilibrio" in check.errors[0].message for check in (bearing, contact, sliding, overturning))
        return
    close(_value(bearing, "e"), expected["e_m"], 1e3)
    close(bearing.demand or 0.0, expected["q_max_kPa"], KPA)
    close(_value(bearing, "q puntera"), expected["q_toe_kPa"], KPA)
    close(_value(bearing, "q talon"), expected["q_heel_kPa"], KPA)
    close(contact.capacity or 0.0, expected["contact"], 1.0)
    close(sliding.capacity or 0.0, expected["R_kN"], KN_M)
    close(_value(sliding, "Pp"), expected["Pp_kN"], KN_M)
    close(_value(sliding, "FS"), expected["FS_sliding"], 1.0)
    close(_value(overturning, "FS"), expected["FS_overturning"], 1.0)
    assert bearing.clause == oracle["bearing_clause"] and sliding.clause == oracle["stability_clause"]


def test_the_manual_example_2_numbers() -> None:
    """ACI MNL-17(21), ejemplo 2 con la base de 24 in: ΣP = 15 450 lb/ft, FS = 2.94 y 1.60, q = 2746 y 596 psf."""
    item = next(case for case in _oracle("aci_318_25")["cases"] if case["id"] == "manual-ejemplo-2")
    checks = _checks("aci_318_25", item)
    lb_ft, psf = 4.448222 / 0.3048, 0.0478803e-3  # N/m por lb/ft (por franja de 1 m); psf → MPa
    assert _value(checks[BEARING], "N") == pytest.approx(15450 * lb_ft, rel=2e-3)
    assert _value(checks[OVERTURNING], "FS") == pytest.approx(2.94, abs=0.005)
    assert _value(checks[SLIDING], "FS") == pytest.approx(1.60, abs=0.005)
    assert checks[BEARING].demand == pytest.approx(2746 * psf, rel=2e-3)
    assert _value(checks[BEARING], "q talon") == pytest.approx(596 * psf, rel=5e-3)


def test_the_manual_wall_by_the_production_route() -> None:
    """El ejemplo 2 (talón corto según Das: θ_v = 16.99° < η = 27.5°) por la ruta de producción: Chu sobre AC reproduce
    el manual, sin excepciones (decisión 9); la última verificación dice que la fase A sigue en construcción."""
    item = next(case for case in _oracle("aci_318_25")["cases"] if case["id"] == "manual-ejemplo-2")
    own = RetainingWall.model_validate(wall(**item["wall"], cases=[item["case"]]))
    soil = RetainingSoil.model_validate(internal_soil(**item["soil"]))
    checks = {check.name: check for check in retaining_wall_checks(basis(), own, soil)}
    assert THRUST not in checks
    assert _value(checks[BEARING], "H") == pytest.approx(70.48e3, abs=5.0)  # N por franja de 1 m
    assert _value(checks[BEARING], "N") == pytest.approx(225.5e3, abs=50.0)
    assert (_value(checks[OVERTURNING], "FS"), _value(checks[SLIDING], "FS")) == (pytest.approx(2.94, abs=0.005),
                                                                                  pytest.approx(1.60, abs=0.005))
    assert checks[BEARING].demand == pytest.approx(131.5e-3, abs=0.1e-3)


def test_without_service_cases_the_bearing_is_incomplete() -> None:
    own = RetainingWall.model_validate(wall(cases=[{"case": "1.2D+1.6H", "kind": "factored", "dead_factor": 1.2,
                                                    "fill_factor": 1.6, "earth_factor": 1.6}]))
    soil = RetainingSoil.model_validate(internal_soil())
    checks = stability_checks(PROFILES["aci-318-25"], own, soil, stability_thrust(own, soil))
    assert [(check.name, str(check.status)) for check in checks] == [(BEARING, "INCOMPLETE")]
