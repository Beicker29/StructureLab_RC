"""Pantalla del muro en voladizo (D-173, fase A, etapa 3) contra el oráculo independiente
tests/oracles/<perfil>/derived_wall_stem.json, y el ejemplo 2 del manual ACI MNL-17(21) contra sus números."""

import json
from pathlib import Path
from typing import Any

import pytest
from wall_inputs import bars, internal_soil, wall

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.retaining_wall import stem as names
from structurelab_rc.domain.retaining_wall.stem import stem_checks
from structurelab_rc.domain.retaining_wall.thrust import stem_thrust
from structurelab_rc.model.project import Materials
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci_318_25": "aci-318-25", "nsr_10": "nsr-10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_wall_stem.json").read_text(encoding="utf-8"))
    return data


def _checks(folder: str, item: dict[str, Any]) -> list[Check]:
    case = {"case": "1.2D+1.6H", "kind": "factored", "dead_factor": 1.2, "fill_factor": 1.6, "earth_factor": item["earth_factor"]}
    own = RetainingWall.model_validate(wall(**{key: value for key, value in item["wall"].items() if key != "stem"},
                                            stem={key: bars(value["designation"], value["spacing"])
                                                  for key, value in item["wall"]["stem"].items()},
                                            cases=[case]))
    soil = RetainingSoil.model_validate(internal_soil(**item["soil"]))
    materials = Materials(fc=item["fc"], fy=item["fy"], fyt=item["fy"], concrete="normalweight", coating="uncoated")
    basis = Basis(PROFILES[FOLDERS[folder]], materials, BARS, "none" if folder == "aci_318_25" else "DMI")
    return stem_checks(basis, own, stem_thrust(own, soil))


CASES = [(folder, item["id"]) for folder in FOLDERS for item in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("folder", "case_id"), CASES)
def test_stem_matches_the_oracle(folder: str, case_id: str) -> None:
    oracle = _oracle(folder)
    item = next(case for case in oracle["cases"] if case["id"] == case_id)
    expected, tolerance = item["expected"], oracle["tolerance_rel"]
    checks = {check.name: check for check in _checks(folder, item)}

    def close(actual: float | None, value: float) -> None:
        assert actual == pytest.approx(value, rel=tolerance)

    flexure, shear = checks[names.FLEXURE], checks[names.SHEAR]
    close(flexure.demand, expected["Mu"])
    close(flexure.capacity, expected["phiMn"])
    close(dict(flexure.values)["d"], expected["d"])
    close(checks[names.STRAIN].capacity, expected["et"])
    close(shear.demand, expected["Vu"])
    close(shear.capacity, expected["phiVc"])
    section = checks[names.SHEAR_SECTION]
    close(section.demand, expected["Vu"])
    close(section.capacity, expected["section"])
    assert str(section.status) == expected["section_status"]
    assert section.clause == oracle["section_clause"]
    close(checks[names.MINIMUM].demand, expected["As_min"])
    close(checks[names.MINIMUM].capacity, expected["As"])
    close(checks[names.SPACING].capacity, expected["spacing_max"])
    close(checks[names.CRACK].capacity, expected["crack"])
    close(checks[names.HORIZONTAL].demand, expected["horizontal_each_face"])
    close(checks[names.HORIZONTAL].capacity, expected["horizontal"])
    close(checks[names.HORIZONTAL_SPACING].capacity, expected["horizontal_max"])
    close(checks[names.FRONT].demand, expected["front_required"])
    close(checks[names.FRONT].capacity, expected["front"])
    close(checks[names.FRONT_SPACING].capacity, expected["front_max"])
    statuses = {name: str(checks[name].status) for name in (names.FLEXURE, names.STRAIN, names.MINIMUM, names.SPACING,
                                                             names.CRACK, names.SHEAR, names.HORIZONTAL, names.FRONT)}
    assert statuses == {names.FLEXURE: expected["flexure"], names.STRAIN: expected["strain"], names.MINIMUM: expected["minimum"],
                        names.SPACING: expected["spacing"], names.CRACK: expected["crack_status"], names.SHEAR: expected["shear"],
                        names.HORIZONTAL: expected["horizontal_status"], names.FRONT: expected["front_status"]}
    assert flexure.clause == oracle["strength_clause"]


def test_the_aci_table_governs_with_a_high_ratio() -> None:
    """Vc es el mayor de 13.3.6.1.1 y de la Tabla 22.5.5.1: con cuantía alta gobierna la tabla (D-173)."""
    item = next(case for case in _oracle("aci_318_25")["cases"] if case["id"] == "cuantia-alta")
    shear = next(check for check in _checks("aci_318_25", item) if check.name == names.SHEAR)
    vc = dict(shear.values)["Vc"]
    assert vc == pytest.approx(item["expected"]["Vc_table"], rel=1e-9)
    assert vc > 0.17 * 31.03**0.5 * 1000 * item["expected"]["d"]


def test_the_manual_example_2_stem_numbers() -> None:
    """ACI MNL-17(21), ejemplo 2 con la base de 24 in: Mu = 32 560 ft·lb/ft y Vu = 6105 lb/ft; con N.° 7 cada 9 in,
    φMn ≈ 517 in·kip/ft (el manual redondea d a 12.5 in; aquí d = 319.1 mm)."""
    item = next(case for case in _oracle("aci_318_25")["cases"] if case["id"] == "manual-ejemplo-2")
    checks = {check.name: check for check in _checks("aci_318_25", item)}
    ft_lb_per_ft, lb_per_ft = 1.3558179 / 0.3048 * 1e3, 4.4482216 / 0.3048  # → N·mm/m y N/m
    assert checks[names.FLEXURE].demand == pytest.approx(32560 * ft_lb_per_ft, rel=2e-3)
    assert checks[names.SHEAR].demand == pytest.approx(6105 * lb_per_ft, rel=2e-3)
    assert checks[names.FLEXURE].capacity == pytest.approx(517 * 112.98483 / 0.3048 * 1e3, rel=1e-2)
