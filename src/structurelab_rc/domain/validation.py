"""Validación de un proyecto contra su perfil normativo y el catálogo."""

from collections.abc import Iterator, Sequence

from structurelab_rc.codes.registry import PROFILES, Profile
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


def _station_errors(member: Member, station: Station, designations: set[str]) -> Iterator[StructuredError]:
    where = {"member": member.id, "x": station.x}
    if station.x > member.length:
        yield invalid_input("La estacion esta fuera de la longitud del miembro", **where)
    for layer in station.layout.layers:
        if layer.designation not in designations:
            yield invalid_input(f"La barra '{layer.designation}' no esta en el catalogo", **where)
        if layer.depth >= member.section.h:
            yield invalid_input(f"La capa a {layer.depth} mm esta fuera de la seccion", **where)
    if not any(layer.role == "flexure" for layer in station.layout.layers):
        yield invalid_input("El armado no tiene capas de flexion", **where)
    stirrups = station.layout.stirrups
    if stirrups is not None and stirrups.designation not in designations:
        yield invalid_input(f"El estribo '{stirrups.designation}' no esta en el catalogo", **where)
    demands = station.demands
    for label, value in (("Pu", demands.pu), ("Mu", demands.mu), ("Vu", demands.vu), ("Tu", demands.tu)):
        if value is None:
            yield incomplete(f"Falta la demanda {label}", **where)


def validate_project(project: Project, bars: Sequence[RebarSpec]) -> Check:
    profile = PROFILES.get(project.profile)
    if profile is None:
        known = ", ".join(sorted(PROFILES))
        return check_from_errors(CHECK_NAME, [invalid_input(f"El perfil '{project.profile}' no existe; valores: {known}")])
    designations = {bar.designation for bar in bars}
    errors = list(_profile_errors(project, profile))
    for member in project.members:
        for station in member.stations:
            errors.extend(_station_errors(member, station, designations))
    return check_from_errors(CHECK_NAME, errors)
