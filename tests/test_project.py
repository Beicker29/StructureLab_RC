import copy
import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import nominal_flexure
from structurelab_rc.domain.check import check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import validate_file
from structurelab_rc.errors import ErrorCode, StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.loader import ProjectLoadError, load_project
from structurelab_rc.model.project import Demands, Materials, Project, Section
from structurelab_rc.setup import load_engine

EXAMPLES = sorted(path for path in (Path(__file__).parent.parent / "examples").glob("*/*/*.json") if path.parts[-3] != "etabs")
BARS = load_engine().bars
BASE: dict[str, Any] = {
    "description": "Prueba",
    "profile": "nsr-10",
    "seismic": {"level": "DMO", "justification": "Declarado para la prueba"},
    "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"},
    "members": [
        {
            "id": "V1",
            "type": "beam",
            "length": 6000.0,
            "section": {"bw": 300.0, "h": 500.0, "cover": 40.0},
            "stations": [
                {
                    "z": 3000.0,
                    "layout": {"layers": [{"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}], "stirrups": None},
                    "demands": {"Pu_kN": 0.0, "Mu_kNm": 180.0, "M2_kNm": 0.0, "Vu_kN": 40.0, "V3_kN": 0.0, "Tu_kNm": 0.0},
                }
            ],
        }
    ],
}


def _project(**changes: Any) -> Project:
    return Project.model_validate(BASE | changes)


def _member_with(**changes: Any) -> list[dict[str, Any]]:
    member = copy.deepcopy(BASE["members"][0])
    member["stations"][0] |= changes
    return [member]


def _validate(project: Project) -> tuple[Status, list[StructuredError]]:
    check = validate_project(project, BARS)
    return check.status, list(check.errors)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: f"{path.parts[-3]}-{path.parent.name}-{path.stem}")
def test_examples_load_and_validate(path: Path) -> None:
    assert validate_file(path).status is Status.PASS


def test_there_are_examples_for_both_profiles() -> None:
    assert {(path.parts[-3], path.parent.name) for path in EXAMPLES} >= {
        (profile, element) for profile in ("aci_318_25", "nsr_10") for element in ("vigas", "zapatas")}


def test_demands_are_converted_to_n_and_nmm() -> None:
    demands = _project().members[0].stations[0].demands
    assert demands.mu == pytest.approx(180e6)
    assert demands.vu == pytest.approx(40e3)
    assert demands.tu == 0.0


def test_a_consistent_project_passes() -> None:
    assert _validate(_project()) == (Status.PASS, [])


def test_seismic_level_of_the_other_profile_is_rejected() -> None:
    status, errors = _validate(_project(seismic={"level": "special", "justification": "Declarado"}))
    assert status is Status.FAIL
    assert "special" in errors[0].message


def test_each_profile_accepts_its_own_vocabulary() -> None:
    project = _project(profile="aci-318-25", seismic={"level": "special", "justification": "Declarado"})
    assert _validate(project)[0] is Status.PASS


def test_unknown_profile_is_rejected() -> None:
    assert _validate(_project(profile="aci-318-19"))[0] is Status.FAIL


def test_concrete_outside_the_beta1_table_is_rejected() -> None:
    assert _validate(_project(materials={"fc": 14.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"}))[0] is Status.FAIL


def test_missing_demand_is_incomplete_and_not_assumed() -> None:
    demands = {"Pu_kN": 0.0, "Mu_kNm": 180.0, "M2_kNm": 0.0, "Vu_kN": 40.0, "V3_kN": 0.0}
    status, errors = _validate(_project(members=_member_with(demands=demands)))
    assert status is Status.INCOMPLETE
    assert errors[0].code is ErrorCode.INCOMPLETE
    assert "Tu" in errors[0].message


def test_unknown_bar_is_rejected() -> None:
    members = _member_with(layout={"layers": [{"bars": ["#99"], "depth": 440.0, "role": "flexure"}], "stirrups": None})
    assert _validate(_project(members=members))[0] is Status.FAIL


def test_layer_outside_the_section_is_rejected() -> None:
    members = _member_with(layout={"layers": [{"bars": ["#8"], "depth": 500.0, "role": "flexure"}], "stirrups": None})
    assert _validate(_project(members=members))[0] is Status.FAIL


def test_station_outside_the_member_is_rejected() -> None:
    assert _validate(_project(members=_member_with(z=6000.1)))[0] is Status.FAIL


@pytest.mark.parametrize(
    "section",
    [
        {"bw": 300.0, "h": 500.0, "cover": 40.0, "overhang_x_neg": 250.0, "overhang_x_pos": 250.0},
        {"bw": 300.0, "h": 500.0, "cover": 40.0, "hf": 100.0},
        {"bw": 300.0, "h": 500.0, "cover": 40.0, "hf": 100.0, "overhang_x_pos": 250.0},
        {"bw": 300.0, "h": 500.0, "cover": 40.0, "hf": 100.0, "overhang_x_neg": 0.0, "overhang_x_pos": 0.0},
        {"bw": 300.0, "h": 500.0, "cover": 40.0, "hf": 500.0, "overhang_x_neg": 250.0, "overhang_x_pos": 250.0},
    ],
)
def test_inconsistent_t_sections_are_rejected(section: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"hf|saliente|overhang"):
        Section.model_validate(section)


def test_load_errors_are_structured(tmp_path: Path) -> None:
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(BASE | {"seismic": {"level": "DMO"}}), encoding="utf-8")
    with pytest.raises(ProjectLoadError) as error:
        load_project(path)
    assert error.value.errors[0].code is ErrorCode.INVALID_INPUT
    assert error.value.errors[0].details == {"location": "seismic.justification"}


def test_invalid_json_and_missing_file_fail_without_a_traceback(tmp_path: Path) -> None:
    broken = tmp_path / "roto.json"
    broken.write_text("{", encoding="utf-8")
    assert validate_file(broken).status is Status.FAIL
    assert validate_file(tmp_path / "no_existe.json").status is Status.FAIL


def test_check_status_comes_from_its_errors() -> None:
    assert check_from_errors("x", []).status is Status.PASS
    assert check_from_errors("x", [blocked("b")]).status is Status.BLOCKED
    assert check_from_errors("x", [incomplete("i"), blocked("b")]).status is Status.INCOMPLETE
    assert check_from_errors("x", [invalid_input("v"), incomplete("i")]).status is Status.FAIL


def test_nominal_flexure_rejects_concrete_outside_the_table() -> None:
    result = nominal_flexure(
        PROFILES["nsr-10"],
        Materials(fc=14.0, fy=420.0, fyt=420.0, concrete="normalweight"),
        Section(bw=300.0, h=500.0, cover=40.0),
        (SteelLayer(440.0, 1530.0),),
        Demands.model_validate({"Mu_kNm": 100.0, "M2_kNm": 0.0, "Pu_kN": 0.0}),
    )
    assert isinstance(result, StructuredError)
    assert result.code is ErrorCode.INVALID_INPUT
