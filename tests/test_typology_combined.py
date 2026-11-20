"""Diseño por tipologías con zapatas combinadas (D-153): el diseño integrado es el mismo que las tipologías aisladas y
cada combinada diseñadas por separado con el f'c elegido, que es el de menor costo total; validaciones de la plantilla y
del proyecto; aviso de zapatas que se traslapan en la planta de localización."""

import json
from pathlib import Path
from typing import Any

import pytest
from frozen_examples import frozen
from pydantic import ValidationError

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing import combined
from structurelab_rc.design.footing.mixed import design_with_pairs, designed_with_pairs, pair_costs
from structurelab_rc.design.footing.typologies import design_typologies
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.domain.footing.drawing import location_views
from structurelab_rc.domain.status import Status
from structurelab_rc.drawing.model import Drawing, Text
from structurelab_rc.engine import import_etabs_footings
from structurelab_rc.model.design import FootingDesignProject, pair_project
from structurelab_rc.model.loader import load_project
from structurelab_rc.model.template import EtabsFootingDesignTemplate
from structurelab_rc.setup import load_engine

NAME = "diseno_tipologias_combinadas_etabs.json"


def _template(profile: str = "nsr_10") -> tuple[Path, dict[str, Any]]:
    path = frozen(profile, "zapatas", NAME)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return path, data


def _imported(profile: str = "nsr_10") -> dict[str, Any]:
    """El proyecto de diseño que arma el importador desde la plantilla congelada (con sus Excel y su tabla de
    coordenadas)."""
    path, data = _template(profile)
    files = {key: (path.parent / value).resolve() for key, value in data["etabs_files"].items()}
    project, _, check = import_etabs_footings(files["service"], files["factored"], path, files.get("locations"))
    assert project is not None and check.status is not Status.FAIL, check
    return project


def _context(project: dict[str, Any]) -> Context:
    design = FootingDesignProject.model_validate(project)
    return Context(design, PROFILES[design.profile], load_engine().bars)


def test_importer_builds_the_pair_with_etabs_positions() -> None:
    """Los nudos del par salen de las tipologías aisladas y van a su combinada, con la posición de la tabla de
    coordenadas y el combined_design común con lo propio del par y los f'c y precios de design."""
    project = _imported()
    _, template = _template()
    paired = template["combined_pairs"][0]["etabs_unique_names"]
    assert not {column.get("location", {}).get("joint") for column in project["columns"]} & set(paired)
    (pair,) = project["combined_footings"]
    assert [column["location"]["joint"] for column in pair["columns"]] == paired
    assert all(column["x"] == column["location"]["x"] and column["y"] == column["location"]["y"] for column in pair["columns"])
    assert pair["combined_design"]["fc_options"] == template["design"]["fc_options"]
    assert pair["combined_design"]["placement_case"] == template["combined_pairs"][0]["design"]["placement_case"]


def test_integrated_design_matches_the_separate_designs() -> None:
    """D-153: con un solo f'c, el diseño integrado da las mismas tipologías que las aisladas solas con ese f'c y la
    misma combinada que su diseño con ese f'c; el f'c es el de menor costo total."""
    ctx = _context(_imported())
    result = design_with_pairs(ctx)
    assert result.fc is not None and len(result.combined) == 1
    fc = result.fc
    alone = ctx.project.model_copy(update={"combined_footings": (), "design": ctx.design.model_copy(update={"fc_options": (fc,)})})
    isolated = design_typologies(Context(alone, ctx.profile, ctx.bars))
    assert [(item.name, item.design.typology, item.columns) for item in isolated.typologies] == \
           [(item.name, item.design.typology, item.columns) for item in result.typologies]
    assert isolated.cost == pytest.approx(result.cost)
    pair = ctx.project.combined_footings[0]
    own = combined.Context(pair_project(ctx.project, pair), ctx.profile, ctx.bars)
    separate = combined.design_for_fc(own, fc).solution
    chosen = result.combined[0].solution
    assert separate is not None and chosen is not None
    assert (separate.geometry, separate.cost) == (chosen.geometry, chosen.cost)
    assert result.combined_cost == pytest.approx(chosen.cost)
    extra = pair_costs(result.combined, ctx.design.fc_options)
    totals = [option.cost + extra[option.fc] for option in result.options if option.cost is not None]
    assert result.cost + result.combined_cost == pytest.approx(min(totals))
    project = designed_with_pairs(ctx, result)
    assert [footing["id"] for footing in project["combined_footings"]] == [pair.id]
    assert all("location" in column for column in project["combined_footings"][0]["columns"])
    assert project["materials" if "materials" in project else "concrete"]["fc"] == fc


@pytest.mark.parametrize(("change", "message"), [
    ({"combined_pairs": [{"id": "ZC9", "etabs_unique_names": ["12", "999"], "principal_direction": "y"}]}, "no estan en columns"),
    ({"combined_pairs": [{"id": "ZC9", "etabs_unique_names": ["12", "20"], "principal_direction": "y",
                          "design": {"fc_options": [21.0]}}]}, "no declaran fc_options"),
    ({"combined_design": None}, "necesita el bloque combined_design"),
])
def test_template_rejects_inconsistent_pairs(change: dict[str, Any], message: str) -> None:
    _, data = _template()
    with pytest.raises(ValidationError, match=message):
        EtabsFootingDesignTemplate.model_validate({**data, **change})


def test_pairs_need_the_location_table(tmp_path: Path) -> None:
    """Las posiciones de las columnas del par salen de la tabla de coordenadas: sin ella, error claro."""
    path, data = _template()
    data["etabs_files"] = {key: str((path.parent / value).resolve()) for key, value in data["etabs_files"].items() if key != "locations"}
    own = tmp_path / NAME
    own.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    files = data["etabs_files"]
    project, _, check = import_etabs_footings(Path(files["service"]), Path(files["factored"]), own)
    assert project is None and check.status is Status.FAIL
    assert any("etabs_files.locations" in error.message for error in check.errors)


def test_project_requires_the_same_fc_options() -> None:
    """Un solo f'c para toda la cimentación: las combinadas prueban los mismos f'c que design."""
    project = _imported()
    project["combined_footings"][0]["combined_design"]["fc_options"] = [21.0]
    with pytest.raises(ValidationError, match="los mismos f'c que design.fc_options"):
        FootingDesignProject.model_validate(project)


def test_location_plan_warns_when_footings_overlap(tmp_path: Path) -> None:
    """D-153: el plano avisa si dos zapatas del mismo nivel se traslapan (el diseño no revisa vecinas)."""
    etabs = frozen("etabs", "zapatas", "Joint Reactions - Servicio.xlsx").parent
    template = frozen("nsr_10", "zapatas", "zapata_centrica_etabs.json")
    data = import_etabs_footings(etabs / "Joint Reactions - Servicio.xlsx", etabs / "Joint Reactions - Ultimas.xlsx", template,
                                 etabs / "Joint Location.xlsx")[0]
    assert data is not None
    first, second = data["footings"][:2]
    second["location"] = {**first["location"], "x": first["location"]["x"] + 100.0}
    path = tmp_path / "solapadas.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    project = load_project(path)
    views = location_views(Drawing("prueba", 50.0), project.footings, project.combined_footings)
    texts = [entity.text for view in views for entity in view.entities if isinstance(entity, Text)]
    assert f"ADVERTENCIA: se traslapan {first['id']} y {second['id']}" in texts
