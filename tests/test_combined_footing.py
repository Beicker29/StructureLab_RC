"""V3J.1 y V3J.2: zapatas combinadas, modelo, entrada, revisión geotécnica y viga en la dirección larga contra los
oráculos independientes (D-080)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.checks import COMBINED_STRUCTURAL
from structurelab_rc.domain.footing.combined_beam import beam_case, long_beam_checks, two_way_warning
from structurelab_rc.domain.footing.combined_columns import column_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.service import BEARING, CONTACT, combined_service_checks
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import report_file, run_project
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil
from structurelab_rc.model.project import Materials, Project
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
    áreas por análisis de momentos pequeños (mm²) y esfuerzos de punzonamiento casi nulos (MPa)."""
    return {"N": 0.1, "N*mm": 0.1, "mm2": 1e-6, "MPa": 1e-6}.get(check.unit, 0.0)


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
        for name, value in item.get("values", {}).items():
            assert values[name] == pytest.approx(value, rel=tolerance), (key, name)


@pytest.mark.parametrize(("profile", "case"), BEAM_CASES)
def test_long_beam_torque_matches_oracle(profile: str, case: dict[str, Any]) -> None:
    """T(x) de la viga larga (D-088) en cada estación, donde se toma el cortante, frente al oráculo: torque de cada
    columna F·y − Mx + H·Vy menos ∫y·q de la carga neta a la izquierda."""
    oracle = _oracle(FOLDERS[profile], "derived_combined_beam")
    footing = CombinedFooting.model_validate(case["footing"])
    soil = Soil.model_validate(oracle["soil"])
    cases, _ = combined_factored_cases(footing, soil)
    beams = {pressure.case: beam_case(footing, soil, pressure, loads) for pressure, loads in cases}
    for item in case["expected"]["torques"]:
        assert beams[item["case"]].torque(item["at"]) == pytest.approx(item["tu_Nmm"], rel=oracle["tolerance_rel"], abs=1.0), item


def _where(check: Check) -> str:
    """Columna o franja de un check de V3J.3 (la nota empieza con ella); el desarrollo ya la lleva en el nombre."""
    if check.name.startswith("Desarrollo") or not check.note.startswith(("Franja", "Columna")):
        return ""
    return check.note.split(",")[0].split(":")[0].split(";")[0]


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
        if "corners" in item:
            # Esfuerzo de punzonamiento en cada esquina del perímetro crítico, ordenadas por y y luego por x.
            for index, (x, y, stress) in enumerate(item["corners"], start=1):
                assert values[f"esquina {index} x"] == pytest.approx(x, abs=1e-6), key
                assert values[f"esquina {index} y"] == pytest.approx(y, abs=1e-6), key
                assert values[f"esquina {index} v"] == pytest.approx(stress, rel=tolerance, abs=1e-6), key
            assert f"esquina {len(item['corners']) + 1} v" not in values
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


@pytest.mark.parametrize(("case_id", "text"), [
    ("presion-nula-franja", "integrada en el ancho de la franja"),
    ("presion-nula-uniforme", "carga uniforme F/B"),
])
def test_strip_load_shape_falls_back_when_the_column_line_has_no_pressure(case_id: str, text: str) -> None:
    """D-085: sin presión en la línea de la columna, la franja usa la presión integrada en su ancho y, si también es nula,
    la carga uniforme; nunca queda BLOCKED y la nota dice qué forma se usó (solo en la franja de esa columna)."""
    oracle = _oracle("nsr_10", "derived_combined_columns")
    case = next(item for item in oracle["cases"] if item["id"] == case_id)
    footing = CombinedFooting.model_validate(case["footing"])
    soil = Soil.model_validate(oracle["soil"])
    cases, _ = combined_factored_cases(footing, soil)
    basis = Basis(PROFILES["nsr-10"], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    checks = column_checks(basis, footing, soil, cases)
    assert not any(check.status is Status.BLOCKED for check in checks)
    stations = [check for check in checks if check.z is not None]  # las del desarrollo no llevan la forma de carga
    first = [check for check in stations if check.note.startswith("Franja transversal de la columna C1,")]
    second = [check for check in stations if check.note.startswith("Franja transversal de la columna C2,")]
    assert first and all(text in check.note for check in first)
    assert second and not any(text in check.note for check in second)


EXAMPLE = Path(__file__).parent.parent / "examples" / "nsr_10" / "zapatas" / "zapata_combinada.json"


def _with_torsion_layers(layers: list[dict[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["combined_footings"][0]["torsion_layers"] = layers
    return data


@pytest.mark.parametrize(("layers", "message"), [
    ([{"depth": 400.0, "role": "torsion", "bars": ["#99", "#99"]}], "'#99' de las capas de torsion no esta en el catalogo"),
    ([{"depth": 400.0, "role": "torsion", "bars": [{"designation": "#5", "x": 20.0}, {"designation": "#5", "x": 2500.0}]}],
     "queda fuera del estribo"),
])
def test_torsion_layers_are_validated_like_beam_layers(layers: list[dict[str, Any]], message: str) -> None:
    """D-088: las capas de Aℓ de la viga larga usan el catálogo y la regla de las vigas (barras dentro del estribo)."""
    check = validate_project(Project.model_validate(_with_torsion_layers(layers)), BARS)
    assert check.status is not Status.PASS
    assert any(message in error.message for error in check.errors)


@pytest.mark.parametrize("layer", [{"depth": 400.0, "role": "flexure", "bars": ["#5", "#5"]},
                                   {"depth": 900.0, "role": "torsion", "bars": ["#5", "#5"]}])
def test_torsion_layers_need_the_torsion_role_and_fit_in_the_thickness(layer: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="role 'torsion'"):
        Project.model_validate(_with_torsion_layers([layer]))


def test_valid_torsion_layers_pass_and_reach_the_report(tmp_path: Path) -> None:
    layers = [{"depth": 400.0, "role": "torsion", "bars": [{"designation": "#5", "x": 100.0}, {"designation": "#5", "x": 2500.0}]}]
    project = Project.model_validate(_with_torsion_layers(layers))
    assert validate_project(project, BARS).status is Status.PASS
    path = tmp_path / "zc.json"
    path.write_text(json.dumps(_with_torsion_layers(layers)), encoding="utf-8")
    report_file(path, tmp_path / "salida")
    text = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert "2 #5 a 400 mm" in text and "Viga en la dirección larga: torsión" in text


def test_wide_footing_warns_about_two_way_behaviour(tmp_path: Path) -> None:
    """D-091: con B ≥ ℓn (luz libre entre las caras de las columnas) se avisa que la zapata puede trabajar en dos
    direcciones; se sigue revisando en una y el estado no cambia. El ejemplo (B = 2600, ℓn = 4475 mm) no avisa."""
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    footing = data["combined_footings"][0]
    assert two_way_warning(CombinedFooting.model_validate(footing)) is None
    footing["ly"] = 4500.0
    warning = two_way_warning(CombinedFooting.model_validate(footing))
    assert warning is not None
    assert warning.clear_span == pytest.approx(4475.0) and warning.ratio == pytest.approx(4500.0 / 4475.0)
    path = tmp_path / "ancha.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    report_file(path, tmp_path / "salida")
    results = json.loads((tmp_path / "salida" / "resultado.json").read_text(encoding="utf-8"))
    assert results["combined_footings"][0]["two_way_warning"]["ln [mm]"] == pytest.approx(4475.0)
    assert "puede trabajar en dos direcciones" in (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
