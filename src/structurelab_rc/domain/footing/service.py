"""Verificación geotécnica con los casos de servicio (V3C; D-052, puntos 2, 3 y 5).

La presión bajo la zapata rígida sigue a Bellos y Bakas (2017) con la resultante de la columna, los pesos propios y las
sobrecargas, con los factores de la combinación de servicio (D-057). Se compara la presión máxima con la admisible y
la fracción de la base en contacto con el mínimo que declara el usuario, y se revisan el deslizamiento y el volcamiento
(D-070, `stability`); sin equilibrio (resultante fuera de la base o sin compresión) el caso es FAIL.
"""

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.base import BaseResultant, base_resultant, combined_resultant
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING, overturning_check, sliding_check
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete, invalid_input
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import footing_pressure
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import Footing, FootingBase, FootingLoad, Soil

BEARING = "Presion admisible del suelo"
CONTACT = "Contacto con el suelo"
CONTACT_CLAUSE = "D-052 (minimo declarado por el usuario)"
_REGIONS = {"A": "triangular", "B": "pentagonal", "C": "total", "D": "trapezoidal en x", "E": "trapezoidal en y"}


def _case_checks(profile: Profile, footing: FootingBase, soil: Soil, load: FootingLoad, resultant: BaseResultant) -> list[Check]:
    """Un caso de servicio con su resultante en la base; load da el nombre del caso, la marca de sismo y la fuerza
    horizontal total."""
    values: tuple[tuple[str, float], ...] = (("N", resultant.n), ("Mx base", resultant.mx), ("My base", resultant.my))
    bearing_clause = profile.footing.clauses()["bearing"]
    stability_clause = profile.footing.clauses()["stability"]
    ex, ey = resultant.ex, resultant.ey
    try:
        if ex is None or ey is None:
            raise NoEquilibrium("la carga de servicio sobre el suelo no es de compresion")
        pressure = footing_pressure(footing.lx, footing.ly, resultant.n, ex, ey)
    except NoEquilibrium as error:
        failure = invalid_input(f"Sin equilibrio con el suelo: {error}", member=footing.id, case=load.case)
        return [
            Check(BEARING, Status.FAIL, (failure,), bearing_clause, values=values, member=footing.id, case=load.case),
            Check(CONTACT, Status.FAIL, (failure,), CONTACT_CLAUSE, values=values, member=footing.id, case=load.case),
            Check(SLIDING, Status.FAIL, (failure,), stability_clause, values=values, member=footing.id, case=load.case),
            Check(OVERTURNING, Status.FAIL, (failure,), stability_clause, values=values, member=footing.id, case=load.case),
        ]
    values += (("ex", ex), ("ey", ey))
    fraction = pressure.contact_fraction()
    capacity = soil.bearing_capacity(load.seismic)
    bearing_ok = pressure.pmax <= capacity
    contact_ok = fraction >= soil.min_contact_fraction
    region = f"Region {pressure.region} de Bellos y Bakas (2017): contacto {_REGIONS[pressure.region]}"
    corners = tuple((f"p esquina {name}", value) for name, value in zip(("-x-y", "+x-y", "+x+y", "-x+y"), pressure.corners(),
                                                                         strict=True))
    bearing_values = (*values, *corners)  # presión en cada esquina, para la planta de la memoria (D-080)
    bearing_note = region
    if load.seismic and soil.seismic_bearing_factor != 1.0:
        bearing_values = (*bearing_values, ("qa", soil.allowable_pressure), ("factor sismo qa", soil.seismic_bearing_factor))
        bearing_note = f"{region}; combinacion con sismo: qa x {soil.seismic_bearing_factor:g} (D-079)"
    return [
        Check(BEARING, Status.PASS if bearing_ok else Status.FAIL, clause=bearing_clause, demand=pressure.pmax,
              capacity=capacity, unit="N/mm2", values=bearing_values, note=bearing_note, member=footing.id, case=load.case),
        # La razón es el mínimo exigido sobre la fracción en contacto: cumple con razón ≤ 1.
        Check(CONTACT, Status.PASS if contact_ok else Status.FAIL, clause=CONTACT_CLAUSE, demand=soil.min_contact_fraction,
              capacity=fraction, values=(*values, ("contacto", fraction)), note=region, member=footing.id, case=load.case),
        sliding_check(stability_clause, footing, soil, load, (resultant, fraction)),
        overturning_check(stability_clause, footing, soil, load, resultant),
    ]


def service_checks(profile: Profile, footing: Footing, soil: Soil) -> list[Check]:
    loads = [load for load in footing.loads if load.kind == "service"]
    if not loads:
        error = incomplete("La zapata no tiene casos de servicio", member=footing.id)
        return [Check(BEARING, Status.INCOMPLETE, (error,), profile.footing.clauses()["bearing"], member=footing.id)]
    return [check for load in loads for check in _case_checks(profile, footing, soil, load, base_resultant(footing, soil, load))]


def combined_service_checks(profile: Profile, footing: CombinedFooting, soil: Soil) -> list[Check]:
    """La misma revisión geotécnica para una zapata combinada (D-080), con la resultante de las dos columnas; la fuerza
    horizontal del deslizamiento es la suma de las dos."""
    cases = [loads for loads in footing.cases() if loads[0].kind == "service"]
    if not cases:
        error = incomplete("La zapata combinada no tiene casos de servicio", member=footing.id)
        return [Check(BEARING, Status.INCOMPLETE, (error,), profile.footing.clauses()["bearing"], member=footing.id)]
    checks = []
    for loads in cases:
        first = loads[0]
        total = FootingLoad.model_construct(case=first.case, kind=first.kind, dead_factor=first.dead_factor,
                                            live_factor=first.live_factor, seismic=first.seismic,
                                            p=sum(load.p for load in loads), vx=sum(load.vx for load in loads),
                                            vy=sum(load.vy for load in loads), mx=sum(load.mx for load in loads),
                                            my=sum(load.my for load in loads))
        checks += _case_checks(profile, footing, soil, total, combined_resultant(footing, soil, loads))
    return checks
