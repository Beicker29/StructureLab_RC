"""V3J.1 y V3J.2: zapatas combinadas, modelo, entrada, revisión geotécnica y viga en la dirección larga contra los
oráculos independientes (D-080)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.checks import COMBINED_STRUCTURAL
from structurelab_rc.domain.footing.combined_beam import beam_case, long_beam_checks
from structurelab_rc.domain.footing.combined_columns import column_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.service import BEARING, CONTACT, combined_service_checks
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import run_project
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}


BARS = load_engine().bars


def _oracle(folder: str, name: str = "derived_combined_service") -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / f"{name}.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
         for case in _oracle(folder)["cases"]]
COLUMN_CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
                for case in _oracle(folder, "derived_combined_columns")["cases"]]
BEAM_CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items()
              for case in _oracle(folder, "derived_combined_beam")["cases"]]


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_combined_geotechnical_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    tolerance = oracle["tolerance_rel"]
    footing = CombinedFooting.model_validate(case["footing"])
    checks = combined_service_checks(PROFILES[profile], footing, Soil.model_validate(oracle["soil"]))
    for name, expected in case["expected"].items():
        own = {check.name: check for check in checks if check.case == name}
        bearing = own[BEARING]
        values = dict(bearing.values)
        assert values["N"] / 1e3 == pytest.approx(expected["N_kN"], rel=tolerance)
        assert values["Mx base"] / 1e6 == pytest.approx(expected["Mx_base_kNm"], rel=tolerance, abs=1e-9)
        assert values["My base"] / 1e6 == pytest.approx(expected["My_base_kNm"], rel=tolerance, abs=1e-9)
        if not expected["equilibrium"]:
            assert {str(own[key].status) for key in (BEARING, CONTACT, SLIDING, OVERTURNING)} == {"FAIL"}
            assert "Sin equilibrio" in bearing.errors[0].message
            continue
        assert str(bearing.status) == expected["bearing"]
        assert bearing.demand is not None and bearing.capacity is not None
        assert bearing.demand * 1e3 == pytest.approx(expected["pmax_kPa"], rel=tolerance)
        assert bearing.capacity * 1e3 == pytest.approx(expected["capacity_kPa"], rel=tolerance)
        corners = [values[f"p esquina {key}"] * 1e3 for key in ("-x-y", "+x-y", "+x+y", "-x+y")]
        assert corners == pytest.approx(expected["corners_kPa"], rel=tolerance, abs=1e-6)
        assert str(own[CONTACT].status) == expected["contact"]
        assert own[CONTACT].capacity == pytest.approx(expected["contact_fraction"], rel=tolerance)
        assert str(own[SLIDING].status) == expected["sliding"]
        sliding, overturning = own[SLIDING], own[OVERTURNING]
        assert sliding.demand is not None and sliding.capacity is not None
        assert overturning.demand is not None and overturning.capacity is not None
        assert sliding.demand / 1e3 == pytest.approx(expected["sliding_demand_kN"], rel=tolerance, abs=1e-9)
        assert sliding.capacity / 1e3 == pytest.approx(expected["sliding_capacity_kN"], rel=tolerance)
        assert str(overturning.status) == expected["overturning"]
        assert overturning.demand / 1e6 == pytest.approx(expected["overturning_demand_kNm"], rel=tolerance, abs=1e-9)
        assert overturning.capacity / 1e6 == pytest.approx(expected["overturning_capacity_kNm"], rel=tolerance)


def _beam_checks(profile: str, footing: CombinedFooting, oracle: dict[str, Any]) -> list[Check]:
    soil = Soil.model_validate(oracle["soil"])
    cases, failures = combined_factored_cases(footing, soil)
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    return [*failures, *long_beam_checks(basis, footing, soil, cases)]


def _noise(check: Check) -> float:
    """Tolerancia absoluta para el ruido numérico de los valores casi nulos: cortantes y momentos donde V = 0 (N, N·mm) y
    áreas por análisis de momentos pequeños (mm²)."""
    return {"N": 0.1, "N*mm": 0.1, "mm2": 1e-6}.get(check.unit, 0.0)


def _station_key(check: Check) -> tuple[str, str, float | None]:
    return check.name, check.case or "", None if check.z is None else round(check.z, 3)


@pytest.mark.parametrize(("profile", "case"), BEAM_CASES)
def test_long_beam_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    """Las verificaciones de vigas en cada estación de la viga larga (D-081) frente al oráculo: mismas estaciones,
    estados, demandas, capacidades y numerales. Las del eje débil (M2, V3) no aplican y se prueban con las vigas."""
    oracle = _oracle(FOLDERS[profile], "derived_combined_beam")
    tolerance = oracle["tolerance_rel"]
    checks = _beam_checks(profile, CombinedFooting.model_validate(case["footing"]), oracle)
    expected = case["expected"]["checks"]
    names = {item["name"] for item in expected}
    got = {_station_key(check): check for check in checks if check.name in names}
    wanted = {(item["name"], item.get("case", ""), None if "z_mm" not in item else round(item["z_mm"], 3)): item for item in expected}
    assert set(got) == set(wanted)
    for key, item in wanted.items():
        check = got[key]
        assert str(check.status) == item["status"], key
        for field in ("demand", "capacity"):
            if field in item:
                # abs: el cortante donde V = 0 es ruido numérico (≈1e-3 N).
                assert getattr(check, field) == pytest.approx(item[field], rel=tolerance, abs=_noise(check)), (key, field)
        for field in ("demand_Nmm", "capacity_Nmm"):
            if field in item:
                expected_value = pytest.approx(item[field], rel=tolerance, abs=_noise(check))
                assert getattr(check, field.removesuffix("_Nmm")) == expected_value, (key, field)
        values = dict(check.values)
        if "as_min" in item:
            assert values["As,min"] == pytest.approx(item["as_min"], rel=tolerance), key
        if "analysis" in item:
            assert values["As analisis"] == pytest.approx(item["analysis"], rel=tolerance, abs=1e-6), key
        if "clause" in item:
            assert check.clause == item["clause"], key


def _where(check: Check) -> str:
    """Columna o franja de un check de V3J.3 (la nota empieza con ella); el desarrollo ya la lleva en el nombre."""
    if check.name.startswith("Desarrollo") or not check.note.startswith(("Franja", "Columna")):
        return ""
    return check.note.split(",")[0].split(":")[0]


@pytest.mark.parametrize(("profile", "case"), COLUMN_CASES)
def test_column_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    """V3J.3 (D-082) frente al oráculo: punzonamiento, franjas con las reglas de vigas, malla y fuera de las franjas,
    desarrollo, aplastamiento y pasadores; mismos checks, estados, demandas, capacidades y numerales."""
    oracle = _oracle(FOLDERS[profile], "derived_combined_columns")
    tolerance = oracle["tolerance_rel"]
    footing = CombinedFooting.model_validate(case["footing"])
    soil = Soil.model_validate(oracle["soil"])
    cases, failures = combined_factored_cases(footing, soil)
    assert not failures
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    expected = case["expected"]
    names = {item["name"] for item in expected}
    checks = [check for check in column_checks(basis, footing, soil, cases) if check.name in names]
    got = {(check.name, check.case or "", None if check.z is None else round(check.z, 3), _where(check)): check for check in checks}
    wanted = {(item["name"], item.get("case", ""), None if "z_mm" not in item else round(item["z_mm"], 3), item.get("where", "")): item
              for item in expected}
    assert len(got) == len(checks)
    assert set(got) == set(wanted)
    for key, item in wanted.items():
        check = got[key]
        assert str(check.status) == item["status"], key
        for field in ("demand", "capacity"):
            if field in item:
                assert getattr(check, field) == pytest.approx(item[field], rel=tolerance, abs=_noise(check)), (key, field)
        values = dict(check.values)
        if "as_min" in item:
            assert values["As,min"] == pytest.approx(item["as_min"], rel=tolerance), key
        if "analysis" in item:
            assert values["As analisis"] == pytest.approx(item["analysis"], rel=tolerance, abs=1e-6), key
        if "clause" in item:
            assert check.clause == item["clause"], key


def test_long_beam_diagrams_close_at_both_ends() -> None:
    """Con la resultante tomada en el plano de la base, V y M de la viga son cero en los dos extremos."""
    oracle = _oracle("nsr_10", "derived_combined_beam")
    for case in oracle["cases"]:
        footing = CombinedFooting.model_validate(case["footing"])
        soil = Soil.model_validate(oracle["soil"])
        cases, _ = combined_factored_cases(footing, soil)
        for pressure, loads in cases:
            beam = beam_case(footing, soil, pressure, loads)
            total = sum(column.force for column in beam.columns)
            assert beam.shear(footing.lx / 2) == pytest.approx(0.0, abs=1e-9 * total)
            assert beam.moment(footing.lx / 2) == pytest.approx(0.0, abs=1e-9 * total * footing.lx)


def _footing(**changes: Any) -> dict[str, Any]:
    footing = json.loads(json.dumps(_oracle("nsr_10")["cases"][0]["footing"]))
    footing.update(changes)
    return footing


@pytest.mark.parametrize(("change", "message"), [
    ({"lx": 4000.0}, "se sale de la base"),
    ({"columns": "traslapo"}, "se traslapan"),
    ({"columns": "casos distintos"}, "mismos casos de carga"),
    ({"columns": "una sola"}, "at least 2"),
])
def test_combined_footing_input_is_validated(change: dict[str, Any], message: str) -> None:
    footing = _footing()
    columns = footing["columns"]
    if change.get("columns") == "traslapo":
        columns[1]["x"] = columns[0]["x"] + 200.0
    elif change.get("columns") == "casos distintos":
        columns[1]["loads"][0]["case"] = "otro"
    elif change.get("columns") == "una sola":
        footing["columns"] = columns[:1]
    else:
        footing.update(change)
    with pytest.raises(ValueError, match=message):
        CombinedFooting.model_validate(footing)


def _project(tmp_path: Path, footing: dict[str, Any]) -> list[Check]:
    oracle = _oracle("nsr_10")
    project = {"description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
               "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
               "soil": oracle["soil"], "combined_footings": [footing]}
    path = tmp_path / "combinada.json"
    path.write_text(json.dumps(project), encoding="utf-8")
    _, checks = run_project(path)
    return list(checks)


def test_project_without_factored_cases_is_incomplete(tmp_path: Path) -> None:
    """Sin casos mayorados la parte estructural queda INCOMPLETE (no se suponen cargas)."""
    by_name = {check.name: check for check in _project(tmp_path, _oracle("nsr_10")["cases"][0]["footing"])}
    assert by_name["Validacion de entrada"].status is Status.PASS
    assert by_name[BEARING].status is Status.PASS
    assert by_name[COMBINED_STRUCTURAL].status is Status.INCOMPLETE


def test_project_with_a_combined_footing_runs_every_structural_check(tmp_path: Path) -> None:
    """Con V3J.3 la zapata combinada ya no queda BLOCKED: viga larga, punzonamiento, franjas, desarrollo, aplastamiento y
    pasadores (sin pasadores declarados, INCOMPLETE: no se suponen)."""
    footing = _footing()
    for column, beam_column in zip(footing["columns"], _oracle("nsr_10", "derived_combined_beam")["cases"][0]["footing"]["columns"],
                                   strict=True):
        column["loads"] = column["loads"] + beam_column["loads"]
    footing["top"] = {"designation": "#7", "spacing": 150.0, "end": "straight"}
    footing["bottom"]["x"] = {"designation": "#7", "spacing": 150.0}
    checks = _project(tmp_path, footing)
    by_name = {check.name: check for check in checks}
    assert by_name["Validacion de entrada"].status is Status.PASS
    assert {"Flexion: resistencia", "Punzonamiento", "Aplastamiento en la zapata", "Desarrollo barras inferiores x",
            "Malla inferior y: acero minimo fuera de las franjas"} <= set(by_name)
    assert not any(check.status is Status.BLOCKED for check in checks)
    assert by_name["Pasadores: area minima"].status is Status.INCOMPLETE
    assert COMBINED_STRUCTURAL not in by_name
