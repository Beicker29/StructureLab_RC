"""Vigas de gran altura (D-089): los criterios de ACI 9.9 y NSR-10 C.11.7 frente al oráculo independiente."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.model.project import Materials, Member
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_deep_beam.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
         for case in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_deep_beam_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    tolerance = oracle["tolerance_rel"]
    member = Member.model_validate(case["member"])
    checks = station_checks(PROFILES[profile], Materials.model_validate(oracle["materials"]), member, member.stations[0], BARS)
    got = {check.name: check for check in checks if check.name.startswith("Viga alta")}
    expected = {item["name"]: item for item in case["expected"]}
    assert set(got) == set(expected)
    for name, item in expected.items():
        check = got[name]
        assert str(check.status) == item["status"], name
        for field in ("demand", "capacity"):
            if field in item:
                assert getattr(check, field) == pytest.approx(item[field], rel=tolerance), (name, field)
        if "clause" in item:
            assert check.clause == item["clause"], name


def test_sectional_checks_are_kept_for_deep_beams() -> None:
    """Opción B del usuario (D-089): la flexión y el cortante seccionales siguen; la memoria avisa."""
    oracle = _oracle("nsr_10")
    case = next(item for item in oracle["cases"] if item["id"] == "cumple")
    member = Member.model_validate(case["member"])
    names = {check.name for check in station_checks(PROFILES["nsr-10"], Materials.model_validate(oracle["materials"]), member,
                                                    member.stations[0], BARS)}
    assert {"Flexion: resistencia", "Cortante: resistencia", "Viga alta: limite de seccion"} <= names
