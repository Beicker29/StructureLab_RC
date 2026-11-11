"""Validación de un proyecto contra su perfil normativo y el catálogo."""

from collections.abc import Iterator, Sequence

from structurelab_rc.codes.registry import PROFILES, Profile
from structurelab_rc.domain.beam.geometry import flange_limits, interior_limits, placed_bars
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.combined_beam import long_beam_member
from structurelab_rc.errors import StructuredError, incomplete, invalid_input
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import BarSet, Dowels, Footing
from structurelab_rc.model.project import Member, Project, Station

CHECK_NAME = "Validacion de entrada"


def _profile_errors(project: Project, profile: Profile) -> Iterator[StructuredError]:
    if project.seismic.level not in profile.seismic.seismic_levels():
        levels = ", ".join(sorted(profile.seismic.seismic_levels()))
        yield invalid_input(f"El nivel sismico '{project.seismic.level}' no existe en {profile.id}; valores: {levels}")
    if profile.strength_assumptions.beta1(project.materials.fc) is None:
        yield invalid_input(f"{profile.id} no define beta1 para fc = {project.materials.fc} MPa")


def _bar_errors(member: Member, station: Station, bars: Sequence[RebarSpec]) -> Iterator[StructuredError]:
    """Cada barra dentro del estribo del alma, o dentro del ala si es de flexión y está a la altura del ala (D-045)."""
    where = {"member": member.id, "z": station.z}
    section, layout = member.section, station.layout
    specs = {bar.designation: bar for bar in bars}
    placed = placed_bars(layout, section, bars)
    for bar in placed:
        left, right = interior_limits(section, layout, specs, bar.diameter)
        if left - 1e-6 <= bar.x <= right + 1e-6:
            continue
        flange = flange_limits(section, bar.diameter)
        in_flange = flange is not None and section.hf is not None and bar.depth <= section.hf
        if bar.role == "flexure" and in_flange and flange is not None and flange[0] - 1e-6 <= bar.x <= flange[1] + 1e-6:
            continue
        yield invalid_input(f"La barra {bar.designation} en x = {bar.x:.1f} mm queda fuera del estribo y del ala", **where)
    for depth in sorted({bar.depth for bar in placed}):
        row = [bar.x for bar in placed if bar.depth == depth]
        if any(second <= first for first, second in zip(row, row[1:], strict=False)):
            yield invalid_input(f"Las barras de la capa a {depth} mm no estan en orden de x creciente", **where)


def _station_errors(member: Member, station: Station, specs: dict[str, RebarSpec]) -> Iterator[StructuredError]:
    where = {"member": member.id, "z": station.z}
    if station.z > member.length:
        yield invalid_input("La estacion esta fuera de la longitud del miembro", **where)
    missing = sorted(station.layout.designations() - set(specs))
    for name in missing:
        yield invalid_input(f"La barra '{name}' no esta en el catalogo", **where)
    for layer in station.layout.layers:
        if layer.depth >= member.section.h:
            yield invalid_input(f"La capa a {layer.depth} mm esta fuera de la seccion", **where)
    if not any(layer.role == "flexure" for layer in station.layout.layers):
        yield invalid_input("El armado no tiene capas de flexion", **where)
    if not missing:
        yield from _bar_errors(member, station, list(specs.values()))
    demands = station.demands
    labels = (("Pu", demands.pu), ("Mu", demands.mu), ("M2", demands.m2), ("Vu", demands.vu), ("V3", demands.v3), ("Tu", demands.tu))
    for label, value in labels:
        if value is None:
            yield incomplete(f"Falta la demanda {label}", **where)


def _bar_set_errors(name: str, bar_set: BarSet, specs: dict[str, RebarSpec], where: dict[str, str]) -> Iterator[StructuredError]:
    spec = specs.get(bar_set.designation)
    if spec is None:
        yield invalid_input(f"La barra '{bar_set.designation}' de {name} no esta en el catalogo", **where)
    elif bar_set.spacing <= spec.diameter_mm:
        yield invalid_input(f"La separacion de {name} no deja espacio libre", **where)


def _layers_errors(layers: list[tuple[str, list[BarSet]]], h: float, cover: float, specs: dict[str, RebarSpec],
                   where: dict[str, str]) -> Iterator[StructuredError]:
    """Barras del catálogo con separación libre positiva, y las capas y los recubrimientos dentro del espesor h."""
    thickness = 2 * cover
    for name, bar_sets in layers:
        for index, bar_set in enumerate(bar_sets):
            yield from _bar_set_errors(f"las barras {'xy'[index] if len(bar_sets) > 1 else 'x'} de la malla {name}", bar_set, specs, where)
        thickness += sum(specs[bar_set.designation].diameter_mm for bar_set in bar_sets if bar_set.designation in specs)
    if thickness >= h:
        yield invalid_input("Las mallas y los recubrimientos no caben en el espesor de la zapata", **where)


def _dowel_errors(dowels: Dowels | None, specs: dict[str, RebarSpec], where: dict[str, str]) -> Iterator[StructuredError]:
    if dowels is not None and dowels.designation not in specs:
        yield invalid_input(f"La barra '{dowels.designation}' de los pasadores no esta en el catalogo", **where)


def _footing_errors(footing: Footing, specs: dict[str, RebarSpec]) -> Iterator[StructuredError]:
    """Barras del catálogo, separación libre positiva y mallas dentro del espesor."""
    where = {"member": footing.id}
    layers = [("inferior", [footing.bottom.x, footing.bottom.y])]
    if footing.top is not None:
        layers.append(("superior", [footing.top.x, footing.top.y]))
    yield from _layers_errors(layers, footing.h, footing.cover, specs, where)
    yield from _dowel_errors(footing.column.dowels, specs, where)


def _combined_errors(footing: CombinedFooting, specs: dict[str, RebarSpec]) -> Iterator[StructuredError]:
    """Lo mismo para una zapata combinada (D-080): malla inferior, barras superiores en X, refuerzo transversal bajo cada
    columna y pasadores."""
    where = {"member": footing.id}
    layers = [("inferior", [footing.bottom.x, footing.bottom.y])]
    if footing.top is not None:
        layers.append(("superior", [footing.top]))
    yield from _layers_errors(layers, footing.h, footing.cover, specs, where)
    for column in footing.columns:
        if column.band is not None:
            yield from _bar_set_errors(f"el refuerzo transversal bajo la columna '{column.id}'", column.band, specs, where)
        yield from _dowel_errors(column.dowels, specs, {**where, "column": column.id})
    if footing.skin is not None and footing.skin.designation not in specs:
        yield invalid_input(f"La barra '{footing.skin.designation}' del refuerzo superficial no esta en el catalogo", **where)
    if footing.stirrups is not None and footing.stirrups.designation not in specs:
        yield invalid_input(f"La barra '{footing.stirrups.designation}' de los estribos no esta en el catalogo", **where)
    missing = sorted({name for layer in footing.torsion_layers for name in layer.designations()} - set(specs))
    for name in missing:
        yield invalid_input(f"La barra '{name}' de las capas de torsion no esta en el catalogo", **where)
    if footing.torsion_layers and not missing and _catalogued(footing, specs):
        # Las barras de Aℓ dentro del estribo de la viga larga, con la regla de las vigas (D-088).
        member = long_beam_member(footing, list(specs.values()))
        yield from _bar_errors(member, member.stations[0], list(specs.values()))


def _catalogued(footing: CombinedFooting, specs: dict[str, RebarSpec]) -> bool:
    """Las barras de la viga larga (mallas, superiores, piel y estribos) están en el catálogo."""
    names = {footing.bottom.x.designation, footing.bottom.y.designation}
    names |= {item.designation for item in (footing.top, footing.skin, footing.stirrups) if item is not None}
    return names <= set(specs)


def validate_project(project: Project, bars: Sequence[RebarSpec]) -> Check:
    profile = PROFILES.get(project.profile)
    if profile is None:
        known = ", ".join(sorted(PROFILES))
        return check_from_errors(CHECK_NAME, [invalid_input(f"El perfil '{project.profile}' no existe; valores: {known}")])
    specs = {bar.designation: bar for bar in bars}
    errors = list(_profile_errors(project, profile))
    for member in project.members:
        for station in member.stations:
            errors.extend(_station_errors(member, station, specs))
    for footing in project.footings:
        errors.extend(_footing_errors(footing, specs))
    for combined in project.combined_footings:
        errors.extend(_combined_errors(combined, specs))
    return check_from_errors(CHECK_NAME, errors)
