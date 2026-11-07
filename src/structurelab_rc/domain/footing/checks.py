"""Verificaciones de una zapata aislada: geotécnica con los casos de servicio (V3C) y estructural con los mayorados (V3D)."""

from collections.abc import Sequence

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.connection import connection_checks
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.domain.footing.shear import shear_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials

STRUCTURAL = "Zapata: verificacion estructural"


def structural_checks(profile: Profile, materials: Materials, footing: Footing, soil: Soil, bars: Sequence[RebarSpec]) -> list[Check]:
    """Casos mayorados: equilibrio con el suelo (D-054), flexión (V3D.1), cortante y punzonamiento (V3D.2), desarrollo,
    aplastamiento y pasadores (V3D.3)."""
    if not any(load.kind == "factored" for load in footing.loads):
        error = incomplete("La zapata no tiene casos mayorados", member=footing.id)
        return [Check(STRUCTURAL, Status.INCOMPLETE, (error,), member=footing.id)]
    cases, failures = factored_cases(footing, soil)
    return [*failures, *flexure_checks(profile, materials, footing, cases, bars),
            *shear_checks(profile, materials, footing, cases, bars), *connection_checks(profile, materials, footing, cases, bars)]


def footing_checks(profile: Profile, materials: Materials, footing: Footing, soil: Soil, bars: Sequence[RebarSpec]) -> list[Check]:
    return [*service_checks(profile, footing, soil), *structural_checks(profile, materials, footing, soil, bars)]
