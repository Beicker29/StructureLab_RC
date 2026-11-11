import math
from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import (
    CRACK_SPACING,
    MIN_REINFORCEMENT,
    MIN_REINFORCEMENT_M2,
    NET_TENSILE_STRAIN,
    NET_TENSILE_STRAIN_BIAXIAL,
    NET_TENSILE_STRAIN_M2,
    SKIN,
    STRENGTH,
)
from structurelab_rc.domain.beam.station import SCOPE, station_checks
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.model.project import Materials, Member
from structurelab_rc.setup import load_engine

BARS = load_engine().bars
MATERIALS = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight", coating="uncoated")


def _member(layers: list[dict[str, Any]], demands: dict[str, float], **changes: Any) -> Member:
    data: dict[str, Any] = {
        "id": "V",
        "type": "beam",
        "length": 6000.0,
        "section": {"bw": 300.0, "h": 500.0, "cover": 40.0},
        "stations": [{"z": 0.0, "layout": {"layers": layers, "stirrups": None}, "demands": demands}],
    }
    return Member.model_validate(data | changes)


def _checks(member: Member, profile: str = "nsr-10") -> dict[str, Check]:
    """Verificaciones de alcance y flexión de la única estación; el cortante se prueba en test_shear_checks.py."""
    checks = station_checks(PROFILES[profile], MATERIALS, member, member.stations[0], BARS)
    return {check.name: check for check in checks if not check.name.startswith("Cortante")}


BOTTOM = [{"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}]


def test_a_well_reinforced_beam_passes_every_check() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 180.0, "M2_kNm": 0.0}))
    assert {name: check.status for name, check in checks.items()} == {
        STRENGTH: Status.PASS,
        NET_TENSILE_STRAIN: Status.PASS,
        NET_TENSILE_STRAIN_M2: Status.PASS,
        NET_TENSILE_STRAIN_BIAXIAL: Status.PASS,
        MIN_REINFORCEMENT: Status.PASS,
        MIN_REINFORCEMENT_M2: Status.PASS,
        CRACK_SPACING: Status.PASS,
    }
    phi = dict(checks[STRENGTH].values)["phi"]
    assert checks[STRENGTH].capacity == pytest.approx(phi * dict(checks[STRENGTH].values)["Mn3"])
    assert checks[STRENGTH].member == "V"
    assert checks[STRENGTH].z == 0.0


def test_insufficient_strength_fails() -> None:
    assert _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 300.0, "M2_kNm": 0.0}))[STRENGTH].status is Status.FAIL


def test_axial_compression_at_the_limit_is_blocked_as_not_a_beam() -> None:
    limit_kn = 0.10 * 28.0 * 300.0 * 500.0 / 1e3
    checks = _checks(_member(BOTTOM, {"Pu_kN": limit_kn, "Mu_kNm": 100.0, "M2_kNm": 0.0}))
    assert list(checks) == [SCOPE]
    assert checks[SCOPE].status is Status.BLOCKED


def test_axial_tension_is_carried_in_equilibrium() -> None:
    no_axial = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 100.0, "M2_kNm": 0.0}))[STRENGTH]
    tension = _checks(_member(BOTTOM, {"Pu_kN": -200.0, "Mu_kNm": 100.0, "M2_kNm": 0.0}))[STRENGTH]
    assert dict(tension.values)["Mn3"] < dict(no_axial.values)["Mn3"]


def test_tension_beyond_the_steel_capacity_fails() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": -700.0, "Mu_kNm": 10.0, "M2_kNm": 0.0}))
    assert checks[STRENGTH].status is Status.FAIL
    assert "tracción axial" in checks[STRENGTH].note


def test_missing_axial_load_is_incomplete() -> None:
    assert _checks(_member(BOTTOM, {"Mu_kNm": 100.0, "M2_kNm": 0.0}))[STRENGTH].status is Status.INCOMPLETE


def test_other_member_types_are_blocked() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 100.0, "M2_kNm": 0.0}, type="column"))
    assert checks[SCOPE].status is Status.BLOCKED


def test_net_tensile_strain_limit_differs_between_profiles() -> None:
    # εt queda entre 0.004 (NSR-10 C.10.3.5) y εty + 0.003 (ACI 9.3.3.1).
    layers = [{"bars": ["#8", "#8", "#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 250.0, "M2_kNm": 0.0})
    nsr, aci = _checks(member, "nsr-10")[NET_TENSILE_STRAIN], _checks(member, "aci-318-25")[NET_TENSILE_STRAIN]
    assert 0.004 < nsr.capacity < 0.0051  # type: ignore[operator]
    assert nsr.status is Status.PASS
    assert aci.status is Status.FAIL


def _whitney_area(mu: float, b: float, d: float) -> float:
    """As con φ = 0.90 y el bloque de Whitney, independiente del paquete: (0.85·f'c·b/fy)·(d − √(d² − 2Mu/(φ·0.85·f'c·b)))."""
    k = 0.85 * MATERIALS.fc * b
    return k / MATERIALS.fy * (d - math.sqrt(d**2 - 2 * mu / (0.9 * k)))


@pytest.mark.parametrize("profile", ["aci-318-25", "nsr-10"])
@pytest.mark.parametrize(("mu", "status"), [(20.0, Status.PASS), (33.0, Status.FAIL)])
def test_below_minimum_reinforcement_uses_the_one_third_exception(profile: str, mu: float, status: Status) -> None:
    """As < As,min pasa si As ≥ 4/3 del requerido por análisis (ACI 9.6.1.3, NSR-10 C.10.5.3; D-081)."""
    layers = [{"bars": ["#4", "#4"], "depth": 440.0, "role": "flexure"}]
    check = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": mu, "M2_kNm": 0.0}), profile)[MIN_REINFORCEMENT]
    analysis = _whitney_area(mu * 1e6, 300.0, 440.0)
    assert check.status is status
    assert dict(check.values)["As analisis"] == pytest.approx(analysis, rel=1e-6)
    assert check.demand == pytest.approx(4 / 3 * analysis, rel=1e-6)
    assert check.capacity == pytest.approx(2 * 129.0)


def test_below_minimum_without_enough_strength_fails() -> None:
    layers = [{"bars": ["#4", "#4"], "depth": 440.0, "role": "flexure"}]
    check = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 60.0, "M2_kNm": 0.0}))[MIN_REINFORCEMENT]
    assert check.status is Status.FAIL
    assert "no aplica la excepcion" in check.note


@pytest.mark.parametrize("profile", ["aci-318-25", "nsr-10"])
@pytest.mark.parametrize(("bars", "width", "status"), [
    (["#8", "#8", "#8"], 300.0, Status.PASS),
    (["#8"], 300.0, Status.FAIL),
    (["#8", "#8"], 600.0, Status.FAIL),
])
def test_crack_control_spacing_of_the_tension_layer(profile: str, bars: list[str], width: float, status: Status) -> None:
    """ACI 24.3.2 y NSR-10 C.10.6.4 con fs = 2/3·fy: s ≤ min(380·280/fs − 2.5·cc, 300·280/fs); una sola barra usa el
    ancho de la cara en tracción (D-081)."""
    layers = [{"bars": bars, "depth": 440.0, "role": "flexure"}]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 50.0, "M2_kNm": 0.0}, section={"bw": width, "h": 500.0, "cover": 40.0})
    check = _checks(member, profile)[CRACK_SPACING]
    cc = 500.0 - 440.0 - 25.4 / 2
    fs = 2 / 3 * MATERIALS.fy
    inset = 40.0 + 25.4 / 2
    expected = width if len(bars) == 1 else (width - 2 * inset) / (len(bars) - 1)
    assert check.status is status
    assert check.demand == pytest.approx(expected)
    assert check.capacity == pytest.approx(min(380 * 280 / fs - 2.5 * cc, 300 * 280 / fs))


T_SECTION = {"bw": 300.0, "h": 500.0, "cover": 40.0, "hf": 100.0, "overhang_x_neg": 350.0, "overhang_x_pos": 350.0}
TOP = [{"bars": ["#6", "#6", "#6", "#6"], "depth": 60.0, "role": "flexure"}]


def test_flange_in_tension_needs_the_determinacy_declared() -> None:
    member = _member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0, "M2_kNm": 0.0}, section=T_SECTION)
    assert _checks(member)[MIN_REINFORCEMENT].status is Status.INCOMPLETE


def test_determinate_beam_uses_the_reduced_flange_width() -> None:
    continuous = _checks(_member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0, "M2_kNm": 0.0}, section=T_SECTION, statically_determinate=False))
    determinate = _checks(_member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0, "M2_kNm": 0.0}, section=T_SECTION, statically_determinate=True))
    assert determinate[MIN_REINFORCEMENT].demand == pytest.approx(2 * continuous[MIN_REINFORCEMENT].demand)  # type: ignore[operator]


def test_aci_caps_fy_at_550_mpa_for_minimum_reinforcement() -> None:
    flexure = PROFILES["aci-318-25"].flexure
    assert flexure.min_flexural_reinforcement(28.0, 690.0, 300.0, 440.0) == flexure.min_flexural_reinforcement(28.0, 550.0, 300.0, 440.0)
    nsr = PROFILES["nsr-10"].flexure
    assert nsr.min_flexural_reinforcement(28.0, 690.0, 300.0, 440.0) < nsr.min_flexural_reinforcement(28.0, 550.0, 300.0, 440.0)


def test_minimum_reinforcement_counts_only_the_tension_side() -> None:
    # El eje neutro queda por encima de las 2#5 superiores, que trabajan a tracción, pero están del lado comprimido
    # (60 mm < h/2): As,min solo cuenta las 3#8 (D-025 revisada por D-081).
    layers = [
        {"bars": ["#5", "#5"], "depth": 60.0, "role": "flexure"},
        {"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"},
    ]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 180.0, "M2_kNm": 0.0}, section=T_SECTION, statically_determinate=False)
    check = _checks(member)[MIN_REINFORCEMENT]
    area = 3 * 510.0
    depth = max(440.0, 0.8 * 500.0)
    assert check.capacity == pytest.approx(area)
    assert check.demand == pytest.approx(1.4 * 300.0 * depth / 420.0)


def test_weak_axis_moment_reduces_the_biaxial_capacity_and_is_checked() -> None:
    layers = [{"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}, {"bars": ["#5", "#5"], "depth": 60.0, "role": "flexure"}]
    alone = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 150.0, "M2_kNm": 0.0}))
    combined = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 150.0, "M2_kNm": 60.0}))
    assert combined[STRENGTH].demand == pytest.approx(math.hypot(150e6, 60e6))
    assert dict(combined[STRENGTH].values)["Mn3"] < dict(alone[STRENGTH].values)["Mn3"]
    assert combined[NET_TENSILE_STRAIN_M2].capacity is not None
    assert combined[MIN_REINFORCEMENT_M2].demand is not None
    assert _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 150.0, "M2_kNm": 200.0}))[STRENGTH].status is Status.FAIL


def test_weak_axis_minimum_reinforcement_uses_h_and_the_total_width() -> None:
    layers = [{"bars": ["#8", "#8", "#8"], "depth": 440.0, "role": "flexure"}, {"bars": ["#5", "#5"], "depth": 60.0, "role": "flexure"}]
    check = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 50.0, "M2_kNm": 20.0}))[MIN_REINFORCEMENT_M2]
    # Ancho h = 500 mm y d no menor que 0.8·bw = 240 mm: el mayor entre 0.25√f'c/fy y 1.4/fy por h·d.
    depth = check.demand / (1.4 / 420.0 * 500.0)  # type: ignore[operator]
    assert depth >= 240.0 - 1e-6


def _skin_layer(depth: float, bw: float = 400.0) -> dict[str, Any]:
    inset = 40.0 + 12.7 / 2
    return {"bars": [{"designation": "#4", "x": inset}, {"designation": "#4", "x": bw - inset}], "depth": depth, "role": "skin"}


@pytest.mark.parametrize("profile", ["aci-318-25", "nsr-10"])
@pytest.mark.parametrize(("skin", "status", "gap"), [
    ([740.0, 540.0], Status.PASS, 200.0),
    ([600.0], Status.FAIL, 340.0),
    ([900.0], Status.FAIL, 400.0),  # la última barra de piel queda lejos de h/2
])
def test_skin_reinforcement_of_a_deep_beam(profile: str, skin: list[float], status: Status, gap: float) -> None:
    """h > 900 mm: barras de piel en las dos caras dentro de h/2 desde la cara en tracción; la mayor separación entre la
    capa en tracción (940), las de piel y h/2 (500) frente a 380·280/fs − 2.5·cc ≤ 300·280/fs con cc a la cara lateral
    (ACI 9.7.2.3, NSR-10 C.10.6.7; D-083). Las barras de piel no cuentan como As."""
    layers = [{"bars": ["#8", "#8", "#8", "#8"], "depth": 940.0, "role": "flexure"}, *(_skin_layer(depth) for depth in skin)]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 400.0, "M2_kNm": 0.0}, section={"bw": 400.0, "h": 1000.0, "cover": 40.0})
    checks = _checks(member, profile)
    fs = 2 / 3 * MATERIALS.fy
    cc = 40.0
    assert checks[SKIN].status is status
    assert checks[SKIN].demand == pytest.approx(gap)
    assert checks[SKIN].capacity == pytest.approx(min(380 * 280 / fs - 2.5 * cc, 300 * 280 / fs))
    plain = _checks(_member(layers[:1], {"Pu_kN": 0.0, "Mu_kNm": 400.0, "M2_kNm": 0.0},
                            section={"bw": 400.0, "h": 1000.0, "cover": 40.0}), profile)
    assert checks[STRENGTH].capacity == pytest.approx(plain[STRENGTH].capacity)


def test_deep_beam_without_skin_reinforcement_fails_and_shallow_beams_skip_it() -> None:
    layers = [{"bars": ["#8", "#8", "#8"], "depth": 940.0, "role": "flexure"}]
    deep = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 300.0, "M2_kNm": 0.0}, section={"bw": 400.0, "h": 1000.0, "cover": 40.0}))
    assert deep[SKIN].status is Status.FAIL
    assert "Falta el refuerzo superficial" in deep[SKIN].errors[0].message
    assert SKIN not in _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 180.0, "M2_kNm": 0.0}))
