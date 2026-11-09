"""Partición óptima de una lista ordenada en un número dado de tramos continuos (programación dinámica) y reasignación
de elementos entre grupos ya formados."""

import math
from collections.abc import Callable, Sequence


def partition(count: int, groups: int, cost: Callable[[int, int], float]) -> tuple[float, list[tuple[int, int]]]:
    """Parte los índices 0..count−1 en exactamente `groups` tramos continuos de menor costo total.

    cost(i, j) es el costo del tramo i..j (inclusivo); math.inf si el tramo no es viable. Devuelve el costo total y los
    tramos; si no hay partición viable, (math.inf, []).
    """
    if not 1 <= groups <= count:
        raise ValueError("el número de tramos debe estar entre 1 y el número de elementos")
    best = [[math.inf] * (count + 1) for _ in range(groups + 1)]
    choice = [[-1] * (count + 1) for _ in range(groups + 1)]
    best[0][0] = 0.0
    for g in range(1, groups + 1):
        for end in range(g, count + 1):  # los primeros `end` elementos en g tramos
            for start in range(g - 1, end):  # el último tramo es start..end−1
                if best[g - 1][start] == math.inf:
                    continue
                total = best[g - 1][start] + cost(start, end - 1)
                if total < best[g][end]:
                    best[g][end], choice[g][end] = total, start
    if best[groups][count] == math.inf:
        return math.inf, []
    segments = []
    end = count
    for g in range(groups, 0, -1):
        start = choice[g][end]
        segments.append((start, end - 1))
        end = start
    return best[groups][count], segments[::-1]


def reassign(owner: Sequence[int], groups: int, cost: Callable[[int, int], float], order: Sequence[int]) -> list[int]:
    """Mueve elementos al grupo más barato sin vaciar ninguno (D-074).

    owner[i] es el grupo del elemento i; cost(i, g) el costo del elemento i en el grupo g (math.inf si no cabe). En el
    orden dado, cada elemento pasa al grupo de menor costo (el de menor índice si empatan) si baja su costo y su grupo
    conserva al menos un elemento; se repite hasta que nada cambie (termina: el costo total baja en cada movimiento).
    """
    owner = list(owner)
    sizes = [0] * groups
    for group in owner:
        sizes[group] += 1
    changed = True
    while changed:
        changed = False
        for item in order:
            here = owner[item]
            if sizes[here] <= 1:
                continue
            target = min(range(groups), key=lambda group: (cost(item, group), group))
            if cost(item, target) < cost(item, here):
                owner[item] = target
                sizes[here] -= 1
                sizes[target] += 1
                changed = True
    return owner
