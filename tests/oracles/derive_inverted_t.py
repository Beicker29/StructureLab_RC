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
    """Capas de flexión de la viga (D-106): (profundidad desde la cara superior, área). La capa inferior declarada cuenta
    dentro del ala efectiva (o del alma si el ala no cuenta); las barras x de la malla de la zarpa van solo fuera del
    ancho que cubre la capa inferior (bottom_width o el ala efectiva) y cuentan dentro del ala."""
    beam = f["beam"]
    bw, big = beam["width"], beam["height"]
    flange = _flange(f)
    reach = (flange or bw) / 2
    flexure = [layer for layer in beam["layers"] if layer["role"] == "flexure"]
    bottom = max(flexure, key=lambda layer: layer["depth"])
    layers = []
    for layer in flexure:
        bars = [bar for bar in layer["bars"] if layer is not bottom or abs(bar["x"] - bw / 2) <= reach + 1e-6]
        if bars:
            layers.append((layer["depth"], sum(BARS[bar["designation"]][1] for bar in bars)))
    mat = f["bottom"]
    db, ab = BARS[mat["x"]["designation"]]
    from_bottom = f["cover"] + (db / 2 if mat["first"] == "x" else BARS[mat["y"]["designation"]][0] + db / 2)
    covered = (beam.get("bottom_width") or flange or bw) / 2
    every = _positions(f["ly"], f["cover"], db, mat["x"]["spacing"])
    extra = [y for y in every if covered + 1e-6 < abs(y) <= reach + 1e-6]
    if extra:
        layers.append((big - from_bottom, len(extra) * ab))
    return {"layers": layers, "bottom_depth": bottom["depth"], "bottom_all": every}


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
    if moment < 0:  # cara superior a tracción: la zarpa comprimida, profundidades desde la cara inferior
        width = _flange(f)
        layers = [(big - depth, area) for depth, area in rows["layers"]]
        return layers, ((bw, width, f["h"]) if width else (bw, bw, f["h"]))
    return list(rows["layers"]), (bw, bw, f["h"])


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
        # Sin la excepción de 4/3 del As requerido (decisión del usuario, D-115): As ≥ As,min siempre.
        checks.append({"name": "Flexion: acero minimo (M3)", "capacity": provided, "demand": as_min,
                       "status": "PASS" if provided >= as_min else "FAIL"})
    if pulled:
        area = sum(a for _, a in pulled)
        d = max(sum(depth * a for depth, a in pulled) / area, 0.8 * big)
        vc = _S._one_way_vc(folder, bw, d, area / (bw * d), abs(shear), abs(moment))
        stirrups = f["beam"].get("stirrups")
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
    # El cortante que gobierna es el de mayor valor absoluto, positivo o negativo.
    best = max(((_maximum(lambda x, s=s: abs(_flange_load(beam, f, x, s, depth)[0]), -half, half), s) for s in (1.0, -1.0)),
               key=lambda item: item[0][1])
    (x, shear), side = best
    mu_d = _flange_load(beam, f, x, side, depth)[1]
    profile = _F.PROFILES[folder]
    state = _B._state([(depth, per_metre)], 1000.0, f["h"])
    capacity = _F._phi(state["et"], profile) * state["Mn"]
    vu = shear * 1000.0
    vc = _S._one_way_vc(folder, 1000.0, depth, per_metre / (1000.0 * depth), vu, abs(mu_d) * 1000.0)
    out = [{"name": "Aleta: flexion (direccion secundaria)", "status": "PASS" if capacity >= moment * 1000.0 else "FAIL",
            "demand": moment * 1000.0, "capacity": capacity},
           {"name": "Aleta: cortante en una direccion (direccion secundaria)", "status": "PASS" if vu <= PHI_SHEAR * vc else "FAIL",
            "demand": vu, "capacity": PHI_SHEAR * vc}]
    top = f.get("top") or {}
    negative = max(_maximum(lambda x, s=s: -_flange_load(beam, f, x, s, 0.0)[1], -half, half)[1] for s in (1.0, -1.0))
    if top.get("y") and negative > 1.0:
        # D-114: momento negativo de la aleta con las barras superiores y de la zarpa (sin estribo en la zarpa de la T);
        # la cara comprimida es la inferior y las barras quedan a h − (recubrimiento + barras x si van primero + db/2).
        dt, at = BARS[top["y"]["designation"]]
        above = BARS[top["x"]["designation"]][0] if top.get("x") and (top.get("first") or "y") == "x" else 0.0
        top_depth = f["h"] - f["cover"] - above - dt / 2
        top_metre = at * 1000.0 / top["y"]["spacing"]
        state = _B._state([(top_depth, top_metre)], 1000.0, f["h"])
        capacity = _F._phi(state["et"], profile) * state["Mn"]
        out.append({"name": "Aleta: flexion, barras superiores (direccion secundaria)",
                    "status": "PASS" if capacity >= negative * 1000.0 else "FAIL", "demand": negative * 1000.0, "capacity": capacity})
    return out


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
        depth = rows["bottom_depth"]
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
    checks.append({"name": "Aleta: acero minimo (direccion secundaria)", "status": "PASS" if provided >= minimum else "FAIL",
                   "demand": minimum, "capacity": provided})
    return {"checks": checks, "flange_width": flange}


def _load(case: str, p: float, dead: float = 1.2, live: float = 1.6, mx: float = 0.0, my: float = 0.0, vx: float = 0.0) -> dict:
    return {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": 0.0,
            "Mx_kNm": mx, "My_kNm": my}


def _layer(depth: float, designation: str, xs: list[float]) -> dict:
    return {"depth": depth, "role": "flexure", "bars": [{"designation": designation, "x": x} for x in xs]}


def _spread(low: float, high: float, count: int) -> list[float]:
    return [low + (high - low) * i / (count - 1) for i in range(count)]


# Viga 600 × 900: 6 #8 arriba por dentro del estribo #4 y, abajo, #6 c/150 en todo el ancho de la zarpa (2400 mm).
TOP = _layer(75 + 12.7 + 25.4 / 2, "#8", _spread(75 + 12.7 + 12.7, 600 - 75 - 12.7 - 12.7, 6))
BOTTOM = _layer(900 - 75 - 19.1 / 2, "#6", [y + 300 for y in _spread(-1050, 1050, 15)])


def _footing(**changes: object) -> dict:
    columns = [{"id": "C1", "cx": 500.0, "cy": 500.0, "x": -2500.0, "y": 0.0, "loads": [_load("U1", 1000.0)]},
               {"id": "C2", "cx": 500.0, "cy": 500.0, "x": 2500.0, "y": 0.0, "loads": [_load("U1", 1150.0)]}]
    beam = {"width": 600.0, "height": 900.0, "end": "straight", "layers": [TOP, BOTTOM],
            "stirrups": {"designation": "#4", "legs": 4, "spacing": 120.0, "closed": True}}
    data = {"id": "ZT", "lx": 6600.0, "ly": 2400.0, "h": 400.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns, "beam": beam,
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#6", "spacing": 150.0},
                       "y": {"designation": "#5", "spacing": 150.0}}}
    beam_changes = changes.pop("beam_changes", {})
    data.update(changes)
    data["beam"] = {**beam, **beam_changes}  # type: ignore[dict-item]
    return data


CASES = [
    ("cumple", "T invertida de 6.6 × 2.4 m, viga 600 × 900 sobre zarpa de 400 mm: ala bf = 4bw = 2400 mm", _footing()),
    ("ala-delgada", "zarpa de 280 mm < 0.5bw: el ala no cuenta (solo el alma) y las barras inferiores solo en el alma",
     _footing(h=280.0, beam_changes={"layers": [TOP, _layer(900 - 75 - 19.1 / 2, "#6", _spread(100.0, 500.0, 4))]})),
    ("aleta-escasa", "malla y #4 c/300: la aleta no cumple flexión ni el mínimo de losa",
     _footing(bottom={"first": "x", "end": "straight", "x": {"designation": "#6", "spacing": 150.0},
                      "y": {"designation": "#4", "spacing": 300.0}})),
    ("momento-positivo", "momentos de columna grandes: momento positivo en las caras y el ala a tracción con min(bf, 2bw)",
     _footing(columns=[{"id": "C1", "cx": 500.0, "cy": 500.0, "x": -2500.0, "y": 0.0, "loads": [_load("U1", 1500.0, my=-600.0)]},
                       {"id": "C2", "cx": 500.0, "cy": 500.0, "x": 2500.0, "y": 0.0, "loads": [_load("U1", 1800.0, my=650.0)]}],
              bottom={"first": "x", "end": "straight", "x": {"designation": "#4", "spacing": 300.0},
                      "y": {"designation": "#5", "spacing": 150.0}},
              beam_changes={"layers": [TOP, _layer(900 - 75 - 12.7 / 2, "#4", [y + 300 for y in _spread(-1050, 1050, 8)])]})),
    ("capa-angosta", "capa inferior de la viga en 1200 mm (bottom_width): fuera de ella, las barras #5 c/200 de la malla de la "
                     "zarpa cuentan dentro del ala (D-106)",
     _footing(bottom={"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 200.0},
                      "y": {"designation": "#5", "spacing": 150.0}},
              beam_changes={"bottom_width": 1200.0,
                            "layers": [TOP, _layer(900 - 75 - 19.1 / 2, "#6", [y + 300 for y in _spread(-450, 450, 7)])]})),
    ("aleta-superior", "Mx grande: la presión baja hacia un borde y aparece el momento negativo en esa aleta, que toman las "
                       "barras superiores y de la zarpa, #5 c/200 (top, D-114)",
     _footing(columns=[{"id": "C1", "cx": 500.0, "cy": 500.0, "x": -2500.0, "y": 0.0, "loads": [_load("U1", 350.0, mx=350.0)]},
                       {"id": "C2", "cx": 500.0, "cy": 500.0, "x": 2500.0, "y": 0.0, "loads": [_load("U1", 400.0, mx=350.0)]}],
              top={"first": "y", "end": "straight", "y": {"designation": "#5", "spacing": 200.0}})),
]


# Casos en los que solo se comparan las aletas: el Mx que produce su momento negativo tuerce la viga por encima del
# umbral y la torsión de la viga de la T no está en este oráculo (D-114).
FLANGE_ONLY = {"aleta-superior"}


def _case(folder: str, case_id: str, text: str, footing: dict) -> dict:
    expected = _expected(folder, footing)
    if case_id in FLANGE_ONLY:
        expected["checks"] = [item for item in expected["checks"] if item["name"].startswith("Aleta")]
    return {"id": case_id, "description": text, "footing": footing, "expected": expected, "flange_only": case_id in FLANGE_ONLY}


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = _F.PROFILES[folder]["levels"]["bajo"]
        cases = [_case(folder, case_id, text, footing) for case_id, text, footing in CASES]
        data = {"description": "Zapata combinada en T invertida (D-093): viga larga en T volteada con el ala de viga aislada, "
                               "aletas por metro, ala a tracción y aplastamiento sobre la viga.",
                "soil": _C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "seismic_level": level, "tolerance_rel": 1e-6, "cases": cases}
        (HERE / folder / "derived_inverted_t.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
