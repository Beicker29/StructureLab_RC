"""Zapata combinada en T invertida (D-093) frente al oráculo independiente: viga larga en T volteada, aletas, ala a
tracción y aplastamiento sobre la viga."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.combined_beam import long_beam_checks
from structurelab_rc.domain.footing.inverted_t import inverted_t_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil
from structurelab_rc.model.project import Materials, Project
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_inverted_t.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
         for case in _oracle(folder)["cases"]]


def _checks(profile: str, footing: CombinedFooting, oracle: dict[str, Any]) -> list[Check]:
    soil = Soil.model_validate(oracle["soil"])
    cases, failures = combined_factored_cases(footing, soil)
    assert not failures
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    return [*long_beam_checks(basis, footing, soil, cases), *inverted_t_checks(basis, footing, soil, cases)]


def _matches(check: Check, item: dict[str, Any]) -> bool:
    if check.name != item["name"]:
        return False
    if "case" in item and check.case != item["case"]:
        return False
    if "z_mm" in item and (check.z is None or round(check.z, 3) != round(item["z_mm"], 3)):
        return False
    return "note_prefix" not in item or check.note.startswith(item["note_prefix"])


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_inverted_t_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    tolerance = oracle["tolerance_rel"]
    checks = _checks(profile, CombinedFooting.model_validate(case["footing"]), oracle)
    # Las estaciones de la viga larga: las mismas que el oráculo para cada verificación que este deriva (en los casos
    # solo de aletas, el oráculo no deriva la viga, D-114).
    names = {item["name"] for item in case["expected"]["checks"] if "z_mm" in item}
    got = {(check.name, check.case, round(check.z, 3)) for check in checks if check.name in names and check.z is not None}
    wanted = {(item["name"], item["case"], round(item["z_mm"], 3)) for item in case["expected"]["checks"] if "z_mm" in item}
    assert got == wanted or case.get("flange_only")
    for item in case["expected"]["checks"]:
        found = [check for check in checks if _matches(check, item)]
        assert len(found) == 1, item
        check = found[0]
        assert str(check.status) == item["status"], item
        for field in ("demand", "capacity"):
            if field in item:
                assert getattr(check, field) == pytest.approx(item[field], rel=tolerance, abs=0.1), (item, field)


def test_isolated_flange_needs_half_the_web_width() -> None:
    """ACI 6.3.2.2, NSR-10 C.8.12.4: el ala cuenta (≤ 4bw) solo si su espesor es ≥ 0.5bw."""
    for profile in PROFILES.values():
        assert profile.flexure.isolated_flange_width(600.0, 300.0) == pytest.approx(2400.0)
        assert profile.flexure.isolated_flange_width(600.0, 299.0) is None


def test_inverted_t_input_is_validated() -> None:
    footing = _oracle("nsr_10")["cases"][0]["footing"]
    beam = footing["beam"]
    for change, message in (({"h": 950.0}, "más alta que la zarpa"),
                            ({"beam": {**beam, "width": 400.0}}, "se sale del ancho de la viga"),
                            # D-106: el refuerzo de la viga va en beam (capas y estribos), no en la zapata.
                            ({"stirrups": {"designation": "#4", "legs": 2, "spacing": 150.0, "closed": True}},
                             "declara el refuerzo de la viga en beam"),
                            ({"beam": {key: value for key, value in beam.items() if key != "end"}}, "end"),
                            ({"beam": {**beam, "bottom_width": 500.0}}, "no puede ser menor que el ancho del alma")):
        with pytest.raises(ValidationError, match=message):
            CombinedFooting.model_validate({**footing, **change})
    # D-114: top es la malla superior de la zarpa (como bottom) y se acepta en la T.
    top = {"first": "y", "end": "straight", "x": {"designation": "#4", "spacing": 300.0}, "y": {"designation": "#5", "spacing": 200.0}}
    assert CombinedFooting.model_validate({**footing, "top": top}).top is not None


def test_bottom_layer_must_stay_within_its_covered_width() -> None:
    """D-106: la capa inferior de la viga solo puede salir del alma hasta bottom_width (o el ala efectiva)."""
    data = json.loads((Path(__file__).parent.parent / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_combinada.json")
                      .read_text(encoding="utf-8"))
    footing = _oracle("nsr_10")["cases"][0]["footing"]
    narrow = {**footing, "beam": {**footing["beam"], "bottom_width": 1200.0}}
    data["combined_footings"] = [{**narrow, "principal_direction": "x"}]
    check = validate_project(Project.model_validate(data), BARS)
    assert check.status is not Status.PASS
    assert any("fuera del ancho cubierto" in error.message for error in check.errors)
