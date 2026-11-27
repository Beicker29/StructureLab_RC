"""Despiece y dibujo del muro de contención en voladizo (D-175) con el ejemplo 2 congelado (ACI 318-25), contra valores
calculados aquí a mano: cantidades por separación, tramos de cara a cara y ganchos de la Tabla 25.3.1 con la convención
de DL-NET (D-147)."""

import json
import math
from pathlib import Path

import pytest
from frozen_examples import frozen
from pydantic import ValidationError

from structurelab_rc.engine import report_file, verify_file
from structurelab_rc.model.project import Project

IN = 25.4
DB7, DB5 = 22.2, 15.9  # mm, catálogo


def _ceil(value: float, step: float) -> float:
    return math.ceil(value / step - 1e-9) * step


def _l90(db: float) -> float:
    """L del gancho de 90° (DL-NET, D-147): 12db + π·(6db + 0.5db)/8, hacia arriba a 50 mm (No. 7 y 5: D = 6db)."""
    return _ceil(12 * db + math.pi * 6.5 * db / 8, 50.0)


def _u180(db: float) -> float:
    """U del gancho de 180°: máx(4db, 65) + 0.5·π·6.5db − 0.5·6.5db, hacia arriba a 50 mm."""
    return _ceil(max(4 * db, 65.0) + 0.5 * math.pi * 6.5 * db - 0.5 * 6.5 * db, 50.0)


def _count(span: float, spacing: float) -> int:
    return math.floor(span / spacing + 1e-9) + 1


def _expected() -> dict[str, tuple[str, int, dict[str, float]]]:
    """Ejemplo 2 en SI con L = 10 m, corona a 180°: marca → (barra, cantidad, dimensiones)."""
    length, hb, stem_h, t = 10000.0, 24 * IN, 16 * 12 * IN, 15 * IN
    toe, heel, stem_cover, base_cover = 30 * IN, 66 * IN, 2 * IN, 3 * IN
    width = toe + t + heel
    vertical = _ceil(hb + stem_h - stem_cover - (base_cover + DB7), 10.0)  # del pie, sobre la malla inferior, a la corona
    heights = _count(hb + stem_h - stem_cover - DB5 / 2 - (hb + stem_cover + DB5 / 2), 450.0)
    return {
        "M1-01": ("#7", _count(length - 2 * stem_cover - DB7, 9 * IN), {"A": vertical, "B": _l90(DB7), "C": _u180(DB7)}),
        "M1-02": ("#5", _count(length - 2 * stem_cover - DB5, 450.0), {"A": vertical, "C": _u180(DB5)}),
        "M1-03": ("#5", 2 * heights, {"A": _ceil(length - 2 * stem_cover, 10.0)}),
        "M1-04": ("#7", _count(length - 2 * base_cover - DB7, 4.5 * IN) + _count(length - 2 * base_cover - DB7, 9 * IN),
                  {"A": _ceil(width - 2 * base_cover, 10.0)}),
        "M1-05": ("#7", 2 * _count(width - 2 * base_cover - DB7, 14 * IN), {"A": _ceil(length - 2 * base_cover, 10.0)}),
    }


def test_the_wall_schedule_and_drawing(tmp_path: Path) -> None:
    report_file(frozen("aci_318_25", "muros", "muro_voladizo.json"), tmp_path)
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    rows = {row["mark"]: row for row in results["retaining_walls"][0]["detailing"]["rows"]}
    expected = _expected()
    assert set(rows) == set(expected)
    for mark, (designation, count, dimensions) in expected.items():
        row = rows[mark]
        assert (row["designation"], row["count"]) == (designation, count), mark
        assert row["dimensions [mm]"] == pytest.approx(dimensions), mark
        assert row["cut_length [mm]"] == pytest.approx(sum(dimensions.values())), mark
    assert rows["M1-01"]["shape"] == "L-U" and rows["M1-02"]["shape"] == "U"
    concrete = (2819.4 * 609.6 + 381.0 * 4876.8) * 10000 / 1e9
    assert results["retaining_walls"][0]["detailing"]["concrete [m3]"] == pytest.approx(concrete, rel=1e-5)
    model = json.loads((tmp_path / f"{tmp_path.name}_drawing.json").read_text(encoding="utf-8"))
    assert model["titles"]["M1"] == "M1 H=5.486"
    assert [view["name"] for view in model["elements"]["M1"]] == ["geometria", "refuerzo", "barras", "alzado", "cartilla"]
    assert {"MURO", "RELLENO"} <= set(model["layers"])
    assert all((tmp_path / f"M1_{name}.svg").exists() for name in ("geometria", "refuerzo", "barras", "alzado", "cartilla"))
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    assert "Despiece y cantidades" in text and "Gancho de la corona pantalla, cara del relleno" in text


def test_a_crown_hook_that_does_not_fit_fails(tmp_path: Path) -> None:
    """Con gancho de 90° en la corona, la pata del N.° 7 (.35) no cabe en la pantalla (.381 − 2 × .0508 = .279)."""
    data = json.loads(frozen("aci_318_25", "muros", "muro_voladizo.json").read_text(encoding="utf-8"))
    data["retaining_walls"][0]["stem"]["crown_end"] = "hook90"
    path = tmp_path / "muro.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    checks = {check.name: check for check in verify_file(path)}
    back, front = checks["Gancho de la corona pantalla, cara del relleno"], checks["Gancho de la corona pantalla, cara exterior"]
    assert (str(back.status), back.demand, back.capacity) == ("FAIL", _l90(DB7), pytest.approx(15 * IN - 4 * IN))
    assert str(front.status) == "PASS" and front.demand == _l90(DB5)


def test_the_wall_detailing_needs_its_length_and_crown() -> None:
    data = json.loads(frozen("aci_318_25", "muros", "muro_voladizo.json").read_text(encoding="utf-8"))
    del data["retaining_walls"][0]["length"]
    with pytest.raises(ValidationError, match="requiere length"):
        Project.model_validate(data)
