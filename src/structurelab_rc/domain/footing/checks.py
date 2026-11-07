"""Verificaciones de una zapata aislada: geotécnica con los casos de servicio (V3C); la estructural llega en V3D."""

from dataclasses import replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.errors import blocked
from structurelab_rc.model.footing import Footing, Soil

STRUCTURAL = "Zapata: verificacion estructural"


def footing_checks(profile: Profile, footing: Footing, soil: Soil) -> list[Check]:
    """Mientras V3D no exista, la parte estructural queda BLOCKED; la zapata nunca pasa sin verificar."""
    error = blocked("La verificacion estructural de zapatas aun no esta implementada (V3D)", member=footing.id)
    return [*service_checks(profile, footing, soil), replace(check_from_errors(STRUCTURAL, [error]), member=footing.id)]
