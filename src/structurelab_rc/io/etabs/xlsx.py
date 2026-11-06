"""Lectura de tablas de ETABS exportadas a Excel (.xlsx) con la biblioteca estándar (D-023)."""

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_TABLE_HEAD_ROWS = 3


class XlsxError(ValueError):
    """El archivo no es un libro de Excel legible o no tiene la hoja pedida."""


@dataclass(frozen=True)
class Table:
    """Tabla de ETABS: encabezados, unidades por columna y filas de datos como texto."""

    headers: tuple[str, ...]
    units: dict[str, str]
    rows: tuple[dict[str, str], ...]


def _column(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if letters is None:
        raise XlsxError(f"referencia de celda invalida: {reference}")
    index = 0
    for letter in letters.group(0):
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in item.iter(f"{_MAIN}t")) for item in root]


def _sheet_path(book: zipfile.ZipFile, name: str) -> str:
    workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
    relations = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {relation.get("Id"): relation.get("Target", "") for relation in relations.iter(f"{_PACKAGE_REL}Relationship")}
    for sheet in workbook.iter(f"{_MAIN}sheet"):
        if sheet.get("name") == name:
            target = targets[sheet.get(f"{_REL}id")].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise XlsxError(f"el libro no tiene la hoja '{name}'")


def _cell_text(cell: ElementTree.Element, strings: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{_MAIN}t"))
    value = cell.find(f"{_MAIN}v")
    if value is None or value.text is None:
        return ""
    return strings[int(value.text)] if kind == "s" else value.text


def read_table(path: Path, sheet: str) -> Table:
    """Lee una hoja con el formato de ETABS: título, encabezados, unidades y datos."""
    try:
        with zipfile.ZipFile(path) as book:
            strings = _shared_strings(book)
            root = ElementTree.fromstring(book.read(_sheet_path(book, sheet)))
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise XlsxError(f"no se pudo leer el libro: {error}") from error
    grid = []
    for row in root.iter(f"{_MAIN}row"):
        cells = {_column(cell.get("r", "A1")): _cell_text(cell, strings) for cell in row.iter(f"{_MAIN}c")}
        grid.append([cells.get(index, "") for index in range(max(cells, default=-1) + 1)])
    if len(grid) < _TABLE_HEAD_ROWS:
        raise XlsxError(f"la hoja '{sheet}' no tiene titulo, encabezados y unidades")
    headers = tuple(grid[1])
    units = {header: (grid[2][index] if index < len(grid[2]) else "") for index, header in enumerate(headers)}
    rows = tuple(
        {header: (values[index] if index < len(values) else "") for index, header in enumerate(headers)}
        for values in grid[3:]
        if any(values)
    )
    return Table(headers, units, rows)
