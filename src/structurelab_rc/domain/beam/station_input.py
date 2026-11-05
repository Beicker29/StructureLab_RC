"""Datos de una estación de viga que comparten las verificaciones de cortante y torsión."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station


@dataclass(frozen=True)
class StationInput:
    profile: Profile
    materials: Materials
    member: Member
    station: Station
    bars: Sequence[RebarSpec]
