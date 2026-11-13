"""Deriva el oráculo de los criterios de vigas de gran altura (D-089) para los dos perfiles.

No importa el paquete. Unidades de trabajo: N y mm. Para una estación de una viga declarada alta:

1. d del cortante: centroide de las capas de flexión a tracción por compatibilidad de deformaciones (bloque de Whitney,
   como derive_combined_beam.py), no menor que 0.8h.
2. Límite de sección: Vu ≤ 0.75·0.83·√f'c·bw·d (ACI 9.9.2.1; NSR-10 C.11.7.3 con √f'c ≤ 8.3 MPa).
3. Refuerzo distribuido transversal: ramas·Ab/s ≥ 0.0025·bw (ACI 9.9.3.1(a); NSR-10 C.11.7.4.1); sin estribos no cumple.
4. Refuerzo distribuido longitudinal: cada capa intermedia (todas las capas menos la superior y la inferior) frente a
   0.0025·bw por su altura tributaria, la mitad de los saltos a sus vecinas; gobierna la de menor razón; sin capas
   intermedias no cumple (ACI 9.9.3.1(b); NSR-10 C.11.7.4.2).
5. Separación: el mayor entre la separación de los estribos y el mayor salto vertical entre capas, frente a la menor
   entre d/5 y 300 mm (ACI 9.9.4.3; NSR-10 C.11.7.4.1 y C.11.7.4.2).
6. Cortinas (solo ACI 9.9.4.4, con bw > 200 mm): separación de las ramas a lo ancho, (bw − 2·recubrimiento − ds)/(ramas
   − 1), frente a 600 mm.

Uso: python tests/oracles/derive_deep_beam.py
"""

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).parent


def _load_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_B = _load_module("derive_combined_beam")
FC = _B.FC
BARS = {**_B.BARS, "#3": (9.5, 71.0)}  # diámetro y área (mm, mm²)
PHI = 0.75


def _area(layer: dict) -> float:
    return sum(BARS[name][1] for name in layer["bars"])


def _d(member: dict, mu: float) -> float:
    h, bw = member["section"]["h"], member["section"]["bw"]
    layers = member["stations"][0]["layout"]["layers"]
    flexural = [(layer["depth"] if mu >= 0 else h - layer["depth"], _area(layer)) for layer in layers if layer["role"] == "flexure"]
    state = _B._state(flexural, bw, h)
    assert state is not None
    pulled = [(depth, area) for (depth, area), strain in zip(flexural, state["strains"], strict=True) if strain > 0]
    total = sum(area for _, area in pulled)
    centroid = sum(depth * area for depth, area in pulled) / total
    return max(centroid, 0.8 * h)


def _expected(folder: str, member: dict) -> list[dict]:
    if not member.get("deep_beam"):
        return []
    station = member["stations"][0]
    section, layout, demands = member["section"], station["layout"], station["demands"]
    bw, cover = section["bw"], section["cover"]
    clauses = {"aci_318_25": {"section": "9.9.2.1", "transverse": "9.9.3.1(a)", "longitudinal": "9.9.3.1(b)",
                              "spacing": "9.9.4.3", "curtains": "9.9.4.4"},
               "nsr_10": {"section": "C.11.7.3", "transverse": "C.11.7.4.1", "longitudinal": "C.11.7.4.2",
                          "spacing": "C.11.7.4.1 y C.11.7.4.2"}}[folder]
    d = _d(member, demands["Mu_kNm"])
    root = math.sqrt(FC) if folder == "aci_318_25" else min(math.sqrt(FC), 8.3)
    limit = PHI * 0.83 * root * bw * d
    vu = abs(demands["Vu_kN"]) * 1e3
    checks = [{"name": "Viga alta: limite de seccion", "status": "PASS" if vu <= limit else "FAIL", "demand": vu, "capacity": limit,
               "clause": clauses["section"]}]
    stirrups = layout["stirrups"]
    if stirrups is None:
        checks.append({"name": "Viga alta: refuerzo distribuido transversal", "status": "FAIL"})
    else:
        provided = stirrups["legs"] * BARS[stirrups["designation"]][1] / stirrups["spacing"]
        checks.append({"name": "Viga alta: refuerzo distribuido transversal", "status": "PASS" if provided >= 0.0025 * bw else "FAIL",
                       "demand": 0.0025 * bw, "capacity": provided, "clause": clauses["transverse"]})
    layers = sorted((layer["depth"], _area(layer)) for layer in layout["layers"])
    gaps = [b[0] - a[0] for a, b in zip(layers, layers[1:], strict=False)]
    inner = layers[1:-1]
    if not inner:
        checks.append({"name": "Viga alta: refuerzo distribuido longitudinal", "status": "FAIL"})
    else:
        options = [(area / (0.0025 * bw * (gaps[i - 1] + gaps[i]) / 2), 0.0025 * bw * (gaps[i - 1] + gaps[i]) / 2, area)
                   for i, (_, area) in enumerate(inner, start=1)]
        _, required, area = min(options)
        checks.append({"name": "Viga alta: refuerzo distribuido longitudinal", "status": "PASS" if area >= required else "FAIL",
                       "demand": required, "capacity": area, "clause": clauses["longitudinal"]})
    spacing = max(stirrups["spacing"] if stirrups else 0.0, max(gaps))
    maximum = min(d / 5, 300.0)
    checks.append({"name": "Viga alta: separacion del refuerzo distribuido", "status": "PASS" if spacing <= maximum else "FAIL",
                   "demand": spacing, "capacity": maximum, "clause": clauses["spacing"]})
    if folder == "aci_318_25" and bw > 200.0:
        if stirrups is None:
            checks.append({"name": "Viga alta: cortinas", "status": "FAIL"})
        else:
            across = (bw - 2 * cover - BARS[stirrups["designation"]][0]) / (stirrups["legs"] - 1)
            checks.append({"name": "Viga alta: cortinas", "status": "PASS" if across <= 600.0 else "FAIL", "demand": across,
                           "capacity": 600.0, "clause": clauses["curtains"]})
    return checks


STIRRUPS = {"designation": "#4", "legs": 2, "spacing": 200.0, "closed": True}


def _member(case: str, *, bw: float = 400.0, vu: float = 900.0, skin: str | None = "#4", stirrups: dict | None = None,
            deep: bool = True) -> dict:
    layers = [{"depth": 60.0, "role": "flexure", "bars": ["#6", "#6"]}]
    if skin is not None:
        layers += [{"depth": depth, "role": "skin", "bars": [skin, skin]} for depth in (180.0, 430.0, 680.0, 930.0, 1180.0)]
    layers.append({"depth": 1433.0, "role": "flexure", "bars": ["#8"] * 6})
    member = {"id": case, "type": "beam", "min_steel_exception": True, "length": 4000.0, "section": {"bw": bw, "h": 1500.0, "cover": 40.0},
              "stations": [{"z": 0.0, "layout": {"layers": layers, "stirrups": stirrups or STIRRUPS},
                            "demands": {"Pu_kN": 0.0, "Mu_kNm": 1500.0, "M2_kNm": 0.0, "Vu_kN": vu, "V3_kN": 0.0, "Tu_kNm": 0.0}}]}
    if deep:
        member["deep_beam"] = True
    return member


CASES = [
    ("cumple", "viga de transferencia de 400 × 1500 mm con estribos #4 c/200 y piel 2#4 cada 250 mm: cumple todo",
     _member("cumple")),
    ("limite-seccion", "Vu mayor que φ0.83√f'c·bw·d", _member("limite-seccion", vu=2000.0)),
    ("distribuido-escaso", "piel 2#3 y estribos c/300 mm: no cumplen el refuerzo distribuido ni su separación",
     _member("distribuido-escaso", skin="#3", stirrups={"designation": "#4", "legs": 2, "spacing": 300.0, "closed": True})),
    ("cortinas", "bw = 900 mm con estribos de dos ramas: cortinas a más de 600 mm (ACI)", _member("cortinas", bw=900.0, vu=1500.0)),
    ("sin-intermedias", "sin capas intermedias: no hay refuerzo distribuido longitudinal", _member("sin-intermedias", skin=None)),
    ("no-declarada", "la misma viga sin deep_beam: no hay verificaciones de viga alta", _member("no-declarada", deep=False)),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        cases = [{"id": case_id, "description": text, "member": member, "expected": _expected(folder, member)}
                 for case_id, text, member in CASES]
        data = {"description": "Criterios de vigas de gran altura (D-089): límite de sección, refuerzo distribuido, su "
                               "separación y cortinas.",
                "materials": {"fc": FC, "fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
                "tolerance_rel": 1e-7, "cases": cases}
        (HERE / folder / "derived_deep_beam.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
