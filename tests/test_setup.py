import math
from pathlib import Path

import pytest

from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.setup import load_engine

STEEL_DENSITY_KG_MM3 = 7850e-9


def test_catalog_has_the_requested_bars() -> None:
    designations = [bar.designation for bar in load_engine().bars]
    assert designations == ["#3", "#4", "#5", "#6", "#7", "#8", "#9", "#10", "#11", "#14", "#18"]


def test_loads_from_any_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_engine().bars


@pytest.mark.parametrize("bar", load_engine().bars, ids=lambda bar: bar.designation)
def test_values_are_internally_consistent(bar: RebarSpec) -> None:
    # Control de errores de digitación, no de exactitud: el área nominal de la #4 difiere 1.8 % de la geométrica.
    assert bar.area_mm2 == pytest.approx(math.pi * bar.diameter_mm**2 / 4, rel=0.02)
    assert bar.mass_kg_m == pytest.approx(STEEL_DENSITY_KG_MM3 * bar.area_mm2 * 1000, rel=0.02)
