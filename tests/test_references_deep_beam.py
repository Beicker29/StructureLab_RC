"""Criterios de vigas de gran altura frente al ACI MNL-17(21), volumen 2, ejemplo de puntal-tensor 1, paso 11 (D-089).

Solo los criterios de ACI 9.9 / NSR-10 C.11.7 (límite de sección, refuerzo distribuido y su separación); el puntal-tensor
del ejemplo no se usa.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.deep import CURTAINS, LONGITUDINAL, SECTION, SPACING, TRANSVERSE
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.model.project import Materials, Member
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
MM_PER_IN, MPA_PER_PSI, N_PER_LB = 25.4, 6.894757e-3, 4.448222
BARS = load_engine().bars
COVER_IN = 1.5


def _example(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "references_deep_beam.json").read_text(encoding="utf-8"))
    return dict(data["mnl_14_1"])


def _member(data: dict[str, Any]) -> Member:
    """La viga del ejemplo: tres capas de 4 #9 abajo (el tensor), 2 #9 arriba y la malla de cada cara: estribos #5 de dos
    ramas a 9 in y capas horizontales de 2 #5 a 9 in desde la capa superior del tensor hacia arriba."""
    h = data["h_in"] * MM_PER_IN
    web = data["web"]
    step = web["spacing_in"] * MM_PER_IN
    ties = [h - level * MM_PER_IN for level in data["tie_layers_from_bottom_in"]]
    layers: list[dict[str, Any]] = [{"depth": 3.0 * MM_PER_IN, "role": "flexure", "bars": ["#9", "#9"]}]
    depth = min(ties) - step
    while depth > 3.0 * MM_PER_IN + 1.0:
        layers.append({"depth": depth, "role": "skin", "bars": [web["designation"]] * 2})
        depth -= step
    layers += [{"depth": tie, "role": "flexure", "bars": [data["tie_designation"]] * data["tie_bars_per_layer"]} for tie in sorted(ties)]
    layers.sort(key=lambda layer: layer["depth"])
    return Member.model_validate({
        "id": "MNL-14-1", "type": "beam", "deep_beam": True, "length": 302.0 * MM_PER_IN,
        "section": {"bw": data["bw_in"] * MM_PER_IN, "h": h, "cover": COVER_IN * MM_PER_IN},
        "stations": [{"z": 0.0, "layout": {"layers": layers, "stirrups": {"designation": web["designation"], "legs": 2, "spacing": step,
                                                                         "closed": True}},
                      "demands": {"Pu_kN": 0.0, "Mu_kNm": 456.0 * 90.0 * 0.112985, "M2_kNm": 0.0, "Vu_kN": data["Vu_kips"] * 4.448222,
                                  "V3_kN": 0.0, "Tu_kNm": 0.0}}]})


@pytest.mark.parametrize("profile", list(FOLDERS))
def test_deep_beam_criteria_match_the_handbook(profile: str) -> None:
    example = _example(FOLDERS[profile])
    data, printed = example["data"], example["printed"]
    materials = Materials.model_validate({"fc": data["fc_psi"] * MPA_PER_PSI, "fy": data["fy_psi"] * MPA_PER_PSI,
                                          "fyt": data["fy_psi"] * MPA_PER_PSI, "concrete": "normalweight", "coating": "uncoated"})
    member = _member(data)
    checks = {check.name: check for check in station_checks(PROFILES[profile], materials, member, member.stations[0], BARS)}
    bw = member.section.bw
    # Refuerzo distribuido: el libro imprime 0.00287 con 0.31 in²; el #5 del catálogo tiene 199 mm² (0.5 % menos).
    transverse = checks[TRANSVERSE]
    assert transverse.status is Status.PASS
    assert transverse.capacity / bw == pytest.approx(printed["Av_over_bws"], rel=0.01)  # type: ignore[operator]
    assert transverse.demand / bw == pytest.approx(printed["min_ratio"], rel=1e-12)  # type: ignore[operator]
    longitudinal = checks[LONGITUDINAL]
    assert longitudinal.status is Status.PASS
    step = data["web"]["spacing_in"] * MM_PER_IN
    assert longitudinal.capacity / (bw * step) == pytest.approx(printed["Avh_over_bws2"], rel=0.01)  # type: ignore[operator]
    # Separación: s = s2 = 9 in frente a la menor entre d/5 y 300 mm (el libro, en unidades inglesas, 12 in).
    spacing = checks[SPACING]
    assert spacing.status is Status.PASS
    assert spacing.demand == pytest.approx(step)
    assert spacing.capacity == pytest.approx(min(printed["d_in"] * MM_PER_IN / 5, 300.0))
    # Límite de sección: el paquete usa φ = 0.75; el libro, φ = 0.85. Se compara la capacidad nominal (±0.2 %).
    section = checks[SECTION]
    assert section.status is Status.PASS
    phi = dict(section.values)["phi"]
    assert dict(section.values)["d"] == pytest.approx(printed["d_in"] * MM_PER_IN, rel=1e-9)
    nominal_book = printed["phi_Vn_limit_lb"] / printed["phi_used"] * N_PER_LB
    assert section.capacity / phi == pytest.approx(nominal_book, rel=0.002)  # type: ignore[operator]
    if profile == "aci-318-25":
        assert checks[CURTAINS].status is Status.PASS  # dos cortinas, una por cara, a menos de 600 mm
