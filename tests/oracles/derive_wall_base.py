"""Deriva el oráculo de la base del muro en voladizo (D-173, fase A, etapa 4) para los dos perfiles.

No importa el paquete; el empuje sin factores sale de derive_wall_stability.thrust (otro oráculo). Por metro de muro, en
kN, m y kPa para las cargas y en N y mm para las secciones:

1. Resultante del caso con sus factores (peso del concreto por dead_factor, suelo por fill_factor, empuje por
   earth_factor), x_r = (Mr − Mo)/N y e = x_r − B/2. Presión lineal: trapecio con |e| ≤ B/6; con B/6 < |e| < B/2,
   triángulo de largo 3·(B/2 − |e|) desde el borde más cargado. q(x) se integra en forma cerrada.
2. Talón (de la cara del relleno de la pantalla, x = puntera + pantalla, al extremo): cargas hacia abajo, su concreto, el
   suelo que cuenta como peso y Pv; menos la presión. V y M en la cara (positivo: tracción arriba).
3. Puntera: la presión menos su concreto; M en la cara exterior y V a d de ella (d de las barras inferiores).
4. Flexión con el bloque rectangular (como derive_wall_stem.py). Cortante sin refuerzo: ACI Vc = 0.17·√f'c·b·d (13.2.6.2(a));
   NSR-10 el mayor de 0.17·√f'c·b·d y (0.16·√f'c + 17·ρw·Vu·d/Mu)·b·d ≤ 0.29·√f'c·b·d. Límite de la sección
   φ(Vc + 0.66·√f'c·b·d).
5. Agrietamiento con fs de servicio: n = 200000/(4700·√f'c), k = √((ρn)² + 2ρn) − ρn, j = 1 − k/3, fs = Ms/(As·j·d), con Ms
   del caso de servicio en la cara; s ≤ min(380·280/fs − 2.5·cc, 300·280/fs).
6. Mínimo 0.0018·b·h, separación ≤ min(3h, 450); longitudinal 0.0018·h·B frente a dos caras de barras a lo ancho, separación
   ≤ min(5h, 450); altura sobre las barras inferiores ≥ 150 mm.
7. Desarrollo: barras de la pantalla con gancho de 90° en la base (disponible h − cc): ACI ℓdh = fy·ψcc/(4.2·√f'c)·db, NSR-10
   ℓdh = 0.24·fy·ψcc/√f'c·db, ψcc = 0.7 (recubrimientos ≥ 65 y 50 mm), ≥ 8db y 150 mm. Barras rectas superiores del talón e
   inferiores de la puntera (disponible: el lado más corto de la cara de la pantalla menos cc): ℓd = fy·ψt/(1.1·√f'c·
   min(cb/db, 2.5))·db (ψs = ψe = ψg = 1 con N.° 7), ψt = 1.3 con más de 300 mm de concreto debajo, ≥ 300 mm.

Uso: python tests/oracles/derive_wall_base.py
"""

import json
import math
from pathlib import Path

from derive_wall_stability import GAMMA_C, thrust  # type: ignore[import-not-found]  # el oráculo vecino, por su ruta

HERE = Path(__file__).parent
STRIP = 1000.0
ES = 200000.0
BARS = {"#4": (12.7, 129.0), "#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0)}  # diámetro (mm), área (mm²)
FC, FY = 31.03, 413.7
SECTION = {"aci_318_25": "22.5.1.2", "nsr_10": "C.11.4.7.9"}


def _beta1(fc: float) -> float:
    return max(0.65, min(0.85, 0.85 - 0.05 * (fc - 28.0) / 7.0))


def _pressure(wall: dict, soil: dict, case: dict) -> tuple[float, float]:
    """(q0, g) de la presión q(x) = max(q0 + g·x, 0) en kPa, x en m desde el borde de la puntera."""
    t, hs, toe, heel, hb = (wall[key] / 1e3 for key in ("stem_thickness", "stem_height", "toe", "heel", "base_thickness"))
    width = toe + t + heel
    height = hb + wall["backfill_height"] / 1e3
    ph, pv, x_p, soil_weight, soil_x = thrust(wall, soil)
    stem, base = GAMMA_C * t * hs * case["dead_factor"], GAMMA_C * width * hb * case["dead_factor"]
    fill, ph, pv = soil_weight * case["fill_factor"], ph * case["earth_factor"], pv * case["earth_factor"]
    n = stem + base + fill + pv
    mr = stem * (toe + t / 2) + base * width / 2 + fill * soil_x + pv * x_p
    e = (mr - ph * height / 3) / n - width / 2
    if abs(e) <= width / 6:
        q_toe, q_heel = n / width * (1 - 6 * e / width), n / width * (1 + 6 * e / width)
        return q_toe, (q_heel - q_toe) / width
    length = 3 * (width / 2 - abs(e))
    peak = 2 * n / length
    return (peak, -peak / length) if e < 0 else (peak * (1 - width / length), peak / length)


def _integral(q: tuple[float, float], a: float, b: float) -> tuple[float, float]:
    """∫q dx y ∫x·q dx entre a y b, con la parte negativa recortada."""
    q0, g = q
    if g != 0:
        root = -q0 / g
        a, b = (max(a, root), b) if g > 0 else (a, min(b, root))
    elif q0 <= 0:
        return 0.0, 0.0
    if b <= a:
        return 0.0, 0.0
    return q0 * (b - a) + g * (b**2 - a**2) / 2, q0 * (b**2 - a**2) / 2 + g * (b**3 - a**3) / 3


def _pieces(wall: dict, soil: dict, case: dict, toe_section: float) -> dict:
    """V (kN/m) y M (kN·m/m) del talón en la cara, de la puntera en la cara y a toe_section (m)."""
    t, toe, heel, hb = (wall[key] / 1e3 for key in ("stem_thickness", "toe", "heel", "base_thickness"))
    face, width = toe + t, toe + t + heel
    q = _pressure(wall, soil, case)
    _, pv, x_p, soil_weight, soil_x = thrust(wall, soil)
    loads = ((GAMMA_C * hb * heel * case["dead_factor"], face + heel / 2), (soil_weight * case["fill_factor"], soil_x),
             (pv * case["earth_factor"], x_p))
    force, static = _integral(q, face, width)
    heel_v = sum(w for w, _ in loads) - force
    heel_m = sum(w * (x - face) for w, x in loads) - (static - force * face)
    weight = GAMMA_C * hb * case["dead_factor"]

    def toe_at(section: float) -> tuple[float, float]:
        if section <= 0:
            return 0.0, 0.0
        f, s = _integral(q, 0.0, section)
        return f - weight * section, f * section - s - weight * section**2 / 2

    toe_v, toe_m = toe_at(toe_section)
    return {"heel": (heel_v, heel_m), "toe": toe_at(toe), "toe_shear": (toe_v, toe_m)}


def _flexure(area: float, depth: float, profile: str) -> tuple[float, float]:
    a = area * FY / (0.85 * FC * STRIP)
    c = a / _beta1(FC)
    strain = 0.003 * (depth - c) / c
    controlled = FY / ES + 0.003 if profile == "aci_318_25" else 0.005
    phi = 0.90 if strain >= controlled else float("nan")
    return phi * area * FY * (depth - a / 2), strain


def _shear(profile: str, depth: float, rho: float, vu: float, mu: float) -> tuple[float, float]:
    """(φVc, φ(Vc + 0.66√f'c·b·d)) en N, con Vu y Mu en N y N·mm."""
    root = min(math.sqrt(FC), 8.3)
    simple = 0.17 * root * STRIP * depth
    if profile == "aci_318_25":
        vc = simple
    else:
        ratio = min(vu * depth / mu, 1.0) if mu > 0 else 1.0
        vc = max(simple, min((0.16 * root + 17 * rho * ratio) * STRIP * depth, 0.29 * root * STRIP * depth))
    return 0.75 * vc, 0.75 * (vc + 0.66 * root * STRIP * depth)


def _crack(moment: float, area: float, depth: float, cover: float) -> tuple[float, float]:
    """(fs, s máx) con el momento de servicio en N·mm por franja."""
    n = ES / (4700.0 * math.sqrt(FC))
    rho_n = area / (STRIP * depth) * n
    k = math.sqrt(rho_n**2 + 2 * rho_n) - rho_n
    fs = moment / (area * (1 - k / 3) * depth)
    return fs, min(380.0 * 280.0 / fs - 2.5 * cover, 300.0 * 280.0 / fs)


def _straight(db: float, spacing: float, cover: float, below: float) -> float:
    psi_t = 1.3 if below > 300.0 else 1.0
    cb = min(cover + db / 2, spacing / 2)
    return max(FY * psi_t / (1.1 * min(math.sqrt(FC), 8.3) * min(cb / db, 2.5)) * db, 300.0)


def _hook(profile: str, db: float) -> float:
    base = FY * 0.7 / (4.2 * math.sqrt(FC)) if profile == "aci_318_25" else 0.24 * FY * 0.7 / math.sqrt(FC)
    return max(base * db, 8 * db, 150.0)


def _expected(profile: str, wall: dict, soil: dict) -> dict:
    h, cover = wall["base_thickness"], wall["base_cover"]
    top, bottom, longitudinal = (wall["base"][key] for key in ("top", "bottom", "longitudinal"))
    (top_db, top_bar), (bottom_db, bottom_bar) = BARS[top["designation"]], BARS[bottom["designation"]]
    top_area, bottom_area = top_bar * STRIP / top["spacing"], bottom_bar * STRIP / bottom["spacing"]
    top_d, bottom_d = h - cover - top_db / 2, h - cover - bottom_db / 2
    toe_section = (wall["toe"] - bottom_d) / 1e3
    factored, service = (_pieces(wall, soil, case, toe_section) for case in (FACTORED, SERVICE))
    kn = 1e3 * STRIP / 1e3  # kN/m → N por franja
    knm = 1e6 * STRIP / 1e3  # kN·m/m → N·mm por franja
    out: dict = {}
    for part, area, depth, spacing in (("heel", top_area, top_d, top["spacing"]), ("toe", bottom_area, bottom_d, bottom["spacing"])):
        mu = factored[part][1] * knm
        phi_mn, strain = _flexure(area, depth, profile)
        shear_v, shear_m = factored[part if part == "heel" else "toe_shear"]
        vu, mu_v = abs(shear_v) * kn, abs(shear_m) * knm
        phi_vc, section = _shear(profile, depth, area / (STRIP * depth), vu, mu_v)
        fs, crack = _crack(service[part][1] * knm, area, depth, cover)
        out[part] = {"Mu": mu, "phiMn": phi_mn, "et": strain, "Vu": vu, "phiVc": phi_vc, "section": section, "As": area,
                     "d": depth, "Ms": service[part][1] * knm, "fs": fs, "crack": crack, "As_min": 0.0018 * STRIP * h,
                     "spacing_max": min(3 * h, 450.0),
                     "flexure": "PASS" if phi_mn >= mu else "FAIL", "shear": "PASS" if vu <= phi_vc else "FAIL",
                     "crack_status": "PASS" if spacing <= crack else "FAIL"}
    width = wall["toe"] + wall["stem_thickness"] + wall["heel"]
    l_db, l_bar = BARS[longitudinal["designation"]]
    stem_db = BARS[wall["stem"]["back"]["designation"]][0]
    out["longitudinal"] = {"required": 0.0018 * h * width, "provided": 2 * l_bar / longitudinal["spacing"] * width,
                           "spacing_max": min(5 * h, 450.0)}
    out["depth"] = bottom_d
    out["development"] = {
        "dowel": (_hook(profile, stem_db), h - cover),
        "heel": (_straight(top_db, top["spacing"], cover, h - cover - top_db / 2),
                 min(wall["heel"], wall["toe"] + wall["stem_thickness"]) - cover),
        "toe": (_straight(bottom_db, bottom["spacing"], cover, 0.0),
                min(wall["toe"], wall["stem_thickness"] + wall["heel"]) - cover),
    }
    return out


def _bars(designation: str, spacing: float, end: str = "straight") -> dict:
    return {"designation": designation, "spacing": spacing, "end": end}


def _wall(**change: object) -> dict:
    """El muro del ejemplo 2 del manual con la base de 24 in, en mm, con su refuerzo."""
    return {"stem_height": 4876.8, "stem_thickness": 381.0, "toe": 762.0, "heel": 1676.4, "base_thickness": 609.6,
            "backfill_height": 4876.8, "stem_cover": 50.8, "base_cover": 76.2,
            "earth_pressure": {"state": "active", "method": "rankine"},
            "stem": {"back": _bars("#7", 228.6, "hook90"), "front": _bars("#5", 450.0), "horizontal": _bars("#5", 450.0)},
            "base": {"top": _bars("#7", 114.3), "bottom": _bars("#7", 228.6), "longitudinal": _bars("#7", 355.6)}, **change}


SOIL = {"unit_weight_backfill": 17.28, "friction_angle": 35.0, "friction_coefficient": 0.5, "allowable_pressure_kPa": 143.64,
        "min_contact_fraction": 0.5, "sliding_safety_factor": 1.5, "overturning_safety_factor": 2.0}
SERVICE = {"case": "D+H", "kind": "service", "dead_factor": 1.0, "fill_factor": 1.0, "earth_factor": 1.0}
FACTORED = {"case": "1.2D+1.6H", "kind": "factored", "dead_factor": 1.2, "fill_factor": 1.6, "earth_factor": 1.6}
CASES = [
    ("manual-ejemplo-2", "el ejemplo 2 del manual con la base de 24 in (Rankine; el paquete usa Chu sobre AC, equivalente)",
     _wall(), SOIL),
    ("talon-corto-coulomb", "talón corto con Coulomb: la cuña y la componente vertical del empuje cargan el talón",
     _wall(heel=1200.0, earth_pressure={"state": "active", "method": "coulomb", "wall_friction_angle": 20.0}),
     {**SOIL, "cohesion": 0.0}),
    ("contacto-parcial", "puntera y talón cortos con Ka declarado: presión triangular, el talón sin presión en su extremo",
     _wall(toe=300.0, heel=1300.0, earth_pressure={"state": "active", "method": "declared", "coefficient": 0.25}), SOIL),
]


def main() -> None:
    for folder, section in SECTION.items():
        cases = [{"id": case_id, "description": text, "wall": wall, "soil": soil, "service": SERVICE, "factored": FACTORED,
                  "expected": _expected(folder, wall, soil)} for case_id, text, wall, soil in CASES]
        data = {"description": "Base del muro en voladizo (D-173, etapa 4): talón con carga neta, puntera, agrietamiento con "
                               "fs de servicio, mínimos, longitudinal y desarrollo, con fórmulas cerradas escritas aquí.",
                "unit_weight_concrete_kNm3": GAMMA_C, "fc": FC, "fy": FY, "section_clause": section, "tolerance_rel": 1e-9,
                "cases": cases}
        (HERE / folder / "derived_wall_base.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                              encoding="utf-8")


if __name__ == "__main__":
    main()
