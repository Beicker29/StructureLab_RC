"""Verificaciones de una zapata aislada. La v3 las incorpora por subfases (V3C geotécnica, V3D estructural)."""

from dataclasses import replace

from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.errors import blocked
from structurelab_rc.model.footing import Footing

PENDING = "Zapata: verificaciones"


def footing_checks(footing: Footing) -> list[Check]:
    """Mientras V3C y V3D no existan, la zapata queda BLOCKED; nunca PASS sin verificar."""
    error = blocked("Las verificaciones de zapatas aun no estan implementadas (V3C y V3D)", member=footing.id)
    return [replace(check_from_errors(PENDING, [error]), member=footing.id)]
