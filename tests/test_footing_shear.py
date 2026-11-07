"""V3D.2: cortante en una dirección y punzonamiento de zapatas contra el oráculo independiente (D-059, D-063)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.shear import shear_checks
from structurelab_rc.mechanics.perimeter import critical_perimeter
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_footing_shear.json").read_text(encoding="utf-8"))
    return data


CASES = [pytest.param(profile, case, id=f"{profile}-{case['id']}")
         for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("profile", "case"), CASES)
def test_shear_checks_match_oracle(profile: str, case: dict[str, Any]) -> None:
    oracle = _oracle(FOLDERS[profile])
    footing = Footing.model_validate(case["footing"])
    cases, _ = factored_cases(footing, Soil.model_validate(oracle["soil"]))
    checks = shear_checks(PROFILES[profile], Materials.model_validate(oracle["materials"]), footing, cases, BARS)
    got = {(check.name, check.case): check for check in checks}
    expected = {(item["name"], item["case"]): item for item in case["expected"]}
    assert set(got) == set(expected)
    tolerance = oracle["tolerance_rel"]
    for key, item in expected.items():
        check = got[key]
        assert str(check.status) == item["status"], key
        assert check.demand == pytest.approx(item["demand"], rel=tolerance), key
        assert check.capacity == pytest.approx(item["capacity"], rel=tolerance), key
        if key[0] == "Punzonamiento":
            values = dict(check.values)
            assert values["alpha s"] == item["alpha_s"]
            assert values["b0"] == pytest.approx(item["b0"], rel=tolerance)
            assert check.clause == oracle["clauses"]["punching"]
        if key[0].startswith("Cortante"):
            assert check.clause == oracle["clauses"]["one_way"]


def test_interior_polar_property_matches_aci_commentary() -> None:
    """R8.4.4.2.3: Jc = d(c1 + d)³/6 + (c1 + d)d³/6 + d(c2 + d)(c1 + d)²/2 para la columna interior."""
    c1, c2, d = 600.0, 400.0, 500.0
    perimeter = critical_perimeter((0.0, 0.0), c1, c2, d, ((-5000.0, -5000.0), (5000.0, 5000.0)))
    b1, b2 = c1 + d, c2 + d
    assert perimeter.outside == 0
    assert perimeter.length == pytest.approx(2 * (b1 + b2))
    assert perimeter.polar(0) == pytest.approx(d * b1**3 / 6 + b1 * d**3 / 6 + d * b2 * b1**2 / 2)
    assert perimeter.polar(1) == pytest.approx(d * b2**3 / 6 + b2 * d**3 / 6 + d * b1 * b2**2 / 2)


@pytest.mark.parametrize(("centre", "outside", "length"), [((1200.0, 0.0), 1, 900.0 + 2 * 750.0), ((1200.0, 1200.0), 2, 750.0 + 750.0)])
def test_edge_and_corner_perimeters_drop_outside_sides(centre: tuple[float, float], outside: int, length: float) -> None:
    """Base de 3000 × 3000: columna de 400 con d = 500 cerca del borde +X (un lado fuera) o de la esquina (dos lados)."""
    perimeter = critical_perimeter(centre, 400.0, 400.0, 500.0, ((-1500.0, -1500.0), (1500.0, 1500.0)))
    assert perimeter.outside == outside
    assert perimeter.length == pytest.approx(length)
