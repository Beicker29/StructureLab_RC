"""Base del muro en voladizo (D-173, fase A, etapa 4) contra el oráculo independiente
tests/oracles/<perfil>/derived_wall_base.json, y el desarrollo del ejemplo 2 del manual ACI MNL-17(21) contra sus números."""

import json
from pathlib import Path
from typing import Any

import pytest
from wall_inputs import bars

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.retaining_wall import base as names
from structurelab_rc.domain.retaining_wall.base import base_checks
from structurelab_rc.domain.retaining_wall.thrust import stability_thrust
from structurelab_rc.mechanics.flexure import cracked_steel_stress
from structurelab_rc.model.project import Materials
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci_318_25": "aci-318-25", "nsr_10": "nsr-10"}
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_wall_base.json").read_text(encoding="utf-8"))
    return data


def _checks(folder: str, item: dict[str, Any]) -> dict[str, Check]:
    oracle = _oracle(folder)
    given = item["wall"]
    reinforcement = {group: {key: bars(value["designation"], value["spacing"], value["end"]) for key, value in given[group].items()}
                     for group in ("stem", "base")}
    own = RetainingWall.model_validate({**given, **reinforcement, "id": "M1", "quantity": 1,
                                        "cases": [item["service"], item["factored"]]})
    soil = RetainingSoil.model_validate({"unit_weight_concrete_kNm3": oracle["unit_weight_concrete_kNm3"], **item["soil"]})
    materials = Materials(fc=oracle["fc"], fy=oracle["fy"], fyt=oracle["fy"], concrete="normalweight", coating="uncoated")
    basis = Basis(PROFILES[FOLDERS[folder]], materials, BARS, "none" if folder == "aci_318_25" else "DMI")
    return {check.name: check for check in base_checks(basis, own, soil, stability_thrust(own, soil))}


CASES = [(folder, item["id"]) for folder in FOLDERS for item in _oracle(folder)["cases"]]


@pytest.mark.parametrize(("folder", "case_id"), CASES)
def test_base_matches_the_oracle(folder: str, case_id: str) -> None:
    oracle = _oracle(folder)
    item = next(case for case in oracle["cases"] if case["id"] == case_id)
    expected, tolerance = item["expected"], oracle["tolerance_rel"]
    checks = _checks(folder, item)

    def close(actual: float | None, value: float) -> None:
        assert actual == pytest.approx(value, rel=tolerance, abs=1e-6)

    for part, label in (("heel", names.HEEL), ("toe", names.TOE)):
        own = expected[part]
        flexure, shear, crack = (checks[f"{name} {label}"] for name in ("Flexion", "Cortante", "Separacion por agrietamiento"))
        close(flexure.demand, own["Mu"])
        close(flexure.capacity, own["phiMn"])
        close(checks[f"Deformacion neta de traccion {label}"].capacity, own["et"])
        close(shear.demand, own["Vu"])
        close(shear.capacity, own["phiVc"])
        close(checks[f"Dimensiones de la seccion por cortante {label}"].capacity, own["section"])
        assert checks[f"Dimensiones de la seccion por cortante {label}"].clause == oracle["section_clause"]
        close(dict(crack.values)["Ms"], own["Ms"])
        close(dict(crack.values)["fs"], own["fs"])
        close(crack.capacity, own["crack"])
        close(checks[f"Acero minimo {label}"].demand, own["As_min"])
        close(checks[f"Acero minimo {label}"].capacity, own["As"])
        close(checks[f"Separacion maxima {label}"].capacity, own["spacing_max"])
        assert (str(flexure.status), str(shear.status), str(crack.status)) == (own["flexure"], own["shear"], own["crack_status"])
    close(checks[names.LONGITUDINAL].demand, expected["longitudinal"]["required"])
    close(checks[names.LONGITUDINAL].capacity, expected["longitudinal"]["provided"])
    close(checks[names.LONGITUDINAL_SPACING].capacity, expected["longitudinal"]["spacing_max"])
    close(checks[names.DEPTH].capacity, expected["depth"])
    for key, name in (("dowel", names.DOWEL), ("heel", names.HEEL_DEVELOPMENT), ("toe", names.TOE_DEVELOPMENT)):
        required, available = expected["development"][key]
        close(checks[name].demand, required)
        close(checks[name].capacity, available)


def test_the_manual_example_2_development() -> None:
    """ACI MNL-17(21), ejemplo 2: ℓd de las barras superiores del talón 30.5 in y de las inferiores de la puntera 23.5 in
    (N.° 7, ψt = 1.3 arriba); la longitud disponible de los ganchos de arranque, 24 − 3 = 21 in. El ℓdh difiere: el manual
    usa el 318-19 (15.0 in) y aquí la ecuación del 318-25 (D-066)."""
    item = next(case for case in _oracle("aci_318_25")["cases"] if case["id"] == "manual-ejemplo-2")
    checks = _checks("aci_318_25", item)
    assert checks[names.HEEL_DEVELOPMENT].demand == pytest.approx(30.5 * 25.4, rel=1e-2)
    assert checks[names.TOE_DEVELOPMENT].demand == pytest.approx(23.5 * 25.4, rel=1e-2)
    assert checks[names.DOWEL].capacity == pytest.approx(21 * 25.4)


def test_the_manual_toe_service_stress() -> None:
    """ACI MNL-17(21), ejemplo 2: con Ms = 7500 ft·lb/ft, N.° 7 cada 9 in y d = 20.56 in, fs = 5858 psi (n = 7.6)."""
    lb_ft = 1.3558179e3 / 0.3048  # ft·lb/ft → N·mm/m
    fs = cracked_steel_stress(7500 * lb_ft, 1000.0, 20.56 * 25.4, 0.8 * 645.16 / 0.3048, 200000 / (4700 * 31.03**0.5))
    assert fs == pytest.approx(5858 * 0.00689476, rel=1e-2)
