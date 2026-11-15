"""Acción de cada pilote sobre el cabezal en cada caso (D-138).

Con las cargas de la columna, el cabezal es rígido y los pilotes, articulados (guía CRSI, cap. 3): la resultante N de la
columna, los pesos y las sobrecargas (domain/footing/base.py) y su momento en el plano de la cabeza de los pilotes se
reparten como R_i = N/n + b·dx_i + c·dy_i, con (dx, dy) respecto al centroide del grupo y (b, c) del equilibrio de
momentos Σ R·dx = My y Σ R·dy = −Mx (pseudoinversa si los pilotes están alineados; el momento que el grupo no resiste se
reporta). El cortante de la columna se reparte por igual. Con las cargas de los pilotes, sus fuerzas y momentos se toman
tal cual, más el peso repartido por igual si sus reacciones no lo incluyen.

Mala ubicación (13.4.1.4, D-138): la excentricidad accidental de magnitud igual a la tolerancia, en la dirección más
desfavorable para cada pilote, cambia su reacción en ±|N|·t·|K⁺·(dx, dy)|. Se aplica solo con las cargas de la columna
(a la capacidad de los pilotes y a las solicitaciones del cabezal); con las de los pilotes la tolerancia solo cambia los
brazos (decisión del usuario, D-138).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from structurelab_rc.domain.footing.base import base_resultant
from structurelab_rc.domain.footing.flexure import FaceMoments
from structurelab_rc.domain.footing.loads import column_faces, uniform_load
from structurelab_rc.model.footing import FootingLoad, UnitWeighted
from structurelab_rc.model.pile_cap import PileCap

_SINGULAR = 1e-9


@dataclass(frozen=True)
class PileForces:
    """Acción de cada pilote sobre el cabezal, en el orden de cap.piles: reacción vertical (N, positiva en compresión del
    pilote), fuerza horizontal (Vx, Vy) en N y momento (Mx, My) en N·mm; spread es el cambio de la reacción por la mala
    ubicación (0 si no se aplica)."""

    reactions: tuple[float, ...]
    shears: tuple[tuple[float, float], ...]
    moments: tuple[tuple[float, float], ...]
    spread: tuple[float, ...]


@dataclass(frozen=True)
class CapCase:
    """Un caso: su carga de referencia (nombre, tipo, factores), las fuerzas de los pilotes, la fuerza vertical de la
    columna (N, para el aplastamiento), la vertical total sobre los pilotes y el momento que el grupo no resiste (N·mm,
    con las cargas de la columna y pilotes alineados)."""

    load: FootingLoad
    forces: PileForces
    column: float
    total: float
    unresisted: float = 0.0

    @property
    def case(self) -> str:
        return self.load.case

    def reaction(self, index: int, sense: float = 0.0) -> float:
        """La reacción de un pilote con la mala ubicación del lado que pide la revisión: sense = +1 la aumenta (compresión
        desfavorable), −1 la reduce (tracción o momento negativo desfavorables) y 0 no la aplica."""
        return self.forces.reactions[index] + sense * self.forces.spread[index]


def _pinv(sxx: float, sxy: float, syy: float) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float] | None]:
    """Pseudoinversa de la matriz simétrica [[sxx, sxy], [sxy, syy]] y la dirección que no resiste (None si es
    invertible)."""
    det = sxx * syy - sxy**2
    scale = max(sxx, syy, 1.0)
    if abs(det) > _SINGULAR * scale**2:
        return (syy / det, -sxy / det), (-sxy / det, sxx / det), None
    trace = sxx + syy
    if trace <= _SINGULAR * scale:
        return (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)
    # Rango 1: K = trace·u·uᵀ con u el eje de los pilotes; K⁺ = u·uᵀ/trace y la dirección normal no resiste.
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(angle), math.sin(angle)
    return (ux * ux / trace, ux * uy / trace), (ux * uy / trace, uy * uy / trace), (-uy, ux)


@dataclass(frozen=True)
class _Group:
    """Centroide del grupo, coordenadas relativas y pseudoinversa de su matriz de segundos momentos."""

    centre: tuple[float, float]
    offsets: tuple[tuple[float, float], ...]
    inverse: tuple[tuple[float, float], tuple[float, float]]
    weak: tuple[float, float] | None


def group_centre(cap: PileCap) -> tuple[float, float]:
    """Centroide del grupo de pilotes, en mm."""
    n = len(cap.piles)
    return sum(pile.x for pile in cap.piles) / n, sum(pile.y for pile in cap.piles) / n


def _group(cap: PileCap) -> _Group:
    xc, yc = group_centre(cap)
    offsets = tuple((pile.x - xc, pile.y - yc) for pile in cap.piles)
    sxx = sum(dx * dx for dx, _ in offsets)
    syy = sum(dy * dy for _, dy in offsets)
    sxy = sum(dx * dy for dx, dy in offsets)
    first, second, weak = _pinv(sxx, sxy, syy)
    return _Group((xc, yc), offsets, (first, second), weak)


def _spread(group: _Group, total: float, tolerance: float) -> tuple[float, ...]:
    """|N|·t·|K⁺·(dx, dy)| de cada pilote: el mayor cambio de su reacción con una excentricidad accidental de magnitud t."""
    (a, b), (c, d) = group.inverse
    return tuple(abs(total) * tolerance * math.hypot(a * dx + b * dy, c * dx + d * dy) for dx, dy in group.offsets)


def _from_column(cap: PileCap, weights: UnitWeighted, load: FootingLoad, group: _Group) -> CapCase:
    resultant = base_resultant(cap, weights, load)
    embedment = cap.pile.embedment
    # Momentos en el plano de la cabeza de los pilotes y respecto al centroide del grupo (N hacia abajo en el origen).
    mx = resultant.mx + embedment * load.vy + group.centre[1] * resultant.n
    my = resultant.my - embedment * load.vx - group.centre[0] * resultant.n
    (a, b), (c, d) = group.inverse
    slope_x, slope_y = a * my + b * -mx, c * my + d * -mx
    n = len(cap.piles)
    reactions = tuple(resultant.n / n + slope_x * dx + slope_y * dy for dx, dy in group.offsets)
    unresisted = 0.0 if group.weak is None else abs(group.weak[0] * my + group.weak[1] * -mx)
    forces = PileForces(reactions, ((load.vx / n, load.vy / n),) * n, ((0.0, 0.0),) * n,
                        _spread(group, resultant.n, cap.mislocation))
    return CapCase(load, forces, load.p, resultant.n, unresisted)


def _weight(cap: PileCap, weights: UnitWeighted, load: FootingLoad) -> float:
    """Peso del cabezal, el pedestal, el relleno y las sobrecargas con los factores del caso, en N."""
    footing, pedestal, fill = cap.weights(weights)
    dead, live = cap.surcharges()
    return load.dead_factor * (footing + pedestal + fill + dead) + load.live_factor * live


def _from_piles(cap: PileCap, weights: UnitWeighted, given: tuple[FootingLoad, tuple[FootingLoad, ...]]) -> CapCase:
    load, piles = given
    weight = _weight(cap, weights, load)
    share = 0.0 if cap.reactions_include_weight else weight / len(piles)
    reactions = tuple(pile.p + share for pile in piles)
    total = sum(reactions)
    forces = PileForces(reactions, tuple((pile.vx, pile.vy) for pile in piles), tuple((pile.mx, pile.my) for pile in piles),
                        (0.0,) * len(piles))
    return CapCase(load, forces, total - weight, total)


def cap_cases(cap: PileCap, weights: UnitWeighted) -> list[CapCase]:
    """Cada caso, de servicio y mayorado, con la acción de cada pilote sobre el cabezal."""
    group = _group(cap)
    return [_from_piles(cap, weights, (load, piles)) if piles else _from_column(cap, weights, load, group)
            for load, piles in cap.case_loads()]


def spread_on_cap(cap: PileCap) -> bool:
    """Si la mala ubicación cambia también las reacciones: solo con las cargas de la columna (D-138)."""
    return not cap.from_piles


AXES = {"x": 0, "y": 1}


@dataclass(frozen=True)
class FactoredCap:
    """Un caso mayorado del cabezal: el caso, la carga uniforme hacia abajo (N/mm²), el sentido de la mala ubicación en
    las reacciones (+1, −1 o 0, ver CapCase.reaction) y la fracción de la reacción que produce cortante en una sección
    (la del perfil: ACI 13.4.6.7, NSR-10 C.15.5.4)."""

    cap: PileCap
    case: CapCase
    load: float
    sense: float
    share: Callable[[float, float], float]

    def reaction(self, index: int) -> float:
        return self.case.reaction(index, self.sense)

    def beyond(self, axis: int, plane: float, outward: float) -> tuple[float, float, float]:
        """Más allá de un plano vertical normal a x (axis = 0) o a y (axis = 1), del lado outward (+1 o −1): el cortante
        con la reacción interpolada, el cortante con la reacción completa y el momento respecto al plano (positivo
        tracciona la cara inferior), en N y N·mm. Un pilote cuenta si, mal ubicado del lado desfavorable (su distancia más
        la tolerancia), queda más allá: con su reacción completa, su brazo y la acción de su cabeza (su momento y el de su
        fuerza horizontal respecto al eje de la sección). El peso del cabezal, hacia abajo."""
        cap = self.cap
        tolerance, size, lever = cap.mislocation, cap.pile.size, cap.pile.embedment - cap.h / 2
        shear = full = moment = 0.0
        for index, pile in enumerate(cap.piles):
            reaction = self.reaction(index)
            arm = outward * ((pile.x, pile.y)[axis] - plane) + tolerance
            shear += self.share(arm, size) * reaction
            if arm <= 0:
                continue
            full += reaction
            moment += reaction * arm
            (vx, vy), (mx, my) = self.case.forces.shears[index], self.case.forces.moments[index]
            moment += -outward * (my + lever * vx) if axis == 0 else outward * (mx - lever * vy)
        half, width = (cap.lx / 2, cap.ly) if axis == 0 else (cap.ly / 2, cap.lx)
        length = max(half - outward * plane, 0.0)
        weight = self.load * width * length
        return shear - weight, full - weight, moment - weight * length / 2

    def face_moments(self) -> FaceMoments:
        """Momento en cada cara de la columna (ACI 13.2.6.6 y 13.4.6.4, NSR-10 C.15.4.1)."""
        faces = column_faces(self.cap)
        return FaceMoments(self.case.case, {direction: (self.beyond(AXES[direction], plus, 1.0)[2],
                                                        self.beyond(AXES[direction], minus, -1.0)[2])
                                            for direction, (plus, minus) in faces.items()})


@dataclass(frozen=True)
class CapAnalysis:
    """El análisis de un cabezal, calculado una vez (D-138): todos los casos con las reacciones de los pilotes, los casos
    mayorados con la mala ubicación del lado de la compresión (cortante y punzonamiento) y los momentos de cara de cada
    caso mayorado; con las cargas de la columna, cada caso da dos, con +ΔR (malla inferior) y −ΔR (momento negativo)."""

    cases: tuple[CapCase, ...]
    factored: tuple[FactoredCap, ...]
    moments: tuple[FaceMoments, ...]


def analyze(cap: PileCap, weights: UnitWeighted, share: Callable[[float, float], float]) -> CapAnalysis:
    """Las reacciones, los casos mayorados y sus momentos de cara; share es la interpolación del perfil."""
    cases = tuple(cap_cases(cap, weights))
    spread = spread_on_cap(cap)
    factored = tuple(FactoredCap(cap, case, uniform_load(cap, weights, case.load), 1.0 if spread else 0.0, share)
                     for case in cases if case.load.kind == "factored")
    if not spread:
        return CapAnalysis(cases, factored, tuple(item.face_moments() for item in factored))
    moments = []
    for item in factored:
        moments.append(replace(item.face_moments(), case=f"{item.case.case} (+ΔR)"))
        moments.append(replace(replace(item, sense=-1.0).face_moments(), case=f"{item.case.case} (−ΔR)"))
    return CapAnalysis(cases, factored, tuple(moments))
