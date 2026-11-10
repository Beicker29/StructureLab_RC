"""Verificaciones de una zapata aislada: geotécnica con los casos de servicio (V3C) y estructural con los mayorados (V3D)."""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.connection import connection_checks
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.service import combined_service_checks, service_checks
from structurelab_rc.domain.footing.shear import shear_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked, incomplete
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing, Soil

STRUCTURAL = "Zapata: verificacion estructural"
COMBINED_STRUCTURAL = "Zapata combinada: verificacion estructural"


def structural_checks(basis: Basis, footing: Footing, soil: Soil) -> list[Check]:
    """Casos mayorados: equilibrio con el suelo (D-054), flexión (V3D.1), cortante y punzonamiento (V3D.2), desarrollo,
    aplastamiento y pasadores (V3D.3)."""
    if not any(load.kind == "factored" for load in footing.loads):
        error = incomplete("La zapata no tiene casos mayorados", member=footing.id)
        return [Check(STRUCTURAL, Status.INCOMPLETE, (error,), member=footing.id)]
    cases, failures = factored_cases(footing, soil)
    profile, materials, bars = basis.profile, basis.materials, basis.bars
    return [*failures, *flexure_checks(basis, footing, cases),
            *shear_checks(profile, materials, footing, cases, bars), *connection_checks(basis, footing, cases)]


def combined_footing_checks(basis: Basis, footing: CombinedFooting, soil: Soil) -> list[Check]:
    """Zapata combinada (D-080): la revisión geotécnica con la resultante de las dos columnas; la verificación estructural
    (viga larga, franjas transversales, punzonamiento, desarrollo y pasadores) llega en V3J.2 y V3J.3: mientras tanto
    queda BLOCKED, para que la zapata nunca resulte PASS sin estar completa."""
    pending = blocked("La verificacion estructural de las zapatas combinadas no esta implementada todavia (D-080, V3J.2 y V3J.3)",
                      member=footing.id)
    return [*combined_service_checks(basis.profile, footing, soil),
            Check(COMBINED_STRUCTURAL, Status.BLOCKED, (pending,), member=footing.id)]


def footing_checks(basis: Basis, footing: Footing, soil: Soil) -> list[Check]:
    return [*service_checks(basis.profile, footing, soil), *structural_checks(basis, footing, soil)]
