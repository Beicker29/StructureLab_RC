"""Deriva el oráculo de la zapata combinada en T invertida (D-093) para los dos perfiles.

No importa el paquete. Unidades de trabajo: N y mm. Para cada caso mayorado:

1. Resultante como en derive_combined_beam.py, más el alma: carga lineal w_alma = bw·(γc·(H − h) − γf·min(H − h, D1)),
   centrada a todo lo largo; cada columna desplaza solo el relleno sobre la viga, γf·max(D1 − (H − h), 0); el cortante
   horizontal actúa a la altura H + pedestal.
2. Viga larga: V y M del cuerpo libre con la carga neta de la zarpa y la carga lineal del alma; estaciones como en la
   combinada, con d desde la cara superior de la viga.
3. Sección: alma bw × H. Ala de viga aislada (ACI 6.3.2.2, NSR-10 C.8.12.4): bf = min(4bw, B) si h ≥ 0.5bw; si no, el
   ala no cuenta. Con M < 0 (cara superior a tracción) la zarpa está comprimida: T con el ala bf × h en la cara
   comprimida; con M > 0 el bloque está en el alma (bw) y las barras x inferiores a tracción solo cuentan dentro de bf.
   Compatibilidad con el bloque de Whitney, acero elastoplástico y concreto desplazado. As,min de vigas con d ≥ 0.8H,
   el acero a tracción más allá de H/2 y, con el ala a tracción (M > 0), el ancho min(bf, 2bw) por ser isostática; la
   excepción de 4/3 por bisección. Cortante con Vc de cimentación en el alma, d del acero a tracción.
4. Aletas (cada lado, por metro): m(x) = ∫(q − w)·(y − cara) dy y v(x) = ∫(q − w) dy desde cara + d, con la presión
   recortada en cero integrada en forma cerrada; máximo a lo largo de X por barrido fino y sección áurea. Flexión de
   1000 × h con la malla y, cortante con Vc de cimentación (b = 1000) y mínimo de losa 0.0018·h·1000.
5. Ala a tracción: ancho de reparto min(bf, ℓn/10) (ACI) o min(bf, ℓ/10) con la luz entre centros (NSR-10); si es
   menor que bf, cumple si hay barras x fuera de él.
6. Aplastamiento de cada columna sobre la viga: A2 con la pendiente 1:2 dentro de la cara superior (lx × bw) y la
   altura H; φBn = 0.65·0.85·f'c·A1·√(A2/A1) ≤ 2.

Uso: python tests/oracles/derive_inverted_t.py
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
_P, _F, _S, _C = _B._P, _B._F, _B._S, _B._C
FC, FY, BARS = _B.FC, _B.FY, _B.BARS
GAMMA_C, GAMMA_F = _B.GAMMA_C, _B.GAMMA_F
ECU, ES, BETA1 = _B.ECU, _B.ES, _B.BETA1
PHI_SHEAR = _S.PHI
SCAN, GOLDEN = 2000, 200


def _beam(f: dict, case: str) -> dict | None:
    lx, ly, h, hp, hf = f["lx"], f["ly"], f["h"], f["pedestal_height"], f["fill_height"]
    big, bw = f["beam"]["height"], f["beam"]["width"]
    stem = big - h
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in f["columns"]]
    fd, fl = loads[0]["dead_factor"], loads[0]["live_factor"]
    dead_area = GAMMA_F * hf + f["surcharge_dead_kNm2"] * 1e-3
    live_area = f["surcharge_live_kNm2"] * 1e-3
    w = fd * (GAMMA_C * h + dead_area) + fl * live_area
    line = fd * bw * (GAMMA_C * stem - GAMMA_F * min(stem, hf))
    n = w * lx * ly + line * lx
    displaced = GAMMA_F * max(hf - stem, 0.0) + f["surcharge_dead_kNm2"] * 1e-3
    mx = my = 0.0
    columns = []
    for column, load in zip(f["columns"], loads, strict=True):
        area = column["cx"] * column["cy"]
        force = load["P_kN"] * 1e3 + fd * (GAMMA_C * area * hp - displaced * area) - fl * live_area * area
        vx, vy = load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
        arm = big + hp
        mx += load["Mx_kNm"] * 1e6 - column["y"] * force - arm * vy
        my += load["My_kNm"] * 1e6 + arm * vx + column["x"] * force
        n += force
        columns.append({"id": column["id"], "x": column["x"], "half": column["cx"] / 2, "force": force,
                        "couple": load["My_kNm"] * 1e6 + arm * vx,
                        "torque": force * column["y"] - load["Mx_kNm"] * 1e6 + arm * vy})
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return None
    plane, _ = _P.solve(lx, ly, n, my / n, -mx / n)
    return {"plane": plane, "w": w, "columns": sorted(columns, key=lambda c: c["x"]), "lx": lx, "ly": ly, "line": line}


def _flange(f: dict) -> float | None:
    bw = f["beam"]["width"]
    return min(4 * bw, f["ly"]) if f["h"] >= 0.5 * bw else None


def _positions(width: float, cover: float, db: float, spacing: float) -> list[float]:
    half = width / 2 - cover - db / 2
    count = math.floor(2 * half / spacing + 1e-6) + 1
    offset = (2 * half - (count - 1) * spacing) / 2
    return [-half + offset + i * spacing for i in range(count)]


def _rows(f: dict) -> dict:
    """Barras de la viga: inferiores x dentro del ala efectiva (centro a from_bottom de la cara inferior) y superiores
    en el alma (a from_top de la cara superior)."""
    ds = BARS[f["stirrups"]["designation"]][0] if f.get("stirrups") else 0.0
    mat = f["bottom"]
    db, ab = BARS[mat["x"]["designation"]]
    from_bottom = f["cover"] + ds + (db / 2 if mat["first"] == "x" else BARS[mat["y"]["designation"]][0] + db / 2)
    reach = (_flange(f) or f["beam"]["width"]) / 2
    bottom = [y for y in _positions(f["ly"], f["cover"], db, mat["x"]["spacing"]) if abs(y) <= reach + 1e-6]
    dt, at = BARS[f["top"]["designation"]]
    top = _positions(f["beam"]["width"], f["cover"] + ds, dt, f["top"]["spacing"])
    all_bottom = _positions(f["ly"], f["cover"], db, mat["x"]["spacing"])
    return {"bottom_area": len(bottom) * ab, "from_bottom": from_bottom, "top_area": len(top) * at, "from_top": f["cover"] + ds + dt / 2,
            "bottom_all": all_bottom, "spacing": mat["x"]["spacing"]}


def _state(layers: list[tuple[float, float]], section: tuple[float, float, float], h: float) -> dict | None:
    """Compatibilidad con el ala (ancho bf, espesor hf) en la cara comprimida y el alma bw. layers: (profundidad desde la
    cara comprimida, área)."""
    bw, bf, hf = section

    def concrete(a: float) -> tuple[float, float]:
        top = min(a, hf)
        area = bf * top + bw * max(a - hf, 0.0)
        moment = bf * top**2 / 2 + (bw * (a**2 - hf**2) / 2 if a > hf else 0.0)
        return area, moment

    def forces(c: float) -> tuple[float, list[tuple[float, float, float]]]:
        a = min(BETA1 * c, h)
        steel = []
        for depth, area in layers:
            strain = ECU * (depth - c) / c
            stress = max(-FY, min(FY, ES * strain))
            displaced = 0.85 * FC if depth < BETA1 * c else 0.0
            steel.append((depth, area * (stress + displaced), strain))
        return sum(force for _, force, _ in steel) - 0.85 * FC * concrete(a)[0], steel

    low, high = 1e-9, h / BETA1
    if forces(low)[0] <= 0 or forces(high)[0] >= 0:
        return None
    for _ in range(300):
        middle = (low + high) / 2
        low, high = (middle, high) if forces(middle)[0] > 0 else (low, middle)
    c = (low + high) / 2
    _, steel = forces(c)
    a = min(BETA1 * c, h)
    nominal = sum(force * depth for depth, force, _ in steel) - 0.85 * FC * concrete(a)[1]
    deepest = max(depth for depth, _ in layers)
    return {"c": c, "Mn": nominal, "et": ECU * (deepest - c) / c, "strains": [strain for _, _, strain in steel]}


def _section(f: dict, rows: dict, moment: float) -> tuple[list[tuple[float, float]], tuple[float, float, float]]:
    big, bw = f["beam"]["height"], f["beam"]["width"]
    if moment < 0:  # cara superior a tracción: la zarpa comprimida
        width = _flange(f)
        layers = [(rows["from_bottom"], rows["bottom_area"]), (big - rows["from_top"], rows["top_area"])]
        return layers, ((bw, width, f["h"]) if width else (bw, bw, f["h"]))
    return [(rows["from_top"], rows["top_area"]), (big - rows["from_bottom"], rows["bottom_area"])], (bw, bw, f["h"])


def _beam_checks(folder: str, f: dict, rows: dict, given: tuple[float, float]) -> list[dict]:
    shear, moment = given
    profile = _F.PROFILES[folder]
    big, bw = f["beam"]["height"], f["beam"]["width"]
    layers, section = _section(f, rows, moment)
    state = _state(layers, section, big)
    assert state is not None
    phi = _F._phi(state["et"], profile)
    checks = [{"name": "Flexion: resistencia", "status": "PASS" if phi * state["Mn"] >= abs(moment) else "FAIL",
               "demand": abs(moment), "capacity": phi * state["Mn"]}]
    pulled = [(depth, area) for (depth, area), strain in zip(layers, state["strains"], strict=True) if strain > 0]
    tension = [(depth, area) for depth, area in pulled if depth > big / 2]
    if moment != 0 and tension:
        checks.append({"name": "Flexion: deformacion neta de traccion (M3)",
                       "status": "PASS" if state["et"] >= profile["strain_min"] else "FAIL", "capacity": state["et"]})
        provided = sum(area for _, area in tension)
        d = max(sum(depth * area for depth, area in tension) / provided, 0.8 * big)
        width = bw
        flange = _flange(f)
        if moment > 0 and flange:  # ala a tracción en una viga isostática
            width = min(flange, 2 * bw)
        as_min = max(0.25 * math.sqrt(FC), 1.4) / FY * width * d
        item = {"name": "Flexion: acero minimo (M3)", "capacity": provided}
        if provided >= as_min:
            item.update(status="PASS", demand=as_min)
        else:
            def design(k: float) -> float:
                scaled = [(depth, area * k if (depth, area) in tension else area) for depth, area in layers]
                own = _state(scaled, section, big)
                return 0.0 if own is None else _F._phi(own["et"], profile) * abs(own["Mn"])

            if design(1.0) < abs(moment):
                item.update(status="FAIL", demand=as_min)
            else:
                lo, hi = 0.0, 1.0
                for _ in range(200):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if design(mid) < abs(moment) else (lo, mid)
                effective = min(as_min, 4 / 3 * hi * provided)
                item.update(status="PASS" if provided >= effective else "FAIL", demand=effective)
        checks.append(item)
    if pulled:
        area = sum(a for _, a in pulled)
        d = max(sum(depth * a for depth, a in pulled) / area, 0.8 * big)
        vc = _S._one_way_vc(folder, bw, d, area / (bw * d), abs(shear), abs(moment))
        stirrups = f.get("stirrups")
        transverse = 0.0 if stirrups is None else stirrups["legs"] * BARS[stirrups["designation"]][1] / stirrups["spacing"]
        vs = transverse * FY * d
        capacity = PHI_SHEAR * (vc + min(vs, 0.66 * math.sqrt(FC) * bw * d))
        checks.append({"name": "Cortante: resistencia", "status": "PASS" if abs(shear) <= capacity else "FAIL",
                       "demand": abs(shear), "capacity": capacity})
    return checks


def _along_y(plane: list[float], x: float, y0: float, y1: float) -> tuple[float, float]:
    """∫q dy y ∫y·q dy con q = q0 + gx·x + gy·y recortada en cero."""
    q0, gx, gy = plane
    a, b = q0 + gx * x, gy
    low, high = y0, y1
    if b == 0:
        if a <= 0:
            return 0.0, 0.0
    else:
        root = -a / b
        low, high = (max(low, root), high) if b > 0 else (low, min(high, root))
    if high <= low:
        return 0.0, 0.0
    return a * (high - low) + b * (high**2 - low**2) / 2, a * (high**2 - low**2) / 2 + b * (high**3 - low**3) / 3


def _flange_load(beam: dict, f: dict, x: float, side: float, at: float) -> tuple[float, float]:
    face, edge = f["beam"]["width"] / 2, f["ly"] / 2
    start = face + at
    if start >= edge:
        return 0.0, 0.0
    y0, y1 = (start, edge) if side > 0 else (-edge, -start)
    force, first = _along_y(beam["plane"], x, y0, y1)
    length = edge - start
    lever = first - start * force if side > 0 else -start * force - first
    return force - beam["w"] * length, lever - beam["w"] * length**2 / 2


def _maximum(function, low: float, high: float) -> tuple[float, float]:
    xs = [low + (high - low) * i / SCAN for i in range(SCAN + 1)]
    values = [function(x) for x in xs]
    i = max(range(len(xs)), key=lambda k: values[k])
    a, b = xs[max(i - 1, 0)], xs[min(i + 1, SCAN)]
    g = (math.sqrt(5) - 1) / 2
    for _ in range(GOLDEN):
        c, d = b - g * (b - a), a + g * (b - a)
        if function(c) >= function(d):
            b = d
        else:
            a = c
    mid = (a + b) / 2
    return max(((xs[i], values[i]), (mid, function(mid))), key=lambda item: item[1])


def _flange_checks(folder: str, f: dict, beam: dict) -> list[dict]:
    db, ab = BARS[f["bottom"]["y"]["designation"]]
    dx = BARS[f["bottom"]["x"]["designation"]][0]
    ds = BARS[f["stirrups"]["designation"]][0] if f.get("stirrups") else 0.0
    depth = f["h"] - f["cover"] - ds - (db / 2 if f["bottom"]["first"] == "y" else dx + db / 2)
    per_metre = ab * 1000.0 / f["bottom"]["y"]["spacing"]
    half = f["lx"] / 2
    moment = max(_maximum(lambda x, s=s: _flange_load(beam, f, x, s, 0.0)[1], -half, half)[1] for s in (1.0, -1.0))
    best = max(((_maximum(lambda x, s=s: _flange_load(beam, f, x, s, depth)[0], -half, half), s) for s in (1.0, -1.0)),
               key=lambda item: item[0][1])
    (x, shear), side = best
    mu_d = _flange_load(beam, f, x, side, depth)[1]
    profile = _F.PROFILES[folder]
    state = _B._state([(depth, per_metre)], 1000.0, f["h"])
    capacity = _F._phi(state["et"], profile) * state["Mn"]
    vu = max(shear, 0.0) * 1000.0
    vc = _S._one_way_vc(folder, 1000.0, depth, per_metre / (1000.0 * depth), vu, abs(mu_d) * 1000.0)
    return [{"name": "Aleta: flexion (barras y)", "status": "PASS" if capacity >= moment * 1000.0 else "FAIL",
             "demand": moment * 1000.0, "capacity": capacity},
            {"name": "Aleta: cortante en una direccion (barras y)", "status": "PASS" if vu <= PHI_SHEAR * vc else "FAIL",
             "demand": vu, "capacity": PHI_SHEAR * vc}]


def _expected(folder: str, f: dict) -> dict:
    rows = _rows(f)
    big = f["beam"]["height"]
    checks = []
    for load in f["columns"][0]["loads"]:
        if load["kind"] != "factored":
            continue
        case = load["case"]
        beam = _beam(f, case)
        assert beam is not None
        depth = big - rows["from_bottom"]
        for x in _B._stations(beam, depth):
            moment = _B._shear_moment(beam, x)[1]
            shear_at = x
            for face, side in _B._faces(beam):
                at_d = face + side * depth
                if abs(face - x) <= 1e-6 * f["lx"] and any(low < at_d < high and low <= face <= high for low, high in _B._regions(beam)):
                    shear_at = at_d
            shear = _B._shear_moment(beam, shear_at)[0]
            checks += [{**item, "case": case, "z_mm": x + f["lx"] / 2} for item in _beam_checks(folder, f, rows, (shear, moment))]
        checks += [{**item, "case": case} for item in _flange_checks(folder, f, beam)]
        for column in f["columns"]:
            pu = next(item for item in column["loads"] if item["case"] == case)["P_kN"] * 1e3
            hx, hy = f["lx"] / 2, f["beam"]["width"] / 2
            gaps = (hx - (column["x"] + column["cx"] / 2), column["x"] - column["cx"] / 2 + hx,
                    hy - (column["y"] + column["cy"] / 2), column["y"] - column["cy"] / 2 + hy)
            spread = min(2 * big, *gaps)
            a1 = column["cx"] * column["cy"]
            a2 = (column["cx"] + 2 * spread) * (column["cy"] + 2 * spread)
            capacity = 0.65 * 0.85 * FC * a1 * min(math.sqrt(a2 / a1), 2.0)
            checks.append({"name": "Aplastamiento en la zapata", "status": "PASS" if pu <= capacity else "FAIL", "demand": pu,
                           "capacity": capacity, "case": case, "note_prefix": f"Columna {column['id']}"})
    flange = _flange(f)
    if flange:
        first, second = sorted(f["columns"], key=lambda c: c["x"])
        clear = (second["x"] - second["cx"] / 2) - (first["x"] + first["cx"] / 2)
        span = clear if folder == "aci_318_25" else second["x"] - first["x"]
        spread = min(flange, span / 10)
        outer = [y for y in rows["bottom_all"] if abs(y) > spread / 2]
        checks.append({"name": "Viga T: refuerzo del ala en traccion", "status": "PASS" if spread >= flange or outer else "FAIL"})
    minimum = 0.0018 * f["h"] * 1000.0
    provided = BARS[f["bottom"]["y"]["designation"]][1] / f["bottom"]["y"]["spacing"] * 1000.0
    checks.append({"name": "Aleta: acero minimo (barras y)", "status": "PASS" if provided >= minimum else "FAIL",
                   "demand": minimum, "capacity": provided})
    return {"checks": checks, "flange_width": flange}


def _load(case: str, p: float, dead: float = 1.2, live: float = 1.6, mx: float = 0.0, my: float = 0.0, vx: float = 0.0) -> dict:
    return {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": 0.0,
            "Mx_kNm": mx, "My_kNm": my}


def _footing(**changes: object) -> dict:
    columns = [{"id": "C1", "cx": 500.0, "cy": 500.0, "x": -2500.0, "y": 0.0, "loads": [_load("U1", 1000.0)]},
               {"id": "C2", "cx": 500.0, "cy": 500.0, "x": 2500.0, "y": 0.0, "loads": [_load("U1", 1150.0)]}]
    data = {"id": "ZT", "lx": 6600.0, "ly": 2400.0, "h": 400.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns,
            "beam": {"width": 600.0, "height": 900.0},
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#6", "spacing": 150.0},
                       "y": {"designation": "#5", "spacing": 150.0}},
            "top": {"designation": "#8", "spacing": 75.0, "end": "straight"},
            "stirrups": {"designation": "#4", "legs": 4, "spacing": 120.0, "closed": True}}
    data.update(changes)
    return data


CASES = [
    ("cumple", "T invertida de 6.6 × 2.4 m, viga 600 × 900 sobre zarpa de 400 mm: ala bf = 4bw = 2400 mm", _footing()),
    ("ala-delgada", "zarpa de 280 mm < 0.5bw: el ala no cuenta (solo el alma) y las barras inferiores solo en el alma",
     _footing(h=280.0)),
    ("aleta-escasa", "malla y #4 c/300: la aleta no cumple flexión ni el mínimo de losa",
     _footing(bottom={"first": "x", "end": "straight", "x": {"designation": "#6", "spacing": 150.0},
                      "y": {"designation": "#4", "spacing": 300.0}})),
    ("momento-positivo", "momentos de columna grandes: momento positivo en las caras y el ala a tracción con min(bf, 2bw)",
     _footing(columns=[{"id": "C1", "cx": 500.0, "cy": 500.0, "x": -2500.0, "y": 0.0, "loads": [_load("U1", 1500.0, my=-600.0)]},
                       {"id": "C2", "cx": 500.0, "cy": 500.0, "x": 2500.0, "y": 0.0, "loads": [_load("U1", 1800.0, my=650.0)]}],
              bottom={"first": "x", "end": "straight", "x": {"designation": "#4", "spacing": 300.0},
                      "y": {"designation": "#5", "spacing": 150.0}})),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = _F.PROFILES[folder]["levels"]["bajo"]
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing)}
                 for case_id, text, footing in CASES]
        data = {"description": "Zapata combinada en T invertida (D-093): viga larga en T volteada con el ala de viga aislada, "
                               "aletas por metro, ala a tracción y aplastamiento sobre la viga.",
                "soil": _C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "seismic_level": level, "tolerance_rel": 1e-6, "cases": cases}
        (HERE / folder / "derived_inverted_t.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
