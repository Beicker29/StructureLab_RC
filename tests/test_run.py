"""`run`: un solo comando por ejemplo (D-096), que reconoce el tipo de ejemplo por su contenido."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from structurelab_rc.cli import main
from structurelab_rc.engine import RunError, default_output, import_etabs_footings, run_plan
from structurelab_rc.model.design import CurveSettings
from structurelab_rc.model.project import Project

ROOT = Path(__file__).parent.parent
EXAMPLES = sorted(path for path in (ROOT / "examples").glob("*/*/*.json"))


def _expected_kind(path: Path) -> str:
    name = path.name
    if name.startswith("plantilla_diseno_"):
        return "etabs_design"
    if name.startswith("plantilla_"):
        return "etabs_beams" if path.parent.name == "vigas" else "etabs_footings"
    if name.startswith("diseno_"):
        return "design"
    if name.startswith("curva_"):
        return "curve"
    return "project"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda path: f"{path.parts[-3]}-{path.parent.name}-{path.stem}")
def test_every_example_has_a_run_plan(path: Path) -> None:
    """Cada ejemplo del repositorio se corre con `run`: su tipo sale del contenido y las plantillas traen sus Excel."""
    plan = run_plan(path)
    assert plan.kind == _expected_kind(path)
    assert plan.output == ROOT / "results" / path.parts[-3] / path.parent.name / path.stem
    for excel in (plan.workbook, plan.service, plan.factored):
        assert excel is None or excel.exists()
    if plan.kind.startswith("etabs"):
        assert any(excel is not None for excel in (plan.workbook, plan.service, plan.factored))


def test_default_output_outside_the_examples(tmp_path: Path) -> None:
    assert default_output(tmp_path / "mio.json") == Path("results") / "mio"


def test_a_template_without_its_excel_is_a_clear_error(tmp_path: Path) -> None:
    template = json.loads((ROOT / "examples/nsr_10/zapatas/plantilla_t_invertida_etabs.json").read_text(encoding="utf-8"))
    template.pop("etabs_files")
    path = tmp_path / "plantilla.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(RunError, match="no declara sus Excel de ETABS en etabs_files"):
        run_plan(path)


def test_the_imported_project_leaves_out_etabs_files() -> None:
    template = ROOT / "examples/nsr_10/zapatas/plantilla_t_invertida_etabs.json"
    plan = run_plan(template)
    project, _, check = import_etabs_footings(plan.service, plan.factored, template)
    assert project is not None and "etabs_files" not in project
    Project.model_validate(project)


@pytest.mark.parametrize(("value", "expected"), [("1-4,6", (1, 2, 3, 4, 6)), ([3, 1, 2], (3, 1, 2)), ("2", (2,))])
def test_curve_settings_take_ranges(value: object, expected: tuple[int, ...]) -> None:
    assert CurveSettings.model_validate({"n": value}).n == expected


def test_curve_settings_reject_bad_text() -> None:
    with pytest.raises(ValidationError, match="valores de N no validos"):
        CurveSettings.model_validate({"n": "uno-seis"})


def test_run_writes_the_results_memoirs_and_figures(tmp_path: Path) -> None:
    out = tmp_path / "salida"
    assert main(["run", str(ROOT / "examples/nsr_10/zapatas/zapata_combinada.json"), "--output", str(out)]) == 0
    names = {path.name for path in out.iterdir()}
    assert {"resultado.json", "memoria.txt", "presion_ZC1.svg", "diagrama_ZC1_longitudinal.svg",
            "diagrama_ZC1_transversal.svg"} <= names


def test_run_a_folder_runs_each_example_in_its_own_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / "ejemplos"
    folder.mkdir()
    for name in ("vigas/viga_t.json", "zapatas/zapata_centrica.json"):
        shutil.copy(ROOT / "examples/nsr_10" / name, folder / Path(name).name)
    assert main(["run", str(folder), "--output", str(tmp_path / "salida")]) == 0
    for stem in ("viga_t", "zapata_centrica"):
        assert (tmp_path / "salida" / stem / "memoria.txt").exists()
    assert "Resumen" in capsys.readouterr().out
