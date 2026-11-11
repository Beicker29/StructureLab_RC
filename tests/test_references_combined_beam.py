"""Viga larga de zapatas combinadas frente a Wight 15-6 y al ejemplo 5 del ACI MNL-17(21) en los dos perfiles (D-080)."""

import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.combined_beam import beam_case, long_beam_checks
from structurelab_rc.domain.footing.combined_columns import column_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Soil
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
LEVELS = {"aci-318-25": "special", "nsr-10": "DES"}
MM_PER_IN, MM_PER_FT, KN_PER_KIP, MPA_PER_PSI = 25.4, 304.8, 4.448222, 6.894757e-3
N_PER_KIP = KN_PER_KIP * 1000
NMM_PER_KIPFT = KN_PER_KIP * MM_PER_FT * 1000
BAR_AREA = {"#8": 510.0, "#9": 645.0}
SOIL = Soil.model_validate({"allowable_pressure_kPa": 240.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 23.6,
                            "unit_weight_fill_kNm3": 18.9, "friction_coefficient": 0.45, "adhesion_kPa": 0.0,
                            "passive_coefficient": 3.0, "cohesion_kPa": 0.0, "passive_factor": 0.5,
                            "sliding_safety_factor": 1.5, "sliding_safety_factor_seismic": 1.1,
                            "overturning_safety_factor": 2.0, "overturning_safety_factor_seismic": 1.5})


def _example(folder: str, name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "references_combined_beam.json").read_text(encoding="utf-8"))
    return dict(data[name])


def _footing(data: dict[str, Any]) -> CombinedFooting:
    """Presión neta de las columnas, como los libros: sin pesos propios ni sobrecargas (factores de peso en cero)."""
    lx = data["lx_in"] * MM_PER_IN
    columns = []
    for column in data["columns"]:
        item: dict[str, Any] = {
            "id": column["id"], "cx": column["cx_in"] * MM_PER_IN, "cy": column["cy_in"] * MM_PER_IN,
            "x": column["x_from_edge_in"] * MM_PER_IN - lx / 2, "y": 0.0,
            "loads": [{"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 0.0, "live_factor": 0.0,
                       "P_kN": column["Pu_kips"] * KN_PER_KIP, "Vx_kN": 0.0, "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": 0.0}]}
        if "band" in column:
            item["band"] = {"designation": column["band"]["designation"], "spacing": column["band"]["spacing_mm"]}
        if "dowels" in column:
            item["dowels"] = column["dowels"]
        columns.append(item)
    y_bars = data.get("bottom_y", {"designation": "#5", "spacing_mm": 300.0})
    bottom = {"designation": data["bottom"]["designation"], "spacing": data["bottom"]["spacing_mm"]}
    return CombinedFooting.model_validate({
        "id": "ZC", "lx": lx, "ly": data["ly_in"] * MM_PER_IN, "h": data["h_in"] * MM_PER_IN,
        "cover": data["cover_in"] * MM_PER_IN, "fill_height": 0.0, "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0,
        "surcharge_live_kNm2": 0.0, "columns": columns,
        "bottom": {"first": "x", "end": "straight", "x": bottom,
                   "y": {"designation": y_bars["designation"], "spacing": y_bars["spacing_mm"]}},
        "top": {"designation": data["top"]["designation"], "spacing": data["top"]["spacing_mm"]}})


def _checks(profile: str, data: dict[str, Any]) -> tuple[CombinedFooting, list[Check]]:
    footing = _footing(data)
    materials = Materials.model_validate({"fc": data["fc_psi"] * MPA_PER_PSI, "fy": data["fy_psi"] * MPA_PER_PSI,
                                          "fyt": data["fy_psi"] * MPA_PER_PSI, "concrete": "normalweight",
                                          "coating": "uncoated"})
    cases, failures = combined_factored_cases(footing, SOIL)
    assert not failures
    basis = Basis(PROFILES[profile], materials, load_engine().bars, LEVELS[profile])
    return footing, [*long_beam_checks(basis, footing, SOIL, cases), *column_checks(basis, footing, SOIL, cases)]


def _beam(checks: list[Check]) -> list[Check]:
    """Las verificaciones de la viga larga (las de las franjas y las columnas llevan la columna en la nota)."""
    return [check for check in checks if not check.note.startswith(("Franja", "Columna"))]


def _strip(checks: list[Check], column: str, name: str) -> Check:
    """La verificación de la cara de la franja transversal de la columna (las dos caras dan lo mismo sin Mx)."""
    title = f"Franja transversal de la columna {column}, cara"
    return max((check for check in checks if check.name == name and check.note.startswith(title)), key=lambda check: check.demand or 0.0)


def _at_column(checks: list[Check], column: str, name: str) -> Check:
    return next(check for check in checks if check.name == name and check.note == f"Columna {column}")


def _at_negative_moment(checks: list[Check]) -> dict[str, Check]:
    """Las verificaciones de la estación del mayor momento negativo de la viga larga (la que tracciona las barras
    superiores)."""
    checks = _beam(checks)
    strength = max((check for check in checks if check.name == "Flexion: resistencia"), key=lambda check: check.demand or 0.0)
    return {check.name: check for check in checks if check.z == strength.z}


def _governing_shear(checks: list[Check]) -> Check:
    return max((check for check in _beam(checks) if check.name == "Cortante: resistencia"),
               key=lambda check: (check.demand or 0.0) / (check.capacity or 1.0))


@pytest.mark.parametrize("profile", FOLDERS)
def test_long_beam_matches_wight_15_6(profile: str) -> None:
    example = _example(FOLDERS[profile], "wight_15_6")
    data, expected, tolerance = example["data"], example["expected"], example["tolerance_rel"]
    _, checks = _checks(profile, data)
    station = _at_negative_moment(checks)
    top = station["Flexion: resistencia"]
    assert top.demand is not None and top.capacity is not None
    assert top.demand / NMM_PER_KIPFT == pytest.approx(expected["Mu_negative_kipft"], rel=tolerance["Mu_negative_kipft"])
    assert top.capacity / NMM_PER_KIPFT == pytest.approx(expected["phi_Mn_negative_kipft"],
                                                         rel=tolerance["phi_Mn_negative_kipft"])
    minimum = station["Flexion: acero minimo (M3)"]
    assert minimum.capacity == pytest.approx(data["top"]["bars"] * BAR_AREA[data["top"]["designation"]])
    assert dict(minimum.values)["As,min"] / MM_PER_IN**2 == pytest.approx(expected["As_min_in2"], rel=tolerance["As_min_in2"])
    shear = _governing_shear(checks)
    assert shear.demand is not None and shear.capacity is not None
    assert str(shear.status) == expected["one_way_shear"]
    assert shear.demand / N_PER_KIP == pytest.approx(expected["one_way_Vu_kips"], rel=tolerance["one_way_Vu_kips"])
    assert shear.capacity / N_PER_KIP == pytest.approx(expected["one_way_phi_Vc_kips"],
                                                       rel=tolerance["one_way_phi_Vc_kips"][FOLDERS[profile]])


@pytest.mark.parametrize("profile", FOLDERS)
def test_long_beam_matches_the_handbook_example_5_where_reproducible(profile: str) -> None:
    example = _example(FOLDERS[profile], "mnl_example_5")
    data, expected = example["data"], example["expected"]
    footing, checks = _checks(profile, data)
    minimum = _at_negative_moment(checks)["Flexion: acero minimo (M3)"]
    assert dict(minimum.values)["As,min"] / MM_PER_IN**2 == pytest.approx(expected["As_min_in2"],
                                                                          rel=example["tolerance_rel"]["As_min_in2"])
    cases, _ = combined_factored_cases(footing, SOIL)
    beam = beam_case(footing, SOIL, *cases[0])
    exterior = beam.columns[0]
    edge_face = beam.moment(exterior.x - exterior.half) / NMM_PER_KIPFT
    assert edge_face == pytest.approx(expected["M_exterior_edge_face_kipft"],
                                      abs=example["tolerance_abs"]["M_exterior_edge_face_kipft"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_transverse_strips_match_wight_15_6(profile: str) -> None:
    example = _example(FOLDERS[profile], "wight_15_6")
    expected, tolerance = example["expected"], example["tolerance_rel"]
    _, checks = _checks(profile, example["data"])
    interior = _strip(checks, "interior", "Flexion: resistencia")
    assert interior.demand is not None
    assert interior.demand / NMM_PER_KIPFT == pytest.approx(expected["strip_Mu_interior_kipft"], rel=tolerance["strip_Mu_interior_kipft"])
    for column in ("interior", "exterior"):
        minimum = _strip(checks, column, "Flexion: acero minimo (M3)")
        key = f"strip_As_min_{column}_in2"
        assert dict(minimum.values)["As,min"] / MM_PER_IN**2 == pytest.approx(expected[key], rel=tolerance[key])


@pytest.mark.parametrize("profile", FOLDERS)
def test_columns_match_the_handbook_example_5(profile: str) -> None:
    example = _example(FOLDERS[profile], "mnl_example_5")
    expected, tolerance = example["expected"], example["tolerance_rel"]
    _, checks = _checks(profile, example["data"])
    for column in ("exterior", "interior"):
        strip = _strip(checks, column, "Flexion: resistencia")
        assert strip.demand is not None
        key = f"strip_Mu_{column}_kipft"
        assert strip.demand / NMM_PER_KIPFT == pytest.approx(expected[key], rel=tolerance[key])
    punching = _at_column(checks, "interior", "Punzonamiento")
    assert punching.capacity is not None
    assert punching.capacity / MPA_PER_PSI == pytest.approx(expected["punching_phi_vc_interior_psi"],
                                                           rel=tolerance["punching_phi_vc_interior_psi"])
    bearing = _at_column(checks, "interior", "Aplastamiento en la zapata")
    assert bearing.capacity is not None
    assert bearing.capacity / N_PER_KIP == pytest.approx(expected["bearing_phi_Bn_interior_kips"],
                                                         rel=tolerance["bearing_phi_Bn_interior_kips"])
    area = _at_column(checks, "interior", "Pasadores: area minima")
    assert area.demand is not None
    assert area.demand / MM_PER_IN**2 == pytest.approx(expected["dowel_min_area_in2"], rel=tolerance["dowel_min_area_in2"])
    anchorage = _at_column(checks, "interior", "Pasadores: anclaje a compresion")
    assert anchorage.demand is not None
    assert anchorage.demand / MM_PER_IN == pytest.approx(expected["dowel_ldc_in"], rel=tolerance["dowel_ldc_in"][FOLDERS[profile]])
