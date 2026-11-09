import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import import_etabs
from structurelab_rc.io.etabs.xlsx import read_table
from structurelab_rc.model.loader import load_project

EXAMPLES = Path(__file__).parent.parent / "examples"
WORKBOOK = EXAMPLES / "etabs" / "vigas" / "Element Forces - Beams.xlsx"
TEMPLATE = EXAMPLES / "nsr_10" / "vigas" / "plantilla_vigas_etabs.json"
HEADERS = ["Story", "Beam", "Unique Name", "Output Case", "Case Type", "Step Type", "Station", "P", "V2", "V3", "T", "M2", "M3"]
UNITS = ["", "", "", "", "", "", "m", "kN", "kN", "kN", "kN-m", "kN-m", "kN-m"]


def _workbook(path: Path, rows: list[list[Any]], units: list[str] = UNITS, headers: list[str] = HEADERS) -> Path:
    """Libro mínimo con la hoja de ETABS, escrito con cadenas en línea."""
    def cell(column: int, row: int, value: Any) -> str:
        reference = f"{chr(65 + column)}{row}"
        if isinstance(value, str):
            return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'
        return f'<c r="{reference}"><v>{value}</v></c>'

    grid = [["TABLE:  Element Forces - Beams"], headers, units, *rows]
    body = "".join(
        f'<row r="{index}">' + "".join(cell(column, index, value) for column, value in enumerate(values)) + "</row>"
        for index, values in enumerate(grid, start=1)
    )
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/workbook.xml", f'<workbook xmlns="{main_ns}" xmlns:r="{rel_ns}"><sheets>'
                      '<sheet name="Element Forces - Beams" sheetId="1" r:id="rId1"/></sheets></workbook>')
        book.writestr("xl/_rels/workbook.xml.rels",
                      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                      '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/></Relationships>')
        book.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{main_ns}"><sheetData>{body}</sheetData></worksheet>')
    return path


def _row(unique: str = "117", case: str = "1.4DT", case_type: str = "Combination", step: str = "", station: float = 1.03) -> list[Any]:
    return ["Piso", "B34", unique, case, case_type, step, station, -10.0, 20.0, 0.1, 1.0, 0.2, 30.0]


def _template(tmp_path: Path, **changes: Any) -> Path:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["members"] = data["members"][:1]
    data |= changes
    path = tmp_path / "plantilla.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_real_workbook_imports_every_combination_state() -> None:
    project, summary, check = import_etabs(WORKBOOK, TEMPLATE)
    assert check.status is not Status.FAIL
    assert project is not None and summary is not None
    assert (summary.members, summary.stations, len(summary.cases), summary.skipped_rows) == (2, 638, 29, 0)
    assert "0.9DT+S.R.A.X+FZ (Max)" in summary.cases
    assert "0.9DT+S.R.A.X+FZ (Min)" in summary.cases


def test_units_and_signs_are_converted_to_the_input_format() -> None:
    project, _, _ = import_etabs(WORKBOOK, TEMPLATE)
    assert project is not None
    station = next(s for s in project["members"][0]["stations"] if s["case"] == "0.9DT+S.R.A.X+FZ (Max)" and s["z"] == pytest.approx(175.0))
    # Fila de ETABS: P = 7.5301 kN (tracción), V2 = −16.3732, V3 = 0.0518 kN, T = 0.6645, M2 = 0.1317, M3 = −2.5491 kN-m.
    expected = {"Pu_kN": -7.5301, "Mu_kNm": -2.5491, "M2_kNm": 0.1317, "Vu_kN": -16.3732, "V3_kN": 0.0518, "Tu_kNm": 0.6645}
    assert station["demands"] == pytest.approx(expected)


def test_each_station_takes_the_layout_of_its_segment() -> None:
    project, _, _ = import_etabs(WORKBOOK, TEMPLATE)
    assert project is not None
    stations = project["members"][0]["stations"]
    support = next(s for s in stations if s["z"] == pytest.approx(175.0))
    midspan = next(s for s in stations if s["z"] == pytest.approx(2312.5))
    assert support["layout"]["stirrups"]["spacing"] == 100.0
    assert midspan["layout"]["stirrups"]["spacing"] == 150.0


def test_cli_writes_a_project_that_loads(tmp_path: Path) -> None:
    output = tmp_path / "proyecto.json"
    assert main(["import-etabs", str(WORKBOOK), str(TEMPLATE), "--output", str(output)]) == 0
    assert len(load_project(output).members) == 2


def test_only_the_listed_combinations_are_imported(tmp_path: Path) -> None:
    project, summary, _ = import_etabs(WORKBOOK, _template(tmp_path, combinations=["1.4DT", "0.9DT+S.R.A.X+FZ"]))
    assert project is not None and summary is not None
    assert set(summary.cases) == {"1.4DT", "0.9DT+S.R.A.X+FZ (Max)", "0.9DT+S.R.A.X+FZ (Min)"}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"combinations": ["NO EXISTE"]}, "NO EXISTE"),
        ({"members": [{**json.loads(TEMPLATE.read_text(encoding="utf-8"))["members"][0], "etabs_unique_name": "999"}]}, "999"),
    ],
)
def test_template_mismatches_are_reported(tmp_path: Path, changes: dict[str, Any], message: str) -> None:
    project, _, check = import_etabs(WORKBOOK, _template(tmp_path, **changes))
    assert project is None
    assert check.status is Status.FAIL
    assert any(message in error.message for error in check.errors)


def test_stations_outside_every_segment_are_rejected(tmp_path: Path) -> None:
    workbook = _workbook(tmp_path / "libro.xlsx", [_row(station=4.7)])
    project, _, check = import_etabs(workbook, _template(tmp_path))
    assert project is None
    assert any("tramo" in error.message for error in check.errors)


def test_wrong_units_and_missing_columns_are_rejected(tmp_path: Path) -> None:
    feet = _workbook(tmp_path / "pies.xlsx", [_row()], units=["", "", "", "", "", "", "ft", "kip", "kN", "kN", "kN-m", "kN-m", "kN-m"])
    _, _, check = import_etabs(feet, _template(tmp_path))
    assert {error.message for error in check.errors} >= {
        "La columna 'Station' debe venir en m; viene en 'ft'",
        "La columna 'P' debe venir en kN; viene en 'kip'",
    }
    row = _row()
    no_torsion = _workbook(tmp_path / "sin_t.xlsx", [[*row[:10], *row[11:]]], [*UNITS[:10], *UNITS[11:]], [*HEADERS[:10], *HEADERS[11:]])
    _, _, check = import_etabs(no_torsion, _template(tmp_path))
    assert any("'T'" in error.message for error in check.errors)


def test_load_cases_that_are_not_combinations_are_skipped(tmp_path: Path) -> None:
    workbook = _workbook(tmp_path / "libro.xlsx", [_row(), _row(case="DEAD", case_type="LinStatic")])
    _, summary, _ = import_etabs(workbook, _template(tmp_path))
    assert summary is not None
    assert (summary.stations, summary.skipped_rows) == (1, 1)


def test_unreadable_files_fail_without_a_traceback(tmp_path: Path) -> None:
    broken = tmp_path / "roto.xlsx"
    broken.write_text("no es un libro", encoding="utf-8")
    _, _, check = import_etabs(broken, TEMPLATE)
    assert check.status is Status.FAIL


def test_reader_handles_shared_and_inline_strings(tmp_path: Path) -> None:
    table = read_table(WORKBOOK, "Element Forces - Beams")
    assert table.units["Station"] == "m"
    synthetic = read_table(_workbook(tmp_path / "libro.xlsx", [_row()]), "Element Forces - Beams")
    assert synthetic.rows[0]["Output Case"] == "1.4DT"
    assert float(synthetic.rows[0]["Station"]) == pytest.approx(1.03)
