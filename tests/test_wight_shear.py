import json
import math
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN = 25.4
MPA_PER_KSI = 6.894757
N_PER_KIP = 4448.2216152605


def _units(case: dict[str, Any]) -> tuple[float, float, float]:
    """Factores de longitud, esfuerzo y fuerza hacia mm, MPa y N."""
    return (MM_PER_IN, MPA_PER_KSI, N_PER_KIP) if case["units"] == "in" else (1.0, 1.0, 1e3)


def _computed(profile: str, case: dict[str, Any]) -> dict[str, float]:
    length, stress, force = _units(case)
    shear = PROFILES[profile].shear
    fc, fyt = case["fc"] * stress, case["fyt"] * stress
    bw, d = case["bw"] * length, case["d"] * length
    vc = shear.concrete_shear(fc=fc, lam=1.0, bw=bw, d=d, h=2 * d, rho_w=0.0, nu=0.0, ag=2 * bw * d, vu=0.0, mu=1.0, av_ge_min=True)
    expected = case["expected"]
    values = {
        "Vc": vc / force,
        "Vu_over_phi_max": (vc + shear.max_steel_shear(fc, bw, d)) / force,
        "half_spacing_threshold": (vc + 0.33 * math.sqrt(fc) * bw * d) / force,
        "s_max_Av_min": expected.get("Av_s_max", 0.0) * length**2 / shear.min_shear_reinforcement(fc, bw, fyt) / length,
    }
    threshold = shear.min_reinforcement_threshold(vc, fc, 1.0, bw, d, False)
    if threshold is not None and profile == "aci-318-25":
        values["Av_min_threshold"] = threshold / shear.strength_reduction() / force
    for index, (av, _) in enumerate(expected.get("s_strength", [])):
        values[f"s_strength_{index}"] = shear.steel_shear(av * length**2, fyt, d, 1.0) / (case["vu_over_phi"] * force - vc) / length
    for index, (av, s, _) in enumerate(expected.get("Vs", [])):
        values[f"Vs_{index}"] = shear.steel_shear(av * length**2, fyt, d, s * length) / force
    return values


def _expected(case: dict[str, Any]) -> dict[str, float]:
    flat = {key: value for key, value in case["expected"].items() if not isinstance(value, list) and key != "Av_s_max"}
    for index, (_, s) in enumerate(case["expected"].get("s_strength", [])):
        flat[f"s_strength_{index}"] = s
    for index, (_, _, vs) in enumerate(case["expected"].get("Vs", [])):
        flat[f"Vs_{index}"] = vs
    return flat


def _cases() -> list[Any]:
    params = []
    for profile, folder in FOLDERS.items():
        oracle = json.loads((ORACLES / folder / "wight_shear.json").read_text(encoding="utf-8"))
        for case in oracle["cases"]:
            for quantity, value in _expected(case).items():
                if quantity == "Av_min_threshold" and profile == "nsr-10":
                    continue
                family = quantity.rsplit("_", 1)[0] if quantity[-1].isdigit() else quantity
                tolerance = oracle.get("tolerance_overrides", {}).get(family, oracle["tolerance_rel"])
                params.append(pytest.param(profile, case, quantity, value, tolerance, id=f"{profile}-{case['id']}-{quantity}"))
    return params


@pytest.mark.parametrize(("profile", "case", "quantity", "expected", "tolerance"), _cases())
def test_matches_wight(profile: str, case: dict[str, Any], quantity: str, expected: float, tolerance: float) -> None:
    assert _computed(profile, case)[quantity] == pytest.approx(expected, rel=tolerance)
