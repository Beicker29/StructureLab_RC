import builtins
import json
import re
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.engine import report_file
from structurelab_rc.reporting.pdf import latin1, write_pdf
from structurelab_rc.reporting.results import check_data, significant

EXAMPLE = Path(__file__).parent.parent / "examples" / "nsr_10" / "vigas" / "pruebas" / "viga_t.json"


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
    # El ancho de la columna de parámetros depende de la etiqueta más larga de la tabla: se compara sin el relleno.
    assert re.search(rf"Factor de reducción de resistencia +φ +{strength['values']['phi']:.4f}", text)


BEAM_CHAPTERS = ("1. Propiedades mecánicas de los materiales", "2. Propiedades geométricas y armado", "3. Solicitaciones",
                 "4. Revisión de requerimientos técnicos", "5. Revisión de condiciones de servicio",
                 "6. Revisión de capacidad a momento flector", "7. Revisión de capacidad a fuerza cortante",
                 "8. Revisión de capacidad a torsión", "9. Índices DCR", "10. Notas y limitaciones")


def test_beam_memoir_has_its_fixed_chapters(tmp_path: Path) -> None:
    _, text = _report(tmp_path)
    assert text.startswith("# Memoria de cálculo — Viga V-1")
    assert "RESULTADO: PASS (CUMPLE)" in text
    for chapter in BEAM_CHAPTERS:
        assert f"## {chapter}" in text
    assert "Nivel sísmico declarado: DMO" in text
    assert "Falta implementación: fisuración, espesor mínimo y deflexiones" in text
    locations = re.compile(r"Ubicación\s+Resultado\s+Demanda")
    assert not locations.search(text)
    _, full = _report(tmp_path / "completo", full=True)
    assert locations.search(full)


def test_failing_checks_are_shown_with_their_governing_location(tmp_path: Path) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["members"][0]["stations"][1]["demands"]["Mu_kNm"] = 600.0
    project = tmp_path / "falla.json"
    project.write_text(json.dumps(data), encoding="utf-8")
    report = report_file(project, tmp_path / "salida")
    text = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert report.status == "FAIL"
    assert "RESULTADO: FAIL (NO CUMPLE)" in text
    assert "### 6.1 Flexión: resistencia; ubicación gobernante: z = 3000 mm" in text


def test_invalid_input_produces_a_short_report(tmp_path: Path) -> None:
    broken = tmp_path / "roto.json"
    broken.write_text("{", encoding="utf-8")
    report = report_file(broken, tmp_path / "salida")
    assert report.status == "FAIL"
    text = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert "La entrada no es válida" in text
    assert "RESULTADO: FAIL (NO CUMPLE)" in text


def test_footing_memoir_has_its_fixed_chapters(tmp_path: Path) -> None:
    footing = Path(__file__).parent.parent / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_centrica.json"
    report_file(footing, tmp_path)
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    assert text.count("# Memoria de cálculo — Zapata ") == len(results["footings"]) == 1
    for chapter in ("4. Revisión geotécnica: presión, contacto y estabilidad", "8. Revisión de cortante en dos direcciones",
                    "10. Revisión de aplastamiento y pasadores", "11. Índices DCR",
                    # D-125: el ejemplo de pruebas declara detailing, así que la memoria trae el despiece antes de las notas.
                    "12. Despiece y cantidades", "13. Notas y limitaciones"):
        assert f"## {chapter}" in text
    assert "Área de la base (A)" in text
    assert "El pedestal no aporta empuje pasivo" in text and "Nivel freático: falta implementación" in text
    assert all("case" in check for check in results["footings"][0]["checks"])


def test_outputs_have_no_date_and_are_reproducible(tmp_path: Path) -> None:
    first, first_text = _report(tmp_path / "a")
    second, second_text = _report(tmp_path / "b")
    assert first == second
    assert first_text == second_text
    assert "2026" not in first_text


def test_pdf_draws_the_document_blocks(tmp_path: Path) -> None:
    assert latin1("Tu ≥ φTth, Aℓ·s, ñ") == "Tu >= phiTth, Al.s, ñ"
    blocks: list[dict[str, Any]] = [{"kind": "title", "element": "Viga V", "meta": [("Norma", "NSR-10")], "status": "PASS",
               "status_text": "CUMPLE",
               "ratio": 0.5}, {"kind": "h1", "text": "1. Capítulo con φ y ≥"},
              {"kind": "table", "headers": ["Parámetro", "Valor"], "rows": [["Área (mm²)", "12"]]}, {"kind": "note", "text": "nota"}]
    assert write_pdf([blocks, blocks], tmp_path / "memoria.pdf")
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


def test_footing_report_draws_the_soil_pressure_in_plan(tmp_path: Path) -> None:
    """D-080: la memoria de cada zapata trae la planta con la presión en las esquinas del caso que gobierna y la tabla de
    las esquinas de todos los casos de servicio; el SVG queda en la carpeta del report."""
    report = report_file(EXAMPLE.parents[2] / "zapatas" / "pruebas" / "zapata_centrica.json", tmp_path)
    figure = tmp_path / "presion_Z1.svg"
    assert figure in report.files
    svg = figure.read_text(encoding="utf-8")
    plan = svg.split('stroke="#c8ced8"')[0]  # la planta, sin la leyenda de muestras (D-105)
    assert svg.startswith("<svg") and plan.count("<circle") == 4
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    assert "Presión del suelo en las esquinas (casos de servicio)" in text and "archivo presion_Z1.svg" in text



def test_requirements_are_grouped_and_spacings_show_the_maximum_as_required(tmp_path: Path) -> None:
    """D-100 y D-102: el capítulo de requisitos va en subcapítulos, con la separación máxima y la mínima por separado; en
    las separaciones máximas lo exigido es "≤ máximo" y lo suministrado la separación dispuesta; cada requisito de flexión
    va por cara en tracción y dirección; solo las columnas requisito, exigido, suministrado, referencia y resultado; el
    capítulo DCR no repite los requisitos."""
    example = EXAMPLE.parents[2] / "zapatas" / "pruebas" / "zapata_combinada.json"
    report_file(example, tmp_path)
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    # D-104: los capítulos 3 (solicitaciones) y 4 (diagramas) se unieron; los requisitos quedan en el 5.
    chapter = text.split("## 5. Revisión de requerimientos técnicos")[1].split("\n## 6.")[0]
    assert re.findall(r"^### (5\.\d+ .+)$", chapter, flags=re.M) == [
        "5.1 Refuerzo mínimo", "5.2 Separación del refuerzo", "5.3 Deformación neta de tracción"]
    assert re.findall(r"^#### (5\.2\.\d .+)$", chapter, flags=re.M) == [
        "5.2.1 Revisión de separación máxima del refuerzo", "5.2.2 Revisión de separación mínima del refuerzo"]
    lines = chapter.splitlines()
    headers = next(line for line in lines if line.startswith("Requisito"))
    assert headers.split() == ["Requisito", "Exigido", "Suministrado", "Referencia", "normativa", "Resultado"]
    spacing = next(line for line in lines if line.startswith("Dirección principal (X): separación máxima (barras inferiores)"))
    assert re.search("≤ 450 mm +150 mm", spacing)
    for label in ("Flexión: acero mínimo (M3) (barras inferiores, dirección principal (X))",
                  "Flexión: acero mínimo (M3) (barras inferiores, dirección secundaria (Y))",
                  "Flexión: separación por fisuración (barras inferiores, dirección secundaria (Y))",
                  "Retracción y temperatura: cuantía (dirección secundaria (Y), zona de band de la columna C1)",
                  "Separación mínima (band, columna C1)", "Separación mínima (barras superiores, dirección principal (X))"):
        assert any(line.startswith(label) for line in lines), label
    dcr = text.split("Índices DCR")[1].split("\n## ")[0]
    assert "Separación" not in dcr and "acero mínimo" not in dcr and "Retracción" not in dcr


def test_strip_shear_over_phi_vc_is_reported_with_dcr_099_and_a_danger_alert(tmp_path: Path) -> None:
    """D-103 y D-114: el cortante de franja que excede φVc se reporta con DCR = 0.99 y, en la propia revisión, un aviso
    en rojo y negrilla de que el excedente lo asume el refuerzo transversal de la viga de cimentación."""
    oracle = json.loads((Path(__file__).parent / "oracles" / "nsr_10" / "derived_combined_columns.json").read_text(encoding="utf-8"))
    footing = next(case["footing"] for case in oracle["cases"] if case["id"] == "delgada")
    project = {"description": "prueba", "profile": "nsr-10", "seismic": {"level": oracle["seismic_level"], "justification": "prueba"},
               "materials": oracle["materials"], "soil": oracle["soil"], "combined_footings": [footing]}
    path = tmp_path / "delgada.json"
    path.write_text(json.dumps(project), encoding="utf-8")
    report_file(path, tmp_path / "salida")
    results = json.loads((tmp_path / "salida" / "resultado.json").read_text(encoding="utf-8"))
    shears = [check for check in results["combined_footings"][0]["checks"]
              if check["name"] == "Cortante: resistencia" and "excedente para la viga [kN]" in check["values"]]
    assert shears and all(check["ratio"] == pytest.approx(0.99) and check["status"] == "PASS" for check in shears)
    text = (tmp_path / "salida" / "memoria.txt").read_text(encoding="utf-8")
    assert "debe ser asumido por el refuerzo transversal de la viga de cimentación; esta revisión se reporta con DCR = 0.99" in text


def test_combined_footing_report_has_its_chapters_and_figure(tmp_path: Path) -> None:
    """V3J.4 (D-080 a D-083): la memoria de la zapata combinada separa la viga larga de las franjas, dibuja la planta con
    las dos columnas y trae los esfuerzos de punzonamiento en cada esquina; el resultado trae combined_footings."""
    example = EXAMPLE.parents[2] / "zapatas" / "pruebas" / "zapata_combinada.json"
    report = report_file(example, tmp_path)
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    footing = results["combined_footings"][0]
    assert [column["id"] for column in footing["columns"]] == ["C1", "C2"]
    assert all("case" in check and "z [mm]" in check for check in footing["checks"])
    figure = tmp_path / "presion_ZC1.svg"
    assert figure in report.files
    svg = figure.read_text(encoding="utf-8")
    plan = svg.split('stroke="#c8ced8"')[0]  # la planta, sin la leyenda de muestras (D-105)
    assert plan.count("<circle") == 4 and plan.count('fill="#9aa4b2"') == 2  # las cuatro esquinas y las dos columnas
    text = (tmp_path / "memoria.txt").read_text(encoding="utf-8")
    assert text.count("# Memoria de cálculo — Zapata combinada ZC1") == 1
    # D-104: capítulos 1 a 3 en subcapítulos; las solicitaciones internas, un diagrama por magnitud y elemento.
    assert re.findall(r"^### (\d\.\d .+)$", text.split("## 4.")[0], flags=re.M) == [
        "1.1 Concreto estructural", "1.2 Acero de refuerzo", "1.3 Suelo", "2.1 Zapata combinada", "2.2 Acero de refuerzo",
        "2.3 Suelo", "2.4 Columnas", "3.1 Sobrecargas", "3.2 Combinaciones de esfuerzos admisibles (ASD)",
        "3.3 Combinaciones de resistencia última (LRFD)", "3.4 Presión sobre el suelo", "3.5 Solicitaciones internas",
        "3.6 Momentos de diseño por Wood-Armer (D-118)"]  # el ejemplo tiene torsión de placa (D-118, D-119)
    assert re.findall(r"^#### (3\.5\.\d) (Fuerza cortante|Momento flector)", text, flags=re.M) == [
        ("3.5.1", "Fuerza cortante"), ("3.5.2", "Momento flector"), ("3.5.3", "Fuerza cortante"), ("3.5.4", "Momento flector"),
        ("3.5.5", "Fuerza cortante"), ("3.5.6", "Momento flector")]
    for chapter in ("Dirección principal (X global): momento positivo",
                    "Dirección principal (X global): momento negativo", "Dirección principal (X global): fuerza cortante",
                    "Dirección secundaria (Y global), franjas transversales: momento positivo",
                    "Dirección secundaria (Y global), franjas transversales: momento negativo",
                    "Dirección secundaria (Y global), franjas transversales: fuerza cortante",
                    "Revisión de cortante en dos direcciones (punzonamiento)",
                    "Revisión de aplastamiento y pasadores"):
        assert chapter in text
    # D-095: diagramas envolventes en la salida, en la memoria y como figuras. En la sección que gobierna la flexión positiva
    # de la viga larga (una cara de columna), la envolvente vale lo mismo que esa revisión: la sección está entre las
    # candidatas de todos los casos. El pico del diagrama cae en el eje de la columna (carga puntual), no en la cara.
    for name in ("diagrama_ZC1_principal_cortante.svg", "diagrama_ZC1_principal_momento.svg",
                 "diagrama_ZC1_franja_C1_cortante.svg", "diagrama_ZC1_franja_C2_momento.svg"):
        assert tmp_path / name in report.files and "<polyline" in (tmp_path / name).read_text(encoding="utf-8")
    diagrams = footing["diagrams"]
    assert [envelope["title"] for envelope in diagrams["secondary"]] == ["Franja transversal de la columna C1",
                                                                         "Franja transversal de la columna C2"]
    longitudinal = diagrams["principal"]
    assert longitudinal["positions [mm]"][0] == -3500 and longitudinal["positions [mm]"][-1] == 3500
    flexure = [check for check in footing["checks"] if check["name"] == "Flexion: resistencia"
               and "momento positivo" in check["note"] and not check["note"].startswith("Franja")]
    governing = max(flexure, key=lambda check: check["demand"])
    x = governing["z [mm]"] - 3500
    positions, values = longitudinal["positions [mm]"], longitudinal["M max [kN-m]"]
    k = next(index for index in range(len(positions) - 1) if positions[index] <= x <= positions[index + 1])
    at = values[k] + (values[k + 1] - values[k]) * (x - positions[k]) / (positions[k + 1] - positions[k])
    # Con torsión de placa (D-118) la demanda es M + |T| y la nota trae M y T: el diagrama vale M en esa sección.
    found = re.search(r"M = (-?[\d.]+) kN\*m, T = (-?[\d.]+) kN\*m", governing["note"])
    moment, torque = (float(found.group(1)), float(found.group(2))) if found else (governing["demand"], 0.0)
    assert governing["demand"] == pytest.approx(moment + abs(torque), abs=0.2)
    assert at == pytest.approx(moment, rel=0.02)
    assert max(values) >= moment
    assert "Esfuerzos de punzonamiento en las esquinas del perímetro crítico" in text and "gobierna" in text
    assert "Cortante V3" not in text  # el eje débil no aplica a la zapata
    # D-119: un subcapítulo por franja de columna y la demanda como suma de la flexión y la torsión de placa.
    assert "Franja transversal de la columna C1" in text and "Franja transversal de la columna C2" in text
    assert re.search(r"^### \d+\.1 Franja transversal de la columna C1$", text, flags=re.M)
    assert "Composición de Mu: M flexión + M torsión" in text and "Composición de Vu: V flexión + V torsión" in text
