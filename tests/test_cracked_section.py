"""Esfuerzo de servicio del acero en la sección fisurada elástica (mechanics.flexure.cracked_steel_stress) contra el oráculo
tests/oracles/mechanics/cracked_section.json, y su uso en las zapatas combinadas (D-174)."""

import json
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.flexure import CRACK_SPACING
from structurelab_rc.domain.footing.combined_beam import beam_case, long_beam_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases, combined_service_cases
from structurelab_rc.mechanics.flexure import SteelLayer, compression_strips, cracked_steel_stress
from structurelab_rc.model.project import Project
from structurelab_rc.setup import load_engine

ORACLE: dict[str, Any] = json.loads((Path(__file__).parent / "oracles" / "mechanics" / "cracked_section.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", ORACLE["cases"], ids=[case["id"] for case in ORACLE["cases"]])
def test_cracked_steel_stress_matches_the_oracle(case: dict[str, Any]) -> None:
    strips = compression_strips(case["bw"], case["h"], case["bf"], case["hf"], flange_in_compression=True)
    layers = tuple(SteelLayer(depth, area) for depth, area in case["layers"])
    fs = cracked_steel_stress(case["moment"], strips, layers, case["n"])
    assert fs == pytest.approx(case["expected"]["fs"], rel=ORACLE["tolerance_rel"])


def test_the_manual_toe_stress_is_5858_psi() -> None:
    case = next(case for case in ORACLE["cases"] if case["id"] == "rectangular-manual")
    assert case["expected"]["fs"] == pytest.approx(5858 * 0.00689476, rel=1e-2)


@pytest.mark.parametrize("profile", ["aci_318_25", "nsr_10"])
def test_combined_long_beam_cracking_uses_the_service_moment(profile: str) -> None:
    """La viga larga de la combinada rectangular (D-174): cada revisión de fisuración con fs calculado lleva el mayor momento
    de Wood-Armer de servicio de su signo en la misma x, de los casos de servicio declarados; sin él, fs = 2/3·fy."""
    project = Project.model_validate(json.loads(frozen(profile, "zapatas", "zapata_combinada.json").read_text(encoding="utf-8")))
    footing, soil = project.combined_footings[0], project.soil
    assert soil is not None and footing.beam is None
    basis = Basis(PROFILES[project.profile], project.materials, load_engine().bars, project.seismic.level)
    cases, _ = combined_factored_cases(footing, soil)
    services = [beam_case(footing, soil, pressure, loads) for pressure, loads in combined_service_cases(footing, soil)]
    assert services
    cracks = [check for check in long_beam_checks(basis, footing, soil, cases) if check.name == CRACK_SPACING]
    with_service = [check for check in cracks if "Ms" in dict(check.values)]
    assert with_service
    for check in with_service:
        assert check.z is not None
        ms = dict(check.values)["Ms"]
        x = check.z + footing.x_range[0]
        same_sign = [value for beam in services for value in beam.plate_moments(x) if value * ms > 0]
        assert ms == pytest.approx(max(same_sign, key=abs), rel=1e-12)
        cc, fs = dict(check.values)["cc"], dict(check.values)["fs calculado"]
        both = (basis.profile.flexure.crack_control_spacing(project.materials.fy, cc, fs),
                basis.profile.flexure.crack_control_spacing(project.materials.fy, cc))
        assert check.capacity == pytest.approx(max(both))  # la mayor de las dos permitidas (D-174)
