"""Verificaciones de una zapata aislada: geotécnica con los casos de servicio (V3C) y estructural con los mayorados (V3D)."""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.combined_beam import long_beam_checks
from structurelab_rc.domain.footing.combined_columns import column_checks
from structurelab_rc.domain.footing.connection import connection_checks
from structurelab_rc.domain.footing.declared import declared_checks
from structurelab_rc.domain.footing.flexure import flexure_checks
from structurelab_rc.domain.footing.inverted_t import inverted_t_checks
from structurelab_rc.domain.footing.loads import combined_factored_cases, equilibrium_checks, factored_cases
from structurelab_rc.domain.footing.service import combined_service_checks, service_checks
from structurelab_rc.domain.footing.shear import shear_checks
from structurelab_rc.domain.footing.spacing import combined_min_spacing_checks, footing_min_spacing_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
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
    cases, _ = factored_cases(footing, soil)
    return [*equilibrium_checks(footing, soil), *flexure_checks(basis, footing, cases), *footing_min_spacing_checks(basis, footing),
            *shear_checks(basis, footing, cases), *connection_checks(basis, footing, cases)]


def combined_footing_checks(basis: Basis, footing: CombinedFooting, soil: Soil) -> list[Check]:
    """Zapata combinada (D-080): la revisión geotécnica con la resultante de las dos columnas y, con los casos mayorados,
    el equilibrio, la viga en la dirección principal (V3J.2, D-081) y, por columna, el punzonamiento, la franja de la
    dirección secundaria, el desarrollo, el aplastamiento y los pasadores (V3J.3, D-082). Se calcula en ejes de la viga
    y se devuelve en los ejes declarados (D-101)."""
    service = combined_service_checks(basis.profile, footing, soil)
    if not any(loads[0].kind == "factored" for loads in footing.cases()):
        error = incomplete("La zapata combinada no tiene casos mayorados", member=footing.id)
        return declared_checks(footing, [*service, Check(COMBINED_STRUCTURAL, Status.INCOMPLETE, (error,), member=footing.id)])
    cases, _ = combined_factored_cases(footing, soil)
    # La T invertida no tiene punzonamiento ni franjas: sus aletas y columnas se revisan aparte (D-093).
    own = inverted_t_checks if footing.beam is not None else column_checks
    return declared_checks(footing, [*service, *equilibrium_checks(footing, soil), *long_beam_checks(basis, footing, soil, cases),
                                     *own(basis, footing, soil, cases), *combined_min_spacing_checks(basis, footing)])


def footing_checks(basis: Basis, footing: Footing, soil: Soil) -> list[Check]:
    return [*service_checks(basis.profile, footing, soil), *structural_checks(basis, footing, soil)]
