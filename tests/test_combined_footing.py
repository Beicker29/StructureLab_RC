"""V3J.1 y V3J.2: zapatas combinadas, modelo, entrada, revisión geotécnica y viga en la dirección larga contra los
oráculos independientes (D-080)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.checks import COMBINED_STRUCTURAL
from structurelab_rc.domain.footing.combined_beam import beam_case, long_beam_checks, two_way_warning
from structurelab_rc.domain.footing.combined_columns import column_checks, strip_demands, strip_limits, transverse_bottom
from structurelab_rc.domain.footing.combined_diagrams import combined_diagrams
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.domain.footing.service import BEARING, CONTACT, combined_service_checks
from structurelab_rc.domain.footing.spacing import combined_min_spacing_checks
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


def _station_key(check: Check) -> tuple[str, str, float | None, str]:
    """Nombre, caso, z y cara: con la torsión de placa una sección puede tener una estación por cara (D-118)."""
    face = "top" if "momento negativo" in check.note else "bottom"
    return check.name, check.case or "", None if check.z is None else round(check.z, 3), face if check.z is not None else ""


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
    wanted = {(item["name"], item.get("case", ""), None if "z_mm" not in item else round(item["z_mm"], 3), item.get("face", "")): item
              for item in expected}
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
    got = {(*_station_key(check)[:3], _where(check), _station_key(check)[3]): check for check in checks}
    wanted = {(item["name"], item.get("case", ""), None if "z_mm" not in item else round(item["z_mm"], 3), item.get("where", ""),
               item.get("face", "")): item for item in expected}
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
        if "excess" in item:
            # Cortante de la franja que excede φVc: lo toma la viga de cimentación (D-103).
            assert values["excedente para la viga"] == pytest.approx(item["excess"], rel=tolerance), key
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


@pytest.mark.parametrize(("profile", "case"), COLUMN_CASES)
def test_min_spacing_matches_oracle(profile: str, case: dict[str, Any]) -> None:
    """D-102: separación libre mínima de cada refuerzo declarado (ACI 25.2.1; NSR-10 C.7.6.1 y C.3.3.2(c))."""
    oracle = _oracle(FOLDERS[profile], "derived_combined_columns")
    footing = CombinedFooting.model_validate(case["footing"])
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    got = {check.name: check for check in combined_min_spacing_checks(basis, footing)}
    assert set(got) == {item["name"] for item in case["min_spacing"]}
    for item in case["min_spacing"]:
        check = got[item["name"]]
        assert (str(check.status), check.clause) == (item["status"], item["clause"]), item["name"]
        assert (check.demand, check.capacity) == pytest.approx((item["demand"], item["capacity"]), rel=oracle["tolerance_rel"])


def test_min_spacing_without_aggregate_is_incomplete() -> None:
    """D-102: sin materials.max_aggregate no se supone el agregado: la separación mínima queda INCOMPLETE."""
    oracle = _oracle("nsr_10", "derived_combined_columns")
    footing = CombinedFooting.model_validate(oracle["cases"][0]["footing"])
    materials = Materials.model_validate({**oracle["materials"], "max_aggregate": None})
    checks = combined_min_spacing_checks(Basis(PROFILES["nsr-10"], materials, BARS, oracle["seismic_level"]), footing)
    assert checks and all(check.status is Status.INCOMPLETE for check in checks)
    assert "max_aggregate" in checks[0].errors[0].message


def test_band_is_the_only_bottom_transverse_steel_in_its_zone() -> None:
    """D-097: la malla inferior y va solo fuera de las zonas de band (la franja de cada columna con band)."""
    case = next(case for case in _oracle("nsr_10", "derived_combined_columns")["cases"] if case["id"] == "interiores")
    footing = CombinedFooting.model_validate(case["footing"])
    row = mat_rows(footing, footing.bottom, BARS)["y"]
    kept = transverse_bottom(footing, row)
    zones = [strip_limits(footing, column, row.depth) for column in footing.columns]
    assert 0 < len(kept.positions) < len(row.positions)
    assert not any(x0 <= position <= x1 for position in kept.positions for x0, x1 in zones)
    # Sin band, la malla queda completa.
    plain = footing.model_copy(update={"columns": tuple(column.model_copy(update={"band": None}) for column in footing.columns)})
    assert transverse_bottom(plain, row) == row


def test_top_y_bars_must_be_in_the_catalog() -> None:
    footing = _footing(top={"first": "x", "end": "straight", "x": {"designation": "#7", "spacing": 150.0},
                            "y": {"designation": "#99", "spacing": 200.0}})
    project = Project.model_validate({"description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
                                      "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight",
                                                    "coating": "uncoated"},
                                      "soil": _oracle("nsr_10")["soil"], "combined_footings": [footing]})
    check = validate_project(project, BARS)
    assert check.status is not Status.PASS
    assert any("'#99' de las barras y de la malla superior" in error.message for error in check.errors)


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
    footing["top"] = {"end": "straight", "x": {"designation": "#7", "spacing": 150.0}}
    footing["bottom"]["x"] = {"designation": "#7", "spacing": 150.0}
    checks = _project(tmp_path, footing)
    by_name = {check.name: check for check in checks}
    assert by_name["Validacion de entrada"].status is Status.PASS
    assert {"Flexion: resistencia", "Punzonamiento", "Aplastamiento en la zapata", "Desarrollo barras inferiores, direccion principal",
            "Retraccion y temperatura: cuantia (direccion secundaria, en todo el largo)"} <= set(by_name)
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


EXAMPLE = Path(__file__).parent.parent / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_combinada.json"


def _to_global_y(load: dict[str, Any]) -> dict[str, Any]:
    """Las cargas que, con la viga en la Y global, ETABS daría para el caso escrito en ejes de la viga (inversa de D-094)."""
    return {**load, "Vx_kN": -load["Vy_kN"], "Vy_kN": load["Vx_kN"], "Mx_kNm": -load["My_kNm"], "My_kNm": load["Mx_kNm"]}


def _footing_along_global_y(footing: dict[str, Any]) -> dict[str, Any]:
    """La misma zapata girada en planta para que su viga vaya en la Y global, escrita en ejes globales como la escribe el
    usuario (D-094): ly a lo largo de la viga, columnas a distintas y, mallas x e y intercambiadas y cargas globales."""
    rotated = json.loads(json.dumps(footing))
    rotated["principal_direction"], rotated["lx"], rotated["ly"] = "y", footing["ly"], footing["lx"]
    for name in ("bottom", "top"):  # las barras superiores también se escriben en ejes globales (D-099)
        mat = footing.get(name)
        if not mat:
            continue
        swapped = {key: value for key, value in mat.items() if key not in ("x", "y", "first")}
        swapped.update({new: mat[old] for old, new in (("x", "y"), ("y", "x")) if old in mat})
        if "first" in mat:
            swapped["first"] = "y" if mat["first"] == "x" else "x"
        rotated[name] = swapped
    for column in rotated["columns"]:
        column["x"], column["y"] = -column["y"], column["x"]
        column["cx"], column["cy"] = column["cy"], column["cx"]
        column["loads"] = [_to_global_y(load) for load in column["loads"]]
    return rotated


_FACES = {"+X": "+Y", "-X": "-Y", "+Y": "-X", "-Y": "+X"}  # girada +90°: X → +Y global, Y → −X global


def _rotated_note(note: str) -> str:
    """La nota de la zapata a lo largo de X, como la escribe la misma zapata girada a lo largo de Y (D-101)."""
    note = re.sub(r"\b([Cc]ara|[Bb]orde|[Vv]oladizo|Aleta) ([+-][XY])\b", lambda m: f"{m.group(1)} {_FACES[m.group(2)]}", note)
    note = re.sub(r"\beje ([XY])\b", lambda m: f"eje {'Y' if m.group(1) == 'X' else 'X'}", note)
    return note.replace("en x = ", "en y = ")


def _rotated_values(values: tuple[tuple[str, float], ...]) -> dict[str, Any]:
    """Los valores con eje de la zapata a lo largo de X, en los ejes de la girada: x = −y, y = x (D-101)."""
    old = dict(values)
    new: dict[str, Any] = dict(old)
    for x_key, y_key in (("ex", "ey"), ("Mx base", "My base"), ("xc", "yc"), ("Msc x", "Msc y")):
        if x_key in old:
            new[x_key], new[y_key] = -old[y_key], old[x_key]
    for x_key, y_key in (("Jc x", "Jc y"), ("gamma v x", "gamma v y"), ("Pp x", "Pp y"), ("ex/lx", "ey/ly")):
        if x_key in old:
            new[x_key], new[y_key] = old[y_key], old[x_key]
    for sx in "+-":
        for sy in "+-":
            if f"p esquina {sx}x{sy}y" in old:
                new[f"p esquina {sx}x{sy}y"] = old[f"p esquina {sy}x{'+' if sx == '-' else '-'}y"]
    corners = [key for key in old if key.startswith("esquina ")]
    for key in corners:
        new.pop(key)
    rotated = sorted((-old[f"esquina {i} y"], old[f"esquina {i} x"], old[f"esquina {i} v"]) for i in range(1, len(corners) // 3 + 1))
    new["corners"] = [value for corner in rotated for value in corner]
    return new


def _corner_set(values: tuple[tuple[str, float], ...]) -> dict[str, Any]:
    own: dict[str, Any] = dict(values)
    keys = [key for key in own if key.startswith("esquina ")]
    corners = sorted((own[f"esquina {i} x"], own[f"esquina {i} y"], own[f"esquina {i} v"]) for i in range(1, len(keys) // 3 + 1))
    own["corners"] = [value for corner in corners for value in corner]
    for key in keys:
        own.pop(key)
    return own


@pytest.mark.parametrize("variant", ["combinada", "t invertida"])
def test_principal_direction_y_gives_the_same_verification(variant: str, tmp_path: Path) -> None:
    """D-094 y D-101: la misma zapata con la viga en la X global y girada en planta con la viga en la Y global (escrita
    en ejes globales: ly a lo largo de la viga y cargas de ETABS) da las mismas verificaciones (nombres, estados,
    demandas y capacidades) y las muestra en sus ejes declarados: notas con las caras giradas, la z de las franjas desde
    el borde −X y los valores con eje girados; la salida devuelve la geometría, las columnas, las cargas y las mallas
    como se declararon."""
    project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    along_x = project["combined_footings"][0]
    if variant == "t invertida":
        height = along_x["h"] + 800.0
        # D-106: el refuerzo de la viga va en sus capas; la zapata no declara top, estribos ni piel.
        layers = [{"depth": depth, "role": "flexure", "bars": [{"designation": "#6", "x": x} for x in (120.0, 340.0, 560.0, 780.0)]}
                  for depth in (100.0, height - 100.0)]
        along_x["beam"] = {"width": 900.0, "height": height, "end": "straight", "layers": layers}
        for key in ("top", "stirrups", "skin"):
            along_x.pop(key, None)
        for column in along_x["columns"]:
            column.pop("band", None)
            column.pop("band_top", None)  # la T no usa band ni band superior (D-119, D-122)
    along_y = {**_footing_along_global_y(along_x), "id": "ZCY"}
    assert along_y["ly"] > along_y["lx"] and along_y["columns"][0]["y"] != along_y["columns"][1]["y"]
    project["combined_footings"] = [along_x, along_y]
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(project), encoding="utf-8")
    _, checks = run_project(path)

    first = [check for check in checks if check.member == along_x["id"]]
    second = [check for check in checks if check.member == "ZCY"]
    assert first and len(first) == len(second)
    width = along_x["ly"]  # el ancho, a lo largo de la dirección secundaria
    for a, b in zip(first, second, strict=True):
        assert (a.name, a.status, a.case, a.demand, a.capacity) == (b.name, b.status, b.case, b.demand, b.capacity)
        assert b.note == _rotated_note(a.note), a.note
        z = None if a.z is None else (width - a.z if a.note.startswith("Franja") else a.z)
        assert b.z == (None if z is None else pytest.approx(z)), a.note
        got, want = _corner_set(b.values), _rotated_values(a.values)
        assert got.pop("corners") == pytest.approx(want.pop("corners")), (a.name, a.note)
        assert got == pytest.approx(want), (a.name, a.note)
    # En la girada, las caras de columna de la viga (dirección principal) son ±Y; las de las franjas, ±X.
    beam_notes = [check.note for check in second if check.z is not None and not check.note.startswith(("Franja", "Aleta"))]
    assert any(re.search(r"[Cc]ara [+-]Y de la columna", note) for note in beam_notes)
    assert not any(re.search(r"[Cc]ara [+-]X de la columna", note) for note in beam_notes)
    overlapping = json.loads(json.dumps(along_y))
    overlapping["columns"][1]["y"] = overlapping["columns"][0]["y"] + 200.0
    with pytest.raises(ValueError, match=r"se traslapan a lo largo de la viga \(dirección principal Y global\)"):
        CombinedFooting.model_validate(overlapping)
    report_file(path, tmp_path / "salida")
    results = json.loads((tmp_path / "salida" / "resultado.json").read_text(encoding="utf-8"))
    out = {footing["id"]: footing for footing in results["combined_footings"]}["ZCY"]
    assert out["geometry [mm]"]["principal_direction"] == "y"
    assert (out["geometry [mm]"]["lx"], out["geometry [mm]"]["ly"]) == (along_y["lx"], along_y["ly"])
    for column, declared in zip(out["columns"], along_y["columns"], strict=True):
        assert [column[key] for key in ("x", "y", "cx", "cy")] == pytest.approx([declared[key] for key in ("x", "y", "cx", "cy")])
        for load, written in zip(column["loads"], declared["loads"], strict=True):
            forces = [load[key] for key in ("Vx [kN]", "Vy [kN]", "Mx [kN-m]", "My [kN-m]")]
            assert forces == pytest.approx([written[key] for key in ("Vx_kN", "Vy_kN", "Mx_kNm", "My_kNm")], abs=1e-9)
    assert out["reinforcement"]["bottom"] == {**along_y["bottom"], "x": {**along_y["bottom"]["x"], "band_spacing": None},
                                              "y": {**along_y["bottom"]["y"], "band_spacing": None}}
    # Diagramas de la dirección secundaria en el eje X declarado: x = −y, así que las posiciones se reflejan y se invierten
    # de orden, M no cambia y V (cuerpo libre a la izquierda) cambia de signo.
    base = {footing["id"]: footing for footing in results["combined_footings"]}[along_x["id"]]["diagrams"]
    for a_env, b_env in zip(base["secondary"], out["diagrams"]["secondary"], strict=True):
        assert b_env["positions [mm]"] == pytest.approx([-p for p in reversed(a_env["positions [mm]"])], abs=1e-6)
        assert b_env["M max [kN-m]"] == pytest.approx(list(reversed(a_env["M max [kN-m]"])), abs=1e-6)
        assert b_env["V max [kN]"] == pytest.approx([-v for v in reversed(a_env["V min [kN]"])], abs=1e-6)
    assert out["diagrams"]["principal"]["positions [mm]"] == pytest.approx(base["principal"]["positions [mm]"])
    memoir = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert "Dirección principal (Y global): momento positivo" in memoir and "Dirección principal (X global): momento positivo" in memoir


def test_diagrams_close_at_the_free_edges_and_match_the_strip_faces() -> None:
    """D-095: la envolvente de la viga larga y la de cada voladizo de franja valen cero en los bordes libres; en la cara de
    la columna, el diagrama transversal da el momento de la sección revisada (strip_demands)."""
    project = Project.model_validate(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    footing, soil = project.combined_footings[0], project.soil
    assert soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    cases, _ = combined_factored_cases(footing, soil)
    longitudinal, transverse = combined_diagrams(basis, footing, soil, cases)
    scale = max(map(abs, (*longitudinal.moment_max, *longitudinal.moment_min)))
    for values in (longitudinal.moment_max, longitudinal.moment_min):
        assert values[0] == pytest.approx(0.0, abs=1e-9 * scale) and values[-1] == pytest.approx(0.0, abs=1e-6 * scale)
    depth = mat_rows(footing, footing.bottom, BARS)["y"].depth
    for index, (column, envelope) in enumerate(zip(footing.columns, transverse, strict=True)):
        (first, last), (second, _) = envelope.segments
        assert envelope.moment_max[first] == 0.0 and envelope.shear_max[first] == 0.0  # borde −Y
        faces = [max(moment for y, moment, _, label in strip_demands(footing, pressure, column,
                                                                     (column_vertical(footing, soil, column, loads[index]), depth))[0]
                     if label == "cara -Y") for pressure, loads in cases]
        assert envelope.moment_max[last] == pytest.approx(max(faces), rel=1e-9)


def test_torsion_layers_are_rejected_because_torsion_is_plate_torsion() -> None:
    """D-118: la torsión de la combinada se diseña como de placa (Wood-Armer); torsion_layers se rechaza con el motivo."""
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["combined_footings"][0]["torsion_layers"] = [{"depth": 400.0, "role": "torsion", "bars": ["#5", "#5"]}]
    with pytest.raises(ValidationError, match="no usa torsion_layers: la torsión se diseña como de placa"):
        Project.model_validate(data)


def test_plate_torsion_drives_the_flexure_of_both_faces_and_the_y_bars_outside_the_strips() -> None:
    """D-118: con una columna desplazada en Y, la viga larga no lleva torsión de vigas; su flexión usa los momentos de
    Wood-Armer (máx(M + |T|, 0) abajo y mín(M − |T|, 0) arriba, por B) y la nota lo dice; fuera de las franjas, las barras
    y se revisan por metro con ±|mxy|."""
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    footing = data["combined_footings"][0]
    footing["columns"][0]["y"] = 400.0
    project = Project.model_validate(data)
    combined, soil = project.combined_footings[0], project.soil
    assert soil is not None
    basis = Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)
    cases, _ = combined_factored_cases(combined, soil)
    checks = long_beam_checks(basis, combined, soil, cases)
    assert not any(check.name.startswith("Torsion") for check in checks)
    strengths = [check for check in checks if check.name == "Flexion: resistencia" and "Wood-Armer (D-118)" in check.note]
    assert strengths
    beams = {pressure.case: beam_case(combined, soil, pressure, loads) for pressure, loads in cases}
    for check in strengths:
        beam = beams[check.case or ""]
        x = (check.z or 0.0) - combined.lx / 2
        moment, torque = beam.moment(x), abs(beam.torque(x))
        expected = -min(moment - torque, 0.0) if "momento negativo" in check.note else max(moment + torque, 0.0)
        assert check.demand == pytest.approx(expected, rel=1e-9)
    names = {check.name for check in column_checks(basis, combined, soil, cases)}
    assert "Direccion secundaria: torsion de placa (barras inferiores)" in names


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
