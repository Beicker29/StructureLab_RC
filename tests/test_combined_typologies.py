"""Tipologías de zapatas combinadas (D-157): la agrupación por programación dinámica contra la fuerza bruta (con costos
simulados), el error con más familias que tipos (antes de diseñar) y, con dos pares reales de la misma familia, el tipo
común: cumple con los casos de los dos pares, se traslada bajo cada uno con su refuerzo por columna en orden y, con
tantos tipos como pares, la agrupación es el diseño de cada par (D-153)."""

import copy
import itertools
import json
import random
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_typology_combined import _context, _imported

from structurelab_rc.design.footing import combined, mixed
from structurelab_rc.engine import report_file

FC = 28.0
SHIFT = 40000.0  # el segundo par, corrido en X (la dirección principal es Y): la misma separación entre columnas


def _fake(name: str, family: str, cost: float) -> Any:
    """Un par simulado: su familia y su costo individual en FC."""
    solution = SimpleNamespace(cost=cost)
    return SimpleNamespace(pair=SimpleNamespace(id=name), ctx=family, at=lambda fc: solution if fc == FC else None)


def _type_cost(group: tuple[Any, ...]) -> float:
    """El costo simulado del tipo de un grupo: el del par más exigente más un recargo por zapata."""
    return max(design.at(FC).cost for design in group) + 5.0


def _designed(pairs: list[Any]) -> mixed.Designed:
    """El tipo de cada subconjunto de dos o más pares de una familia, con los pares en orden de costo (como los pide la
    programación dinámica)."""
    designed: mixed.Designed = {}
    for family in {design.ctx for design in pairs}:
        members = sorted((design for design in pairs if design.ctx == family), key=lambda design: design.at(FC).cost)
        for size in range(2, len(members) + 1):
            for group in itertools.combinations(members, size):
                designed[mixed._key(FC, group)] = mixed.Group(group, SimpleNamespace(cost=_type_cost(group)), None)  # type: ignore[arg-type]
    return designed


def _partitions(items: list[Any]) -> Any:
    """Todas las particiones de items en bloques (sin orden)."""
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for partition in _partitions(rest):
        yield [[first], *partition]
        for index in range(len(partition)):
            yield [*partition[:index], [first, *partition[index]], *partition[index + 1:]]


def _brute_force(pairs: list[Any], count: int) -> float:
    """El menor costo entre todas las particiones de los pares en a lo más count tipos, cada tipo de una sola familia y
    cada par construyendo una zapata de su tipo."""
    best = float("inf")
    for partition in _partitions(pairs):
        if len(partition) > count or any(len({design.ctx for design in block}) > 1 for block in partition):
            continue
        cost = sum(len(block) * (block[0].at(FC).cost if len(block) == 1 else _type_cost(tuple(block))) for block in partition)
        best = min(best, cost)
    return best


@pytest.mark.parametrize("seed", range(6))
def test_grouping_matches_brute_force(seed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-157: la partición en grupos seguidos (en orden de costo) de cada familia y el reparto de los tipos entre
    familias dan el óptimo de todas las particiones, para cada número de tipos."""
    monkeypatch.setattr(mixed, "family_key", lambda ctx: ctx)
    rng = random.Random(seed)
    sizes = rng.choice([(4, 2, 1), (3, 3), (5,), (2, 2, 2)])
    pairs = [_fake(f"ZC{family}{index}", f"F{family}", rng.uniform(100.0, 200.0))
             for family, size in enumerate(sizes) for index in range(size)]
    designed = _designed(pairs)
    for count in range(1, len(pairs) + 2):
        found = mixed.grouping(pairs, FC, count, designed)
        if count < len(sizes):
            assert found is None
            continue
        assert found is not None
        assert found.cost == pytest.approx(_brute_force(pairs, count))
        assert len(found.groups) <= count
        assert sorted(design.pair.id for group in found.groups for design in group.pairs) == sorted(design.pair.id for design in pairs)


def test_spans_skip_what_the_last_step_does_not_use() -> None:
    """Con m = most solo cuenta el último fin, y un solo grupo empieza en el primer par."""
    assert mixed._spans(3, 1) == [(1, 0, 3)]
    assert (2, 1, 3) in mixed._spans(3, 2) and (2, 1, 2) not in mixed._spans(3, 2)


def _second_pair(project: dict[str, Any]) -> dict[str, Any]:
    """Una copia del par de la plantilla congelada, corrida SHIFT en X, con las cargas al 80 % y las columnas declaradas
    al revés (la familia se arma en orden a lo largo de la dirección principal, no en el declarado)."""
    pair = copy.deepcopy(project["combined_footings"][0])
    pair["id"] = "ZC2"
    for column in pair["columns"]:
        column["id"] += "b"
        column["x"] += SHIFT
        column["location"] = {**column["location"], "x": column["location"]["x"] + SHIFT, "joint": column["location"]["joint"] + "b"}
        for load in column["loads"]:
            for key in ("P_kN", "Vx_kN", "Vy_kN", "Mx_kNm", "My_kNm"):
                load[key] *= 0.8
    pair["columns"].reverse()
    return pair


def _two_pairs(typologies: int) -> dict[str, Any]:
    project = _imported()
    project["columns"] = []
    project["combined_footings"].append(_second_pair(project))
    for block in (project["design"], *(pair["combined_design"] for pair in project["combined_footings"])):
        block["fc_options"] = [FC]
    project["design"]["combined_typologies"] = typologies
    return project


def test_more_families_than_types_fails_before_designing(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-157: cada familia necesita un tipo; el error sale sin diseñar ningún par."""
    project = _two_pairs(1)
    project["combined_footings"][1]["columns"][0]["cx"] += 100.0  # otra sección: otra familia
    monkeypatch.setattr(mixed, "design_pairs", lambda *_: pytest.fail("no debe diseñar"))
    result = mixed.design_with_pairs(_context(project))
    assert result.fc is None and "hay 2 familias" in result.failure


def test_type_of_two_pairs_passes_for_both(tmp_path: Path) -> None:
    """D-157 con dos pares reales de la misma familia: con N = 2, la agrupación es la mejor entre el tipo común y el
    diseño de cada par (D-153); con N = 1, el tipo común cumple con los casos de los dos pares y se traslada bajo cada
    par con su refuerzo por columna en orden; su verificación pasa. No se exige que cueste al menos lo del par más
    exigente: la búsqueda es heurística y el tipo puede hallar una solución que la del par solo no halló (D-174)."""
    ctx = _context(_two_pairs(2))
    pairs = mixed.design_pairs(ctx)
    assert len(mixed.families(pairs)) == 1
    designed = mixed.group_designs(pairs, (FC,), 2)
    one, two = (mixed.grouping(pairs, FC, count, designed) for count in (1, 2))
    assert one is not None and two is not None
    alone = [design.at(FC) for design in pairs]
    assert all(solution is not None for solution in alone)
    individual = sum(solution.cost for solution in alone if solution is not None)
    assert two.cost == pytest.approx(min(one.cost, individual))

    (group,) = one.groups
    assert one.cost == pytest.approx(2 * group.solution.cost)
    chosen = mixed._chosen(pairs, FC, {FC: one})
    assert [design.typology for design in chosen] == ["ZCT1", "ZCT1"]
    first, second = (design.solution for design in chosen)
    assert first is not None and second is not None
    assert [(item.geometry.length, item.geometry.width, item.geometry.h) for item in (first, second)].count(
        (first.geometry.length, first.geometry.width, first.geometry.h)) == 2
    assert second.geometry.center[0] - first.geometry.center[0] == pytest.approx(SHIFT)
    assert first.geometry.center[1] == pytest.approx(second.geometry.center[1])
    assert first.cost == pytest.approx(second.cost)
    for key in ("dowels", "bands", "band_tops"):
        value = first.reinforcement.get(key)
        if not isinstance(value, dict):
            continue
        orders = [[column.id for column in combined.ordered(design.ctx)] for design in chosen]
        assert [value.get(column) for column in orders[0]] == [second.reinforcement[key].get(column) for column in orders[1]]

    result = mixed._only_pairs(ctx, tuple(pairs), {FC: one.cost}, {FC: one})
    project = mixed.designed_with_pairs(ctx, result)
    assert [footing["typology"] for footing in project["combined_footings"]] == ["ZCT1", "ZCT1"]
    path = tmp_path / "tipos.json"
    path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    report_file(path, tmp_path / "salida")
    results = json.loads((tmp_path / "salida" / "resultado.json").read_text(encoding="utf-8"))
    assert results["status"] == "PASS", results.get("status")
