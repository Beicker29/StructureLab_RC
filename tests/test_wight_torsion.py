import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN = 25.4
MPA_PER_KSI = 6.894757
N_PER_KIP = 4448.2216152605


def _computed(profile: str, case: dict[str, Any]) -> dict[str, float]:
    torsion, shear = PROFILES[profile].torsion, PROFILES[profile].shear
    fc, fy, fyt = case["fc"] * MPA_PER_KSI, case["fy"] * MPA_PER_KSI, case["fyt"] * MPA_PER_KSI
    bw, h, d = case["bw"] * MM_PER_IN, case["h"] * MM_PER_IN, case["d"] * MM_PER_IN
    vu, tu = case["Vu"] * N_PER_KIP, case["Tu_kip_ft"] * 12 * N_PER_KIP * MM_PER_IN
    inset = (2 * case["cover"] + case["stirrup_diameter"]) * MM_PER_IN
    x1, y1 = bw - inset, h - inset
    aoh, ph = x1 * y1, 2 * (x1 + y1)
    a0, acp, pcp = 0.85 * aoh, bw * h, 2 * (bw + h)
    phi = torsion.strength_reduction()
    vc = shear.concrete_shear(fc=fc, lam=1.0, bw=bw, d=d, h=h, rho_w=0.0, nu=0.0, ag=acp, vu=0.0, mu=1.0, av_ge_min=True)
    at_s = torsion.required_transverse(tu, a0, fyt)
    av_s = (vu / phi - vc) / (fyt * d)
    psi = MPA_PER_KSI / 1000
    return {
        "phi_Tth": phi * torsion.threshold_torsion(fc, 1.0, acp, pcp, 0.0, acp) / (N_PER_KIP * MM_PER_IN),
        "Aoh": aoh / MM_PER_IN**2,
        "ph": ph / MM_PER_IN,
        "Vc": vc / N_PER_KIP,
        "combined_stress": torsion.combined_stress(vu, tu, bw, d, ph, aoh) / psi,
        "combined_limit": torsion.combined_stress_limit(vc, fc, bw, d) / psi,
        "At_s": at_s / MM_PER_IN,
        "Av_s": av_s / MM_PER_IN,
        "Av_plus_2At_s": (av_s + 2 * at_s) / MM_PER_IN,
        "min_transverse": torsion.min_transverse(fc, bw, fyt) / MM_PER_IN,
        "s_max": torsion.max_spacing(ph) / MM_PER_IN,
        "Al": torsion.required_longitudinal(tu, at_s, a0, ph, fyt, fy) / MM_PER_IN**2,
        "Al_min": torsion.min_longitudinal(fc, acp, fy, at_s, ph, fyt, bw) / MM_PER_IN**2,
    }


def _cases() -> list[Any]:
    params = []
    for profile, folder in FOLDERS.items():
        oracle = json.loads((ORACLES / folder / "wight_torsion.json").read_text(encoding="utf-8"))
        for case in oracle["cases"]:
            for quantity, value in case["expected"].items():
                tolerance = oracle["tolerance_overrides"].get(quantity, oracle["tolerance_rel"])
                params.append(pytest.param(profile, case, quantity, value, tolerance, id=f"{profile}-{case['id']}-{quantity}"))
    return params


@pytest.mark.parametrize(("profile", "case", "quantity", "expected", "tolerance"), _cases())
def test_matches_wight(profile: str, case: dict[str, Any], quantity: str, expected: float, tolerance: float) -> None:
    assert _computed(profile, case)[quantity] == pytest.approx(expected, rel=tolerance)
