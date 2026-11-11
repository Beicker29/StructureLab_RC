"""Datos de una estación de viga que comparten las verificaciones de cortante y torsión."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials, Member, Station


@dataclass(frozen=True)
class StationInput:
    """foundation: la viga es la dirección larga de una zapata combinada (D-081): Vc y Av,min de cimentación.
    side_faces: la sección tiene caras laterales libres, donde va el refuerzo superficial; las franjas transversales de la
    zapata combinada no las tienen (D-083)."""

    profile: Profile
    materials: Materials
    member: Member
    station: Station
    bars: Sequence[RebarSpec]
    foundation: bool = False
    side_faces: bool = True
