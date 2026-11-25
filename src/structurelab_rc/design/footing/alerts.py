"""Alertas de tipologías atípicas del diseño por tipologías (D-172): métricas sobre el resultado de la corrida para
alertar al analista, sin cambiar el diseño ni volver a diseñar.

Lee las tipologías elegidas y los diseños individuales de cada columna que la búsqueda ya calculó (DesignResult.singles).
Por columna, con su zapata individual: e/B de los casos de servicio y el contacto (la misma revisión del suelo,
service_checks), la estabilidad por P de servicio y el factor de amplificación FA = A(P, M)/A(P, 0), con la planta por
suelo de soil_plan en el espesor de su diseño individual y los momentos de la columna en cero (el único cálculo extra; no
diseña mallas). Por tipología: área, volumen, columnas, costo, atípicas por Tukey y por z robusto, pequeñas, sobrecosto
por agrupación y la concentración del concreto y del costo. La solución la decide el analista en el proyecto
(combined_pairs o exclude_unique_names).
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.design.footing.typologies import DesignResult
from structurelab_rc.design.footing.typology import Context, Typology, column_cost, footing_for, soil_plan
from structurelab_rc.domain.footing.service import CONTACT, service_checks
from structurelab_rc.model.design import DesignColumn, TypologyAlerts

MAD_SCALE = 1.4826  # el MAD por este factor estima la desviación estándar de una normal
METRICS = ("area", "volume")
FA = "FA"
UPLIFT = "levantamiento (P <= 0)"
LOW_P = "carga axial baja"
NO_EQUILIBRIUM = "sin equilibrio con el suelo"


def eccentricity_reason(direction: str) -> str:
    return f"excentricidad {direction}"


@dataclass(frozen=True)
class ColumnSignal:
    """Señales de una columna con su zapata individual. P de servicio en N; e/B = |ex|/lx y |ey|/ly con su caso de
    servicio; contact: la menor fracción de la base en contacto y su caso; reasons: por qué es candidata (vacío si no)."""

    column: str
    joint: str | None
    typology: str
    p_max: float
    p_min: float
    fa: float | None
    ex_ratio: float | None
    ex_case: str | None
    ey_ratio: float | None
    ey_case: str | None
    contact: float | None
    contact_case: str | None
    reasons: tuple[str, ...]

    @property
    def candidate(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True)
class Statistic:
    """La estadística de una métrica entre las tipologías: el límite de Tukey (Q3 + k·IQR, cuartiles inclusivos) y la
    mediana y el MAD del z robusto; las notas explican lo que no se calcula."""

    q1: float | None
    q3: float | None
    tukey_limit: float | None
    median: float | None
    mad: float | None
    tukey_note: str = ""
    z_note: str = ""

    def above_tukey(self, value: float) -> bool:
        return self.tukey_limit is not None and value > self.tukey_limit

    def z(self, value: float) -> float | None:
        if self.median is None or not self.mad:
            return None
        return (value - self.median) / (MAD_SCALE * self.mad)


@dataclass(frozen=True)
class TypologyStats:
    """Métricas de una tipología: dimensiones (mm), sus columnas, su costo y la suma de los diseños individuales de esas
    columnas, sus candidatas, el z de cada métrica y las señales (atypical_by: "tukey area", "z area", "tukey volume",
    "z volume")."""

    name: str
    lx: float
    ly: float
    h: float
    columns: tuple[str, ...]
    cost: float
    singles_cost: float
    candidates: int
    z: dict[str, float | None]
    atypical_by: tuple[str, ...]
    small: bool
    flagged: bool

    @property
    def area(self) -> float:
        """mm², de una zapata."""
        return self.lx * self.ly

    @property
    def volume(self) -> float:
        """mm³, de una zapata."""
        return self.lx * self.ly * self.h

    @property
    def grouping_overcost(self) -> float:
        return self.cost - self.singles_cost


@dataclass(frozen=True)
class Concentration:
    """Las count columnas de total que más consumen (la fracción pedida, hacia arriba) y su parte del concreto y del
    costo de las aisladas, en %."""

    fraction: float
    count: int
    total: int
    concrete_share: float
    cost_share: float


@dataclass(frozen=True)
class AlertsResult:
    settings: TypologyAlerts
    fc: float
    columns: tuple[ColumnSignal, ...]
    typologies: tuple[TypologyStats, ...]
    statistics: dict[str, Statistic]
    concentration: Concentration


def statistic(values: Sequence[float], settings: TypologyAlerts) -> Statistic:
    """Tukey y z robusto de una métrica: con menos tipologías que min_typologies_for_statistics, ninguno; con MAD = 0,
    sin z (no se define)."""
    least = settings.min_typologies_for_statistics
    if len(values) < least:
        note = f"hay {len(values)} tipologías y la estadística necesita al menos {least} (min_typologies_for_statistics)"
        return Statistic(None, None, None, None, None, note, note)
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    median = statistics.median(values)
    mad = statistics.median([abs(value - median) for value in values])
    z_note = "" if mad else "MAD = 0: al menos la mitad de las tipologías tiene el mismo valor; el z robusto no se define"
    return Statistic(q1, q3, q3 + settings.tukey_k * (q3 - q1), median, mad, "", z_note)


def zeroed(column: DesignColumn) -> DesignColumn:
    """La columna con los mismos casos y Mx = My = 0 (Vx y Vy se conservan)."""
    return column.model_copy(update={"loads": tuple(load.model_copy(update={"mx": 0.0, "my": 0.0}) for load in column.loads)})


def column_signal(ctx: Context, settings: TypologyAlerts, column: DesignColumn, owner: str, single: Typology) -> ColumnSignal:
    """Las señales de una columna con su zapata individual (single)."""
    service = [load.p for load in column.loads if load.kind == "service"]
    p_max, p_min = max(service, default=0.0), min(service, default=0.0)
    reasons: list[str] = []
    with_moment = soil_plan(ctx, column, single.fc, single.h)
    without = soil_plan(ctx, zeroed(column), single.fc, single.h)
    fa = None if with_moment is None or without is None else with_moment[0] * with_moment[1] / (without[0] * without[1])
    if fa is not None and fa >= settings.fa_threshold:
        reasons.append(FA)
    worst: dict[str, tuple[float, str | None]] = {"x": (-1.0, None), "y": (-1.0, None)}
    contact: tuple[float, str | None] = (math.inf, None)
    unbalanced = False
    for check in service_checks(ctx.profile, footing_for(ctx, single, column, None), ctx.soil):
        if check.name != CONTACT:
            continue
        values = dict(check.values)
        if "ex" not in values:  # sin equilibrio: la resultante no comprime el suelo
            unbalanced = True
            continue
        for direction, size in (("x", single.lx), ("y", single.ly)):
            ratio = abs(values[f"e{direction}"]) / size
            if ratio > worst[direction][0]:
                worst[direction] = (ratio, check.case)
        if values["contacto"] < contact[0]:
            contact = (values["contacto"], check.case)
    reasons += [eccentricity_reason(direction) for direction in ("x", "y")
                if worst[direction][1] is not None and worst[direction][0] > settings.eccentricity_threshold]
    if unbalanced:
        reasons.append(NO_EQUILIBRIUM)
    if p_min <= 0:
        reasons.append(UPLIFT)
    elif p_min < settings.min_relative_p * p_max:
        reasons.append(LOW_P)
    ratio_x, case_x = worst["x"]
    ratio_y, case_y = worst["y"]
    return ColumnSignal(column.id, None if column.location is None else column.location.joint, owner, p_max, p_min, fa,
                        None if case_x is None else ratio_x, case_x, None if case_y is None else ratio_y, case_y,
                        None if contact[1] is None else contact[0], contact[1], tuple(reasons))


def _concentration(ctx: Context, result: DesignResult, fraction: float) -> Concentration:
    """Concreto (m³, zapata y pedestal) y costo de cada columna en su tipología (column_cost, el que suma el diseño)."""
    columns = {column.id: column for column in ctx.project.columns}
    concrete, cost = [], []
    for item in result.typologies:
        for column_id in item.columns:
            own = column_cost(ctx, item.design.typology, columns[column_id], item.design.dowels[column_id])
            cost.append(own[0])
            concrete.append(own[1])
    total = len(cost)
    count = max(1, math.ceil(round(fraction * total, 9)))

    def share(values: list[float]) -> float:
        whole = sum(values)
        return 0.0 if not whole else 100 * sum(sorted(values, reverse=True)[:count]) / whole

    return Concentration(fraction, count, total, share(concrete), share(cost))


def typology_alerts(ctx: Context, result: DesignResult) -> AlertsResult:
    """Las alertas del resultado de la corrida (D-172); no lo cambia. Requiere la solución (f'c) y los diseños
    individuales del f'c elegido."""
    settings = ctx.project.typology_alerts
    assert settings is not None and result.fc is not None
    columns = {column.id: column for column in ctx.project.columns}
    signals = tuple(column_signal(ctx, settings, columns[column_id], item.name, result.singles[column_id].typology)
                    for item in result.typologies for column_id in item.columns)
    candidates = {signal.column for signal in signals if signal.candidate}
    stats = {metric: statistic([_measure(item.design.typology, metric) for item in result.typologies], settings)
             for metric in METRICS}
    typologies = []
    for item in result.typologies:
        t = item.design.typology
        z = {metric: stats[metric].z(_measure(t, metric)) for metric in METRICS}
        by = tuple(f"{test} {metric}" for metric in METRICS for test, hit in
                   (("tukey", stats[metric].above_tukey(_measure(t, metric))),
                    ("z", (z[metric] or 0.0) > settings.z_threshold)) if hit)
        count = sum(column_id in candidates for column_id in item.columns)
        typologies.append(TypologyStats(
            item.name, t.lx, t.ly, t.h, item.columns, item.design.cost,
            sum(result.singles[column_id].cost for column_id in item.columns), count, z, by,
            bool(by) and len(item.columns) <= settings.small_typology_max_columns, bool(by) and count > 0))
    return AlertsResult(settings, result.fc, signals, tuple(typologies), stats,
                        _concentration(ctx, result, settings.pareto_fraction))


def _measure(typology: Typology, metric: str) -> float:
    """Área (mm²) o volumen (mm³) de una zapata de la tipología."""
    area = typology.lx * typology.ly
    return area if metric == "area" else area * typology.h
