"""Diseño de la zapata combinada de dos columnas (v3 Fase 3B, D-107).

El diseño no tiene fórmulas propias: su ubicación y su largo se comparan con el oráculo independiente
(tests/oracles/derive_combined_design.py); la solución del ejemplo se verifica entera con la verificación de la
combinada, y en la viga larga y en cada band ninguna opción más liviana de su lista también cumple.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing import combined as design
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import combined_resultant
from structurelab_rc.domain.footing.checks import combined_footing_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.domain.validation import validate_project
from structurelab_rc.engine import RunPlan, design_combined_file, run_plan
from structurelab_rc.io.etabs.footings import build_combined_design_project
from structurelab_rc.io.etabs.xlsx import Table
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.design import CombinedDesignProject
from structurelab_rc.model.project import Project
from structurelab_rc.model.template import EtabsCombinedDesignTemplate
from structurelab_rc.setup import load_engine

ROOT = Path(__file__).parent.parent
ORACLES = Path(__file__).parent / "oracles"
FOLDERS = {"aci-318-25": "aci_318_25", "nsr-10": "nsr_10"}
EXAMPLE = ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas" / "diseno_combinada.json"
BARS = load_engine().bars


def _oracle(folder: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ORACLES / folder / "derived_combined_design.json").read_text(encoding="utf-8"))
    return data


def _context(data: dict[str, Any]) -> design.Context:
    project = CombinedDesignProject.model_validate(data)
    return design.Context(project, PROFILES[project.profile], BARS)


CASES = [pytest.param(case, id=f"{profile}-{case['id']}") for profile, folder in FOLDERS.items() for case in _oracle(folder)["cases"]]


@pytest.mark.parametrize("case", CASES)
def test_base_sits_on_the_service_resultant(case: dict[str, Any]) -> None:
    """Largo mínimo al paso, centroide en la resultante de D+L (o corrido por el voladizo máximo) y ancho que cubre
    las columnas, frente al oráculo."""
    geometry = design.geometry_for(_context(case["project"]), case["h_mm"], 0)
    assert geometry is not None
    expected = case["expected"]
    assert geometry.length == pytest.approx(expected["length_mm"], abs=1e-6)
    assert geometry.width == pytest.approx(expected["cover_width_mm"], abs=1e-6)
    assert geometry.center == pytest.approx(tuple(expected["center_mm"]), abs=1e-6)


def test_centred_base_has_no_service_eccentricity() -> None:
    """Con el centroide en la resultante, el caso D+L no tiene momento en la base (D-107)."""
    case = _oracle("nsr_10")["cases"][0]
    ctx = _context(case["project"])
    geometry = design.geometry_for(ctx, case["h_mm"], 0)
    assert geometry is not None
    footing = CombinedFooting.model_validate(design._footing_data(ctx, replace(geometry, width=2000.0), design._placeholder(ctx)))
    loads = next(pair for pair in footing.cases() if pair[0].case == "D+L")
    resultant = combined_resultant(footing, ctx.project.soil, loads)
    assert abs(resultant.my) / resultant.n < 1e-6
    assert abs(resultant.mx) / resultant.n < 1e-6


def test_design_input_is_validated() -> None:
    data = _oracle("nsr_10")["cases"][0]["project"]
    first, second = data["columns"]
    service = [load for load in first["loads"] if not (load["kind"] == "service" and not load["seismic"])]
    for change, message in (
        ({"columns": [first, {**second, "loads": second["loads"][:-1]}]}, "mismos casos de carga"),
        ({"columns": [{**first, "loads": service}, {**second, "loads": [load for load in second["loads"]
                                                                        if load["case"] in {item["case"] for item in service}]}]},
         "caso de servicio sin sismo"),
        ({"columns": [first, {**second, "id": "C1"}]}, "únicos"),
        ({"combined_design": {**data["combined_design"], "fc_options": [30.0]}}, "comercial"),
        # D-108: el caso que ubica la base debe existir, ser de servicio y no tener sismo.
        ({"combined_design": {**data["combined_design"], "placement_case": "D+0.5L"}}, "no es un caso de servicio"),
        ({"combined_design": {**data["combined_design"], "placement_case": "1.2D+1.6L"}}, "no es un caso de servicio"),
        ({"combined_design": {**data["combined_design"], "placement_case": "D+0.7E"}}, "caso con sismo"),
    ):
        with pytest.raises(ValidationError, match=message):
            CombinedDesignProject.model_validate({**data, **change})


@pytest.mark.parametrize(("name", "note", "group", "kind"), [
    ("Presion admisible del suelo", "", "soil", "area"),
    ("Punzonamiento", "Columna C1", "h", "area"),
    # D-110: el cortante y la torsión transversal de la viga larga van a los estribos; Aℓ, a la piel; la franja, al espesor.
    ("Cortante: resistencia", "A d de la cara +X de la columna C1, momento negativo", "stirrups", "area"),
    ("Cortante: refuerzo minimo", "Entre columnas, V = 0, momento negativo", "stirrups", "area"),
    ("Cortante: separacion maxima", "Cara +X de la columna C2, momento positivo", "stirrups", "max_spacing"),
    ("Torsion: refuerzo transversal", "", "stirrups", "area"),
    ("Torsion: refuerzo longitudinal", "", "skin", "area"),
    ("Cortante: resistencia", "Franja transversal de la columna C1, cara +Y, momento positivo", "h", "area"),
    ("Cortante: dimensiones de la seccion", "Entre columnas, V = 0, momento negativo", "h", "area"),
    ("Torsion: dimensiones de la seccion", "", "h", "area"),
    ("Flexion: deformacion neta de traccion (M3)", "Entre columnas, V = 0, momento negativo", "h", "area"),
    ("Flexion: resistencia", "Cara +X de la columna C2, momento positivo", "bottom_x", "area"),
    ("Flexion: acero minimo (M3)", "Entre columnas, V = 0, momento negativo", "top_x", "area"),
    ("Flexion concreto simple", "Entre columnas, V = 0, momento negativo", "top_x", "area"),
    ("Flexion: separacion por fisuracion", "Franja transversal de la columna C2, cara +Y, momento positivo", "band:C2", "max_spacing"),
    # D-119: el momento negativo de la franja lo toma el band superior de su columna.
    ("Flexion: resistencia", "Franja transversal de la columna C1, cara -Y, momento negativo", "band_top:C1", "area"),
    # D-120: la parte negativa de γf·Msc, las barras superiores en bslab (en Y, el band superior de la columna).
    ("Transferencia de momento: parte negativa (direccion secundaria)", "Columna C2: malla superior dentro de bslab",
     "band_top:C2", "area"),
    ("Transferencia de momento: parte negativa (direccion principal)", "Columna C1: malla superior dentro de bslab",
     "top_x", "area"),
    ("Flexion: refuerzo superficial", "A d de la cara +X de la columna C1, momento negativo", "skin", "max_spacing"),
    ("Desarrollo barras inferiores, direccion principal", "", "bottom_x", "development"),
    ("Desarrollo barras superiores, direccion principal", "", "top_x", "development"),
    ("Desarrollo refuerzo band (columna C1)", "", "band:C1", "development"),
    ("Separacion minima (band, columna C2)", "", "band:C2", "min_spacing"),
    ("Separacion minima (barras superiores, direccion secundaria)", "", "top_y", "min_spacing"),
    ("Direccion principal: separacion maxima (barras inferiores)", "", "bottom_x", "max_spacing"),
    ("Direccion secundaria: separacion maxima (malla inferior)", "", "bottom_y", "max_spacing"),
    ("Retraccion y temperatura: cuantia (direccion secundaria, fuera de las zonas de band)", "", "bottom_y", "area"),
    ("Retraccion y temperatura: cuantia (direccion secundaria, zona de band de la columna C1)", "", "band:C1", "area"),
    ("Retraccion y temperatura: separacion (direccion secundaria, superiores, zona de band de la columna C2)", "", "top_y",
     "max_spacing"),
    ("Retraccion y temperatura: cuantia (direccion principal, en todo el ancho)", "", "bottom_x", "area"),
    ("Transferencia de momento por flexion (direccion secundaria)", "Columna C2: malla inferior dentro de bslab", "band:C2", "area"),
    ("Transferencia de momento: parte negativa (direccion principal)", "Columna C1: la resiste la malla superior", "top_x", "area"),
    ("Pasadores: anclaje a compresion", "Columna C2", "dowels:C2", "development"),
    ("Aplastamiento en la zapata", "Columna C1", "dowels:C1", "area"),
])
def test_each_failure_goes_to_the_group_that_fixes_it(name: str, note: str, group: str, kind: str) -> None:
    assert design.classify(Check(name, Status.FAIL, note=note)) == (group, kind)


def test_stirrup_spacing_across_asks_for_more_legs() -> None:
    """La separación de estribos que falla por las ramas a lo ancho pide más ramas, no menor separación (D-110)."""
    across = Check("Cortante: separacion maxima", Status.FAIL, demand=200.0, capacity=350.0, note="Entre columnas",
                   values=(("across", 800.0), ("across_max", 700.0)))
    along = replace(across, demand=400.0, values=(("across", 500.0), ("across_max", 700.0)))
    assert design.classify(across) == ("stirrups", "legs")
    assert design.classify(along) == ("stirrups", "max_spacing")
    outer = Check("Torsion: refuerzo transversal", Status.FAIL, note="Entre columnas",
                  values=(("Av/s", 0.2), ("At/s", 0.5), ("At/s rama exterior", 0.3), ("Vc", 1e5)))
    assert design.classify(outer) == ("stirrups", "outer_leg")
    assert design.classify(replace(outer, values=(("Av/s", 0.2), ("At/s", 0.2), ("At/s rama exterior", 0.3)))) == ("stirrups", "area")


@pytest.fixture(scope="module")
def designed() -> tuple[dict[str, Any], design.CombinedDesignResult]:
    project, result, check = design_combined_file(EXAMPLE, workers=2)
    assert check.status is Status.PASS
    assert project is not None and result is not None
    return project, result


def test_example_design_passes_its_verification(designed: tuple[dict[str, Any], design.CombinedDesignResult]) -> None:
    project, result = designed
    assert result.best is not None
    assert result.best.cost == min(option.solution.cost for option in result.options if option.solution is not None)
    checked = Project.model_validate(project)
    footing = checked.combined_footings[0]
    ctx = _context(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    checks = combined_footing_checks(ctx.basis(result.best.fc), footing, checked.soil)  # type: ignore[arg-type]
    assert all(check.status is Status.PASS for check in checks)
    assert project["materials"]["fc"] == result.best.fc
    # Barras x continuas de borde a borde (sin cortes) y una barra de pasadores por columna.
    assert set(footing.bottom.model_dump(exclude_none=True)) >= {"x", "y"}
    assert all(column.dowels is not None and column.band is not None for column in footing.columns)


def test_no_lighter_option_of_a_group_passes(designed: tuple[dict[str, Any], design.CombinedDesignResult]) -> None:
    """Ninguna opción más liviana que la elegida, en las barras inferiores de la viga larga, en las superiores, en los
    estribos y en cada band, aprueba la verificación con el resto del refuerzo igual."""
    _, result = designed
    best = result.best
    assert best is not None
    ctx = _context(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    groups = design._groups(ctx, best.fc, best.geometry)
    assert groups is not None
    basis = ctx.basis(best.fc)
    for name in ("bottom_x", "top_x", "stirrups", *(f"band:{column.id}" for column in ctx.project.columns)):
        chosen = best.reinforcement["bands"][name[5:]] if name.startswith("band:") else best.reinforcement[name]
        if chosen is None:
            continue
        options = [{key: value for key, value in option.items() if not key.startswith("_")} for option in groups[name].options]
        lighter = options[: options.index(chosen)]
        for option in lighter:
            trial = json.loads(json.dumps(best.reinforcement))
            if name.startswith("band:"):
                trial["bands"][name[5:]] = option
            else:
                trial[name] = option
            footing = design._footing(ctx, best.geometry, trial)
            assert footing is not None
            checks = combined_footing_checks(basis, footing, ctx.project.soil)
            assert any(check.status is not Status.PASS for check in checks), (name, option)


def test_run_recognizes_the_combined_design(tmp_path: Path) -> None:
    plan = run_plan(EXAMPLE, tmp_path)
    assert plan == RunPlan("combined_design", EXAMPLE, tmp_path)


def test_stirrups_win_when_they_are_cheaper(designed: tuple[dict[str, Any], design.CombinedDesignResult]) -> None:
    """D-110: con estribos el ejemplo sale más delgado y más barato que el mejor diseño sin ellos con el mismo f'c."""
    _, result = designed
    best = result.best
    assert best is not None and best.reinforcement["stirrups"] is not None
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["combined_design"] = {key: value for key, value in data["combined_design"].items() if key != "stirrup_bars"}
    plain = design.design_for_fc(_context(data), best.fc).solution
    assert plain is not None and plain.reinforcement["stirrups"] is None
    assert best.geometry.h < plain.geometry.h
    assert best.cost < plain.cost


def test_plate_torsion_is_taken_by_the_x_and_y_bars() -> None:
    """D-118: con C2 corrida en Y y Mx, la torsión es de placa: la toman las barras x (Wood-Armer en las dos caras) y las
    barras y fuera de las franjas; no hay torsión de vigas, así que no hacen falta estribos cerrados ni piel por ella."""
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for load in data["columns"][1]["loads"]:
        load["Mx_kNm"] = -300.0 * (1.6 if load["kind"] == "factored" else 1.0)
    ctx = _context(data)
    solution = design._at_height(ctx, 28.0, 0, 800.0)
    assert isinstance(solution, design.CombinedSolution)
    reinforcement = solution.reinforcement
    assert reinforcement["top_x"] is not None and reinforcement["top_y"] is not None
    footing = design._footing(ctx, solution.geometry, reinforcement)
    assert footing is not None
    checks = combined_footing_checks(ctx.basis(28.0), footing, ctx.project.soil)
    assert all(check.status is Status.PASS for check in checks)
    assert not any(check.name.startswith("Torsion") for check in checks)
    assert any(check.name == "Direccion secundaria: torsion de placa (barras superiores)" for check in checks)

def test_etabs_template_builds_the_combined_design_project() -> None:
    """D-112: las cargas de servicio salen del Excel de ETABS y las mayoradas de la plantilla (loads_source); el
    proyecto de diseño que resulta es válido y el diseño propone pasadores y band (no se declaran)."""
    headers = ("Story", "Label", "Unique Name", "Output Case", "Case Type", "Step Type", "FX", "FY", "FZ", "MX", "MY", "MZ")
    units = {"FX": "kN", "FY": "kN", "FZ": "kN", "MX": "kN-m", "MY": "kN-m", "MZ": "kN-m"}

    def row(unique: str, fz: float) -> dict[str, str]:
        return {"Story": "Base", "Label": f"A{unique}", "Unique Name": unique, "Output Case": "SERV (D+L)",
                "Case Type": "Combination", "Step Type": "", "FX": "0", "FY": "0", "FZ": str(fz), "MX": "0", "MY": "0", "MZ": "0"}

    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    factored = [{"case": "1.2D+1.6L", "kind": "factored", "dead_factor": 1.2, "live_factor": 1.6, "P_kN": p, "Vx_kN": 0.0,
                 "Vy_kN": 0.0, "Mx_kNm": 0.0, "My_kNm": 0.0} for p in (1250.0, 1700.0)]
    columns = [{"id": column["id"], "etabs_unique_name": unique, "cx": column["cx"], "cy": column["cy"], "x": column["x"],
                "y": column["y"], "loads": [load]} for column, unique, load in zip(data["columns"], ("7", "9"), factored, strict=True)]
    raw = {key: data[key] for key in ("description", "profile", "seismic", "materials", "soil", "principal_direction")}
    template = EtabsCombinedDesignTemplate.model_validate({
        **raw, "load_factors": {"SERV (D+L)": {"dead": 1.0, "live": 1.0}},
        "loads_source": {"service": "etabs", "factored": "json"},
        "combined_design": {**data["combined_design"], "placement_case": "SERV (D+L)"}, "columns": columns})
    service = Table(headers, units, (row("7", 900.0), row("9", 1300.0)))
    project, summary = build_combined_design_project(template, service, None)
    checked = CombinedDesignProject.model_validate(project)
    assert [load.case for load in checked.columns[1].loads] == ["SERV (D+L)", "1.2D+1.6L"]
    assert checked.columns[1].loads[0].p == pytest.approx(1300e3)
    assert summary.footings == 1
    with pytest.raises(ValidationError, match="propone los pasadores"):
        EtabsCombinedDesignTemplate.model_validate({**template.model_dump(mode="json"),
                                                    "columns": [{**columns[0], "dowels": {"designation": "#6", "count": 8}},
                                                                columns[1]]})


# T invertida (D-113).
EXAMPLE_T = ROOT / "examples" / "nsr_10" / "zapatas" / "pruebas" / "diseno_t_invertida.json"


def test_inverted_t_input_is_validated() -> None:
    data = json.loads(EXAMPLE_T.read_text(encoding="utf-8"))
    block = data["combined_design"]
    for change, message in (({"web_margin": None}, "necesita web_margin"),
                            ({"beam_h_max": 600.0}, "beam_h_max debe ser al menos beam_h_min"),
                            ({"beam_h_min": 200.0, "beam_h_max": 900.0}, "beam_h_min debe superar h_min")):
        with pytest.raises(ValidationError, match=message):
            CombinedDesignProject.model_validate({**data, "combined_design": {**block, **change}})
    rectangular = {**block, "shape": "rectangular"}
    with pytest.raises(ValidationError, match="solo se declaran con shape"):
        CombinedDesignProject.model_validate({**data, "combined_design": rectangular})


@pytest.mark.parametrize(("name", "values", "group", "kind"), [
    ("Aleta: flexion (direccion secundaria)", (), "bottom_y", "area"),
    ("Aleta: separacion maxima (direccion secundaria)", (), "bottom_y", "max_spacing"),
    ("Desarrollo barras inferiores, direccion secundaria (aletas)", (), "bottom_y", "development"),
    ("Aleta: cortante en una direccion (direccion secundaria)", (), "zarpa", "area"),
    ("Altura minima de la zarpa", (), "zarpa", "area"),
    ("Direccion principal: separacion maxima (barras inferiores)", (), "mat_x", "max_spacing"),
    ("Cortante: dimensiones de la seccion", (), "web", "area"),
    ("Viga alta: limite de seccion", (), "web", "area"),
    ("Viga alta: refuerzo distribuido longitudinal", (), "skin", "area"),
    ("Viga alta: separacion del refuerzo distribuido", (("s estribos", 300.0), ("sd vertical", 150.0)), "stirrups", "max_spacing"),
    ("Viga alta: separacion del refuerzo distribuido", (("s estribos", 150.0), ("sd vertical", 300.0)), "skin", "max_spacing"),
    ("Flexion: resistencia", (), "bottom_x", "area"),
])
def test_inverted_t_failures_go_to_their_group(name: str, values: tuple[tuple[str, float], ...], group: str, kind: str) -> None:
    check = Check(name, Status.FAIL, note="Cara +X de la columna C2, momento positivo", capacity=240.0, values=values)
    assert design.classify_t(check) == (group, kind)


@pytest.fixture(scope="module")
def designed_t() -> tuple[dict[str, Any], design.CombinedDesignResult]:
    project, result, check = design_combined_file(EXAMPLE_T, workers=2)
    assert check.status is Status.PASS
    assert project is not None and result is not None
    return project, result


def test_inverted_t_design_passes_its_verification(designed_t: tuple[dict[str, Any], design.CombinedDesignResult]) -> None:
    """La T diseñada pasa la validación de entrada y la verificación entera, con la viga en las capas (D-106)."""
    project, result = designed_t
    assert result.best is not None and result.best.geometry.beam is not None
    checked = Project.model_validate(project)
    assert validate_project(checked, BARS).status is Status.PASS
    footing = checked.combined_footings[0]
    assert footing.beam is not None and footing.top is None and footing.stirrups is None
    ctx = _context(json.loads(EXAMPLE_T.read_text(encoding="utf-8")))
    checks = combined_footing_checks(ctx.basis(result.best.fc), footing, checked.soil)  # type: ignore[arg-type]
    assert all(check.status is Status.PASS for check in checks)
    web, height = result.best.geometry.beam
    assert web >= design.web_minimum(ctx, height)


def test_no_lighter_beam_option_of_the_t_passes(designed_t: tuple[dict[str, Any], design.CombinedDesignResult]) -> None:
    """Ninguna opción más liviana de las capas de la viga ni de los estribos de la T también cumple."""
    _, result = designed_t
    best = result.best
    assert best is not None
    ctx = _context(json.loads(EXAMPLE_T.read_text(encoding="utf-8")))
    groups = design._groups(ctx, best.fc, best.geometry)
    assert groups is not None
    basis = ctx.basis(best.fc)
    for name in ("bottom_x", "top_x", "stirrups"):
        chosen = best.reinforcement[name]
        if chosen is None:
            continue
        options = [{key: value for key, value in option.items() if not key.startswith("_")} for option in groups[name].options]
        for option in options[: options.index(chosen)]:
            footing = design._footing(ctx, best.geometry, {**best.reinforcement, name: option})
            assert footing is not None
            checks = combined_footing_checks(basis, footing, ctx.project.soil)
            assert any(check.status is not Status.PASS for check in checks), (name, option)


def test_tall_t_beam_is_declared_deep_and_checked() -> None:
    """D-109: con luz libre / alto ≤ 4 la viga de la T se declara deep_beam y la revisan los criterios de D-089."""
    data = json.loads(EXAMPLE_T.read_text(encoding="utf-8"))
    data["columns"][1]["y"] = 0.0
    for column in data["columns"]:
        for load in column["loads"]:
            load["Mx_kNm"], load["Vy_kN"] = 0.0, 0.0
    data["combined_design"]["beam_h_max"] = 1300.0
    ctx = _context(data)
    solution = design._at_height(ctx, 28.0, 0, 1300.0)
    assert isinstance(solution, design.CombinedSolution)
    assert solution.data["deep_beam"] is True
    footing = design._footing(ctx, solution.geometry, solution.reinforcement)
    assert footing is not None and footing.deep_beam
    checks = combined_footing_checks(ctx.basis(28.0), footing, ctx.project.soil)
    assert all(check.status is Status.PASS for check in checks)
    assert any(check.name.startswith("Viga alta") for check in checks)
