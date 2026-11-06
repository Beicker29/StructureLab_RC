"""Validación de un proyecto contra su perfil normativo y el catálogo."""

from collections.abc import Iterator, Sequence

from structurelab_rc.codes.registry import PROFILES, Profile
from structurelab_rc.domain.beam.geometry import interior_limits
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.errors import StructuredError, incomplete, invalid_input
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Member, Project, Station

CHECK_NAME = "Validacion de entrada"


def _profile_errors(project: Project, profile: Profile) -> Iterator[StructuredError]:
    if project.seismic.level not in profile.seismic.seismic_levels():
        levels = ", ".join(sorted(profile.seismic.seismic_levels()))
        yield invalid_input(f"El nivel sismico '{project.seismic.level}' no existe en {profile.id}; valores: {levels}")
    if profile.strength_assumptions.beta1(project.materials.fc) is None:
        yield invalid_input(f"{profile.id} no define beta1 para fc = {project.materials.fc} MPa")


def _bar_errors(member: Member, station: Station, specs: dict[str, RebarSpec]) -> Iterator[StructuredError]:
    """Barras con posición explícita: dentro de las caras interiores del estribo y en orden de izquierda a derecha."""
    where = {"member": member.id, "x": station.x}
    for layer in station.layout.layers:
        positions = [bar for bar in layer.bars if not isinstance(bar, str)]
        for bar in positions:
            left, right = interior_limits(member.section, station.layout, specs, specs[bar.designation].diameter_mm)
            if not left - 1e-6 <= bar.z <= right + 1e-6:
                yield invalid_input(f"La barra {bar.designation} en z = {bar.z} mm queda fuera del estribo", **where)
        if any(second.z <= first.z for first, second in zip(positions, positions[1:], strict=False)):
            yield invalid_input(f"Las barras de la capa a {layer.depth} mm no estan en orden de izquierda a derecha", **where)


def _station_errors(member: Member, station: Station, specs: dict[str, RebarSpec]) -> Iterator[StructuredError]:
    where = {"member": member.id, "x": station.x}
    if station.x > member.length:
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
        yield from _bar_errors(member, station, specs)
    demands = station.demands
    for label, value in (("Pu", demands.pu), ("Mu", demands.mu), ("Vu", demands.vu), ("Tu", demands.tu)):
        if value is None:
            yield incomplete(f"Falta la demanda {label}", **where)


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
    return check_from_errors(CHECK_NAME, errors)
