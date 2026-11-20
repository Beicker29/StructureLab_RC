"""Diseño de cabezales sobre pilotes (D-141): arreglos y cota de pilotes contra el oráculo independiente
(tests/oracles/derive_pile_cap_design.py), búsqueda de menor costo y proyecto diseñado que la verificación aprueba."""

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import element_of, frozen, frozen_all, profile_of
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.pile_cap import search
from structurelab_rc.design.pile_cap.patterns import arrangements
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import design_pile_caps_file, run_plan
from structurelab_rc.model.loader import validate_input
from structurelab_rc.model.pile_cap import PileCap
from structurelab_rc.model.pile_cap_design import PileCapDesignProject
from structurelab_rc.model.project import Project
from structurelab_rc.setup import load_engine

ROOT = Path(__file__).parent.parent
ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
EXAMPLES = [path for path in frozen_all("diseno_*.json") if element_of(path) == "cabezales" and not path.stem.endswith("_etabs")]
TEMPLATES = [path for path in frozen_all("diseno_*_etabs.json") if element_of(path) == "cabezales"]


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_pile_cap_design.json").read_text(encoding="utf-8"))
    return data


def _example(folder: str, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(frozen(folder, "cabezales", name).read_text(encoding="utf-8"))
    return data


def _context(data: dict[str, Any]) -> search.Context:
    project = PileCapDesignProject.model_validate(data)
    return search.Context(project, PROFILES[project.profile], load_engine().bars)


@pytest.mark.parametrize("folder", FOLDERS.values())
@pytest.mark.parametrize("count", range(2, 14))
def test_arrangements_match_oracle(folder: str, count: int) -> None:
    oracle = _oracle(folder)
    expected = oracle["arrangements"][str(count)]
    found = arrangements(count, oracle["spacing"], oracle["edge"])
    assert [item.name for item in found] == [item["name"] for item in expected]
    for item, wanted in zip(found, expected, strict=True):
        assert sorted([x, y] for x, y in item.piles) == wanted["piles"]
        assert (item.lx, item.ly) == pytest.approx((wanted["lx"], wanted["ly"]))
        assert list(item.column) == pytest.approx(wanted["column"])
        assert [clip.model_dump() for clip in item.clips] == wanted["clips"]
        closest = min(math.dist(p, q) for index, p in enumerate(item.piles) for q in item.piles[index + 1 :])
        assert closest >= oracle["spacing"] - 1e-9


@pytest.mark.parametrize("folder", FOLDERS.values())
def test_start_count_matches_oracle(folder: str) -> None:
    oracle = _oracle(folder)["start_count"]
    data = _example(folder, "diseno_cabezal_columna.json")
    data["soil"] |= {"pile_capacity_compression_kN": oracle["capacity_kN"], "group_efficiency": oracle["efficiency"],
                     "seismic_capacity_factor": oracle["seismic_factor"]}
    template = data["caps"][0]["loads"][0]
    data["caps"][0]["loads"] = [{**template, "case": f"S{index}", "kind": "service", "seismic": item["seismic"], "P_kN": item["P_kN"]}
                                for index, item in enumerate(oracle["loads"])]
    ctx = _context(data)
    assert search._start_count(ctx, ctx.project.caps[0]) == oracle["count"]


@pytest.mark.parametrize("folder", FOLDERS.values())
def test_concrete_volume_matches_oracle(folder: str) -> None:
    oracle = _oracle(folder)["cost"]
    data = _example(folder, "diseno_cabezal_columna.json")
    data["pile_cap_design"]["pedestal_height"] = oracle["pedestal"]
    ctx = _context(data)
    clips = [{"corner": corner, "along_x": ax, "along_y": ay} for corner, (ax, ay) in zip(("-x+y", "+x+y"), oracle["clips"], strict=True)]
    base = _example(folder, "cabezal_tres_pilotes.json")["pile_caps"][0]
    cap = PileCap.model_validate({**base, "lx": oracle["lx"], "ly": oracle["ly"], "h": oracle["h"], "clipped_corners": clips})
    assert search._concrete(ctx, cap) == pytest.approx(oracle["concrete_m3"], rel=1e-12)
    prices = oracle["prices"]
    cost = oracle["concrete_m3"] * prices["concrete"] + oracle["steel_kg"] * prices["steel"] + oracle["piles"] * prices["pile"]
    assert cost == pytest.approx(oracle["cost"], rel=1e-12)


@pytest.fixture(scope="module", params=[str(path.relative_to(ROOT).as_posix()) for path in EXAMPLES])
def designed(request: pytest.FixtureRequest) -> tuple[str, dict[str, Any], search.DesignResult]:
    path = ROOT / request.param
    project, result, check = design_pile_caps_file(path)
    assert check.status is Status.PASS, check
    assert project is not None and result is not None
    return request.param, project, result


def test_designed_project_passes_verification(designed: tuple[str, dict[str, Any], search.DesignResult], tmp_path: Path) -> None:
    from structurelab_rc.engine import verify_file

    name, project, _ = designed
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    checks = verify_file(path)
    failing = [(check.name, check.status, check.note) for check in checks if check.status is not Status.PASS]
    assert not failing, (name, failing)


def test_best_is_the_cheapest_trial(designed: tuple[str, dict[str, Any], search.DesignResult]) -> None:
    _, _, result = designed
    totals = {fc: sum(item.best.cost for item in designs if item.best is not None) for fc, designs in result.options
              if all(item.best is not None for item in designs)}
    assert result.fc == min(totals, key=lambda fc: totals[fc])
    for item in result.caps:
        assert item.best is not None
        solved = [trial.solution.cost for trial in item.trials if trial.solution is not None]
        assert item.best.cost == min(solved)
        assert all(trial.failure for trial in item.trials if trial.solution is None)


def test_designed_project_loads_and_keeps_declared_piles(designed: tuple[str, dict[str, Any], search.DesignResult]) -> None:
    name, project, result = designed
    loaded = validate_input(project, Project)
    assert loaded.materials.fc == result.fc
    source = PileCapDesignProject.model_validate(json.loads((ROOT / name).read_text(encoding="utf-8")))
    for cap, declared in zip(loaded.pile_caps, source.caps, strict=True):
        if declared.loads_from != "piles":
            continue
        column = (cap.columns[0].offset_x, cap.columns[0].offset_y)
        for pile, given in zip(cap.piles, declared.piles, strict=True):
            assert pile.id == given.id
            assert (pile.x - column[0], pile.y - column[1]) == pytest.approx((given.x, given.y))


def test_summary_lists_every_trial(designed: tuple[str, dict[str, Any], search.DesignResult]) -> None:
    _, _, result = designed
    data = search.summary(result)
    assert data["fc [MPa]"] == result.fc
    assert len(data["options"]) == len(result.options)
    for option, (_, designs) in zip(data["options"], result.options, strict=True):
        for cap, item in zip(option["caps"], designs, strict=True):
            assert len(cap["trials"]) == len(item.trials)


def test_run_plan_detects_pile_cap_design() -> None:
    assert all(run_plan(path).kind == "pile_cap_design" for path in EXAMPLES)


def test_column_cap_rejects_declared_piles() -> None:
    data = _example("aci_318_25", "diseno_cabezal_columna.json")
    bad = copy.deepcopy(data)
    bad["caps"][0]["piles"] = [{"id": "P1", "x": 0.0, "y": 0.0}]
    with pytest.raises(ValidationError, match="loads_from = column"):
        PileCapDesignProject.model_validate(bad)
    bad = copy.deepcopy(data)
    bad["pile_cap_design"]["pile_spacing"] = 300.0
    with pytest.raises(ValidationError, match="pile_spacing"):
        PileCapDesignProject.model_validate(bad)


def test_pile_cap_without_solution_reports_why(tmp_path: Path) -> None:
    data = _example("aci_318_25", "diseno_cabezal_columna.json")
    data["pile_cap_design"] |= {"max_piles": 3, "h_max": 700.0}
    path = tmp_path / "diseno.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    project, result, check = design_pile_caps_file(path)
    assert project is None and result is not None and result.fc is None
    assert check.status is Status.FAIL
    assert "Sin solucion" in check.errors[0].message


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda path: f"{profile_of(path)}-{path.stem}")
def test_etabs_template_imports_and_designs(path: Path, tmp_path: Path) -> None:
    """Plantilla de diseño de ETABS (D-141): importa las cargas de la columna o de los pilotes, diseña y el proyecto
    diseñado pasa la verificación; con la tabla de coordenadas, la columna queda ubicada."""
    from structurelab_rc.engine import import_etabs_footings, verify_file

    plan = run_plan(path)
    assert plan.kind == "etabs_pile_cap_design"
    imported, summary, check = import_etabs_footings(plan.service, plan.factored, path, plan.locations, plan.combinations)
    assert check.status is Status.PASS, check
    assert imported is not None and summary is not None and summary.factored_cases
    source = tmp_path / "diseno.json"
    source.write_text(json.dumps(imported, ensure_ascii=False), encoding="utf-8")
    project, result, check = design_pile_caps_file(source)
    assert check.status is Status.PASS, check
    assert project is not None and result is not None
    assert all(("location" in cap) == (plan.locations is not None) for cap in project["pile_caps"])
    designed = tmp_path / "proyecto.json"
    designed.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    assert all(item.status is Status.PASS for item in verify_file(designed))


def test_design_template_rejects_more_than_16_piles() -> None:
    """D-152: el alcance es de hasta 16 pilotes por cabezal; max_piles no puede pasar de 16."""
    from pydantic import ValidationError

    data = _example("nsr_10", "diseno_cabezal_columna.json")
    data["pile_cap_design"] = {**data["pile_cap_design"], "max_piles": 17}
    with pytest.raises(ValidationError, match="less than or equal to 16"):
        PileCapDesignProject.model_validate(data)
