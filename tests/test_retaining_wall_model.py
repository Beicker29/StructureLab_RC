"""Modelo y validación del muro de contención en voladizo (D-173), fase A, etapa 1."""

import copy
import math
from typing import Any

import pytest
from pydantic import ValidationError
from wall_inputs import internal_soil
from wall_inputs import project as _project
from wall_inputs import soil as _soil
from wall_inputs import wall as _wall

from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.model.project import Project
from structurelab_rc.model.retaining_wall import EarthPressure, RetainingSoil, RetainingWall
from structurelab_rc.setup import load_engine

BARS = load_engine().bars


def test_the_manual_example_loads_with_internal_units() -> None:
    project = Project.model_validate(_project())
    soil, wall = project.retaining_soil, project.retaining_walls[0]
    assert soil is not None
    assert soil.unit_weight_backfill == pytest.approx(17.28e-6)  # N/mm³
    assert soil.allowable_pressure == pytest.approx(0.1436)  # MPa
    assert soil.friction_angle == pytest.approx(math.radians(35.0))
    assert wall.base_width == pytest.approx(762.0 + 381.0 + 1676.0)
    assert wall.retained_height == pytest.approx(610.0 + 4877.0)
    assert validate_project(project, BARS).status is Status.PASS


@pytest.mark.parametrize("pressure", [{"state": "active", "method": "jaky"}, {"state": "at_rest", "method": "rankine"},
                                      {"state": "active", "method": "declared"},
                                      {"state": "active", "method": "rankine", "coefficient": 0.3},
                                      {"state": "at_rest", "method": "mayne_kulhawy"},
                                      {"state": "at_rest", "method": "jaky", "ocr": 2.0}])
def test_invalid_earth_pressure_choices_are_rejected(pressure: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        EarthPressure.model_validate(pressure)


@pytest.mark.parametrize("pressure", [{"state": "active", "method": "rankine"}, {"state": "active", "method": "declared",
                                                                                 "coefficient": 0.3},
                                      {"state": "at_rest", "method": "jaky"},
                                      {"state": "at_rest", "method": "mayne_kulhawy", "ocr": 2.0},
                                      {"state": "at_rest", "method": "declared", "coefficient": 0.5}])
def test_valid_earth_pressure_choices_load(pressure: dict[str, Any]) -> None:
    assert EarthPressure.model_validate(pressure).state == pressure["state"]


def test_coulomb_needs_the_wall_friction_and_only_coulomb_takes_it() -> None:
    with pytest.raises(ValidationError, match="wall_friction_angle"):
        EarthPressure.model_validate({"state": "active", "method": "coulomb"})
    with pytest.raises(ValidationError, match="wall_friction_angle"):
        EarthPressure.model_validate({"state": "active", "method": "rankine", "wall_friction_angle": 20.0})
    pressure = EarthPressure.model_validate({"state": "active", "method": "coulomb", "wall_friction_angle": 20.0})
    assert pressure.wall_friction_angle == pytest.approx(math.radians(20.0))


def test_coulomb_needs_the_declared_cohesion() -> None:
    coulomb = {"state": "active", "method": "coulomb", "wall_friction_angle": 20.0}
    with pytest.raises(ValidationError, match="cohesion"):
        Project.model_validate(_project(retaining_walls=[_wall(earth_pressure=coulomb)]))
    project = Project.model_validate(_project(retaining_soil=_soil(cohesion=0.0), retaining_walls=[_wall(earth_pressure=coulomb)]))
    assert project.retaining_soil is not None and project.retaining_soil.cohesion == 0.0


def test_the_passive_pressure_needs_its_coefficient_and_the_front_soil_weight() -> None:
    with pytest.raises(ValidationError, match="passive_coefficient"):
        RetainingSoil.model_validate(internal_soil(passive_coefficient=3.69))
    soil = RetainingSoil.model_validate(internal_soil(passive_coefficient=3.69, unit_weight_front=17.28))
    assert soil.unit_weight_front == pytest.approx(17.28e-6)


@pytest.mark.parametrize(("change", "message"), [({"backfill_height": 5000.0}, "relleno"), ({"toe": 0.0}, "puntera"),
                                                 ({"heel": 0.0}, "talón"), ({"stem_cover": 200.0}, "pantalla"),
                                                 ({"base_cover": 400.0}, "base")])
def test_invalid_walls_are_rejected(change: dict[str, float], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        RetainingWall.model_validate(_wall(**change))


def test_repeated_cases_and_band_spacing_are_rejected() -> None:
    data = _wall()
    data["cases"] = [data["cases"][0], data["cases"][0]]
    with pytest.raises(ValidationError, match="repite"):
        RetainingWall.model_validate(data)
    data = _wall()
    data["base"]["top"] = {**data["base"]["top"], "band_spacing": 100.0}
    with pytest.raises(ValidationError, match="band_spacing"):
        RetainingWall.model_validate(data)


def test_walls_and_their_soil_go_together() -> None:
    with pytest.raises(ValidationError, match="retaining_soil"):
        Project.model_validate(_project(retaining_soil=None))
    with pytest.raises(ValidationError, match="retaining_soil"):
        Project.model_validate(_project(retaining_walls=[], members=[]))
    with pytest.raises(ValidationError, match="únicos"):
        Project.model_validate(_project(retaining_walls=[_wall(), _wall()]))


def test_validation_reports_unknown_bars_and_reinforcement_that_does_not_fit() -> None:
    data = _project()
    data["retaining_walls"][0]["stem"]["back"]["designation"] = "#99"
    check = validate_project(Project.model_validate(data), BARS)
    assert check.status is Status.FAIL and "no esta en el catalogo" in check.errors[0].message
    data = copy.deepcopy(_project())
    data["retaining_walls"][0]["stem_thickness"] = 160.0  # 2·50 + #7 + #5 + 2·#5 = 170 mm
    check = validate_project(Project.model_validate(data), BARS)
    assert check.status is Status.FAIL and "no caben en el espesor de la pantalla" in check.errors[0].message
