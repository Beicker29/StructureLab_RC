"""Separación libre mínima de las barras de las zapatas (D-102): ACI 25.2.1, NSR-10 C.7.6.1 y C.3.3.2(c).

Cada tipo de refuerzo declarado se revisa por separado: la separación libre (separación centro a centro menos el
diámetro) frente al mínimo del perfil, que depende del diámetro y del tamaño máximo nominal del agregado. Sin el
agregado (materials.max_aggregate) la verificación queda INCOMPLETE: no se supone (decisión del usuario).
"""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.combined_beam import long_beam_member, spread_bottom_layer
from structurelab_rc.domain.footing.declared import PRINCIPAL, SECONDARY
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing
from structurelab_rc.model.reinforcement import BarPosition, BarSpacing

MIN_SPACING = "Separacion minima"
_TOLERANCE = 1e-3  # mm


def min_spacing_check(basis: Basis, member: str, label: str, bars: tuple[str, float]) -> Check:
    """La separación libre mínima de unas barras paralelas; bars = (designación, separación centro a centro en mm)."""
    designation, spacing = bars
    name = f"{MIN_SPACING} ({label})"
    development = basis.profile.development
    clause = development.clauses()["min_spacing"]
    aggregate = basis.materials.max_aggregate
    if aggregate is None:
        error = incomplete("Falta materials.max_aggregate (tamano maximo nominal del agregado grueso, mm): sin el no se revisa "
                           "la separacion minima del refuerzo (D-102)", member=member)
        return Check(name, Status.INCOMPLETE, (error,), clause, member=member)
    spec = next((bar for bar in basis.bars if bar.designation == designation), None)
    if spec is None:  # la validación de entrada ya reporta la barra fuera del catálogo
        return Check(name, Status.BLOCKED, clause=clause, member=member)
    clear = spacing - spec.diameter_mm
    required = development.min_clear_spacing(spec.diameter_mm, aggregate)
    return Check(name, Status.PASS if clear >= required else Status.FAIL, clause=clause, demand=required, capacity=clear,
                 unit="mm", member=member, values=(("s", spacing), ("db", spec.diameter_mm), ("dagg", aggregate)))


def footing_min_spacing_checks(basis: Basis, footing: Footing) -> list[Check]:
    """Zapata aislada: cada dirección de la malla inferior y de la superior, y la separación de la franja central."""
    checks = []
    for mat, name in ((footing.bottom, "inferior"), (footing.top, "superior")):
        if mat is None:
            continue
        for direction in ("x", "y"):
            bar_set = getattr(mat, direction)
            checks.append(min_spacing_check(basis, footing.id, f"malla {name}, barras {direction}", (bar_set.designation, bar_set.spacing)))
            if bar_set.band_spacing is not None:
                checks.append(min_spacing_check(basis, footing.id, f"malla {name}, barras {direction}, franja central",
                                                (bar_set.designation, bar_set.band_spacing)))
    return checks


def combined_min_spacing_checks(basis: Basis, footing: CombinedFooting) -> list[Check]:
    """Zapata combinada: las barras inferiores y superiores de la dirección principal y de la secundaria y el band de
    cada columna, cada uno con su separación declarada."""
    directions = {"x": PRINCIPAL, "y": SECONDARY}
    declared: list[tuple[str, tuple[str, float]]] = [
        (f"barras inferiores, {directions[direction]}", (bars.designation, bars.spacing))
        for direction, bars in (("x", footing.bottom.x), ("y", footing.bottom.y))]
    declared += [(f"band, columna {column.id}", (column.band.designation, column.band.spacing))
                 for column in footing.columns if column.band is not None]
    declared += [(f"band superior, columna {column.id}", (column.band_top.designation, column.band_top.spacing))
                 for column in footing.columns if column.band_top is not None]
    if footing.top is not None:
        declared += [(f"barras superiores, {directions[direction]}", (bars.designation, bars.spacing))
                     for direction, bars in (("x", footing.top.x), ("y", footing.top.y)) if bars is not None]
    if footing.beam is not None:
        declared += _beam_layers(basis, footing)
    return [min_spacing_check(basis, footing.id, label, bars) for label, bars in declared]


def _beam_layers(basis: Basis, footing: CombinedFooting) -> list[tuple[str, tuple[str, float]]]:
    """Capas de flexión de la viga de la T invertida (D-106, D-114): la menor separación entre barras vecinas de cada
    capa, con las posiciones que se colocan: las declaradas, las de su separación o, si se declararon solo las barras,
    las repartidas (la capa inferior en el ancho cubierto; las demás entre las esquinas del estribo, como en las vigas)."""
    beam = footing.beam
    assert beam is not None
    member = long_beam_member(footing, basis.bars, basis.profile)
    placed = placed_bars(member.stations[0].layout, member.section, basis.bars)
    out = []
    flexure = [layer for layer in beam.layers if layer.role == "flexure"]
    highest = min(flexure, key=lambda layer: layer.depth)
    for layer in flexure:
        position = "inferior" if layer is beam.bottom_layer else ("superior" if layer is highest else "intermedia")
        label = f"capa {position} a {layer.depth:.0f} mm de la viga"
        if isinstance(layer.bars, BarSpacing):
            out.append((label, (layer.bars.designation, layer.bars.spacing)))
            continue
        if layer is beam.bottom_layer:
            source = spread_bottom_layer(basis.profile, footing, basis.bars)
            pairs = [(bar.designation, bar.x) for bar in source.bars if isinstance(bar, BarPosition)]
        elif all(isinstance(bar, BarPosition) for bar in layer.bars):
            pairs = [(bar.designation, bar.x) for bar in layer.bars if isinstance(bar, BarPosition)]
        else:  # solo las barras: las posiciones de la regla de vigas, en la profundidad de la capa (la viga va volteada)
            depth = footing.total_height - layer.depth
            pairs = [(bar.designation, bar.x) for bar in placed if abs(bar.depth - depth) <= _TOLERANCE]
        xs = sorted(x for _, x in pairs)
        gaps = [b - a for a, b in zip(xs, xs[1:], strict=False)]
        if gaps:
            out.append((label, (pairs[0][0], min(gaps))))
    return out
