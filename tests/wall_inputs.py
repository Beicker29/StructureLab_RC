"""Entradas de prueba del muro de contención en voladizo (D-173): el ejemplo 2 del manual ACI MNL-17(21), capítulo 12,
pasado a SI (relleno de 110 pcf y 35°, μ = 0.5, qa = 3000 psf; pantalla de 15 in y 16 ft, base de 24 in, puntera de
2 ft 6 in y talón de 5 ft 6 in)."""

from typing import Any

CONCRETE_WEIGHT = 23.56  # kN/m³ (150 pcf), en concrete.unit_weight_kNm3 (D-139)


def soil(**change: Any) -> dict[str, Any]:
    """El bloque retaining_soil del JSON de entrada (sin el peso del concreto, que va en concrete)."""
    return {"unit_weight_backfill": 17.28, "friction_angle": 35.0, "friction_coefficient": 0.5, "allowable_pressure_kPa": 143.6,
            "min_contact_fraction": 1.0, "sliding_safety_factor": 1.5, "overturning_safety_factor": 2.0, **change}


def internal_soil(**change: Any) -> dict[str, Any]:
    """El suelo como lo recibe RetainingSoil: con el peso del concreto que internal() le pasa desde concrete."""
    return {"unit_weight_concrete_kNm3": CONCRETE_WEIGHT, **soil(**change)}


def bars(designation: str, spacing: float, end: str = "straight") -> dict[str, Any]:
    return {"designation": designation, "spacing": spacing, "end": end}


def wall(**change: Any) -> dict[str, Any]:
    return {"id": "M1", "quantity": 1, "stem_height": 4877.0, "stem_thickness": 381.0, "toe": 762.0, "heel": 1676.0,
            "base_thickness": 610.0, "backfill_height": 4877.0, "stem_cover": 50.0, "base_cover": 75.0,
            "earth_pressure": {"state": "active", "method": "rankine"},
            "stem": {"back": bars("#7", 225.0, "hook90"), "front": bars("#5", 450.0), "horizontal": bars("#5", 450.0)},
            "base": {"top": bars("#7", 110.0), "bottom": bars("#7", 225.0), "longitudinal": bars("#7", 200.0)},
            "cases": [{"case": "D+H", "kind": "service", "dead_factor": 1.0, "fill_factor": 1.0, "earth_factor": 1.0},
                      {"case": "1.2D+1.6H", "kind": "factored", "dead_factor": 1.2, "fill_factor": 1.6, "earth_factor": 1.6}],
            **change}


def project(**change: Any) -> dict[str, Any]:
    return {"description": "prueba", "profile": "aci-318-25", "seismic": {"level": "none", "justification": "prueba"},
            "concrete": {"fc": 31.0, "type": "normalweight", "unit_weight_kNm3": CONCRETE_WEIGHT},
            "reinforcement_steel": {"fy": 420.0, "fyt": 420.0, "coating": "uncoated"},
            "retaining_soil": soil(), "retaining_walls": [wall()], **change}
