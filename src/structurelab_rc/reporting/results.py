"""Resultado de la verificación en unidades de presentación (kN, kN·m, mm, MPa), redondeado a 6 cifras (D-050, D-068).

Trae todo lo que la memoria imprime: propiedades de los materiales que usa el perfil, solicitaciones y armado de cada
estación, casos de carga de cada zapata y las verificaciones; la memoria no calcula nada.
"""

import math
from typing import Any

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import MPA_PER_KPA, N_MM3_PER_KN_M3, Footing, FootingLoad, RectangularBase, Soil
from structurelab_rc.model.project import Demands, Project
from structurelab_rc.reporting.units import kN, kNm, kPa

_DIGITS = 6
# Unidad interna → (unidad de presentación, conversión).
_UNITS = {"N*mm": ("kN-m", kNm), "N": ("kN", kN), "N/mm2": ("kPa", kPa)}
# Valores de una verificación con unidad: nombre → unidad interna.
_VALUE_UNITS = {"Mn3": "N*mm", "Mn2": "N*mm", "Mn": "N*mm", "Tu": "N*mm", "phi Tth": "N*mm", "Vc": "N", "Vs": "N",
                "c": "mm", "d": "mm", "theta": "deg", "Aoh": "mm2", "ph": "mm", "across": "mm", "across_max": "mm",
                "N": "N", "Mx base": "N*mm", "My base": "N*mm", "ex": "mm", "ey": "mm", "As": "mm2", "Vu": "N",
                "b0": "mm", "vuv": "MPa", "bslab": "mm", "A1": "mm2", "A2": "mm2", "Av/s": "mm2/mm", "At/s": "mm2/mm",
                "At/s rama exterior": "mm2/mm", "mu N": "N", "ca Ac": "N", "Pp x": "N", "Pp y": "N", "V": "N", "R": "N",
                "Mo": "N*mm", "Mr": "N*mm", "qa": "N/mm2", "p esquina -x-y": "N/mm2", "p esquina +x-y": "N/mm2",
                "p esquina +x+y": "N/mm2", "p esquina -x+y": "N/mm2", "h calculo": "mm", "Sm": "mm3", "Msc x": "N*mm",
                "Msc y": "N*mm", "Jc x": "mm4", "Jc y": "mm4", "xc": "mm", "yc": "mm", "cc": "mm", "As,min": "mm2",
                "As analisis": "mm2", "x": "mm", "Msc": "N*mm", "gamma f Msc": "N*mm", "As bslab": "mm2",
                "para la viga": "N*mm"}
# Valores con número: "esquina 3 v" (esfuerzo de punzonamiento en la esquina 3) y sus coordenadas (D-083).
_CORNER_UNITS = {"x": "mm", "y": "mm", "v": "MPa"}


def significant(value: float) -> float:
    """Redondeo de presentación a 6 cifras significativas; el cálculo interno no se redondea."""
    if value == 0 or not math.isfinite(value):
        return value
    return float(f"{value:.{_DIGITS}g}")


def _present(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    convert = _UNITS.get(unit, (unit, lambda number: number))[1]
    return significant(convert(value))


def _unit(unit: str) -> str:
    return _UNITS.get(unit, (unit, None))[0] or "-"


def _value_key(name: str) -> tuple[str, str]:
    unit = _VALUE_UNITS.get(name, "")
    if name.startswith("esquina "):
        unit = _CORNER_UNITS.get(name.rsplit(" ", 1)[-1], "")
    shown = _unit(unit) if unit else ""
    return (f"{name} [{shown}]" if shown else name), unit


def check_ratio(check: Check) -> float | None:
    """Razón demanda/capacidad; las verificaciones se cumplen con razón ≤ 1 (en εt, εt mínima sobre εt)."""
    if check.demand is None or not check.capacity:
        return None
    return check.demand / check.capacity


def check_data(check: Check) -> dict[str, Any]:
    values = {}
    for name, value in check.values:
        key, unit = _value_key(name)
        values[key] = _present(value, unit)
    ratio = check_ratio(check)
    return {
        "name": check.name,
        "status": str(check.status),
        "clause": check.clause,
        "unit": _unit(check.unit),
        "demand": _present(check.demand, check.unit),
        "capacity": _present(check.capacity, check.unit),
        "ratio": None if ratio is None else significant(ratio),
        "values": values,
        "note": check.note,
        "errors": [{"code": str(error.code), "message": error.message, "details": dict(error.details)} for error in check.errors],
    }


_MM2_PER_M2 = 1e6
_MM3_PER_M3 = 1e9
_MM4_PER_M4 = 1e12


def _base_properties(footing: RectangularBase, soil: Soil) -> dict[str, float]:
    """Propiedades derivadas de las dimensiones de la base (nunca declaradas), comunes a la zapata aislada y la combinada."""
    footing_weight, pedestal_weight, fill_weight = footing.weights(soil)
    dead_surcharge, live_surcharge = footing.surcharges()
    kern_x, kern_y = footing.kern
    properties = {
        "A [m2]": footing.area / _MM2_PER_M2,
        "Ix [m4]": footing.inertia_x / _MM4_PER_M4,
        "Iy [m4]": footing.inertia_y / _MM4_PER_M4,
        "Sx [m3]": footing.modulus_x / _MM3_PER_M3,
        "Sy [m3]": footing.modulus_y / _MM3_PER_M3,
        "nucleo lx/6 [mm]": kern_x,
        "nucleo ly/6 [mm]": kern_y,
        "W zapata [kN]": kN(footing_weight),
        "W pedestal [kN]": kN(pedestal_weight),
        "W relleno [kN]": kN(fill_weight),
        "Sobrecarga muerta [kN]": kN(dead_surcharge),
        "Sobrecarga viva [kN]": kN(live_surcharge),
    }
    return {key: significant(value) for key, value in properties.items()}


def _geometry(footing: Footing | CombinedFooting, include: set[str]) -> dict[str, Any]:
    geometry = footing.model_dump(mode="json", include={"lx", "ly", "h", "cover", "fill_height", "pedestal_height", *include})
    geometry["surcharge_dead [kN/m2]"] = significant(footing.surcharge_dead / MPA_PER_KPA)
    geometry["surcharge_live [kN/m2]"] = significant(footing.surcharge_live / MPA_PER_KPA)
    return geometry


def footing_data(footing: Footing, soil: Soil, checks: list[Check]) -> dict[str, Any]:
    """Zapata con sus propiedades derivadas de las dimensiones (nunca declaradas) y sus verificaciones."""
    return {
        "id": footing.id,
        "geometry [mm]": _geometry(footing, {"column"}),
        "properties": _base_properties(footing, soil),
        "reinforcement": {"bottom": footing.bottom.model_dump(mode="json"),
                          "top": None if footing.top is None else footing.top.model_dump(mode="json")},
        "loads": [_load_data(load) for load in footing.loads],
        "status": _status(checks),
        # En las zapatas cada verificación lleva su caso de carga (None si vale para toda la zapata).
        "checks": [{**check_data(check), "case": check.case} for check in checks],
        "foundation_beam_moments": beam_moments(checks),
    }


def combined_footing_data(footing: CombinedFooting, soil: Soil, checks: list[Check]) -> dict[str, Any]:
    """Zapata combinada (D-080): geometría, columnas con sus cargas, propiedades derivadas, armado y verificaciones con su
    caso, su posición z (viga larga o franja) y su nota (la sección o la columna)."""
    columns = [{**column.model_dump(mode="json", exclude={"loads"}), "loads": [_load_data(load) for load in column.loads]}
               for column in footing.columns]
    return {
        "id": footing.id,
        "geometry [mm]": _geometry(footing, set()),
        "columns": columns,
        "properties": _base_properties(footing, soil),
        "reinforcement": footing.model_dump(mode="json", include={"bottom", "top", "stirrups", "skin", "torsion_layers"}),
        "status": _status(checks),
        "checks": [{**check_data(check), "case": check.case, "z [mm]": None if check.z is None else significant(check.z)}
                   for check in checks],
        "foundation_beam_moments": beam_moments(checks),
    }


NEGATIVE_TRANSFER = "Transferencia de momento: parte negativa"


def beam_moments(checks: list[Check]) -> list[dict[str, Any]]:
    """Momentos γf·Msc que debe tomar la viga de cimentación (D-087): la parte negativa del momento transferido que la
    zapata no resiste. Por caso, columna (o grupo) y dirección de la viga (la de las barras que lo transmitirían)."""
    out = []
    for check in checks:
        if not check.name.startswith(NEGATIVE_TRANSFER):
            continue
        moment = dict(check.values).get("para la viga", 0.0)
        if moment > 0:
            column = check.note.split(":")[0] if check.note.startswith("Columna") else ""
            direction = check.name.rsplit(" ", 1)[-1].rstrip(")").upper()
            out.append({"case": check.case, "column": column, "beam_direction": direction,
                        "M [kN-m]": significant(kNm(moment))})
    return out


def _load_data(load: FootingLoad) -> dict[str, Any]:
    return {"case": load.case, "kind": load.kind, "dead_factor": load.dead_factor, "live_factor": load.live_factor,
            "seismic": load.seismic, "P [kN]": significant(kN(load.p)), "Vx [kN]": significant(kN(load.vx)),
            "Vy [kN]": significant(kN(load.vy)), "Mx [kN-m]": significant(kNm(load.mx)), "My [kN-m]": significant(kNm(load.my))}


def _demands_data(demands: Demands) -> dict[str, float | None]:
    pairs = (("Pu [kN]", demands.pu, kN), ("Mu [kN-m]", demands.mu, kNm), ("M2 [kN-m]", demands.m2, kNm),
             ("Vu [kN]", demands.vu, kN), ("V3 [kN]", demands.v3, kN), ("Tu [kN-m]", demands.tu, kNm))
    return {key: None if value is None else significant(convert(value)) for key, value, convert in pairs}


def _materials_used(project: Project) -> dict[str, Any]:
    """Valores del perfil que usa el cálculo (los mismos que domain toma de codes); la memoria solo los imprime."""
    profile = PROFILES.get(project.profile)
    if profile is None:
        return {}
    assumptions, materials = profile.strength_assumptions, project.materials
    es = assumptions.steel_modulus()
    return {"beta1": assumptions.beta1(materials.fc), "ecu": assumptions.max_concrete_strain(),
            "alpha1": assumptions.stress_block_factor(), "Es [MPa]": es,
            "ety": significant(profile.flexure.yield_strain(materials.fy, es)),
            "lambda": assumptions.concrete_lambda(materials.concrete)}


def _status(checks: list[Check]) -> str:
    return str(aggregate(check.status for check in checks)) if checks else str(Status.PASS)


def build_results(project: Project | None, checks: tuple[Check, ...], version: str) -> dict[str, Any]:
    """Resultado completo; si la entrada no cargó, solo la validación."""
    validation, station_checks = checks[0], checks[1:]
    results: dict[str, Any] = {
        "software": {"name": "structurelab-rc", "version": version},
        "status": _status(list(checks)),
        "validation": check_data(validation),
    }
    if project is None:
        return results
    results["project"] = {
        "description": project.description,
        "profile": project.profile,
        "seismic": {"level": project.seismic.level, "justification": project.seismic.justification},
        "materials": {"fc [MPa]": project.materials.fc, "fy [MPa]": project.materials.fy, "fyt [MPa]": project.materials.fyt,
                      "concrete": project.materials.concrete, "coating": project.materials.coating},
        "materials_used": _materials_used(project),
    }
    members = []
    for member in project.members:
        own = [check for check in station_checks if check.member == member.id]
        stations = []
        for station in member.stations:
            here = [check for check in own if check.z == station.z and check.case == station.case]
            data = [check_data(check) for check in here]
            stations.append({"z [mm]": station.z, "case": station.case, "status": _status(here),
                             "demands": _demands_data(station.demands), "layout": station.layout.model_dump(mode="json", by_alias=True),
                             "checks": data})
        members.append({
            "id": member.id,
            "type": member.type,
            "length [mm]": member.length,
            "section": member.section.model_dump(exclude_none=True),
            "status": _status(own),
            "stations": stations,
        })
    results["members"] = members
    if (project.footings or project.combined_footings) and project.soil is not None:
        soil = project.soil
        results["soil"] = {"qa [kPa]": significant(soil.allowable_pressure / MPA_PER_KPA),
                           "contacto minimo [-]": soil.min_contact_fraction,
                           "gamma concreto [kN/m3]": significant(soil.unit_weight_concrete / N_MM3_PER_KN_M3),
                           "gamma relleno [kN/m3]": significant(soil.unit_weight_fill / N_MM3_PER_KN_M3),
                           "mu [-]": soil.friction_coefficient, "ca [kPa]": significant(soil.adhesion / MPA_PER_KPA),
                           "Kp [-]": soil.passive_coefficient, "c [kPa]": significant(soil.cohesion / MPA_PER_KPA),
                           "fp [-]": soil.passive_factor, "FS deslizamiento [-]": soil.sliding_safety_factor,
                           "FS deslizamiento sismo [-]": soil.sliding_safety_factor_seismic,
                           "FS volcamiento [-]": soil.overturning_safety_factor,
                           "FS volcamiento sismo [-]": soil.overturning_safety_factor_seismic,
                           "factor sismo qa [-]": soil.seismic_bearing_factor}
        results["footings"] = [footing_data(footing, soil, [check for check in station_checks if check.member == footing.id])
                               for footing in project.footings]
        if project.combined_footings:
            results["combined_footings"] = [
                combined_footing_data(footing, soil, [check for check in station_checks if check.member == footing.id])
                for footing in project.combined_footings]
    return results
