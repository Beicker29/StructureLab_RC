"""V3B: modelo de zapata, propiedades derivadas e importación de reacciones de ETABS (D-052, D-054, D-055)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.cli import main
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import import_etabs_footings, run_project
from structurelab_rc.io.etabs.footings import build_footing_project
from structurelab_rc.io.etabs.importer import EtabsImportError
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import EtabsFootingTemplate
from structurelab_rc.setup import load_engine

EXAMPLES = Path(__file__).parent.parent / "examples" / "etabs" / "zapatas"
SERVICE = EXAMPLES / "Joint Reactions - Servicio.xlsx"
FACTORED = EXAMPLES / "Joint Reactions - Ultimas.xlsx"
TEMPLATE = EXAMPLES / "plantilla_zapatas_nsr10.json"
HEADERS = ("Story", "Label", "Unique Name", "Output Case", "Case Type", "Step Type", "FX", "FY", "FZ", "MX", "MY", "MZ")
UNITS = {"FX": "kN", "FY": "kN", "FZ": "kN", "MX": "kN-m", "MY": "kN-m", "MZ": "kN-m"}
SOIL = {"allowable_pressure_kPa": 200.0, "min_contact_fraction": 0.6, "unit_weight_concrete_kNm3": 24.0,
        "unit_weight_fill_kNm3": 18.0,
        "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
        "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
        "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
        "overturning_safety_factor_seismic": 1.5}
MAT = {"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 150.0}, "y": {"designation": "#5", "spacing": 200.0}}


def _footing(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "Z1", "lx": 3000.0, "ly": 2000.0, "h": 600.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 500.0,
        "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0,
        "column": {"cx": 400.0, "cy": 500.0, "offset_x": 0.0, "offset_y": 0.0}, "bottom": MAT, "top": None,
        "loads": [{"case": "D+L", "kind": "service", "dead_factor": 1.0, "live_factor": 1.0, "P_kN": 1000.0, "Vx_kN": 0.0,
                   "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": 0.0},
                  {"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 1.2, "live_factor": 1.6, "P_kN": 1400.0,
                   "Vx_kN": 10.0, "Vy_kN": -5.0, "Mx_kNm": 20.0, "My_kNm": -30.0}],
    }
    data.update(changes)
    return data


def _project(**footing_changes: Any) -> dict[str, Any]:
    return {"description": "zapata", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "ejemplo"},
            "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"}, "soil": SOIL,
            "footings": [_footing(**footing_changes)]}


def test_units_and_derived_properties() -> None:
    project = Project.model_validate(_project())
    footing, soil = project.footings[0], project.soil
    assert soil is not None
    assert soil.allowable_pressure == pytest.approx(0.2)  # MPa
    assert soil.unit_weight_concrete == pytest.approx(24e-6)  # N/mm³
    factored = footing.loads[1]
    assert (factored.p, factored.vx, factored.mx) == (1.4e6, 1e4, 2e7)
    assert footing.area == 6e6
    assert footing.inertia_x == pytest.approx(3000 * 2000**3 / 12)
    assert footing.inertia_y == pytest.approx(2000 * 3000**3 / 12)
    assert footing.modulus_x == pytest.approx(3000 * 2000**2 / 6)
    assert footing.kern == (500.0, pytest.approx(2000 / 6))
    weight, pedestal, fill = footing.weights(soil)
    assert weight == pytest.approx(24e-6 * 6e6 * 600)  # 86.4 kN
    assert pedestal == pytest.approx(24e-6 * 400 * 500 * 500)  # 2.4 kN
    assert fill == pytest.approx(18e-6 * (6e6 - 2e5) * 1000)  # 104.4 kN
    assert footing.surcharge_dead == pytest.approx(2e-3)  # kN/m² → N/mm²
    assert footing.surcharges() == (pytest.approx(2e-3 * 5.8e6), pytest.approx(5e-3 * 5.8e6))  # 11.6 y 29 kN


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"column": {"cx": 400.0, "cy": 500.0, "offset_x": 1400.0, "offset_y": 0.0}}, "se sale de la base"),
        ({"cover": 300.0}, "recubrimiento"),
        ({"loads": [{"case": "C", "kind": "factored", "dead_factor": 1.2, "P_kN": 1.0, "Vx_kN": 0, "Vy_kN": 0, "Mx_kNm": 0,
                     "My_kNm": 0}]}, "live_factor"),
        ({"loads": [{"case": "C", "kind": "service", "live_factor": 1.0, "P_kN": 1.0, "Vx_kN": 0, "Vy_kN": 0, "Mx_kNm": 0,
                     "My_kNm": 0}]}, "dead_factor"),
        ({"surcharge_live_kNm2": -1.0}, "surcharge_live"),
    ],
    ids=["columna-fuera", "recubrimiento", "sin-factor-vivo", "sin-factor-muerto", "sobrecarga-negativa"],
)
def test_invalid_footings(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Footing.model_validate(_footing(**changes))


def test_footings_require_soil() -> None:
    data = _project()
    del data["soil"]
    with pytest.raises(ValidationError, match="soil"):
        Project.model_validate(data)


def test_soil_has_no_defaults() -> None:
    with pytest.raises(ValidationError):
        Soil.model_validate({key: value for key, value in SOIL.items() if key != "min_contact_fraction"})


@pytest.mark.parametrize(
    ("changes", "message"),
    [({"bottom": {**MAT, "x": {"designation": "#99", "spacing": 150.0}}}, "no esta en el catalogo"),
     ({"bottom": {**MAT, "y": {"designation": "#5", "spacing": 10.0}}}, "espacio libre"),
     ({"h": 200.0, "cover": 75.0, "top": MAT}, "no caben")],
    ids=["catalogo", "separacion", "espesor"],
)
def test_domain_validation(changes: dict[str, Any], message: str) -> None:
    check = validate_project(Project.model_validate(_project(**changes)), load_engine().bars)
    assert check.status is Status.FAIL
    assert any(message in error.message for error in check.errors)


def test_missing_dowels_are_incomplete(tmp_path: Path) -> None:
    """Sin pasadores declarados, su verificación es INCOMPLETE: no se suponen (D-059)."""
    path = tmp_path / "zapata.json"
    path.write_text(json.dumps(_project()), encoding="utf-8")
    _, checks = run_project(path)
    assert checks[0].status is Status.PASS
    dowels = [check for check in checks if check.name == "Pasadores: area minima"]
    assert [(check.member, check.status) for check in dowels] == [("Z1", Status.INCOMPLETE)]


def _row(case: str, step: str, forces: tuple[float, float, float, float, float]) -> dict[str, str]:
    """Fila de reacciones con FX, FY, FZ, MX y MY (MZ = 0) para el nudo 10."""
    values = (*forces, 0.0)
    return {"Story": "Base", "Label": "7", "Unique Name": "10", "Output Case": case, "Case Type": "Combination",
            "Step Type": step, **{name: str(value) for name, value in zip(HEADERS[6:], values, strict=True)}}


def _template(**changes: Any) -> EtabsFootingTemplate:
    footing = {key: value for key, value in _footing().items() if key not in {"id", "loads"}}
    data = {"description": "t", "profile": "nsr-10", "seismic": {"level": "DES", "justification": "ejemplo"},
            "materials": {"fc": 28.0, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight"}, "soil": SOIL,
            "load_factors": {"S1": {"dead": 1.0, "live": 1.0}, "U1": {"dead": 1.2, "live": 1.6},
                             "U2": {"dead": 0.9, "live": 0.0}},
            "footings": [{"id": "Z1", "etabs_unique_names": ["10"], **footing}]}
    data.update(changes)
    return EtabsFootingTemplate.model_validate(data)


def test_reactions_become_actions_on_the_footing() -> None:
    """La reacción del apoyo actúa sobre la estructura; sobre la zapata va la opuesta, salvo P = FZ (compresión)."""
    service = Table(HEADERS, UNITS, (_row("S1", "", (10.0, -20.0, 500.0, 30.0, -40.0)),))
    factored = Table(HEADERS, UNITS, (_row("U1", "Max", (1.0, 2.0, 700.0, 3.0, 4.0)), _row("U1", "Min", (-1.0, -2.0, 600.0, -3.0, -4.0)),
                                      _row("U2", "", (0.0, 0.0, -50.0, 0.0, 0.0))))

    project, summary = build_footing_project(_template(), service, factored)

    footing = project["footings"][0]
    assert footing["id"] == "Z1-7"
    loads = {load["case"]: load for load in footing["loads"]}
    assert loads["S1"] == {"case": "S1", "kind": "service", "dead_factor": 1.0, "live_factor": 1.0, "seismic": False, "P_kN": 500.0,
                           "Vx_kN": -10.0, "Vy_kN": 20.0, "Mx_kNm": -30.0, "My_kNm": 40.0}
    assert (loads["U1 (Max)"]["dead_factor"], loads["U1 (Max)"]["live_factor"]) == (1.2, 1.6)
    assert footing["surcharge_live_kNm2"] == 5.0
    assert loads["U1 (Min)"]["P_kN"] == 600.0
    assert (loads["U2"]["dead_factor"], loads["U2"]["live_factor"]) == (0.9, 0.0)
    assert loads["U2"]["P_kN"] == -50.0  # tracción en el apoyo: se resolverá como FAIL en V3D (D-054)
    assert summary.service_cases == ("S1",)
    assert summary.factored_cases == ("U1 (Max)", "U1 (Min)", "U2")
    Project.model_validate(project)


def test_missing_factors_and_joint_are_reported() -> None:
    service = Table(HEADERS, UNITS, (_row("S1", "", (0.0, 0.0, 500.0, 0.0, 0.0)),))
    factored = Table(HEADERS, UNITS, (_row("U1", "", (0.0, 0.0, 700.0, 0.0, 0.0)), _row("U3", "", (0.0, 0.0, 700.0, 0.0, 0.0))))
    template = _template(footings=[{**_template().footings[0].model_dump(mode="json"), "etabs_unique_names": ["10", "99"]}])

    with pytest.raises(EtabsImportError) as raised:
        build_footing_project(template, service, factored)

    messages = " | ".join(error.message for error in raised.value.errors)
    assert "'U3' no tiene factores de carga" in messages
    assert "'U2' de la plantilla no aparece en las tablas" in messages
    assert "'99' no tiene combinaciones en la tabla de servicio" in messages


def test_wrong_units_are_rejected() -> None:
    table = Table(HEADERS, {**UNITS, "FZ": "kip"}, ())
    with pytest.raises(EtabsImportError, match="FZ"):
        build_footing_project(_template(), table, table)


def test_example_workbooks_import(tmp_path: Path) -> None:
    project, summary, check = import_etabs_footings(SERVICE, FACTORED, TEMPLATE)

    assert check.status is Status.PASS
    assert project is not None and summary is not None
    assert summary.footings == 65
    assert len(summary.service_cases) == 9  # 1 sin envolvente + 4 con Max y Min
    assert len(summary.factored_cases) == 10  # 2 sin envolvente + 4 con Max y Min
    assert all(len(footing["loads"]) == 19 for footing in project["footings"])

    output = tmp_path / "zapatas.json"
    code = main(["import-etabs-footings", str(SERVICE), str(FACTORED), str(TEMPLATE), "--output", str(output)])
    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == project
