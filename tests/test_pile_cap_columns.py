"""Cabezal de dos columnas (D-143) contra el oráculo independiente (tests/oracles/derive_pile_cap_columns.py):
reacciones, momentos en las caras y entre columnas, cortante a d, franja de cada columna y punzonamiento."""

import json
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.pile_cap.checks import cap_analysis, pile_cap_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _setup(profile: str) -> tuple[dict[str, Any], Basis, PileCap, PileCapSoil]:
    oracle: dict[str, Any] = json.loads((ORACLES / FOLDERS[profile] / "derived_pile_cap_columns.json").read_text(encoding="utf-8"))
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    return oracle, basis, PileCap.model_validate(oracle["cap"]), PileCapSoil.model_validate(oracle["soil"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_reactions_and_sections_match_oracle(profile: str) -> None:
    oracle, basis, cap, soil = _setup(profile)
    tolerance = oracle["tolerance_rel"]
    analysis = cap_analysis(basis, cap, soil)
    cases = {item.case: item for item in analysis.cases}
    moments = {item.case: item for item in analysis.moments}
    for expected in oracle["cases"]:
        forces = cases[expected["case"]].forces
        assert forces.reactions == pytest.approx(expected["R"], rel=tolerance)
        assert forces.spread == pytest.approx(expected["dR"], rel=tolerance)
        for section in expected.get("sections", []):
            found = moments[section["case"]]
            assert found.sections is not None
            values = sorted(moment for moment, item in zip(found.moments["x"], found.sections["x"], strict=True)
                            if abs(item.plane - section["plane"]) < 1e-6)
            assert values == pytest.approx(section["moments"], rel=tolerance, abs=1.0), section


@pytest.mark.parametrize("profile", FOLDERS)
def test_shear_strips_and_punching_match_oracle(profile: str) -> None:
    oracle, basis, cap, soil = _setup(profile)
    tolerance = oracle["tolerance_rel"]
    checks = pile_cap_checks(basis, cap, soil)
    for expected in (case for case in oracle["cases"] if case["kind"] == "factored"):
        name = expected["case"]
        one_way = [check for check in checks if check.name == expected["one_way"]["name"] and check.case == name]
        assert len(one_way) == 1
        assert one_way[0].demand == pytest.approx(expected["one_way"]["demand"], rel=tolerance)
        assert one_way[0].capacity == pytest.approx(expected["one_way"]["capacity"], rel=tolerance)
        for strip in expected["strips"]:
            title = f"Franja de la columna {strip['column']} (barras y)"
            own = [check for check in checks if check.case == name and check.note.startswith(title)]
            strength = sorted(abs(check.demand or 0.0) for check in own if check.name == "Franja de la columna: resistencia")
            assert strength == pytest.approx(strip["moments"], rel=tolerance), strip
            shears = [check.demand for check in own if check.name == "Franja de la columna: cortante"]
            assert shears == pytest.approx([strip["shear"]], rel=tolerance), strip
        punching = [check for check in checks if check.name == "Punzonamiento" and check.case == name]
        assert len(punching) == len(expected["punching"])  # sin perímetro común si no se traslapan
        for area in expected["punching"]:
            label = "perimetro comun" if area["area"] == "comun" else f"Columna {area['area']},"
            found = [check for check in punching if label in check.note]
            assert len(found) == 1, area
            force = dict(found[0].values)["Vu"]
            assert any(force == pytest.approx(value, rel=tolerance) for value in area["forces"]), (area, force)


@pytest.mark.parametrize("profile", FOLDERS)
def test_pile_loads_without_column_loads_leave_sections_incomplete(profile: str) -> None:
    """Con las cargas de los pilotes y varias columnas sin cargas, las secciones entre columnas y el aplastamiento quedan
    INCOMPLETE: el reparto entre columnas no se supone (D-143)."""
    oracle, basis, cap, soil = _setup(profile)
    analysis = cap_analysis(basis, cap, soil)
    data = dict(oracle["cap"])
    factored = [case for case in analysis.cases if case.load.kind == "factored"]
    piles = []
    for index, pile in enumerate(data["piles"]):
        loads = [{"case": case.case, "kind": "factored", "dead_factor": case.load.dead_factor, "live_factor": case.load.live_factor,
                  "seismic": case.load.seismic, "P_kN": case.forces.reactions[index] / 1e3, "Vx_kN": 0.0, "Vy_kN": 0.0,
                  "Mx_kNm": 0.0, "My_kNm": 0.0} for case in factored]
        piles.append({**pile, "loads": loads})
    columns = [{key: value for key, value in column.items() if key != "loads"} for column in data["columns"]]
    from_piles = PileCap.model_validate({**data, "loads_from": "piles", "reactions_include_weight": True, "piles": piles,
                                         "columns": columns})
    incomplete = {check.name for check in pile_cap_checks(basis, from_piles, soil) if check.status is Status.INCOMPLETE}
    assert {"Flexion: secciones", "Aplastamiento"} <= incomplete


@pytest.mark.parametrize("profile", FOLDERS)
def test_close_columns_add_a_common_perimeter(profile: str) -> None:
    """Si los perímetros a d/2 de dos columnas se traslapan, se revisa además el perímetro común (D-143)."""
    oracle, basis, _, soil = _setup(profile)
    data = dict(oracle["cap"])
    data["columns"] = [{**column, "offset_x": 400.0 * (1 if column["offset_x"] > 0 else -1)} for column in data["columns"]]
    cap = PileCap.model_validate(data)
    notes = {check.note for check in pile_cap_checks(basis, cap, soil) if check.name == "Punzonamiento"}
    assert any("perimetro comun" in note for note in notes)
    assert any(note.startswith("Columna C1,") for note in notes) and any(note.startswith("Columna C2,") for note in notes)


def test_etabs_template_reads_each_column(tmp_path: Path) -> None:
    """La plantilla de verificación lee las reacciones de cada columna por su Unique Name (D-143)."""
    from structurelab_rc.engine import import_etabs_footings

    root = frozen("aci_318_25", "cabezales", "cabezal_columna_etabs.json").parent
    template = json.loads((root / "cabezal_columna_etabs.json").read_text(encoding="utf-8"))
    template["etabs_files"] = {key: str((root / value).resolve()) for key, value in template["etabs_files"].items()}
    cap = template["pile_caps"][0]
    first = cap["columns"][0]
    cap["lx"] = 4000.0
    cap["columns"] = [{**first, "id": "C1", "offset_x": -900.0}, {**first, "id": "C2", "offset_x": 900.0, "column_unique_name": "1601"}]
    path = tmp_path / "plantilla.json"
    path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    files = template["etabs_files"]
    project, _, check = import_etabs_footings(Path(files["service"]), Path(files["factored"]), path, None, Path(files["combinations"]))
    assert check.status is Status.PASS, check
    assert project is not None
    columns = project["pile_caps"][0]["columns"]
    assert [column["id"] for column in columns] == ["C1", "C2"]
    assert columns[0]["loads"] and columns[1]["loads"]
    assert columns[0]["loads"] != columns[1]["loads"]


def _grid(profile: str) -> tuple[dict[str, Any], Basis, PileCap, PileCapSoil]:
    oracle: dict[str, Any] = json.loads((ORACLES / FOLDERS[profile] / "derived_pile_cap_grid.json").read_text(encoding="utf-8"))
    basis = Basis(PROFILES[profile], Materials.model_validate(oracle["materials"]), BARS, oracle["seismic_level"])
    return oracle, basis, PileCap.model_validate(oracle["cap"]), PileCapSoil.model_validate(oracle["soil"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_grid_strips_match_oracle(profile: str) -> None:
    """Cuatro columnas en cuadrícula (D-145): franjas en las dos direcciones, con la columna vecina dentro de la franja."""
    oracle, basis, cap, soil = _grid(profile)
    tolerance = oracle["tolerance_rel"]
    analysis = cap_analysis(basis, cap, soil)
    cases = {item.case: item for item in analysis.cases}
    checks = pile_cap_checks(basis, cap, soil)
    assert not [check for check in checks if check.status is Status.BLOCKED]
    for expected in oracle["cases"]:
        assert cases[expected["case"]].forces.reactions == pytest.approx(expected["R"], rel=tolerance)
        for strip in expected.get("strips", []):
            title = f"Franja de la columna {strip['column']} (barras {strip['along']})"
            own = [check for check in checks if check.case == expected["case"] and check.note.startswith(title)]
            strength = sorted(abs(check.demand or 0.0) for check in own if check.name == "Franja de la columna: resistencia")
            assert strength == pytest.approx(strip["moments"], rel=tolerance), strip
            shears = [check.demand for check in own if check.name == "Franja de la columna: cortante"]
            assert shears == ([] if strip["shear"] is None else pytest.approx([strip["shear"]], rel=tolerance)), strip


def test_clipped_corners_with_several_columns_are_rejected() -> None:
    """Las franjas no usan el contorno recortado: esquinas recortadas con varias columnas se rechazan (D-145)."""
    from pydantic import ValidationError

    oracle, _, _, _ = _setup("aci-318-25")
    data = {**oracle["cap"], "clipped_corners": [{"corner": "+x+y", "along_x": 200.0, "along_y": 200.0}]}
    with pytest.raises(ValidationError, match="esquinas recortadas y varias columnas"):
        PileCap.model_validate(data)
