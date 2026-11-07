import builtins
import json
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import report_file
from structurelab_rc.reporting.pdf import latin1, write_pdf
from structurelab_rc.reporting.results import check_data, significant

EXAMPLE = Path(__file__).parent.parent / "examples" / "nsr_10" / "beam_t.json"


def _report(tmp_path: Path, **options: Any) -> tuple[dict[str, Any], str]:
    report_file(EXAMPLE, tmp_path, **options)
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    return results, (tmp_path / "memoria.txt").read_text(encoding="utf-8")


def test_significant_rounds_only_for_presentation() -> None:
    assert significant(123456789.0) == 123457000.0
    assert significant(0.000123456789) == 0.000123457
    assert significant(0.0) == 0.0


def test_check_data_converts_to_presentation_units() -> None:
    check = Check("Flexion: resistencia", Status.PASS, demand=150e6, capacity=174.7e6, unit="N*mm",
                  values=(("phi", 0.9), ("Mn3", 194.1e6), ("Vc", 118.7e3), ("d", 440.0)))
    data = check_data(check)
    assert (data["unit"], data["demand"], data["capacity"]) == ("kN-m", 150.0, 174.7)
    assert data["ratio"] == significant(150e6 / 174.7e6)
    assert data["values"] == {"phi": 0.9, "Mn3 [kN-m]": 194.1, "Vc [kN]": 118.7, "d [mm]": 440.0}


def test_results_hold_every_station_and_check(tmp_path: Path) -> None:
    results, _ = _report(tmp_path)
    assert results["status"] == "PASS"
    assert results["project"]["seismic"]["justification"]
    member = results["members"][0]
    assert [station["z [mm]"] for station in member["stations"]] == [0.0, 3000.0]
    names = {check["name"] for check in member["stations"][0]["checks"]}
    assert {"Flexion: resistencia", "Torsion: refuerzo longitudinal", "Cortante V3: resistencia"} <= names


def test_phi_in_the_memoir_comes_from_the_results(tmp_path: Path) -> None:
    results, text = _report(tmp_path)
    strength = next(check for check in results["members"][0]["stations"][0]["checks"] if check["name"] == "Flexion: resistencia")
    assert f"phi = {strength['values']['phi']:.5f}" in text


def test_memoir_has_its_sections_and_the_declared_seismic_level(tmp_path: Path) -> None:
    _, text = _report(tmp_path)
    for heading in ("1. DATOS DEL PROYECTO", "2. SUPUESTOS Y CONVENCIONES", "3. RESUMEN POR MIEMBRO",
                    "4. VERIFICACIONES QUE NO CUMPLEN", "5. ESTACIONES CRITICAS"):
        assert heading in text
    assert "Nivel sismico declarado: DMO" in text
    assert "6. DETALLE DE TODAS LAS ESTACIONES" not in text
    _, full = _report(tmp_path / "completo", full=True)
    assert "6. DETALLE DE TODAS LAS ESTACIONES" in full


def test_failing_checks_are_listed(tmp_path: Path) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["members"][0]["stations"][1]["demands"]["Mu_kNm"] = 600.0
    project = tmp_path / "falla.json"
    project.write_text(json.dumps(data), encoding="utf-8")
    report = report_file(project, tmp_path / "salida")
    text = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert report.status == "FAIL"
    section = text.split("4. VERIFICACIONES QUE NO CUMPLEN")[1].split("5. ESTACIONES CRITICAS")[0]
    assert "Flexion: resistencia, z = 3000 mm" in section


def test_invalid_input_produces_a_short_report(tmp_path: Path) -> None:
    broken = tmp_path / "roto.json"
    broken.write_text("{", encoding="utf-8")
    report = report_file(broken, tmp_path / "salida")
    assert report.status == "FAIL"
    assert "La entrada no es valida" in (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")


def test_outputs_have_no_date_and_are_reproducible(tmp_path: Path) -> None:
    first, first_text = _report(tmp_path / "a")
    second, second_text = _report(tmp_path / "b")
    assert first == second
    assert first_text == second_text
    assert "2026" not in first_text


def test_pdf_uses_latin1_equivalents(tmp_path: Path) -> None:
    assert latin1("Tu ≥ φTth, Aℓ·s, ñ") == "Tu >= phiTth, Al.s, ñ"
    assert write_pdf("Memoria con φ y ≥\nsegunda linea", tmp_path / "memoria.pdf")
    assert (tmp_path / "memoria.pdf").read_bytes().startswith(b"%PDF")


def test_missing_fpdf_skips_only_the_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def without_fpdf(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "fpdf":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_fpdf)
    report = report_file(EXAMPLE, tmp_path)
    assert not report.pdf_written
    assert sorted(path.name for path in tmp_path.iterdir()) == ["memoria.txt", "resultado.json"]


def test_cli_report_writes_the_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["report", str(EXAMPLE), "--output", str(tmp_path)]) == 0
    assert "Resultado: PASS" in capsys.readouterr().out
    assert {path.name for path in tmp_path.iterdir()} == {"resultado.json", "memoria.txt", "memoria.pdf"}
