import copy
import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.nominal_flexure import nominal_flexure
from structurelab_rc.domain.check import check_from_errors
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import validate_file
from structurelab_rc.errors import ErrorCode, StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.loader import ProjectLoadError, load_project
from structurelab_rc.model.project import Materials, Project, Section
from structurelab_rc.setup import load_engine

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*/*.json"))
BARS = load_engine().bars
BASE: dict[str, Any] = {
    "description": "Prueba",
    "profile": "nsr-10",
    "seismic": {"level": "DMO", "justification": "Declarado para la prueba"},
    "materials": {"fc": 28.0, "fy": 420.0},
    "members": [
        {
            "id": "V1",
            "length": 6000.0,
            "section": {"bw": 300.0, "h": 500.0},
            "stations": [
                {
                    "x": 3000.0,
                    "layout": {"layers": [{"designation": "#8", "count": 3, "depth": 440.0}]},
                    "demands": {"Mu_kNm": 180.0, "Vu_kN": 40.0, "Tu_kNm": 0.0},
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


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: f"{path.parent.name}-{path.stem}")
def test_examples_load_and_validate(path: Path) -> None:
    assert validate_file(path).status is Status.PASS


def test_there_are_examples_for_both_profiles() -> None:
    assert {path.parent.name for path in EXAMPLES} >= {"aci_318_25", "nsr_10"}


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
    assert _validate(_project(materials={"fc": 14.0, "fy": 420.0}))[0] is Status.FAIL


def test_missing_demand_is_incomplete_and_not_assumed() -> None:
    status, errors = _validate(_project(members=_member_with(demands={"Mu_kNm": 180.0, "Vu_kN": 40.0})))
    assert status is Status.INCOMPLETE
    assert errors[0].code is ErrorCode.INCOMPLETE
    assert "Tu" in errors[0].message


def test_unknown_bar_is_rejected() -> None:
    members = _member_with(layout={"layers": [{"designation": "#99", "count": 1, "depth": 440.0}]})
    assert _validate(_project(members=members))[0] is Status.FAIL


def test_layer_outside_the_section_is_rejected() -> None:
    members = _member_with(layout={"layers": [{"designation": "#8", "count": 1, "depth": 500.0}]})
    assert _validate(_project(members=members))[0] is Status.FAIL


def test_station_outside_the_member_is_rejected() -> None:
    assert _validate(_project(members=_member_with(x=6000.1)))[0] is Status.FAIL


@pytest.mark.parametrize(
    "section",
    [
        {"bw": 300.0, "h": 500.0, "bf": 800.0},
        {"bw": 300.0, "h": 500.0, "hf": 100.0},
        {"bw": 300.0, "h": 500.0, "bf": 200.0, "hf": 100.0},
        {"bw": 300.0, "h": 500.0, "bf": 800.0, "hf": 500.0},
    ],
)
def test_inconsistent_t_sections_are_rejected(section: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"bf|hf"):
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
        Materials(fc=14.0, fy=420.0),
        Section(bw=300.0, h=500.0),
        (SteelLayer(440.0, 1530.0),),
        top_in_compression=True,
    )
    assert isinstance(result, StructuredError)
    assert result.code is ErrorCode.INVALID_INPUT
