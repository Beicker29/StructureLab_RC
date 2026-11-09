"""MILP de tipologías (E2, D-075): coincidencia con una fuerza bruta independiente y el diseño con method = milp."""

import itertools
import json
import random
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing import assignment
from structurelab_rc.design.footing.assignment import INFEASIBLE, OPTIMAL, assign
from structurelab_rc.design.footing.typologies import design_typologies, designed_project
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import design_footings, run_project
from structurelab_rc.model.design import FootingDesignProject
from structurelab_rc.setup import load_engine

pytest.importorskip("highspy")

Matrix = list[list[int | None]]


def _brute(cost: Matrix, steel: Matrix, groups: int) -> tuple[int, int, int] | None:
    """Mínimo lexicográfico (costo, acero, Σ j) entre las asignaciones con exactamente `groups` candidatos distintos;
    independiente del modelo: enumera todas las asignaciones."""
    best = None
    for choice in itertools.product(range(len(cost[0])), repeat=len(cost)):
        if len(set(choice)) != groups or any(cost[i][j] is None for i, j in enumerate(choice)):
            continue
        key = (sum(cost[i][j] or 0 for i, j in enumerate(choice)), sum(steel[i][j] or 0 for i, j in enumerate(choice)), sum(choice))
        best = key if best is None or key < best else best
    return best


def _random(seed: int, columns: int, candidates: int) -> tuple[Matrix, Matrix]:
    rng = random.Random(seed)
    cost: Matrix = [[None if rng.random() < 0.35 else rng.randint(10, 40) for _ in range(candidates)] for _ in range(columns)]
    steel: Matrix = [[None if value is None else rng.randint(1, 5) for value in row] for row in cost]
    return cost, steel


@pytest.mark.parametrize(("seed", "columns", "candidates", "groups"),
                         [(seed, 6 + seed % 3, 5, 2 + seed % 3) for seed in range(12)])
def test_milp_matches_brute_force_with_its_tie_break(seed: int, columns: int, candidates: int, groups: int) -> None:
    cost, steel = _random(seed, columns, candidates)
    expected = _brute(cost, steel, groups)
    result = assign(cost, steel, groups, None, 60.0)
    if expected is None:
        assert result.status == INFEASIBLE and result.choice == ()
        return
    assert result.status == OPTIMAL
    choice = result.choice
    assert len(set(choice)) == groups and all(cost[i][j] is not None for i, j in enumerate(choice))
    assert (result.cost, sum(steel[i][j] or 0 for i, j in enumerate(choice)), sum(choice)) == expected


def test_milp_starts_from_a_feasible_solution_and_never_ends_worse() -> None:
    cost, steel = _random(3, 7, 5)
    start = None
    for choice in itertools.product(range(5), repeat=7):
        if len(set(choice)) == 3 and all(cost[i][j] is not None for i, j in enumerate(choice)):
            start = list(choice)
            break
    assert start is not None
    result = assign(cost, steel, 3, start, 60.0)
    assert result.cost <= sum(cost[i][j] or 0 for i, j in enumerate(start))
    assert result.choice == assign(cost, steel, 3, None, 60.0).choice  # el arranque no cambia el óptimo elegido


def _loads(p: float, m: float) -> list[dict[str, Any]]:
    return [{"case": "D+L", "kind": "service", "dead_factor": 1.0, "live_factor": 1.0, "P_kN": p, "Vx_kN": 0.0, "Vy_kN": 0.0,
             "Mx_kNm": 0.0, "My_kNm": 0.2 * m},
            {"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 1.2, "live_factor": 1.6, "P_kN": 1.4 * p, "Vx_kN": 0.0,
             "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": m}]


def _project(method: str = "milp") -> dict[str, Any]:
    loads = [(400, 300.0, 20.0), (400, 480.0, 40.0), (500, 750.0, 60.0), (450, 600.0, 30.0)]
    return {
        "description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
        "materials": {"fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
        "soil": {"allowable_pressure_kPa": 200.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                 "unit_weight_fill_kNm3": 18.0, "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                 "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                 "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                 "overturning_safety_factor_seismic": 1.5},
        "design": {"typologies": 2, "fc_options": [21.0], "method": method, "milp_time_limit_s": 60.0,
                   "prices": {"concrete_per_m3": {"21": 500000.0}, "steel_per_kg": 6000.0},
                   "plan_step": 100.0, "plan_max": 4000.0, "h_min": 350.0, "h_step": 50.0, "h_max": 900.0, "cover": 75.0,
                   "fill_height": 800.0, "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
                   "bars": ["#4", "#5"], "spacing_step": 25.0, "end": "straight", "dowel_bars": ["#5"]},
        "columns": [{"id": f"C{index}", "cx": float(side), "cy": float(side), "loads": _loads(p, m)}
                    for index, (side, p, m) in enumerate(loads, start=1)],
    }


def _context(data: dict[str, Any]) -> Context:
    project = FootingDesignProject.model_validate(data)
    return Context(project, PROFILES[project.profile], load_engine().bars)


def test_milp_design_is_not_worse_than_the_dp_and_verifies(tmp_path: Path) -> None:
    ctx = _context(_project())
    result = design_typologies(ctx)
    milp = result.milp
    assert result.method == "milp" and milp is not None and milp.status == OPTIMAL
    assert milp.milp_cost is not None and milp.milp_cost <= milp.dp_cost + 1.0  # C_MILP ≤ C_DP en pesos enteros
    assert result.cost == pytest.approx(milp.milp_cost)
    assert len(result.typologies) == 2 and result.distinct_count == 2
    assert sorted(column for item in result.typologies for column in item.columns) == ["C1", "C2", "C3", "C4"]
    dp = design_typologies(_context(_project("dp")))
    assert milp.dp_cost == pytest.approx(dp.cost)
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(designed_project(ctx, result)), encoding="utf-8")
    _, checks = run_project(path)
    assert {str(check.status) for check in checks} == {"PASS"}


def test_milp_design_is_the_same_in_parallel() -> None:
    ctx = _context(_project())
    serial, parallel = design_typologies(ctx, workers=1), design_typologies(ctx, workers=2)
    assert parallel.typologies == serial.typologies and parallel.cost == serial.cost


def test_milp_without_the_solver_is_a_clear_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "diseno.json"
    path.write_text(json.dumps(_project("dp")), encoding="utf-8")
    monkeypatch.setattr("structurelab_rc.engine.solver_available", lambda: False)
    project, result, check = design_footings(path, method="milp")
    assert project is None and result is None and check.status is Status.FAIL
    assert "structurelab-rc[opt]" in check.errors[0].message
    assert assignment.available()  # en este entorno sí está: la falla es la simulada


def test_cli_method_milp_writes_the_comparison(tmp_path: Path) -> None:
    source = tmp_path / "diseno.json"
    source.write_text(json.dumps(_project("dp")), encoding="utf-8")
    assert main(["design-footings", str(source), "--output", str(tmp_path / "salida"), "--workers", "1", "--method", "milp"]) == 0
    summary = json.loads((tmp_path / "salida" / "tipologias.json").read_text(encoding="utf-8"))
    assert summary["method"] == "milp" and summary["milp"]["status"] == "optimal"
    assert summary["milp"]["milp_cost"] == summary["cost"] and summary["by_fc"][0]["milp"]["status"] == "optimal"
