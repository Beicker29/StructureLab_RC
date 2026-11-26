"""Alertas de tipologías atípicas del diseño por tipologías (D-172): solo leen el resultado y no lo cambian."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen
from pydantic import ValidationError

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing.alerts import FA, LOW_P, UPLIFT, statistic, typology_alerts
from structurelab_rc.design.footing.mixed import design_with_pairs, designed_with_pairs
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.engine import import_etabs_footings, report_file
from structurelab_rc.model.design import FootingDesignProject, TypologyAlerts
from structurelab_rc.model.layout import public
from structurelab_rc.reporting.alerts import NOTES, alerts_data, alerts_document, columns_csv, typologies_csv
from structurelab_rc.reporting.text import render_text
from structurelab_rc.setup import load_engine

SECTION = {"fa_threshold": 1.5, "eccentricity_threshold": 0.1667, "min_relative_p": 0.10, "tukey_k": 1.5, "z_threshold": 3.0,
           "small_typology_max_columns": 3, "min_typologies_for_statistics": 4, "pareto_fraction": 0.10}
SETTINGS = TypologyAlerts.model_validate(SECTION)
ETABS = Path(__file__).parent.parent / "examples" / "etabs" / "zapatas" / "pruebas"


def _loads(p: float, m: float, low: float | None = None) -> list[dict[str, Any]]:
    """Un caso de servicio D+L con My = m, otro de servicio con P = low si se pide, y uno mayorado."""
    zero = {"Vx_kN": 0.0, "Vy_kN": 0.0, "Mx_kNm": 0.0}
    cases = [{"case": "D+L", "kind": "service", "dead_factor": 1.0, "live_factor": 1.0, "P_kN": p, **zero, "My_kNm": m}]
    if low is not None:
        cases.append({"case": "0.9D", "kind": "service", "dead_factor": 0.9, "live_factor": 0.0, "P_kN": low, **zero,
                      "My_kNm": 0.0})
    cases.append({"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 1.2, "live_factor": 1.6, "P_kN": 1.4 * p, **zero,
                  "My_kNm": 1.4 * m})
    return cases


def _project(columns: Sequence[tuple[float, float, float | None]], typologies: int, alerts: bool = True) -> dict[str, Any]:
    """Columnas de 400 × 400 con (P, My, P baja) en kN y kN·m, un f'c y la DP (rápida)."""
    return public({
        "description": "prueba", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "prueba"},
        "materials": {"fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated", "max_aggregate": 19.0},
        "soil": {"allowable_pressure_kPa": 200.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                 "unit_weight_fill_kNm3": 18.0, "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                 "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                 "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                 "overturning_safety_factor_seismic": 1.5},
        "design": {"typologies": typologies, "fc_options": [21.0], "method": "dp",
                   "prices": {"concrete_per_m3": {"21": 500000.0}, "steel_per_kg": 6000.0},
                   "plan_step": 100.0, "plan_max": 6000.0, "h_min": 400.0, "h_step": 100.0, "h_max": 1000.0, "cover": 75.0,
                   "fill_height": 800.0, "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
                   "bars": ["#5"], "spacing_step": 50.0,
                   "ends": {"bottom": "straight", "top": "straight", "dowels": "hook90"}, "dowel_bars": ["#5"]},
        "columns": [{"id": f"C{index}", "cx": 400.0, "cy": 400.0, "loads": _loads(p, m, low)}
                    for index, (p, m, low) in enumerate(columns, start=1)],
        **({"typology_alerts": SECTION} if alerts else {}),
    })


def _alerts(columns: Sequence[tuple[float, float, float | None]], typologies: int) -> Any:
    project = FootingDesignProject.model_validate(_project(columns, typologies))
    ctx = Context(project, PROFILES[project.profile], load_engine().bars)
    result = design_with_pairs(ctx)
    return typology_alerts(ctx, result)


# Cuatro columnas parecidas sin momento y una con momento grande, cada una en su tipología.
_MOMENT = [(400.0, 0.0, None), (450.0, 0.0, None), (500.0, 0.0, None), (550.0, 0.0, None), (400.0, 260.0, None)]


@pytest.fixture(scope="module")
def moment_alerts() -> Any:
    return _alerts(_MOMENT, 5)


def test_large_moment_makes_a_candidate_and_flags_its_typology(moment_alerts: Any) -> None:
    signal = next(signal for signal in moment_alerts.columns if signal.column == "C5")
    assert signal.candidate and signal.fa is not None and signal.fa >= SETTINGS.fa_threshold and FA in signal.reasons
    typology = next(item for item in moment_alerts.typologies if "C5" in item.columns)
    assert typology.atypical_by and typology.candidates == 1 and typology.flagged and typology.small
    assert all(not item.flagged for item in moment_alerts.typologies if item is not typology)


def test_without_moments_there_are_no_candidates_and_fa_is_one() -> None:
    alerts = _alerts([(400.0, 0.0, None), (450.0, 0.0, None), (500.0, 0.0, None), (550.0, 0.0, None)], 2)
    assert all(signal.fa == 1.0 and not signal.candidate for signal in alerts.columns)
    assert all(signal.ex_ratio == 0.0 and signal.ey_ratio == 0.0 for signal in alerts.columns)
    assert not any(item.flagged for item in alerts.typologies)


def test_low_and_negative_axial_load_make_stability_candidates() -> None:
    alerts = _alerts([(400.0, 0.0, 30.0), (400.0, 0.0, -10.0), (400.0, 0.0, 200.0)], 1)
    reasons = {signal.column: signal.reasons for signal in alerts.columns}
    assert reasons == {"C1": (LOW_P,), "C2": (UPLIFT,), "C3": ()}


def test_grouping_overcost_and_concentration_add_up(moment_alerts: Any) -> None:
    for item in moment_alerts.typologies:  # una columna por tipología: la tipología es su diseño individual
        assert item.grouping_overcost == pytest.approx(0.0)
    concentration = moment_alerts.concentration
    assert (concentration.count, concentration.total) == (1, 5)  # 0.10 · 5 hacia arriba
    assert 20.0 < concentration.concrete_share <= 100.0


def test_tukey_and_robust_z_with_known_values() -> None:
    stat = statistic([1.0, 2.0, 3.0, 4.0, 100.0], SETTINGS)
    assert (stat.q1, stat.q3, stat.tukey_limit, stat.median, stat.mad) == (2.0, 4.0, 7.0, 3.0, 1.0)
    assert stat.above_tukey(100.0) and not stat.above_tukey(4.0)
    assert stat.z(100.0) == pytest.approx(97.0 / 1.4826)


def test_mad_zero_leaves_tukey_and_explains_z() -> None:
    stat = statistic([5.0, 5.0, 5.0, 9.0], SETTINGS)
    assert stat.tukey_limit == pytest.approx(6.0 + 1.5 * 1.0)  # Q1 = 5, Q3 = 6 (cuartiles inclusivos)
    assert stat.mad == 0.0 and stat.z(9.0) is None and "MAD = 0" in stat.z_note


def test_few_typologies_skip_the_statistics() -> None:
    stat = statistic([1.0, 2.0, 30.0], SETTINGS)
    assert stat.tukey_limit is None and stat.z(30.0) is None
    assert "min_typologies_for_statistics" in stat.tukey_note and stat.tukey_note == stat.z_note


def test_report_lists_the_flagged_typology_with_the_three_notes(moment_alerts: Any) -> None:
    data = alerts_data(moment_alerts)
    text = render_text([alerts_document(data)])
    assert all(note in text for note in NOTES)
    flagged = next(item.name for item in moment_alerts.typologies if item.flagged)
    assert f"Tipologías señaladas: {flagged}" in text and "combined_pairs" in text and "exclude_unique_names" in text
    assert typologies_csv(data).count("\n") == 1 + len(moment_alerts.typologies)
    assert columns_csv(data).splitlines()[1].startswith("C5;")


@pytest.mark.parametrize("change", [{"fa_threshold": 1.0}, {"pareto_fraction": 0.0}, {"min_typologies_for_statistics": 1},
                                    {"eccentricity_threshold": 0.6}, {"umbral": 1.0}])
def test_invalid_settings_are_rejected(change: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        TypologyAlerts.model_validate({**SECTION, **change})


def test_alerts_are_not_allowed_with_the_curve() -> None:
    data = {**_project([(400.0, 0.0, None)], 1), "curve": {"n": "1"}}
    with pytest.raises(ValidationError, match="typology_alerts"):
        FootingDesignProject.model_validate(data)


def test_alerts_do_not_change_the_design_nor_the_verification(tmp_path: Path) -> None:
    designed = {}
    for alerts in (False, True):
        project = FootingDesignProject.model_validate(_project(_MOMENT, 5, alerts))
        ctx = Context(project, PROFILES[project.profile], load_engine().bars)
        designed[alerts] = designed_with_pairs(ctx, design_with_pairs(ctx))
    assert designed[True] == designed[False]
    path = tmp_path / "proyecto.json"
    path.write_text(json.dumps(designed[True], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_file(path, tmp_path / "sin")
    report_file(path, tmp_path / "con", alerts=alerts_data(_alerts(_MOMENT, 5)))
    for name in ("resultado.json", "cartilla.csv"):
        if (tmp_path / "sin" / name).exists():
            assert (tmp_path / "sin" / name).read_bytes() == (tmp_path / "con" / name).read_bytes(), name
    plain = (tmp_path / "sin" / "memoria.txt").read_text(encoding="utf-8")
    with_alerts = (tmp_path / "con" / "memoria.txt").read_text(encoding="utf-8")
    assert with_alerts.startswith(plain.rstrip("\n")) and "Alertas de tipologías atípicas (D-172)" in with_alerts
    assert "D-172" not in plain


def _design_file(tmp_path: Path, alerts: bool) -> Path:
    path = tmp_path / ("con.json" if alerts else "sin.json")
    path.write_text(json.dumps(_project(_MOMENT, 5, alerts), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def test_run_writes_the_alert_files_only_with_the_section(tmp_path: Path) -> None:
    names = ("alertas_tipologias.json", "tipologias_estadistica.csv", "alertas_columnas.csv")
    assert main(["run", str(_design_file(tmp_path, True)), "--output", str(tmp_path / "con"), "--workers", "1"]) == 0
    assert all((tmp_path / "con" / name).exists() for name in names)
    assert "Alertas de tipologías atípicas" in (tmp_path / "con" / "memoria.txt").read_text(encoding="utf-8")
    # La misma carpeta sin la sección: las alertas anteriores se borran y no llegan a la memoria.
    assert main(["run", str(_design_file(tmp_path, False)), "--output", str(tmp_path / "con"), "--workers", "1"]) == 0
    assert not any((tmp_path / "con" / name).exists() for name in names)
    assert "Alertas de tipologías atípicas" not in (tmp_path / "con" / "memoria.txt").read_text(encoding="utf-8")


def _template(tmp_path: Path, alerts: bool) -> Path:
    """La plantilla congelada de tipologías desde ETABS, con los Excel de pruebas en rutas absolutas."""
    data = json.loads(frozen("nsr_10", "zapatas", "diseno_tipologias_etabs.json").read_text(encoding="utf-8"))
    data["etabs_files"] = {key: str(ETABS / Path(value).name) for key, value in data["etabs_files"].items()}
    if alerts:
        data["typology_alerts"] = SECTION
    path = tmp_path / ("con.json" if alerts else "sin.json")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_etabs_import_passes_the_section_only_when_declared(tmp_path: Path) -> None:
    excel = (ETABS / "Joint Reactions - Servicio.xlsx", ETABS / "Joint Reactions - Ultimas.xlsx")
    plain = import_etabs_footings(*excel, _template(tmp_path, False), ETABS / "Joint Location.xlsx")[0]
    alerted = import_etabs_footings(*excel, _template(tmp_path, True), ETABS / "Joint Location.xlsx")[0]
    assert plain is not None and alerted is not None
    assert "typology_alerts" not in plain and alerted.pop("typology_alerts") == SECTION
    assert alerted == plain
