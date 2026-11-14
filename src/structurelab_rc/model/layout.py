"""Bloques de materiales de los JSON de entrada (D-139): concrete, reinforcement_steel y soil.

    "concrete": {"fc": 28.0, "type": "normalweight", "max_aggregate": 19.0, "unit_weight_kNm3": 24.0}
    "reinforcement_steel": {"fy": 420.0, "fyt": 420.0, "coating": "uncoated"}
    "soil": {"unit_weight_fill_kNm3": 18.0, ...}

fc falta en los diseños (sale de fc_options); unit_weight_kNm3 solo con soil (zapatas y cabezales). Al cargar,
internal() los pasa a la estructura interna (materials y el peso del concreto en soil), con la que calcula el programa;
al escribir un proyecto (importado o diseñado), public() hace lo inverso. El bloque materials ya no se acepta.
"""

from typing import Any

_CONCRETE = {"fc": "fc", "type": "concrete", "max_aggregate": "max_aggregate"}
_STEEL = ("fy", "fyt", "coating")
_UNIT_WEIGHT, _SOIL_UNIT_WEIGHT = "unit_weight_kNm3", "unit_weight_concrete_kNm3"


def internal(data: Any) -> Any:
    """Del formato de entrada (concrete, reinforcement_steel, soil) a la estructura interna (materials, soil)."""
    if not isinstance(data, dict):
        return data
    if "materials" in data:
        raise ValueError("el bloque materials se reemplazo por concrete y reinforcement_steel (D-139)")
    soil = data.get("soil")
    if isinstance(soil, dict) and _SOIL_UNIT_WEIGHT in soil:
        raise ValueError("el peso unitario del concreto va en concrete.unit_weight_kNm3, no en soil (D-139)")
    if "concrete" not in data and "reinforcement_steel" not in data:
        return data
    concrete, steel = data.get("concrete"), data.get("reinforcement_steel")
    if not isinstance(concrete, dict) or not isinstance(steel, dict):
        raise ValueError("concrete y reinforcement_steel son obligatorios y son objetos (D-139)")
    unknown = sorted({*concrete} - {*_CONCRETE, _UNIT_WEIGHT}) + sorted({*steel} - {*_STEEL})
    if unknown:
        raise ValueError(f"campos desconocidos en concrete o reinforcement_steel: {', '.join(unknown)}")
    materials = {_CONCRETE[key]: value for key, value in concrete.items() if key in _CONCRETE} | dict(steel)
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "concrete":
            out["materials"] = materials
        elif key != "reinforcement_steel":
            out[key] = value
    if _UNIT_WEIGHT in concrete:
        if not isinstance(soil, dict):
            raise ValueError("concrete.unit_weight_kNm3 solo se declara con soil (zapatas y cabezales)")
        out["soil"] = {_SOIL_UNIT_WEIGHT: concrete[_UNIT_WEIGHT], **soil}
    return out


def public(data: dict[str, Any]) -> dict[str, Any]:
    """De la estructura interna al formato de entrada, en el lugar de materials."""
    materials = data.get("materials")
    if not isinstance(materials, dict):
        return data
    soil = data.get("soil")
    concrete = {key: materials[name] for key, name in _CONCRETE.items() if name in materials}
    if isinstance(soil, dict) and _SOIL_UNIT_WEIGHT in soil:
        concrete[_UNIT_WEIGHT] = soil[_SOIL_UNIT_WEIGHT]
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "materials":
            out["concrete"] = concrete
            out["reinforcement_steel"] = {key: materials[key] for key in _STEEL if key in materials}
        elif key == "soil" and isinstance(value, dict):
            out["soil"] = {name: item for name, item in value.items() if name != _SOIL_UNIT_WEIGHT}
        else:
            out[key] = value
    return out
