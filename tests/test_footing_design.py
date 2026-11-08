"""V3F: diseño de zapatas por tipologías (D-069). Todo diseño se aprueba con la verificación de V3C y V3D."""

import itertools
import json
import math
import random
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing.grouping import partition
from structurelab_rc.design.footing.typologies import design_typologies, designed_project
from structurelab_rc.design.footing.typology import Context, Typology, column_checks, design_group
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import design_footings, run_project
from structurelab_rc.io.etabs.footings import build_footing_design_project
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.design import FootingDesignProject
from structurelab_rc.model.template import EtabsFootingDesignTemplate
from structurelab_rc.setup import load_engine

BARS = load_engine().bars


def _loads(p: float, m: float) -> list[dict[str, Any]]:
    return [{"case": "D+L", "kind": "service", "dead_factor": 1.0, "live_factor": 1.0, "P_kN": p, "Vx_kN": 0.0, "Vy_kN": 0.0,
             "Mx_kNm": 0.0, "My_kNm": 0.2 * m},
            {"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 1.2, "live_factor": 1.6, "P_kN": 1.4 * p, "Vx_kN": 0.0,
             "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": m}]


def _project(typologies: int = 2, plan_max: float = 4000.0, columns: int = 3) -> dict[str, Any]:
    loads = [(400, 300.0, 20.0), (400, 480.0, 40.0), (500, 750.0, 60.0)][:columns]
    return {
        "description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
        "materials": {"fy": 420.0, "fyt": 420.0, "concrete": "normalweight"},
        "soil": {"allowable_pressure_kPa": 200.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                 "unit_weight_fill_kNm3": 18.0,
                 "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                 "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                 "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                 "overturning_safety_factor_seismic": 1.5},
        "design": {"typologies": typologies, "prices": {"concrete_per_m3": {"21": 500000.0}, "steel_per_kg": 6000.0},
                   "plan_step": 100.0, "plan_max": plan_max, "h_min": 350.0, "h_step": 50.0, "h_max": 900.0, "cover": 75.0,
                   "fill_height": 800.0, "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
                   "bars": ["#4", "#5"], "spacing_step": 25.0, "end": "straight", "dowel_bars": ["#5"]},
        "columns": [{"id": f"C{index}", "cx": float(side), "cy": float(side), "loads": _loads(p, m)}
                    for index, (side, p, m) in enumerate(loads, start=1)],
    }


def _context(data: dict[str, Any]) -> Context:
    project = FootingDesignProject.model_validate(data)
    return Context(project, PROFILES[project.profile], BARS)


@pytest.mark.parametrize("seed", range(5))
def test_partition_matches_brute_force(seed: int) -> None:
    rng = random.Random(seed)
    count, groups = 6, 3
    table = {(i, j): rng.uniform(1, 10) * (j - i + 1) for i in range(count) for j in range(i, count)}
    total, segments = partition(count, groups, lambda i, j: table[(i, j)])
    best = math.inf
    for cuts in itertools.combinations(range(1, count), groups - 1):
        bounds = (0, *cuts, count)
        best = min(best, sum(table[(bounds[k], bounds[k + 1] - 1)] for k in range(groups)))
    assert total == pytest.approx(best)
    assert sum(end - start + 1 for start, end in segments) == count
    assert segments[0][0] == 0 and segments[-1][1] == count - 1


def test_partition_reports_infeasible() -> None:
    assert partition(3, 2, lambda i, j: math.inf) == (math.inf, [])


def test_designed_typologies_cover_every_column_and_verify(tmp_path: Path) -> None:
    ctx = _context(_project())
    result = design_typologies(ctx)
    assert result.fc == 21.0
    assert len(result.typologies) == 2
    assigned = [column for typology in result.typologies for column in typology.columns]
    assert sorted(assigned) == ["C1", "C2", "C3"]
    assert result.cost == pytest.approx(sum(typology.design.cost for typology in result.typologies))
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(designed_project(ctx, result)), encoding="utf-8")
    _, checks = run_project(path)
    assert {str(check.status) for check in checks} == {"PASS"}


def test_parallel_design_gives_the_same_result() -> None:
    ctx = _context(_project(typologies=2, columns=3))
    assert design_typologies(ctx, workers=2) == design_typologies(ctx, workers=1)


def test_design_takes_the_least_thickness_for_its_plan_and_mats() -> None:
    ctx = _context(_project(typologies=1, columns=1))
    column = ctx.project.columns[0]
    design = design_group(ctx, [column], 21.0)
    assert design is not None
    t = design.typology
    if t.h - ctx.design.h_step >= ctx.design.h_min:
        thinner = Typology(t.fc, t.lx, t.ly, t.h - ctx.design.h_step, t.bottom, t.top)
        failures, _ = column_checks(ctx, thinner, column)
        assert failures


def test_no_solution_within_the_limits_is_a_failure(tmp_path: Path) -> None:
    path = tmp_path / "diseno.json"
    path.write_text(json.dumps(_project(typologies=1, plan_max=900.0)), encoding="utf-8")
    project, result, check = design_footings(path)
    assert project is None and result is not None
    assert check.status is Status.FAIL
    assert "Sin solucion" in check.errors[0].message


def test_cli_writes_the_designed_project(tmp_path: Path) -> None:
    source = tmp_path / "diseno.json"
    source.write_text(json.dumps(_project(typologies=1, columns=2)), encoding="utf-8")
    assert main(["design-footings", str(source), "--output", str(tmp_path / "salida")]) == 0
    summary = json.loads((tmp_path / "salida" / "tipologias.json").read_text(encoding="utf-8"))
    assert summary["fc [MPa]"] == 21.0 and len(summary["typologies"]) == 1
    assert (tmp_path / "salida" / "proyecto.json").exists()


def test_etabs_design_template_builds_a_design_project() -> None:
    headers = ("Story", "Label", "Unique Name", "Output Case", "Case Type", "Step Type", "FX", "FY", "FZ", "MX", "MY", "MZ")
    units = {"FX": "kN", "FY": "kN", "FZ": "kN", "MX": "kN-m", "MY": "kN-m", "MZ": "kN-m"}

    def row(unique: str, label: str, case: str, fz: float) -> dict[str, str]:
        return {"Story": "Base", "Label": label, "Unique Name": unique, "Output Case": case, "Case Type": "Combination",
                "Step Type": "", "FX": "0", "FY": "0", "FZ": str(fz), "MX": "0", "MY": "0", "MZ": "0"}

    service = Table(headers, units, (row("10", "A1", "S", 500.0), row("11", "A2", "S", 700.0)))
    factored = Table(headers, units, (row("10", "A1", "U", 700.0), row("11", "A2", "U", 950.0)))
    data = _project()
    template = EtabsFootingDesignTemplate.model_validate({
        "description": "t", "profile": "nsr-10", "seismic": data["seismic"], "materials": data["materials"], "soil": data["soil"],
        "load_factors": {"S": {"dead": 1.0, "live": 1.0}, "U": {"dead": 1.2, "live": 1.6}}, "design": data["design"],
        "columns": [{"etabs_unique_names": ["10", "11"], "cx": 400.0, "cy": 450.0}]})
    project, summary = build_footing_design_project(template, service, factored)
    design = FootingDesignProject.model_validate(project)
    assert [column.id for column in design.columns] == ["A1", "A2"]
    assert (design.columns[1].cy, design.columns[1].loads[1].p) == (450.0, 950e3)
    assert summary.footings == 2
