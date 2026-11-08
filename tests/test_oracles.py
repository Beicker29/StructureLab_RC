import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import nominal_flexure, steel_layers
from structurelab_rc.mechanics.flexure import FlexureState, SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel
from structurelab_rc.model.project import Demands, Materials, Section
from structurelab_rc.model.reinforcement import ReinforcementLayout
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN = 25.4
MPA_PER_PSI = 6.894757e-3


def _oracle(folder: str, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / name).read_text(encoding="utf-8"))
    return data


MNL = _oracle("aci_318_25", "mnl17_flexure.json")


@pytest.mark.parametrize("case", MNL["cases"], ids=lambda case: case["id"])
def test_mechanics_matches_handbook(case: dict[str, Any]) -> None:
    strips = compression_strips(
        case["bw_in"] * MM_PER_IN,
        case["h_in"] * MM_PER_IN,
        case["bf_in"] * MM_PER_IN,
        case["hf_in"] * MM_PER_IN,
        flange_in_compression=case["flange_in_compression"],
    )
    layers = (SteelLayer(case["d_in"] * MM_PER_IN, case["area_in2"] * MM_PER_IN**2),)
    concrete = ConcreteBlock(MNL["fc_psi"] * MPA_PER_PSI, MNL["stress_factor"], MNL["beta1"], MNL["max_strain"])
    steel = SteelModel(MNL["fy_psi"] * MPA_PER_PSI, MNL["es_psi"] * MPA_PER_PSI)

    state = flexure_state(strips, layers, concrete, steel)

    expected = case["expected"]
    tolerance = MNL["tolerance_rel"]
    assert state.a / MM_PER_IN == pytest.approx(expected["a_in"], rel=tolerance)
    assert state.c / MM_PER_IN == pytest.approx(expected["c_in"], rel=tolerance)
    assert state.extreme_strain == pytest.approx(expected["extreme_strain"], rel=tolerance)


DERIVED = [
    pytest.param(profile, case, id=f"{profile}-{case['id']}")
    for profile, folder in FOLDERS.items()
    for case in _oracle(folder, "derived_flexure.json")["cases"]
]


@pytest.mark.parametrize(("profile", "case"), DERIVED)
def test_profile_flexure_matches_closed_form(profile: str, case: dict[str, Any]) -> None:
    layout = ReinforcementLayout.model_validate({"layers": case["layers"], "stirrups": None})
    layers = steel_layers(layout, load_engine().bars)
    assert isinstance(layers, tuple)
    materials = Materials(fc=case["fc"], fy=case["fy"], fyt=420.0, concrete="normalweight", coating="uncoated")
    geometry = dict(case["section"])
    bf = geometry.pop("bf", None)
    if bf is not None:
        geometry |= {"overhang_x_neg": (bf - geometry["bw"]) / 2, "overhang_x_pos": (bf - geometry["bw"]) / 2}
    section = Section.model_validate(geometry | {"cover": 40.0})

    demands = Demands.model_validate({"Mu_kNm": 1.0 if case["top_in_compression"] else -1.0, "Pu_kN": case.get("Pu_N", 0.0) / 1e3})

    state = nominal_flexure(PROFILES[profile], materials, section, layers, demands)

    assert isinstance(state, FlexureState)
    expected = case["expected"]
    tolerance = _oracle(FOLDERS[profile], "derived_flexure.json")["tolerance_rel"]
    assert state.c == pytest.approx(expected["c"], rel=tolerance)
    assert state.a == pytest.approx(expected["a"], rel=tolerance)
    assert state.extreme_strain == pytest.approx(expected["extreme_strain"], rel=tolerance)
    assert state.nominal_moment == pytest.approx(expected["Mn_Nmm"], rel=tolerance)


@pytest.mark.parametrize(("profile", "folder"), FOLDERS.items())
def test_strength_assumptions_match_the_code(profile: str, folder: str) -> None:
    oracle = _oracle(folder, "strength_assumptions.json")
    assumptions = PROFILES[profile].strength_assumptions
    assert assumptions.max_concrete_strain() == oracle["max_concrete_strain"]
    assert assumptions.stress_block_factor() == oracle["stress_block_factor"]
    assert assumptions.steel_modulus() == oracle["steel_modulus"]
    for row in oracle["beta1"]:
        value = assumptions.beta1(row["fc"])
        if row["value"] is None:
            assert value is None
        else:
            assert value == pytest.approx(row["value"], rel=1e-12)
    assert sorted(PROFILES[profile].seismic.seismic_levels()) == oracle["seismic_levels"]
    for row in oracle["phi_moment_ety_0.0021"]:
        assert PROFILES[profile].flexure.strength_reduction_moment(row["et"], 0.0021) == pytest.approx(row["value"], rel=1e-12)


DERIVED_SHEAR = [
    pytest.param(profile, case, id=f"{profile}-{case['id']}")
    for profile, folder in FOLDERS.items()
    for case in _oracle(folder, "derived_shear.json")["cases"]
]


@pytest.mark.parametrize(("profile", "case"), DERIVED_SHEAR)
def test_concrete_shear_matches_hand_derivation(profile: str, case: dict[str, Any]) -> None:
    vc = PROFILES[profile].shear.concrete_shear(
        fc=case["fc"], lam=1.0, bw=case["bw"], d=case["d"], h=case["h"], rho_w=case["rho_w"], nu=case["nu"], ag=case["ag"],
        vu=case["vu"], mu=case["mu"], av_ge_min=case["av_ge_min"],
    )
    assert vc == pytest.approx(case["expected_Vc_N"], rel=1e-9)
