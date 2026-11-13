"""Despiece (v3 Fase 4A, D-125): datos normativos del perfil, geometría de las barras y cartilla, frente al oráculo
independiente (tests/oracles/derive_detailing.py) y con la coherencia de la cartilla de un ejemplo."""

import json
import math
import re
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.cli import main
from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.detailing.schedule import BarRun, Hook, pieces, schedule, totals
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.development import BarAnchorage, lap_splice
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.checks import combined_footing_checks, footing_checks
from structurelab_rc.domain.footing.combined_columns import band_row, strip_limits
from structurelab_rc.domain.footing.detailing import combined_runs, footing_runs, splice_ratio
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.engine import report_file
from structurelab_rc.model.loader import load_project
from structurelab_rc.model.project import Materials
from structurelab_rc.setup import load_engine

ROOT = Path(__file__).parent.parent
ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
BARS = load_engine().bars
DIAMETER = {bar.designation: bar.diameter_mm for bar in BARS}
MASS = {bar.designation: bar.mass_kg_m for bar in BARS}
MATERIALS = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight", coating="uncoated")


def _oracle(profile: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / FOLDERS[profile] / "derived_detailing.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("profile", FOLDERS)
def test_hooks_and_bends_follow_the_profile(profile: str) -> None:
    detailing, oracle = PROFILES[profile].detailing, _oracle(profile)
    for designation, expected in oracle["hooks"].items():
        db = DIAMETER[designation]
        assert detailing.hook_bend_diameter(db) == pytest.approx(expected["bend"])
        assert detailing.hook_extension(db, 90) == pytest.approx(expected["ext90"])
        assert detailing.hook_extension(db, 180) == pytest.approx(expected["ext180"])
    for designation, expected in oracle["stirrups"].items():
        db = DIAMETER[designation]
        assert detailing.stirrup_bend_diameter(db) == pytest.approx(expected["bend"])
        assert detailing.stirrup_hook_extension(db, 135) == pytest.approx(expected["ext135"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_splice_lengths_and_class(profile: str) -> None:
    detailing, oracle = PROFILES[profile].detailing, _oracle(profile)
    assert detailing.lap_splice_class(2.0, 0.5) == "A"
    assert detailing.lap_splice_class(1.9, 0.5) == "B"
    assert detailing.lap_splice_class(3.0, 1.0) == "B"
    expected = oracle["tension_lap"]
    db = DIAMETER[expected["designation"]]
    bar = BarAnchorage(db, "straight", cb=expected["cb"], concrete_below=0.0, clear_cover=75.0, clear_spacing=150.0)
    assert lap_splice(PROFILES[profile], MATERIALS, bar, (1.0, 0.5)) == (pytest.approx(expected["B"]), "B")
    assert lap_splice(PROFILES[profile], MATERIALS, bar, (2.5, 0.5)) == (pytest.approx(expected["A"]), "A")
    compression = oracle["compression_lap"]
    assert detailing.compression_lap_length(420.0, 28.0, DIAMETER[compression["designation"]]) == pytest.approx(compression["length"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_bar_geometry_matches_the_oracle(profile: str) -> None:
    detailing, oracle = PROFILES[profile].detailing, _oracle(profile)
    u = oracle["u_bar"]
    db = DIAMETER[u["designation"]]
    hook = Hook(90, detailing.hook_bend_diameter(db), detailing.hook_extension(db, 90))
    piece = pieces(BarRun("u", u["designation"], db, MASS[u["designation"]], 1, u["A"], (hook, hook)), 12000.0)[0]
    assert piece.shape == "U" and piece.cut_length == u["cut"]
    assert dict(piece.dimensions)["B"] == pytest.approx(u["leg"])
    closed = oracle["closed_stirrup"]
    db = DIAMETER[closed["designation"]]
    extension = detailing.stirrup_hook_extension(db, 135)
    assert extension is not None
    stirrup = Hook(135, detailing.stirrup_bend_diameter(db), extension)
    run = BarRun("e", closed["designation"], db, MASS[closed["designation"]], 1, 0.0, (stirrup, stirrup),
                 stirrup=(closed["W"], closed["H"]))
    assert pieces(run, 12000.0)[0].cut_length == closed["cut"]


def test_long_bars_are_spliced_and_staggered() -> None:
    oracle = _oracle("nsr-10")["spliced"]
    run = BarRun("x", "#7", 22.2, MASS["#7"], 4, oracle["length"], lap=oracle["lap"])
    cut = pieces(run, oracle["stock"])
    lengths = {(piece.cut_length, piece.count) for piece in cut}
    assert lengths == {*((length, 2) for length in oracle["pattern_a"]), *((length, 2) for length in oracle["pattern_b"])}
    assert all(piece.cut_length <= oracle["stock"] for piece in cut)
    single = pieces(BarRun("x", "#7", 22.2, MASS["#7"], 4, 5000.0, lap=oracle["lap"]), oracle["stock"])
    assert [(piece.cut_length, piece.count) for piece in single] == [(5000.0, 4)]


def test_identical_bars_share_a_mark_and_the_totals_add_up() -> None:
    runs = [BarRun("malla x", "#5", 15.9, MASS["#5"], 10, 2450.0), BarRun("malla y", "#5", 15.9, MASS["#5"], 8, 2450.0),
            BarRun("otra", "#6", 19.1, MASS["#6"], 3, 1000.0)]
    rows = schedule("Z1", runs, 12000.0)
    assert [row.mark for row in rows] == ["Z1-01", "Z1-02"]
    assert rows[0].piece.count == 18 and rows[0].piece.group == "malla x, malla y"
    assert totals(rows)["#5"] == pytest.approx(18 * 2.45 * MASS["#5"])


@pytest.mark.parametrize("profile", FOLDERS)
def test_example_schedule_has_every_bar_once(profile: str) -> None:
    """Cartilla de la zapata combinada de pruebas: las barras de cada fila aparecen una sola vez (contando los tramos de
    las empalmadas como una) y el peso de la cartilla suma el de sus filas."""
    project = load_project(ROOT / "examples" / FOLDERS[profile] / "zapatas" / "pruebas" / "zapata_combinada.json")
    assert project.detailing is not None and project.soil is not None
    footing = project.combined_footings[0]
    basis = Basis(PROFILES[profile], project.materials, BARS, project.seismic.level)
    runs = combined_runs(basis, footing, project.soil)
    bottom_x = next(run for run in runs if run.group == "malla inferior x")
    assert bottom_x.count == len(mat_rows(footing, footing.bottom, BARS)["x"].positions)
    rows = schedule(footing.id, runs, project.detailing.stock_length)
    pieces_by_run = sum(len(pieces(run, project.detailing.stock_length)) for run in runs)
    assert sum(1 for _ in rows) <= pieces_by_run
    assert sum(row.mass for row in rows) == pytest.approx(sum(totals(rows).values()))
    isolated = load_project(ROOT / "examples" / FOLDERS[profile] / "zapatas" / "pruebas" / "zapata_centrica.json")
    assert isolated.soil is not None
    assert footing_runs(Basis(PROFILES[profile], isolated.materials, BARS, isolated.seismic.level), isolated.footings[0],
                        isolated.soil)


@pytest.mark.parametrize("profile", FOLDERS)
def test_splice_ratio_and_class_match_the_oracle(profile: str) -> None:
    """D-129: As provisto / As requerido por análisis (sin el mínimo) de una sección rectangular y la clase que da."""
    basis = Basis(PROFILES[profile], MATERIALS, BARS, "none" if profile == "aci-318-25" else "DMI")
    for case in _oracle(profile)["splice_class"]:
        ratio = splice_ratio(basis, (case["b"], case["h"], case["d"]), case["provided"], case["Mu"])
        if case["ratio"] is None:
            assert math.isinf(ratio), case["name"]
        else:
            assert ratio == pytest.approx(case["ratio"], rel=1e-4), case["name"]
        assert PROFILES[profile].detailing.lap_splice_class(ratio, 0.5) == case["class"], case["name"]


def _note_ratio(note: str) -> float:
    match = re.search(r"As/As req = ([0-9.]+)", note)
    assert match is not None, note
    return float(match.group(1))


@pytest.mark.parametrize("profile", FOLDERS)
def test_isolated_mesh_splice_uses_the_largest_face_moment_of_its_check(profile: str) -> None:
    """D-129: la razón de la malla inferior de la aislada sale del mayor Mu de su verificación de flexión en todos los
    casos, con el As requerido por análisis."""
    project = load_project(ROOT / "examples" / FOLDERS[profile] / "zapatas" / "pruebas" / "zapata_centrica.json")
    assert project.soil is not None
    footing = project.footings[0]
    basis = Basis(PROFILES[profile], project.materials, BARS, project.seismic.level)
    checks = footing_checks(basis, footing, project.soil)
    runs = {run.group: run for run in footing_runs(basis, footing, project.soil)}
    for direction, row in mat_rows(footing, footing.bottom, BARS).items():
        moment = max(check.demand or 0.0 for check in checks if check.name == f"Flexion malla inferior (barras {direction})")
        required = required_area(basis.profile, basis.materials, RectangularSection(row.width, footing.h), row.depth, moment)
        assert required is not None
        assert _note_ratio(runs[f"malla inferior {direction}"].note) == pytest.approx(row.area / required, abs=0.006)


@pytest.mark.parametrize("profile", FOLDERS)
def test_combined_band_splice_uses_the_largest_positive_moment_of_its_strip(profile: str) -> None:
    """D-129: la razón del band de cada columna sale del mayor Mu positivo (Wood-Armer) de la flexión de su franja, con
    las barras del band en el ancho de la franja."""
    project = load_project(ROOT / "examples" / FOLDERS[profile] / "zapatas" / "pruebas" / "zapata_combinada.json")
    assert project.soil is not None
    footing = project.combined_footings[0]
    basis = Basis(PROFILES[profile], project.materials, BARS, project.seismic.level)
    checks = combined_footing_checks(basis, footing, project.soil)
    runs = {run.group: run for run in combined_runs(basis, footing, project.soil)}
    row = mat_rows(footing, footing.bottom, BARS)["y"]
    for column in footing.columns:
        band = band_row(footing, column, row, basis)
        if band is None:
            continue
        moment = max(check.demand or 0.0 for check in checks if check.name == "Flexion: resistencia"
                     and check.note.startswith(f"Franja transversal de la columna {column.id}") and "momento positivo" in check.note)
        x0, x1 = strip_limits(footing, column, row.depth)
        provided = sum(1 for y in band.positions if x0 - 1e-6 <= y <= x1 + 1e-6) * band.bar_area
        required = required_area(basis.profile, basis.materials, RectangularSection(x1 - x0, footing.h), row.depth, moment)
        assert required is not None
        assert _note_ratio(runs[f"band columna {column.id}"].note) == pytest.approx(provided / required, abs=0.006)


def test_t_zarpa_bars_without_analysis_demand_keep_class_b(tmp_path: Path) -> None:
    """D-129: la malla x de la zarpa de la T fuera del ala no tiene demanda por análisis: queda en clase B y lo dice."""
    main(["run", str(ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_t_invertida_etabs.json"), "--output", str(tmp_path)])
    rows = next(tmp_path.rglob("cartilla.csv")).read_text(encoding="utf-8").splitlines()
    assert any("viga, capa" in line and "As/As req = " in line for line in rows)
    assert all("clase B: sin As requerido por analisis" in line for line in rows if "zarpa, malla inferior x" in line)


def test_report_writes_the_schedule(tmp_path: Path) -> None:
    report = report_file(ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas" / "zapata_combinada.json", tmp_path)
    assert (tmp_path / "cartilla.csv") in report.files
    results = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    data = results["combined_footings"][0]["detailing"]
    assert data["stock_length [mm]"] == 6000.0 and data["steel [kg]"] > 0 and data["concrete [m3]"] > 0
    assert "Despiece y cantidades" in (tmp_path / "memoria.txt").read_text(encoding="utf-8")
