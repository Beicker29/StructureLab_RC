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
from structurelab_rc.design.footing import typology as typology_module
from structurelab_rc.design.footing.grouping import partition, reassign
from structurelab_rc.design.footing.profiling import profile_typologies
from structurelab_rc.design.footing.typologies import (
    Duplicate,
    FcOption,
    TypologyResult,
    _duplicates,
    _reassign,
    _run,
    design_typologies,
    designed_project,
)
from structurelab_rc.design.footing.typology import (
    Context,
    GroupDesign,
    Typology,
    _demands,
    _dowel_options,
    _mat_candidates,
    checks_for,
    column_checks,
    column_cost,
    covers,
    design_group,
    priced,
)
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import design_footings, report_file, run_project
from structurelab_rc.io.etabs.footings import build_footing_design_project
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.design import DesignColumn, FootingDesignProject
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
        "materials": {"fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
        "soil": {"allowable_pressure_kPa": 200.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                 "unit_weight_fill_kNm3": 18.0,
                 "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                 "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                 "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                 "overturning_safety_factor_seismic": 1.5},
        "design": {"typologies": typologies, "fc_options": [21.0], "method": "dp",  # estas pruebas son de la DP
                   "prices": {"concrete_per_m3": {"21": 500000.0}, "steel_per_kg": 6000.0},
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


@pytest.mark.parametrize("seed", range(20))
def test_reassign_lowers_the_cost_and_keeps_every_group(seed: int) -> None:
    rng = random.Random(seed)
    items, groups = 9, 3
    table = {(i, g): (math.inf if rng.random() < 0.3 else rng.uniform(1, 10)) for i in range(items) for g in range(groups)}
    owner = [i % groups for i in range(items)]
    for i in range(items):
        table[(i, owner[i])] = rng.uniform(1, 10)  # su grupo de partida lo cubre
    order = list(range(items))
    result = reassign(owner, groups, lambda i, g: table[(i, g)], order)
    assert sum(table[(i, result[i])] for i in range(items)) <= sum(table[(i, owner[i])] for i in range(items))
    sizes = [result.count(g) for g in range(groups)]
    assert min(sizes) >= 1
    for i in range(items):  # estable: nadie baja su costo moviéndose sin vaciar su grupo
        assert sizes[result[i]] == 1 or all(table[(i, g)] >= table[(i, result[i])] for g in range(groups))
    assert reassign(result, groups, lambda i, g: table[(i, g)], order) == result


def test_reassign_keeps_one_item_in_each_group_in_the_given_order() -> None:
    costs = {(0, 0): 5.0, (0, 1): 1.0, (1, 0): 5.0, (1, 1): 1.0, (2, 0): math.inf, (2, 1): 2.0}
    # Los dos elementos del grupo 0 quieren pasar al 1: pasa el primero en el orden y el segundo conserva el grupo 0.
    assert reassign([0, 0, 1], 2, lambda i, g: costs[(i, g)], [1, 0, 2]) == [0, 1, 1]
    assert reassign([0, 0, 1], 2, lambda i, g: costs[(i, g)], [0, 1, 2]) == [1, 0, 1]


def test_identical_columns_are_marked_as_duplicates(tmp_path: Path) -> None:
    data = _project(typologies=2, columns=1)
    data["columns"].append({**data["columns"][0], "id": "C2"})
    ctx = _context(data)
    result = design_typologies(ctx)
    assert len(result.typologies) == 2 and result.distinct_count == 1
    assert [group.typologies for group in result.duplicates] == [("Z1", "Z2")]
    assert result.options == (FcOption(21.0, result.cost, 1),)
    assert result.reassigned == () and result.cost_before_reassignment == result.cost
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(designed_project(ctx, result)), encoding="utf-8")
    report_file(path, tmp_path / "salida")
    assert "ADVERTENCIA: tipologías repetidas: Z1 = Z2" in (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")


def test_duplicates_report_the_design_limits() -> None:
    ctx = _context(_project(typologies=1, columns=1))
    design = design_group(ctx, ctx.project.columns, 21.0)
    assert design is not None
    t = design.typology
    assert max(t.lx, t.ly) + ctx.design.plan_step <= ctx.design.plan_max and t.h + ctx.design.h_step <= ctx.design.h_max
    limited = _context(_project(typologies=1, columns=1, plan_max=max(t.lx, t.ly)))  # el paso siguiente ya no cabe
    pair = (TypologyResult("Z1", design, ("C1",)), TypologyResult("Z2", design, ("C2",)))
    assert _duplicates(limited, pair) == (Duplicate(("Z1", "Z2"), ("plan_max",)),)
    assert _duplicates(ctx, pair[:1]) == ()


def test_reassignment_moves_a_column_to_a_cheaper_typology_that_covers_it() -> None:
    ctx = _context(_project(typologies=2, columns=3))
    c1, c2, c3 = ctx.project.columns
    largest, middle = design_group(ctx, [c3], 21.0), design_group(ctx, [c2], 21.0)
    assert largest is not None and middle is not None
    dowels = covers(ctx, largest.typology, c1)
    assert dowels is not None and covers(ctx, middle.typology, c1) is not None
    chosen = [(priced(ctx, largest.typology, [c1, c3], {"C1": dowels, "C3": largest.dowels["C3"]}), [c1, c3]), (middle, [c2])]
    position = {column.id: index for index, column in enumerate(ctx.project.columns)}
    regrouped, shifts = _reassign(ctx, chosen, lambda tasks: [_run(ctx, task) for task in tasks], position)
    assert [(column, source, target) for column, source, target, _ in shifts] == [("C1", 0, 1)]
    assert [[column.id for column in columns] for _, columns in regrouped] == [["C3"], ["C1", "C2"]]
    before, after = sum(design.cost for design, _ in chosen), sum(design.cost for design, _ in regrouped)
    assert after == pytest.approx(before - shifts[0][3]) and shifts[0][3] > 0
    assert regrouped[1][0].dowels["C1"] == covers(ctx, middle.typology, c1)


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


def _without_times(value: Any) -> Any:
    """La medición sin los tiempos (claves *_s), que cambian entre corridas."""
    if isinstance(value, dict):
        return {key: _without_times(item) for key, item in value.items() if not key.endswith("_s") and key != "estimate_over_design"}
    if isinstance(value, list):
        return [_without_times(item) for item in value]
    return value


def test_profile_gives_the_same_result_and_the_same_counts_in_parallel() -> None:
    ctx = _context(_project(typologies=2, columns=3))
    result, measurement = profile_typologies(ctx, workers=1)
    assert result == design_typologies(ctx, workers=1)
    parallel, measured = profile_typologies(ctx, workers=2)
    assert parallel == result
    assert _without_times(measured | {"workers": 1}) == _without_times(measurement)
    stage = measurement["fc"][0]
    assert stage["single"]["count"] == 3
    assert stage["covered_segments"] + stage["redesigned_segments"] == stage["segments"]
    assert stage["design"]["count"] == stage["redesigned_segments"]
    assert stage["sample"]["pairs_sampled"] == stage["sample"]["pairs_full"] <= 3 * stage["sample"]["candidates"]
    assert stage["sample"]["soil_rejects_but_covers"] == 0
    assert measurement["solution"]["repeated"] == 0 and measurement["solution"]["typologies"] == 2


def test_cli_profile_writes_the_measurement_without_changing_the_design(tmp_path: Path) -> None:
    source = tmp_path / "diseno.json"
    source.write_text(json.dumps(_project(typologies=1, columns=2)), encoding="utf-8")
    assert main(["design-footings", str(source), "--output", str(tmp_path / "a"), "--workers", "1"]) == 0
    assert main(["design-footings", str(source), "--output", str(tmp_path / "b"), "--workers", "1", "--profile"]) == 0
    for name in ("proyecto.json", "tipologias.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    measurement = json.loads((tmp_path / "b" / "medicion.json").read_text(encoding="utf-8"))
    assert measurement["environment"]["workers"] == 1 and measurement["fc"][0]["fc"] == 21.0


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
    assert summary["distinct_count"] == 1 and summary["duplicates"] == [] and summary["reassigned"] == []
    assert summary["cost_before_reassignment"] == summary["cost"]
    assert summary["by_fc"] == [{"fc [MPa]": 21.0, "cost": summary["cost"], "distinct_count": 1}]
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


@pytest.mark.parametrize(("level", "top"), [("DMO", False), ("DES", True)])
def test_negative_moment_uses_plain_concrete_where_permitted(level: str, top: bool) -> None:
    """D-072: con momento negativo el diseño prueba primero sin malla superior; con DES el concreto simple no se permite."""
    data = _project(typologies=1, columns=1)
    data["seismic"]["level"] = level
    data["columns"][0]["loads"] = _loads(150, 120.0)
    result = design_typologies(_context(data))
    assert (result.typologies[0].design.typology.top is not None) is top


def _enumerate(ctx: Context, column: DesignColumn, fc: float, plan: tuple[float, float]) -> float:
    """Menor costo de la columna en la planta, enumerando todos los espesores de h_min a h_max y todas las combinaciones de
    mallas candidatas (inferior × superior o ninguna) con los pasadores de menor área que pasan. Independiente de la
    búsqueda: no usa _at_height, _verify ni la bisección; solo las candidatas, footing_checks y el costo por columna."""
    design = ctx.design
    best = math.inf
    count = int(round((design.h_max - design.h_min) / design.h_step)) + 1
    for h in (design.h_min + index * design.h_step for index in range(count)):
        bars = {"designation": design.bars[0], "spacing": 100.0}
        provisional = Typology(fc, plan[0], plan[1], h, {"first": "x", "end": design.end, "x": bars, "y": bars}, None)
        bottoms = list(_mat_candidates(ctx, provisional, _demands(ctx, [column], provisional, 1.0)))
        negative = _demands(ctx, [column], provisional, -1.0)
        tops = [None, *_mat_candidates(ctx, provisional, negative)] if max(negative.values()) > 0 else [None]
        for bottom, top in itertools.product(bottoms, tops):
            typology = Typology(fc, plan[0], plan[1], h, bottom, top)
            for dowels in _dowel_options(ctx, typology, column):  # de menor a mayor área (y costo)
                if all(check.status is Status.PASS for check in checks_for(ctx, typology, column, dowels)):
                    best = min(best, column_cost(ctx, typology, column, dowels)[0])
                    break
    return best


def _thickness_case(case: str) -> dict[str, Any]:
    data = _project(typologies=1, columns=1)
    data["design"]["h_max"] = 700.0
    if case != "sin negativo":
        data["seismic"]["level"] = "DES" if case == "negativo DES" else "DMO"
        data["columns"][0]["loads"] = _loads(150, 120.0)
    return data


@pytest.mark.parametrize("case", ["sin negativo", "negativo DES", "negativo DMO"])
def test_thickness_and_mats_are_the_cheapest_of_the_enumeration(case: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-076: en una planta fija, el resultado es el mínimo de la enumeración completa (incluidos los espesores menores
    que el de la bisección), y las mallas separables no necesitan el respaldo conjunto."""
    monkeypatch.setattr(typology_module, "_MAT_TRIES", 3)  # menos candidatas: la enumeración cabe en una prueba
    monkeypatch.setattr(typology_module, "_jointly", lambda *args: pytest.fail("las mallas no resultaron separables"))
    ctx = _context(_thickness_case(case))
    column = ctx.project.columns[0]
    design = design_group(ctx, [column], 21.0)
    assert design is not None
    plan = (design.typology.lx, design.typology.ly)
    found = typology_module._for_plan(ctx, [column], 21.0, plan, ctx.design.h_min)
    assert isinstance(found, GroupDesign)
    assert found.cost == pytest.approx(_enumerate(ctx, column, 21.0, plan))


def test_the_bound_never_prunes_the_optimum(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _context(_thickness_case("negativo DMO"))
    column = ctx.project.columns[0]
    design = design_group(ctx, [column], 21.0)
    assert design is not None
    plan = (design.typology.lx, design.typology.ly)
    pruned = typology_module._for_plan(ctx, [column], 21.0, plan, ctx.design.h_min)
    monkeypatch.setattr(typology_module, "_lower_bound", lambda *args: -math.inf)  # sin poda: todos los espesores
    full = typology_module._for_plan(ctx, [column], 21.0, plan, ctx.design.h_min)
    assert isinstance(pruned, GroupDesign) and isinstance(full, GroupDesign)
    assert pruned.cost == pytest.approx(full.cost)


@pytest.mark.parametrize(("options", "message"), [([21.0, 26.0], "no es un valor comercial"), ([21.0, 28.0], "no tiene precio")])
def test_fc_options_must_be_commercial_and_priced(options: list[float], message: str) -> None:
    data = _project()
    data["design"]["fc_options"] = options
    with pytest.raises(ValueError, match=message):
        FootingDesignProject.model_validate(data)
