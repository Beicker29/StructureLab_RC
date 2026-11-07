"""Verificaciones de una zapata aislada: geotécnica con los casos de servicio (V3C) y estructural con los mayorados (V3D)."""

from collections.abc import Sequence
from dataclasses import replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.domain.footing.shear import shear_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked, incomplete
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials

PENDING = "Zapata: verificaciones pendientes"
STRUCTURAL = "Zapata: verificacion estructural"


def structural_checks(profile: Profile, materials: Materials, footing: Footing, soil: Soil, bars: Sequence[RebarSpec]) -> list[Check]:
    """Casos mayorados: equilibrio con el suelo (D-054), flexión (V3D.1), cortante y punzonamiento (V3D.2)."""
    if not any(load.kind == "factored" for load in footing.loads):
        error = incomplete("La zapata no tiene casos mayorados", member=footing.id)
        return [Check(STRUCTURAL, Status.INCOMPLETE, (error,), member=footing.id)]
    cases, failures = factored_cases(footing, soil)
    return [*failures, *flexure_checks(profile, materials, footing, cases, bars),
            *shear_checks(profile, materials, footing, cases, bars)]


def footing_checks(profile: Profile, materials: Materials, footing: Footing, soil: Soil, bars: Sequence[RebarSpec]) -> list[Check]:
    """Mientras falten partes de V3D, quedan BLOCKED; la zapata nunca pasa sin verificar."""
    error = blocked("Desarrollo del refuerzo, aplastamiento y pasadores aun no estan implementados (V3D.3)", member=footing.id)
    return [
        *service_checks(profile, footing, soil),
        *structural_checks(profile, materials, footing, soil, bars),
        replace(check_from_errors(PENDING, [error]), member=footing.id),
    ]
