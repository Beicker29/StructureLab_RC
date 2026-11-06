import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.mechanics.flexure import SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN = 25.4
MPA_PER_KSI = 6.894757
NMM_PER_KIP_IN = 4448.2216152605 * MM_PER_IN

def _cases() -> list[Any]:
    params = []
    for profile, folder in FOLDERS.items():
        oracle = json.loads((ORACLES / folder / "wight_flexure.json").read_text(encoding="utf-8"))
        for case in oracle["cases"]:
            for quantity, value in case["expected"].items():
                tolerance = oracle.get("tolerance_overrides", {}).get(quantity, oracle["tolerance_rel"])
                params.append(pytest.param(profile, case, quantity, value, tolerance, id=f"{profile}-{case['id']}-{quantity}"))
    return params


def _computed(profile: str, case: dict[str, Any]) -> dict[str, float]:
    inch = case["units"] == "in"
    length, stress = (MM_PER_IN, MPA_PER_KSI) if inch else (1.0, 1.0)
    moment = NMM_PER_KIP_IN if inch else 1e6
    section = case["section"]
    bw, h = section["bw"] * length, section["h"] * length
    bf, hf = section.get("bf", section["bw"]) * length, section.get("hf", section["h"] / 2) * length
    layers = tuple(SteelLayer(d * length, area * length**2) for d, area in case["layers"])
    fc, fy, es = case["fc"] * stress, case["fy"] * stress, case["es"] * stress
    strips = compression_strips(bw, h, bf, hf, flange_in_compression=True)
    state = flexure_state(strips, layers, ConcreteBlock(fc, 0.85, case["beta1"], 0.003), SteelModel(fy, es))
    dt = case.get("dt", max(d for d, _ in case["layers"])) * length
    et = 0.003 * (dt - state.c) / state.c
    tension = [layer for layer in layers if layer.depth > h / 2]
    depth = sum(layer.depth * layer.area for layer in tension) / sum(layer.area for layer in tension)
    flexure = PROFILES[profile].flexure
    return {
        "a": state.a / length,
        "c": state.c / length,
        "et": et,
        "Mn": state.nominal_moment / moment,
        "phi": flexure.strength_reduction_moment(et, flexure.yield_strain(fy, es)),
        "As_min": flexure.min_flexural_reinforcement(fc, fy, bw, depth) / length**2,
    }


@pytest.mark.parametrize(("profile", "case", "quantity", "expected", "tolerance"), _cases())
def test_matches_wight(profile: str, case: dict[str, Any], quantity: str, expected: float, tolerance: float) -> None:
    assert _computed(profile, case)[quantity] == pytest.approx(expected, rel=tolerance)
