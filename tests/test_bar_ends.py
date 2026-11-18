"""Extremos de las barras declarados por grupo (D-134): vocabulario obligatorio, desarrollo con gancho de 90° y 180°, el
gancho de 135° de una barra desarrollado como recta, ganchos del despiece, validación de lo que el perfil no define y la
cartilla DL-NET ante un gancho que no representa."""

import json
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.footing.checks import footing_checks
from structurelab_rc.domain.footing.detailing import face_envelope, footing_runs
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import report_file
from structurelab_rc.io.dlnet import TEMPLATE_VARIABLE
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.project import Project
from structurelab_rc.setup import load_engine

ROOT = Path(__file__).parent.parent
FOLDERS = ("aci_318_25", "nsr_10")
NAMES = {"aci_318_25": "aci-318-25", "nsr_10": "nsr-10"}
BARS = load_engine().bars
DIAMETER = {bar.designation: bar.diameter_mm for bar in BARS}


def _centric(profile: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((frozen(profile, "zapatas", "zapata_centrica.json")).read_text(encoding="utf-8"))
    return data


def _with(data: dict[str, Any], **bottom_x: Any) -> Project:
    footing = data["footings"][0]
    footing["bottom"]["x"] = {**footing["bottom"]["x"], **bottom_x}
    return Project.model_validate(data)


def _basis(project: Project) -> Basis:
    return Basis(PROFILES[project.profile], project.materials, BARS, project.seismic.level)


@pytest.mark.parametrize("profile", PROFILES)
def test_hook_cover_factor_asks_for_extension_cover_only_with_90_degrees(profile: str) -> None:
    """ACI Tabla 25.4.3.2 (ψcc) y NSR-10 C.12.5.3(a): el recubrimiento sobre la extensión (≥ 50 mm) solo en ganchos de 90°."""
    development = PROFILES[profile].development
    assert development.hook_cover_factor(db=19.1, side_cover=75.0, extension_cover=30.0, angle=90) == 1.0
    assert development.hook_cover_factor(db=19.1, side_cover=75.0, extension_cover=30.0, angle=180) == pytest.approx(0.7)
    assert development.hook_cover_factor(db=19.1, side_cover=75.0, extension_cover=75.0, angle=90) == pytest.approx(0.7)


@pytest.mark.parametrize("folder", FOLDERS)
def test_each_group_must_declare_its_end(folder: str) -> None:
    data = _centric(folder)
    del data["footings"][0]["bottom"]["y"]["end"]
    with pytest.raises(ValidationError, match="end"):
        Project.model_validate(data)
    data = _centric(folder)
    del data["footings"][0]["column"]["dowels"]["end"]
    with pytest.raises(ValidationError, match="end"):
        Project.model_validate(data)
    data = _centric(folder)
    data["footings"][0]["bottom"]["x"]["end"] = "hook"  # el vocabulario anterior ya no vale
    with pytest.raises(ValidationError, match="hook90"):
        Project.model_validate(data)


def test_combined_stirrups_must_declare_their_hook() -> None:
    data = json.loads((frozen("nsr_10", "zapatas", "zapata_combinada.json")).read_text(encoding="utf-8"))["combined_footings"][0]
    data["stirrups"] = {"designation": "#4", "legs": 4, "spacing": 200.0, "closed": True}
    with pytest.raises(ValidationError, match="estribos .* declaran end"):
        CombinedFooting.model_validate(data)


@pytest.mark.parametrize("folder", FOLDERS)
def test_hook_ends_choose_the_development_equation(folder: str) -> None:
    """hook90 y hook180 se desarrollan con ℓdh; hook135, que no es gancho estándar, como barra recta, con su nota (D-134)."""
    clauses = PROFILES[NAMES[folder]].development.clauses()

    def development(end: str) -> Any:
        project = _with(_centric(folder), end=end)
        checks = footing_checks(_basis(project), project.footings[0], project.soil)  # type: ignore[arg-type]
        return next(check for check in checks if check.name == "Desarrollo malla inferior (barras x)")

    straight, hook90, hook180, hook135 = (development(end) for end in ("straight", "hook90", "hook180", "hook135"))
    assert clauses["hook"] in hook90.clause and clauses["hook"] in hook180.clause
    assert clauses["hook"] not in straight.clause and clauses["hook"] not in hook135.clause
    assert hook135.demand == pytest.approx(straight.demand)
    assert "con gancho de 135" in hook135.note and "desarrollo como barra recta" in hook135.note
    assert "con gancho de 180" in hook180.note


@pytest.mark.parametrize("folder", FOLDERS)
def test_detailing_uses_the_declared_hooks(folder: str) -> None:
    profile = PROFILES[NAMES[folder]]
    data = _centric(folder)
    data["footings"][0]["column"]["dowels"]["end"] = "hook180"
    project = _with(data, end="hook135")
    assert project.soil is not None
    footing = project.footings[0]
    runs = {run.group: run for run in footing_runs(_basis(project), footing, face_envelope(footing, project.soil))}
    mesh = runs["malla inferior x"]
    db = mesh.diameter
    hook = mesh.hooks[0]
    assert hook is not None and hook.angle == 135
    assert hook.extension == pytest.approx(profile.detailing.stirrup_hook_extension(db, 135))  # del gancho de 135° de estribos
    assert hook.bend_diameter == pytest.approx(profile.detailing.hook_bend_diameter(db))  # doblado del gancho estándar
    foot = runs["pasadores"].hooks[0]
    assert foot is not None and foot.angle == 180
    assert foot.extension == pytest.approx(profile.detailing.hook_extension(runs["pasadores"].diameter, 180))
    assert runs["malla inferior y"].hooks == (None, None)


@pytest.mark.parametrize("folder", FOLDERS)
def test_hooks_the_profile_does_not_define_are_input_errors(folder: str) -> None:
    """El gancho de 135° de una barra toma la extensión del de estribos, que ACI (Tabla 25.3.2) y NSR-10 (C.7.1.3) definen
    hasta la No. 25 / #8: una #9 no se puede (D-134)."""
    project = _with(_centric(folder), designation="#9", end="hook135")
    check = validate_project(project, BARS)
    assert check.status is Status.FAIL
    assert any("gancho de 135 grados" in error.message for error in check.errors)


def test_nsr10_has_no_180_degree_stirrup_hook() -> None:
    """NSR-10 C.7.1.3 define ganchos de estribo de 90° y 135°; ACI Tabla 25.3.2 también el de 180°."""
    for folder, valid in (("nsr_10", False), ("aci_318_25", True)):
        data = json.loads((frozen(folder, "zapatas", "zapata_combinada.json")).read_text(encoding="utf-8"))
        data["combined_footings"][0]["stirrups"] = {"designation": "#4", "legs": 4, "spacing": 200.0, "closed": True, "end": "hook180"}
        check = validate_project(Project.model_validate(data), BARS)
        assert (check.status is not Status.FAIL) == valid, folder


def test_dlnet_skips_with_a_note_when_a_hook_has_no_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un gancho de 135° en una malla no tiene sintaxis DL-NET: la salida avisa y escribe lo demás (no se detiene)."""
    template = ROOT / "references" / "dlnet" / "plantilla.dli"
    if not template.is_file():
        pytest.skip("falta la plantilla DL-NET local")
    monkeypatch.setenv(TEMPLATE_VARIABLE, str(template))
    data = _centric("nsr_10")
    data["footings"][0]["bottom"]["x"]["end"] = "hook135"
    project = tmp_path / "zapata.json"
    project.write_text(json.dumps(data), encoding="utf-8")
    report = report_file(project, tmp_path / "salida")
    assert not any(path.suffix == ".dli" for path in report.files)
    assert any("135" in note for note in report.notes)
    assert (tmp_path / "salida" / "cartilla.csv").is_file()
