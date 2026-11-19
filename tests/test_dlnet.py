"""Cartilla DL-NET (.dli, D-133): registros y punteros, lectura y escritura byte a byte, líneas de barras frente a las de
archivos guardados por DL-NET, formato numérico, mapa de diámetros desde la librería de la plantilla, grupos de la cola,
errores ante lo no soportado y la salida de report.

Los archivos reales (tests/fixtures/dlnet/, fuera de Git porque llevan la licencia de DL-NET del usuario) se usan si
están; las demás pruebas corren con una plantilla sintética con la misma estructura."""

import json
import struct
from pathlib import Path

import pytest
from frozen_examples import frozen

from structurelab_rc.detailing.schedule import Piece, ScheduleRow
from structurelab_rc.engine import report_file
from structurelab_rc.io.dlnet import (
    FINAL,
    TEMPLATE_PATH,
    TEMPLATE_VARIABLE,
    DliError,
    Record,
    bar_names,
    find_template,
    number,
    read_dli,
    read_records,
    row_line,
    schedule_dli,
    write_dli,
    write_records,
)

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "dlnet"
REAL = FIXTURES / "n_12.dli"  # guardado por DL-NET 2026: barra con L.5 L.5 y estribo E
SAVED = FIXTURES / "PRUEBA_StructureLab.dli"  # guardado por DL-NET: barra recta, un gancho, dos ganchos y estribo


def _real(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"falta {path.name} (plantilla real de DL-NET, local y fuera de Git)")
    return path.read_bytes()


def _synthetic(groups: tuple[str, ...] = ("Total",)) -> bytes:
    """Una plantilla con la estructura de DL-NET y sin datos de licencia: encabezado, librería de barras, librería de
    mallas, cero elementos y la cola con sus grupos."""
    texts = ["licencia de prueba", "DL-NET    PREFERENCIAS DIBUJOS   0", " 3 + 0",
             "\"5/8''\"   \"SR-No5\"   \"5\"   \"5/8\"   \"#5\"", "\"3/4''\"   \"SR-No6\"   \"6\"   \"#6\"",
             "\"1/2''\"   \"SR-No4\"   \"4\"   \"1/2\"   \"#4\"", "\"7/8''\"   \"SR-No7\"   \"#7\"",
             "\"3/8''\"   \"SR-No3\"   \"#3G60\"   \"#3\"", " 1 + 0", "\"XX-084\"   \"M-084\"", " 0",
             f" {len(groups)}", *(text for name in groups for text in (name, "-1", "")), " 0", " 0", ' 18    3   "Pagina"   ']
    return write_records([*(Record(text.encode("latin-1")) for text in texts), Record(FINAL, b"")])


def _row(mark: str, piece: Piece) -> ScheduleRow:
    return ScheduleRow(mark, piece)


def _bar(count: int, designation: str, cut: float, legs: dict[str, float], angles: tuple[int | None, int | None]) -> ScheduleRow:
    shape = "-".join({90: "L", 180: "U", 135: "135"}[angle] for angle in angles if angle is not None) or "recta"
    dimensions = (("A", cut), *legs.items())
    return _row("Z-01", Piece("g", designation, shape, dimensions, cut, 1.0, count, "", angles))


def _stirrup(count: int, designation: str, size: tuple[float, float], hook: float, angle: int = 135) -> ScheduleRow:
    dimensions = (("A", size[0]), ("B", size[1]), ("C", hook))
    return _row("Z-02", Piece("estribos", designation, "E", dimensions, 2000.0, 1.0, count, "", (angle, angle)))


NAMES = {"#3": "3/8''", "#4": "1/2''", "#5": "5/8''", "#6": "3/4''", "#9": "1-1/8''"}


def test_real_file_round_trips_byte_by_byte() -> None:
    data = _real(REAL)
    assert write_records(read_records(data)) == data
    assert write_dli(read_dli(data)) == data


def test_generated_file_has_correct_pointers() -> None:
    template = _synthetic()
    data = write_dli(read_dli(template).__class__(read_dli(template).prefix, (), read_dli(template).suffix))
    offset, previous = 0, None
    while True:
        pointer, size = struct.unpack_from("<dH", data, offset)
        text = data[offset + 10:offset + 10 + size]
        if text == FINAL:
            assert pointer == previous  # el último repite el puntero del anterior
            assert offset + 10 + size == len(data)
            break
        assert pointer == offset + 12 + size + 1  # la posición, en base 1, del registro siguiente
        previous, offset = pointer, offset + 12 + size


def test_lines_match_the_files_saved_by_dlnet() -> None:
    """Las líneas generadas desde la cartilla son las que guardó DL-NET (barra con L.5 L.5 en n_12.dli; barra recta, un
    gancho, dos ganchos y estribo en PRUEBA_StructureLab.dli)."""
    real = read_dli(_real(REAL))
    names = bar_names(real.prefix)
    assert row_line(_bar(1, "#9", 5800.0, {"B": 500.0, "C": 500.0}, (90, 90)), names) == real.elements[0].lines[0]
    saved = read_dli(_real(SAVED))
    lines = [line for element in saved.elements for line in element.lines]
    assert row_line(_bar(3, "#6", 6400.0, {"B": 300.0, "C": 300.0}, (90, 90)), names) == lines[0]
    assert row_line(_bar(3, "#6", 6400.0, {"B": 300.0}, (90, None)), names) == lines[1]
    assert row_line(_bar(2, "#5", 2200.0, {}, (None, None)), names) == lines[2]
    assert row_line(_stirrup(28, "#3", (300.0, 450.0), 100.0), names) == lines[5]


def test_lines_without_the_real_files() -> None:
    assert row_line(_bar(1, "#9", 5800.0, {"B": 500.0, "C": 500.0}, (90, 90)), NAMES) == '1  "1-1/8\'\'"  5.8   L.5   L.5'
    assert row_line(_bar(2, "#5", 2200.0, {}, (None, None)), NAMES) == '2  "5/8\'\'"  2.2'
    assert row_line(_bar(3, "#6", 6400.0, {"C": 300.0}, (None, 90)), NAMES) == '3  "3/4\'\'"  6.4   L.3'
    assert row_line(_bar(1, "#5", 5800.0, {"B": 180.0, "C": 180.0}, (180, 180)), NAMES) == '1  "5/8\'\'"  5.8   U.2   U.2'
    assert row_line(_stirrup(6, "#4", (300.0, 500.0), 150.0), NAMES) == '6  E  "1/2\'\'"  .3*.5   G.15   F0/90'
    # Las dimensiones son las de la cartilla: redondeadas hacia arriba a 50 mm.
    assert row_line(_bar(16, "#6", 1550.0, {"B": 331.0}, (90, None)), NAMES) == '16  "3/4\'\'"  1.55   L.35'


@pytest.mark.parametrize(("value", "text"), [(0.5, ".5"), (6.0, "6"), (2.45, "2.45"), (0.05, ".05"), (12.0, "12"),
                                             (1.55, "1.55"), (0.125, ".125"), (10.5, "10.5")])
def test_number_format(value: float, text: str) -> None:
    assert number(value) == text


def test_bar_names_come_from_the_template_library() -> None:
    names = bar_names(read_dli(_synthetic()).prefix)
    assert names["#5"] == "5/8''" and names["5/8"] == "5/8''" and names["#4"] == "1/2''" and names["#6"] == "3/4''"
    assert "M-084" not in names  # la librería de mallas no entra


def test_bar_names_of_the_real_template() -> None:
    names = bar_names(read_dli(_real(REAL)).prefix)
    expected = {"#3": "3/8''", "#4": "1/2''", "#5": "5/8''", "#6": "3/4''", "#7": "7/8''", "#8": "1''", "#9": "1-1/8''",
                "#10": "1-1/4''"}
    assert {key: names[key] for key in expected} == expected


@pytest.mark.parametrize(("row", "message"), [
    (_row("Z-09", Piece("g", "#5", "G", (("A", 500.0),), 500.0, 1.0, 6, "", (None, None))), "forma 'G'"),
    (_bar(1, "#5", 2000.0, {"B": 300.0}, (135, None)), "gancho de 135"),
    (_stirrup(4, "#4", (300.0, 400.0), 100.0, angle=90), "estribos con ganchos de 135"),
    (_bar(1, "#14", 2000.0, {}, (None, None)), "no está en la librería"),
])
def test_unsupported_bars_raise_a_clear_error(row: ScheduleRow, message: str) -> None:
    with pytest.raises(DliError, match=message):
        row_line(row, NAMES)


def test_group_membership_follows_the_elements(tmp_path: Path) -> None:
    template = tmp_path / "plantilla.dli"
    template.write_bytes(_synthetic(("Total", "vigas")))
    rows = [_bar(2, "#5", 2200.0, {}, (None, None))]
    result = read_dli(schedule_dli([("Z1", rows), ("Z2", rows), ("Z3", rows)], template))
    assert [element.name for element in result.elements] == ["Z1", "Z2", "Z3"]
    assert [record.value for record in result.suffix[:7]] == [" 2", "Total", "-1", " 1  1  1 ", "vigas", "-1", " 1  1  1 "]


def test_find_template_prefers_the_environment_then_searches_upward(tmp_path: Path) -> None:
    project = tmp_path / "a" / "b"
    project.mkdir(parents=True)
    (tmp_path / TEMPLATE_PATH).parent.mkdir(parents=True)
    (tmp_path / TEMPLATE_PATH).write_bytes(_synthetic())
    assert find_template(project, {}) == (tmp_path / TEMPLATE_PATH).resolve()  # la de la carpeta superior más cercana
    other = tmp_path / "otra.dli"
    other.write_bytes(_synthetic())
    assert find_template(project, {TEMPLATE_VARIABLE: str(other)}) == other
    assert find_template(project, {TEMPLATE_VARIABLE: str(tmp_path / "no_existe.dli")}) is None


def test_report_writes_the_dli_with_the_declared_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template = tmp_path / "plantilla.dli"
    template.write_bytes(_synthetic())
    monkeypatch.setenv(TEMPLATE_VARIABLE, str(template))
    output = tmp_path / "zapata_combinada"
    report = report_file(frozen("nsr_10", "zapatas", "zapata_combinada.json"), output)
    path = output / "zapata_combinada.dli"
    assert path in report.files and not report.notes
    written = read_dli(path.read_bytes())
    rows = json.loads((output / "resultado.json").read_text(encoding="utf-8"))["combined_footings"][0]["detailing"]["rows"]
    assert [element.name for element in written.elements] == ["ZC1"]
    assert len(written.elements[0].lines) == len(rows)  # una línea por marca de la cartilla


def test_report_without_template_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TEMPLATE_VARIABLE, str(tmp_path / "no_existe.dli"))
    report = report_file(frozen("nsr_10", "zapatas", "zapata_centrica.json"), tmp_path / "salida")
    assert not any(path.suffix == ".dli" for path in report.files)
    assert any("salida.dli no se genero" in note for note in report.notes)
