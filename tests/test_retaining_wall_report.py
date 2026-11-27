"""Memoria y resultado del muro de contención en voladizo (D-173, fase A, etapa 5) con el ejemplo 2 congelado."""

import json
from pathlib import Path

import pytest
from frozen_examples import frozen

from structurelab_rc.engine import report_file

CHAPTERS = ("Propiedades geométricas, suelo y armado", "Empuje del relleno y casos de carga",
            "Revisión geotécnica: presión, contacto y estabilidad", "Revisión de requerimientos técnicos",
            "Revisión de capacidad a momento flector", "Revisión de cortante en una dirección",
            "Revisión de desarrollo y anclaje del refuerzo", "Índices DCR", "Notas y limitaciones")


@pytest.mark.parametrize("profile", ["aci_318_25", "nsr_10"])
def test_the_wall_report(profile: str, tmp_path: Path) -> None:
    report = report_file(frozen(profile, "muros", "muro_voladizo.json"), tmp_path)
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    (wall,) = results["retaining_walls"]
    assert report.status == wall["status"] == ("PASS" if profile == "aci_318_25" else "FAIL")
    assert results["retaining_soil"]["phi [deg]"] == pytest.approx(35.0)
    thrust = wall["thrust"]["estabilidad"]
    # Ejemplo 2 del manual: talón corto por Das, Chu sobre AC; Ph = 70.5 kN/m y Pv = 79.5 kN/m.
    assert (thrust["plano"], thrust["talon"]) == ("AC", "corto")
    assert thrust["Ph [kN]"] == pytest.approx(70.48, abs=0.01)
    bearing = next(check for check in wall["checks"] if check["name"] == "Presion admisible del suelo")
    assert bearing["case"] == "D+H" and bearing["values"]["N [kN]"] == pytest.approx(225.5, abs=0.05)
    assert bearing["demand"] == pytest.approx(131.4, abs=0.05)  # kPa
    flexure = next(check for check in wall["checks"] if check["name"] == "Flexion pantalla")
    assert flexure["demand"] == pytest.approx(144.83, abs=0.01)  # kN·m por metro
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    assert "Muro de contención M1" in text and "Franja de cálculo: 1 m de muro" in text
    assert all(chapter in text for chapter in CHAPTERS)
    assert "Resultante, presiones y factores de seguridad por caso de servicio" in text
    assert "ubicación gobernante: caso D+H" in text
