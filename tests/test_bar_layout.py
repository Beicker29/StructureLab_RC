from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import steel_layers
from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.beam.station import station_checks
from structurelab_rc.domain.beam.torsion import DETAILING
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.model.project import Materials, Member, Project, Section
from structurelab_rc.model.reinforcement import BarLayer, ReinforcementLayout
from structurelab_rc.setup import load_engine

BARS = load_engine().bars
SECTION = Section(bw=300.0, h=500.0, cover=40.0)
STIRRUPS = {"designation": "#3", "legs": 2, "spacing": 100.0, "closed": True}


def _layout(layers: list[dict[str, Any]], stirrups: dict[str, Any] | None = STIRRUPS) -> ReinforcementLayout:
    return ReinforcementLayout.model_validate({"layers": layers, "stirrups": stirrups})


def test_short_form_spreads_bars_between_the_stirrup_corners() -> None:
    # Esquina: 40 (recubrimiento) + 9.5 (estribo #3) + 25.4/2 (barra #8) = 62.2 mm desde cada cara.
    bars = placed_bars(_layout([{"depth": 440.0, "role": "flexure", "bars": ["#8", "#8", "#8"]}]), SECTION, BARS)
    assert [bar.z for bar in bars] == pytest.approx([62.2, 150.0, 237.8])


def test_mixed_diameters_keep_each_corner_bar_at_its_own_corner() -> None:
    bars = placed_bars(_layout([{"depth": 440.0, "role": "flexure", "bars": ["#8", "#5", "#5", "#6"]}]), SECTION, BARS)
    left, right = 40.0 + 9.5 + 25.4 / 2, 300.0 - (40.0 + 9.5 + 19.1 / 2)
    assert [bar.z for bar in bars] == pytest.approx([left, left + (right - left) / 3, left + 2 * (right - left) / 3, right])
    areas = steel_layers(_layout([{"depth": 440.0, "role": "flexure", "bars": ["#8", "#5", "#5", "#6"]}]), BARS)
    assert isinstance(areas, tuple)
    assert areas[0].area == pytest.approx(510.0 + 2 * 199.0 + 284.0)


def test_a_single_bar_is_centred_and_no_stirrups_use_the_cover_only() -> None:
    assert placed_bars(_layout([{"depth": 440.0, "role": "flexure", "bars": ["#8"]}]), SECTION, BARS)[0].z == pytest.approx(150.0)
    open_section = placed_bars(_layout([{"depth": 440.0, "role": "flexure", "bars": ["#8", "#8"]}], None), SECTION, BARS)
    assert open_section[0].z == pytest.approx(40.0 + 12.7)


def test_explicit_positions_are_kept() -> None:
    layer = {"depth": 440.0, "role": "flexure", "bars": [{"designation": "#8", "z": 63.0}, {"designation": "#5", "z": 120.0}]}
    bars = placed_bars(_layout([layer]), SECTION, BARS)
    assert [(bar.designation, bar.z) for bar in bars] == [("#8", 63.0), ("#5", 120.0)]


def test_one_layer_cannot_mix_both_forms() -> None:
    with pytest.raises(ValidationError):
        BarLayer.model_validate({"depth": 440.0, "role": "flexure", "bars": ["#8", {"designation": "#8", "z": 200.0}]})


def _project(layer: dict[str, Any]) -> Project:
    station = {
        "x": 0.0,
        "layout": {"layers": [layer], "stirrups": STIRRUPS},
        "demands": {"Pu_kN": 0.0, "Mu_kNm": 100.0, "Vu_kN": 50.0, "Tu_kNm": 0.0},
    }
    return Project.model_validate({
        "description": "Prueba",
        "profile": "nsr-10",
        "seismic": {"level": "DMO", "justification": "Prueba"},
        "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"},
        "members": [{"id": "V", "type": "beam", "length": 6000.0, "section": SECTION.model_dump(exclude_none=True), "stations": [station]}],
    })


@pytest.mark.parametrize(
    ("bars", "message"),
    [
        ([{"designation": "#8", "z": 50.0}, {"designation": "#8", "z": 237.8}], "fuera del estribo"),
        ([{"designation": "#8", "z": 237.8}, {"designation": "#8", "z": 62.2}], "orden"),
        (["#8", "#99"], "#99"),
    ],
)
def test_invalid_bar_layers_are_rejected(bars: list[Any], message: str) -> None:
    check = validate_project(_project({"depth": 440.0, "role": "flexure", "bars": bars}), BARS)
    assert check.status is Status.FAIL
    assert any(message in error.message for error in check.errors)


def _detailing(layers: list[dict[str, Any]], bw: float = 300.0) -> str:
    station = {"x": 0.0, "layout": {"layers": layers, "stirrups": STIRRUPS | {"designation": "#4"}},
               "demands": {"Pu_kN": 0.0, "Mu_kNm": 100.0, "Vu_kN": 120.0, "Tu_kNm": 25.0}}
    member = Member.model_validate({"id": "V", "type": "beam", "length": 6000.0,
                                    "section": {"bw": bw, "h": 500.0, "cover": 40.0}, "stations": [station]})
    materials = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight")
    checks = station_checks(PROFILES["nsr-10"], materials, member, member.stations[0], BARS)
    detailing = next(check for check in checks if check.name == DETAILING)
    return "" if detailing.status is Status.PASS else detailing.note


TORSION = {"depth": 250.0, "role": "torsion", "bars": ["#6", "#6"]}
BOTTOM = {"depth": 440.0, "role": "flexure", "bars": ["#8", "#8", "#8"]}


def test_explicit_bars_away_from_the_corner_fail_the_detailing() -> None:
    top = {"depth": 60.0, "role": "flexure", "bars": [{"designation": "#5", "z": 120.0}, {"designation": "#5", "z": 239.0}]}
    assert "esquinas" in _detailing([top, TORSION, BOTTOM])
    corner = {"depth": 60.0, "role": "flexure", "bars": [{"designation": "#5", "z": 61.0}, {"designation": "#5", "z": 239.0}]}
    assert _detailing([corner, TORSION, BOTTOM]) == ""


def test_wide_gaps_between_explicit_bars_fail_the_detailing() -> None:
    top = {"depth": 60.0, "role": "flexure", "bars": ["#5", "#5"]}
    bottom = {"depth": 440.0, "role": "flexure", "bars": ["#8", "#8"]}
    assert "separa sus barras" in _detailing([top, TORSION, bottom], bw=500.0)
