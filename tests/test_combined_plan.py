"""Zapata combinada trapezoidal y en planta T o L (D-164) frente al oráculo independiente: centroide y área, presión,
cuerpo libre de la viga, franjas con los bordes locales, perímetro de punzonamiento con αs por esquinas y volcamiento
por los lados de la envolvente; y la planta declarada con la viga en la Y global, igual que en la X."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.checks import PLAN_PENDING, combined_footing_checks
from structurelab_rc.domain.footing.combined_beam import beam_case
from structurelab_rc.domain.footing.combined_columns import strip_cantilever, strip_edges, strip_limits, strip_load, transverse_bottom
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.domain.footing.service import combined_service_checks
from structurelab_rc.domain.footing.stability import OVERTURNING
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.perimeter import plan_perimeter
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLE = json.loads((Path(__file__).parent / "oracles" / "derived_combined_plan.json").read_text(encoding="utf-8"))
CASES = ORACLE["cases"]
SOIL = Soil.model_validate(ORACLE["soil"])
TOLERANCE = ORACLE["tolerance_rel"]
BARS = load_engine().bars
MATERIALS = Materials.model_validate({"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"})


def _ids(cases: list[dict[str, Any]]) -> list[str]:
    return [case["id"] for case in cases]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_plan_geometry_pressure_and_beam_match_oracle(case: dict[str, Any]) -> None:
    footing = CombinedFooting.model_validate(case["footing"])
    assert footing.area == pytest.approx(case["area"], rel=1e-12)
    _, along, across = footing.plan.area_centroid()  # type: ignore[union-attr]
    assert (along, across) == pytest.approx(tuple(case["centroid"]), rel=1e-9, abs=1e-9)
    cases, failures = combined_factored_cases(footing, SOIL)
    assert not failures
    pressure, loads = next((pressure, loads) for pressure, loads in cases if pressure.case == "U1")
    plane = (pressure.pressure.p0, pressure.pressure.gx, pressure.pressure.gy)
    peak = case["plane"][0]
    assert plane == pytest.approx(tuple(case["plane"]), rel=1e-7, abs=1e-9 * abs(peak))
    beam = beam_case(footing, SOIL, pressure, loads)
    scale = max(abs(item["M"]) for item in case["beam"])
    for item in case["beam"]:
        x = item["x"]
        assert beam.shear(x) == pytest.approx(item["V"], rel=TOLERANCE, abs=1e-7 * scale / 1000.0), x
        assert beam.moment(x) == pytest.approx(item["M"], rel=TOLERANCE, abs=1e-7 * scale), x
        assert beam.torque(x) == pytest.approx(item["T"], rel=TOLERANCE, abs=1e-7 * scale), x


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_plan_strips_match_oracle(case: dict[str, Any]) -> None:
    footing = CombinedFooting.model_validate(case["footing"])
    cases, _ = combined_factored_cases(footing, SOIL)
    pressure, loads = next((pressure, loads) for pressure, loads in cases if pressure.case == "U1")
    depth = transverse_bottom(footing, mat_rows(footing, footing.bottom, BARS)["y"]).depth
    for index, (column, expected) in enumerate(zip(footing.columns, case["strips"], strict=True)):
        assert depth == pytest.approx(expected["depth"])
        assert strip_limits(footing, column, depth) == pytest.approx((expected["x0"], expected["x1"]))
        assert strip_edges(footing, column, depth) == pytest.approx((expected["low"], expected["high"]))
        load, _ = strip_load(footing, pressure, column, (column_vertical(footing, SOIL, column, loads[index]), depth))
        plus = strip_cantilever(footing, load, column.y + column.cy / 2, 1.0)[0]
        minus = strip_cantilever(footing, load, column.y - column.cy / 2, -1.0)[0]
        assert plus == pytest.approx(expected["M_face_plus"], rel=TOLERANCE)
        assert minus == pytest.approx(expected["M_face_minus"], rel=TOLERANCE)


@pytest.mark.parametrize("case", [case for case in CASES if case["punching"]], ids=_ids([case for case in CASES if case["punching"]]))
def test_plan_punching_perimeter_matches_oracle(case: dict[str, Any]) -> None:
    """b0 = lo que queda dentro de la planta; αs por las esquinas dentro (D-164)."""
    footing = CombinedFooting.model_validate(case["footing"])
    for expected in case["punching"]:
        column = next(column for column in footing.columns if column.id == expected["column"])
        perimeter = plan_perimeter((column.x, column.y), column.cx, column.cy, expected["depth"], footing.outline)
        assert perimeter.length == pytest.approx(expected["b0"], rel=1e-9)
        assert perimeter.outside == expected["outside"]


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_plan_overturning_matches_oracle(case: dict[str, Any]) -> None:
    footing = CombinedFooting.model_validate(case["footing"])
    check = next(check for check in combined_service_checks(PROFILES["aci-318-25"], footing, SOIL) if check.name == OVERTURNING)
    assert check.demand == pytest.approx(case["overturning"]["demand"], rel=1e-7)
    assert check.capacity == pytest.approx(case["overturning"]["capacity"], rel=1e-7)


def _along_y(data: dict[str, Any]) -> dict[str, Any]:
    """La misma zapata con la viga en la Y global (D-094): las columnas (a, t) pasan a (x = t, y = a) y las mallas se
    intercambian; la planta se declara igual (a lo largo de la dirección principal y t en el eje transversal)."""
    turned = copy.deepcopy(data)
    turned["principal_direction"] = "y"
    for column in turned["columns"]:
        column["x"], column["y"] = column["y"], column["x"]
        for load in column["loads"]:
            # El problema queda reflejado en t (Y de la viga = −X global): Vy y Mx cambian de signo en ejes de la viga.
            load["Vx_kN"], load["Vy_kN"] = load["Vy_kN"], load["Vx_kN"]
            load["Mx_kNm"], load["My_kNm"] = -load["My_kNm"], -load["Mx_kNm"]
    for name in ("bottom", "top"):
        mat = turned[name]
        turned[name] = {"first": "y" if mat["first"] == "x" else "x", "x": mat["y"], "y": mat["x"]}
    return turned


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_plan_along_global_y_gives_the_same_checks(case: dict[str, Any]) -> None:
    """Ejes globales (D-094, D-164): la planta con la viga en Y es, en ejes de la viga, el reflejo t → −t de la misma
    planta con la viga en X (la Y de la viga es −X global); con las cargas reflejadas igual, las verificaciones, sus
    estados y sus demandas coinciden."""
    basis = Basis(PROFILES["nsr-10"], MATERIALS, BARS, "DES")
    along_x = CombinedFooting.model_validate(case["footing"])
    along_y = CombinedFooting.model_validate(_along_y(case["footing"]))
    first = combined_footing_checks(basis, along_x, SOIL)
    second = combined_footing_checks(basis, along_y, SOIL)
    def summary(checks: list[Any]) -> list[tuple[str, str, float]]:
        # El reflejo intercambia las caras ±Y de cada franja: se comparan sin orden, con la demanda redondeada.
        return sorted((check.name, check.status.value, round(check.demand or 0.0, -2)) for check in checks)

    assert summary(first) == summary(second)


def test_plan_rejects_declared_sizes_and_columns_outside() -> None:
    data = copy.deepcopy(CASES[0]["footing"])
    with pytest.raises(ValidationError, match="lx y ly se calculan"):
        CombinedFooting.model_validate({**data, "lx": 7000.0, "ly": 2600.0})
    data["columns"][1]["y"] = 200.0  # C2 en a = 6300: el borde +Y allí es 300 - (6300/7000)·0 ... cae fuera
    with pytest.raises(ValidationError, match="se sale de la base"):
        CombinedFooting.model_validate(data)


def test_plan_stirrups_are_blocked() -> None:
    """D-164: estribos y refuerzo superficial no están implementados en planta no rectangular."""
    data = {**copy.deepcopy(CASES[0]["footing"]),
            "stirrups": {"designation": "#4", "legs": 4, "spacing": 200.0, "closed": True, "end": "hook135"}}
    footing = CombinedFooting.model_validate(data)
    basis = Basis(PROFILES["aci-318-25"], MATERIALS, BARS, "special")
    blocked = [check for check in combined_footing_checks(basis, footing, SOIL) if check.name == PLAN_PENDING]
    assert [check.status for check in blocked] == [Status.BLOCKED]
