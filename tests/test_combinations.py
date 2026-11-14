"""Excel de combinaciones (D-137): lectura, filas con Usar = No, validaciones y su uso desde la plantilla."""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from structurelab_rc.engine import import_etabs_footings
from structurelab_rc.io.etabs.combinations import read_combinations
from structurelab_rc.io.etabs.importer import EtabsImportError

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Combinaciones.xlsx"
HEADERS = ("Combinacion", "Tipo", "Factor D", "Factor L", "Sismo", "Usar")


def _book(rows: list[tuple[object, ...]], path: Path, headers: tuple[str, ...] = HEADERS) -> Path:
    """Un libro mínimo con la hoja Combinaciones (celdas de texto en línea)."""
    def cell(column: int, row: int, value: object) -> str:
        reference = f"{chr(ord('A') + column)}{row}"
        if isinstance(value, (int, float)):
            return f'<c r="{reference}"><v>{value}</v></c>'
        return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
    data = "".join(f'<row r="{number}">{"".join(cell(index, number, value) for index, value in enumerate(values))}</row>'
                   for number, values in enumerate([headers, *rows], start=1))
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relations = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/workbook.xml", f'<workbook xmlns="{main}" xmlns:r="{relations}"><sheets>'
                                         '<sheet name="Combinaciones" sheetId="1" r:id="rId1"/></sheets></workbook>')
        book.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                                                    f'relationships"><Relationship Id="rId1" Type="{relations}/worksheet" '
                                                    'Target="worksheets/sheet1.xml"/></Relationships>')
        book.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{main}"><sheetData>{data}</sheetData></worksheet>')
    return path


def test_example_combinations() -> None:
    combinations = read_combinations(EXAMPLE)
    assert len(combinations) == 11
    service = combinations["SERVICIO 4 (D+L+EX+EZ)"]
    assert (service.kind, service.factors.dead, service.factors.live, service.factors.seismic) == ("service", 1.0, 1.0, True)
    factored = combinations["COMB1 (1.2D+1.6L)"]
    assert (factored.kind, factored.factors.dead, factored.factors.live, factored.factors.seismic) == ("factored", 1.2, 1.6, False)


def test_rows_with_use_no_are_left_out_and_text_is_tolerant(tmp_path: Path) -> None:
    """Tildes y mayúsculas no importan (Última, SÍ); la coma decimal vale; Usar = No deja la fila fuera."""
    book = _book([("S1", "Servicio", 1, 1, "No", "Si"), ("U1", "Última", "1,2", "1.6", "SÍ", "sí"),
                  ("ENV", "Ultima", 1, 1, "No", "No")], tmp_path / "c.xlsx")
    combinations = read_combinations(book)
    assert set(combinations) == {"S1", "U1"}
    assert (combinations["U1"].kind, combinations["U1"].factors.dead, combinations["U1"].factors.seismic) == ("factored", 1.2, True)


@pytest.mark.parametrize(("rows", "message"), [
    ([("S1", "Servicio", 1, 1, "No", "Si"), ("S1", "Servicio", 1, 1, "No", "Si")], "esta repetida"),
    ([("S1", "Mayorada", 1, 1, "No", "Si")], "'Tipo' debe ser servicio o ultima"),
    ([("S1", "Servicio", "uno", 1, "No", "Si")], "'Factor D' debe ser un numero"),
    ([("S1", "Servicio", -1, 1, "No", "Si")], "no puede ser negativo"),
    ([("S1", "Servicio", 1, 1, "Tal vez", "Si")], "'Sismo' debe ser si o no"),
    ([("S1", "Servicio", 1, 1, "No", "No")], "ninguna combinacion con Usar = Si"),
])
def test_invalid_rows_are_reported(rows: list[tuple[object, ...]], message: str, tmp_path: Path) -> None:
    with pytest.raises(EtabsImportError) as raised:
        read_combinations(_book(rows, tmp_path / "c.xlsx"))
    assert any(message in error.message for error in raised.value.errors), [error.message for error in raised.value.errors]


def test_missing_columns_are_reported(tmp_path: Path) -> None:
    book = _book([("S1", "Servicio", 1, 1)], tmp_path / "c.xlsx", HEADERS[:4])
    with pytest.raises(EtabsImportError) as raised:
        read_combinations(book)
    assert {error.message for error in raised.value.errors} == {"Falta la columna 'Sismo' en el Excel de combinaciones",
                                                                "Falta la columna 'Usar' en el Excel de combinaciones"}


def test_template_uses_its_combinations_excel_and_an_explicit_one_overrides_it(tmp_path: Path) -> None:
    """D-137: la importación toma el Excel de etabs_files.combinations; uno explícito lo reemplaza (aquí, sin las
    combinaciones de sismo: los casos mayorados con sismo dejan de entrar y el resumen los nombra)."""
    template = ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_centrica_etabs.json"
    reactions = ROOT / "examples" / "etabs" / "zapatas" / "pruebas"
    service, factored = reactions / "Joint Reactions - Servicio.xlsx", reactions / "Joint Reactions - Ultimas.xlsx"
    project, summary, check = import_etabs_footings(service, factored, template)
    assert project is not None and summary is not None and summary.ignored_combinations == ()
    rows: list[tuple[object, ...]] = [(name, "Servicio", 1, 1, "No", "Si") for name in ("SERVICIO 1 (D+L)",)]
    rows += [(name, "Ultima", 1.2, 1.6, "No", "Si") for name in ("COMB1 (1.2D+1.6L)",)]
    project, summary, check = import_etabs_footings(service, factored, template, combinations=_book(rows, tmp_path / "c.xlsx"))
    assert project is not None and summary is not None
    assert {load["case"] for load in project["footings"][0]["loads"]} <= {"SERVICIO 1 (D+L)", "COMB1 (1.2D+1.6L)"}
    assert "COMB4A (1.2D+L+EX+EZ)" in summary.ignored_combinations and "SERVICIO 2 (D+EX+EZ)" in summary.ignored_combinations
