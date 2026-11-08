"""Ejemplo 15-3 de Wight (zapata cuadrada) frente a la flexión de zapatas en los dos perfiles (D-014, D-015, D-062)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.shear import PUNCHING, shear_checks
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN, MM_PER_FT, KN_PER_KIP, MPA_PER_PSI = 25.4, 304.8, 4.448222, 6.894757e-3
N_PER_KIP = KN_PER_KIP * 1000
KNM_PER_KIPFT = KN_PER_KIP * MM_PER_FT / 1000


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "wight_footing.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("profile", FOLDERS)
def test_square_footing_flexure_matches_wight(profile: str) -> None:
    oracle = _oracle(FOLDERS[profile])
    data, expected = oracle["data"], oracle["expected"]
    tolerance = oracle["tolerance_rel"]
    side, column = data["side_ft"] * MM_PER_FT, data["column_in"] * MM_PER_IN
    mat = {"designation": data["bar"], "spacing": data["spacing_mm"]}
    footing = Footing.model_validate({
        "id": "Z", "lx": side, "ly": side, "h": data["h_in"] * MM_PER_IN, "cover": data["cover_in"] * MM_PER_IN,
        "fill_height": 0.0, "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
        "column": {"cx": column, "cy": column, "offset_x": 0.0, "offset_y": 0.0},
        "bottom": {"first": "x", "end": "straight", "x": mat, "y": mat}, "top": None,
        # Wight trabaja con la presión neta de la columna: sin pesos propios (factores en cero).
        "loads": [{"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 0.0, "live_factor": 0.0,
                   "P_kN": data["Pu_kips"] * KN_PER_KIP, "Vx_kN": 0.0, "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": 0.0}],
    })
    soil = Soil.model_validate({"allowable_pressure_kPa": 287.0, "min_contact_fraction": 0.5,
                                "unit_weight_concrete_kNm3": 23.6, "unit_weight_fill_kNm3": 18.9,
                                "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                                "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                                "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                                "overturning_safety_factor_seismic": 1.5})
    materials = Materials.model_validate({"fc": data["fc_psi"] * MPA_PER_PSI, "fy": data["fy_psi"] * MPA_PER_PSI,
                                          "fyt": data["fy_psi"] * MPA_PER_PSI, "concrete": "normalweight", "coating": "uncoated"})

    cases, _ = factored_cases(footing, soil)
    checks = {check.name: check for check in flexure_checks(PROFILES[profile], materials, footing, cases, load_engine().bars)}

    for direction in ("x", "y"):
        strength = checks[f"Flexion malla inferior (barras {direction})"]
        assert strength.demand is not None and strength.capacity is not None
        assert strength.demand / 1e6 / KNM_PER_KIPFT == pytest.approx(expected["Mu_kipft"], rel=tolerance)
        phi_tolerance = oracle["tolerance_overrides"]["phi_Mn_kipft"]
        assert strength.capacity / 1e6 / KNM_PER_KIPFT == pytest.approx(expected["phi_Mn_kipft"], rel=phi_tolerance)
        minimum = checks[f"Acero minimo malla inferior (barras {direction})"]
        assert minimum.demand is not None and minimum.capacity is not None
        assert minimum.demand / MM_PER_IN**2 == pytest.approx(expected["As_min_in2"], rel=tolerance)
        assert minimum.capacity / MM_PER_IN**2 == pytest.approx(expected["As_in2"], rel=tolerance)
        assert minimum.capacity == pytest.approx(expected["bars"] * 510.0)  # #8: 510 mm²
        assert str(minimum.status) == "PASS"

    overrides = oracle["tolerance_overrides"]
    shear = {check.name: check for check in shear_checks(PROFILES[profile], materials, footing, cases, load_engine().bars)}
    for direction in ("x", "y"):
        one_way = shear[f"Cortante en una direccion (barras {direction})"]
        assert one_way.demand is not None and one_way.capacity is not None
        assert one_way.demand / N_PER_KIP == pytest.approx(expected["one_way_Vu_kips"], rel=overrides["one_way_Vu_kips"])
        assert one_way.capacity / N_PER_KIP == pytest.approx(expected["one_way_phi_Vc_kips"], rel=overrides["one_way_phi_Vc_kips"])
    punching = shear[PUNCHING]
    values = dict(punching.values)
    assert values["Vu"] / N_PER_KIP == pytest.approx(expected["punching_Vu_kips"], rel=tolerance)
    assert values["b0"] / MM_PER_IN == pytest.approx(expected["punching_b0_in"], rel=tolerance)
    assert punching.demand is not None and punching.capacity is not None
    assert punching.demand / MPA_PER_PSI == pytest.approx(expected["punching_vu_psi"], rel=tolerance)
    assert punching.capacity / MPA_PER_PSI == pytest.approx(expected["punching_phi_vc_psi"], rel=tolerance)
