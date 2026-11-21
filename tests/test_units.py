"""Elementos tipo y sus N unidades (D-159): la agrupación de las cartillas por tipo (N es la suma de quantity, solo se
unen las cartillas iguales barra por barra), la cartilla de N unidades y, de extremo a extremo, dos zapatas del mismo
tipo: una cartilla y un despiece por tipo, la tabla de N unidades en el resultado, la memoria, el CSV y el DXF, y N en los
grupos del .dli."""

import copy
import csv
import io
import json
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen

from structurelab_rc.detailing.schedule import Piece, ScheduleRow
from structurelab_rc.detailing.units import Member, scaled, units
from structurelab_rc.engine import report_file
from structurelab_rc.io.dlnet import read_dli

FIRST, SECOND = 2, 3  # las unidades declaradas de las dos zapatas del tipo


def _rows(typology: str, count: int = 10, group: str = "malla inferior x") -> tuple[ScheduleRow, ...]:
    piece = Piece(group, "#5", "recta", (("A", 2300.0),), 2300.0, 1.552, count, f"nota de {group}")
    return (ScheduleRow(f"{typology}-01", piece),)


def test_members_of_a_type_add_their_units() -> None:
    """El grupo y la nota no cuentan (nombran las columnas de cada elemento); el tipo conserva los del primero."""
    found, warnings = units([Member("Z1-150", "Z1", FIRST, _rows("Z1")),
                             Member("Z1-28", "Z1", SECOND, _rows("Z1", group="band columna C28")),
                             Member("Z2", "Z2", 1, _rows("Z2", count=4))])
    assert warnings == []
    assert [(unit.name, unit.members, unit.quantity) for unit in found] == [("Z1", ("Z1-150", "Z1-28"), FIRST + SECOND),
                                                                           ("Z2", ("Z2",), 1)]
    assert found[0].rows[0].piece.group == "malla inferior x"


def test_a_member_with_other_bars_keeps_its_own_schedule() -> None:
    found, warnings = units([Member("Z1-150", "Z1", 1, _rows("Z1")), Member("Z1-28", "Z1", 1, _rows("Z1", count=11))])
    assert [(unit.name, unit.quantity) for unit in found] == [("Z1", 1), ("Z1-28", 1)]
    assert [row.mark for row in found[1].rows] == ["Z1-28-01"]
    assert len(warnings) == 1 and "Z1-28" in warnings[0] and "D-159" in warnings[0]


def test_scaled_multiplies_the_count_and_the_mass() -> None:
    (row,) = _rows("Z1")
    (many,) = scaled([row], 7)
    assert many.piece.count == 7 * row.piece.count
    assert many.mass == pytest.approx(7 * row.mass)
    assert many.mark == row.mark


def _two_of_a_type() -> dict[str, Any]:
    """La zapata congelada dos veces con el mismo tipo: la primera se construye FIRST veces y la segunda SECOND."""
    project = json.loads(frozen("nsr_10", "zapatas", "zapata_centrica.json").read_text(encoding="utf-8"))
    first = project["footings"][0]
    second = copy.deepcopy(first)
    first.update(id="Z1a", typology="ZT", quantity=FIRST)
    second.update(id="Z1b", typology="ZT", quantity=SECOND)
    project["footings"] = [first, second]
    return project


@pytest.fixture(scope="module")
def two_of_a_type(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("tipo")
    path = folder / "tipo.json"
    path.write_text(json.dumps(_two_of_a_type(), ensure_ascii=False), encoding="utf-8")
    report_file(path, folder / "salida")
    return folder / "salida"


def test_one_schedule_per_type_with_its_units(two_of_a_type: Path) -> None:
    results = json.loads((two_of_a_type / "resultado.json").read_text(encoding="utf-8"))
    data = [footing["detailing"] for footing in results["footings"]]
    assert data[0] == data[1]
    unit = data[0]
    assert (unit["element"], unit["members"], unit["units"]) == ("ZT", ["Z1a", "Z1b"], FIRST + SECOND)
    assert all(row["mark"].startswith("ZT-") for row in unit["rows"])
    n = FIRST + SECOND
    assert [item["count"] for item in unit["total"]["rows"]] == [row["count"] * n for row in unit["rows"]]
    for row, item in zip(unit["rows"], unit["total"]["rows"], strict=True):
        assert item["mass [kg]"] == pytest.approx(row["mass [kg]"] * n, abs=0.06 * n)
    assert unit["total"]["steel [kg]"] == pytest.approx(unit["steel [kg]"] * n, abs=0.06 * n)
    assert unit["total"]["concrete [m3]"] == pytest.approx(unit["concrete [m3]"] * n, abs=1e-3 * n)


def test_csv_lists_the_type_once_with_the_totals(two_of_a_type: Path) -> None:
    rows = list(csv.DictReader(io.StringIO((two_of_a_type / "cartilla.csv").read_text(encoding="utf-8")), delimiter=";"))
    assert {row["elemento"] for row in rows} == {"ZT"}
    assert len({row["marca"] for row in rows}) == len(rows)
    for row in rows:
        assert int(row["unidades"]) == FIRST + SECOND
        assert int(row["cantidad total"]) == int(row["cantidad"]) * (FIRST + SECOND)


def test_drawing_and_memoir_show_the_type_once(two_of_a_type: Path) -> None:
    drawing = json.loads((two_of_a_type / "salida_drawing.json").read_text(encoding="utf-8"))
    views = drawing["elements"]
    assert "ZT" in views and "Z1a" not in views and "Z1b" not in views
    (cartilla,) = [view for view in views["ZT"] if view["name"] == "cartilla"]
    texts = [entity["text"] for entity in cartilla["entities"] if entity.get("text")]
    assert f"Cartilla de despiece ZT: {FIRST + SECOND} unidades" in texts
    memoir = (two_of_a_type / "memoria.txt").read_text(encoding="utf-8")
    assert f"Tipo ZT: se construye {FIRST + SECOND} veces (Z1a, Z1b; D-159)" in memoir
    assert f"Cant. ({FIRST + SECOND} u.)" in memoir


def test_dli_has_one_element_per_type_with_its_units(two_of_a_type: Path) -> None:
    files = list(two_of_a_type.glob("*.dli"))
    if not files:
        pytest.skip("sin plantilla DL-NET local (references/dlnet/plantilla.dli)")
    saved = read_dli(files[0].read_bytes())
    assert [element.name for element in saved.elements] == ["ZT"]
    assert saved.suffix[3].value == f" {FIRST + SECOND} "
