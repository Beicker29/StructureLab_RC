"""Deriva el oráculo de la viga en la dirección larga de zapatas combinadas (D-080, V3J.2) para los dos perfiles.

No importa el paquete. Unidades de trabajo: N y mm. Para cada caso mayorado:

1. Resultante en el centroide de la base por suma de r × F (cada columna en (x, y, h + hp); su pedestal y el área que
   ocupa, sin relleno ni sobrecarga, en su eje; la zapata, el relleno y las sobrecargas en el centroide) y la presión
   sin tracción por el equilibrio de derive_soil_pressure.py.
2. Cuerpo libre a la izquierda de cada sección x: la carga neta (presión recortada en cero menos la carga uniforme
   w = fd·(γc·h + γf·hf + qD) + fl·qL) sobre [−L/2, x] × [−B/2, B/2], integrada con el recorte exacto de
   derive_footing_shear.py; cada columna a la izquierda baja F = P + fd·(γc·A·hp − (γf·hf + qD)·A) − fl·qL·A en su eje
   y aplica el par My + (h + hp)·Vx. V = suma de fuerzas hacia arriba; M = suma de momentos respecto a la sección
   (positivo tracciona abajo).
3. Estaciones de cada caso: el mayor y el menor momento entre las cuatro caras y los extremos interiores de cada tramo
   (barrido fino de M y sección áurea, no por las raíces de V, como el paquete), y las secciones a d (de las barras
   inferiores x) de cada cara hacia su tramo.
4. En cada estación, las reglas de vigas (D-081) escritas aparte: resistencia por compatibilidad de deformaciones con
   las dos capas (bloque de Whitney, acero elastoplástico, concreto desplazado), εt, As,min de vigas con d ≥ 0.8h y el
   acero a tracción más allá de h/2, excepción de 4/3 por bisección del acero escalado, separación por fisuración (fs = 2/3·fy) y
   cortante con Vc de cimentación, estribos y Av,min de cimentación. Sin barras superiores y M < 0, la flexión es de
   concreto simple (D-072); el cortante sigue la regla de vigas (las barras inferiores quedan a tracción cerca de la cara
   comprimida y d = 0.8h, D-043). Separación 3h y 450 mm por capa.
5. Torsión (D-088): T(x) = ∫y·q dA de la carga neta a la izquierda − Σ (F·y − Mx + (h + hp)·Vy) de las columnas a la
   izquierda, tomada donde el cortante (a d de la cara). Umbral φTth = 0.75·0.083·√f'c·Acp²/pcp con Acp = B·h; si
   Tu ≥ φTth, la verificación combinada reemplaza al cortante: sin estribos no cumple; con estribos, sección
   (√((Vu/bd)² + (Tu·ph/1.7Aoh²)²) ≤ φ(Vc/bd + 0.66√f'c)), Av/s + 2At/s con At/s = Tu/(φ·2·0.85Aoh·fyt), mínimo
   transversal y Aℓ = máx(Tu·ph/(φ·2·0.85Aoh·fy), Aℓ,min) frente a las capas de torsión más las barras de piel.
6. Piel y torsión se sirven mutuamente (decisión del usuario, D-090): las barras de piel cuentan como Aℓ y las capas de
   torsión, con barras cerca de las dos caras laterales, cuentan como piel (con su recubrimiento lateral).

Uso: python tests/oracles/derive_combined_beam.py
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


_P = _load_module("derive_soil_pressure")
_F = _load_module("derive_footing_flexure")
_S = _load_module("derive_footing_shear")
_C = _load_module("derive_combined_service")

FC, FY = _F.FC, _F.FY
GAMMA_C, GAMMA_F = _F.GAMMA_C, _F.GAMMA_F  # N/mm³
BARS = _F.BARS
PHI_SHEAR = _S.PHI
SCAN, GOLDEN_STEPS = 4000, 200
ECU, ES, BETA1 = 0.003, 200000.0, 0.85
CLAUSES = {"aci_318_25": {"strength": "9.5.1.1(a) y Tabla 21.2.2", "min": "9.6.1.2 y 9.6.1.3", "crack": "24.3.2 y 24.3.2.1",
                          "skin": "9.7.2.3", "shear": "13.2.6.2(a) y 13.2.7.2", "min_shear": "13.3.2.1 y 7.6.3.1",
                          "spacing": "13.3.2.1 y 7.7.2.3"},
           "nsr_10": {"strength": "C.9.3.2.1 y C.9.3.2.2", "min": "C.10.5.1 y C.10.5.2 y C.10.5.3", "crack": "C.10.6.4", "skin": "C.10.6.7",
                      "shear": "C.15.5.1, C.15.5.2 y C.11.2", "min_shear": "C.11.4.6.1(a)", "spacing": "C.10.5.4"}}


def _beam(f: dict, case: str) -> dict | None:
    """Presión, carga uniforme y fuerzas de las columnas de un caso; None si la resultante sale de la base."""
    lx, ly, h, hp, hf = f["lx"], f["ly"], f["h"], f["pedestal_height"], f["fill_height"]
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in f["columns"]]
    fd, fl = loads[0]["dead_factor"], loads[0]["live_factor"]
    dead_area = GAMMA_F * hf + f["surcharge_dead_kNm2"] * 1e-3
    live_area = f["surcharge_live_kNm2"] * 1e-3
    w = fd * (GAMMA_C * h + dead_area) + fl * live_area
    n = w * lx * ly
    mx = my = 0.0
    columns = []
    for column, load in zip(f["columns"], loads, strict=True):
        area = column["cx"] * column["cy"]
        force = load["P_kN"] * 1e3 + fd * (GAMMA_C * area * hp - dead_area * area) - fl * live_area * area
        vx, vy = load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
        r = (column["x"], column["y"], h + hp)
        # r × F con F = (Vx, Vy, −force), más los pares de la columna.
        mx += load["Mx_kNm"] * 1e6 + r[1] * (-force) - r[2] * vy
        my += load["My_kNm"] * 1e6 + r[2] * vx - r[0] * (-force)
        n += force
        columns.append({"id": column["id"], "x": column["x"], "half": column["cx"] / 2, "force": force,
                        "couple": load["My_kNm"] * 1e6 + (h + hp) * vx,
                        "torque": force * column["y"] - load["Mx_kNm"] * 1e6 + (h + hp) * vy})
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return None
    plane, _ = _P.solve(lx, ly, n, my / n, -mx / n)
    return {"plane": plane, "w": w, "columns": sorted(columns, key=lambda c: c["x"]), "lx": lx, "ly": ly}


def _shear_moment(beam: dict, x: float) -> tuple[float, float]:
    hx, hy = beam["lx"] / 2, beam["ly"] / 2
    force = sx = 0.0
    if x > -hx:
        force, sx, _ = _S._net(beam["plane"], beam["w"], (-hx, -hy, x, hy))
    shear, moment = force, x * force - sx
    # Carga lineal hacia abajo del alma de la T invertida (derive_inverted_t.py), en toda la longitud.
    span = min(max(x + hx, 0.0), beam["lx"])
    shear -= beam.get("line", 0.0) * span
    moment -= beam.get("line", 0.0) * span**2 / 2
    for column in beam["columns"]:
        if column["x"] < x:
            shear -= column["force"]
            moment -= column["force"] * (x - column["x"]) - column["couple"]
    return shear, moment


def _torque(beam: dict, x: float) -> float:
    hx, hy = beam["lx"] / 2, beam["ly"] / 2
    sy = _S._net(beam["plane"], beam["w"], (-hx, -hy, x, hy))[2] if x > -hx else 0.0
    return sy - sum(column["torque"] for column in beam["columns"] if column["x"] < x)


def _regions(beam: dict) -> list[tuple[float, float]]:
    a, b = beam["columns"]
    return [(-beam["lx"] / 2, a["x"] - a["half"]), (a["x"] + a["half"], b["x"] - b["half"]), (b["x"] + b["half"], beam["lx"] / 2)]


def _faces(beam: dict) -> list[tuple[float, float]]:
    return [(c["x"] + side * c["half"], side) for c in beam["columns"] for side in (-1.0, 1.0)]


def _extreme(beam: dict, low: float, high: float, sign: float) -> list[tuple[float, float]]:
    """Máximos interiores de sign·M en el tramo: barrido y sección áurea."""
    if high - low <= 0:
        return []
    xs = [low + (high - low) * i / SCAN for i in range(SCAN + 1)]
    values = [sign * _shear_moment(beam, x)[1] for x in xs]
    found = []
    for i in range(1, SCAN):
        if values[i] >= values[i - 1] and values[i] >= values[i + 1] and values[i] > min(values[i - 1], values[i + 1]):
            a, b = xs[i - 1], xs[i + 1]
            g = (math.sqrt(5) - 1) / 2
            for _ in range(GOLDEN_STEPS):
                c, d = b - g * (b - a), a + g * (b - a)
                if sign * _shear_moment(beam, c)[1] >= sign * _shear_moment(beam, d)[1]:
                    b = d
                else:
                    a = c
            x = (a + b) / 2
            found.append((x, _shear_moment(beam, x)[1]))
    return found


def _stations(beam: dict, depth: float) -> list[float]:
    """Las x de las estaciones: el mayor momento positivo y el mayor negativo, si los hay (caras y extremos interiores),
    y las secciones a d."""
    candidates = [(x, _shear_moment(beam, x)[1]) for x, _ in _faces(beam)]
    for low, high in _regions(beam):
        candidates += _extreme(beam, low, high, 1.0) + _extreme(beam, low, high, -1.0)
    largest, smallest = max(candidates, key=lambda item: item[1]), min(candidates, key=lambda item: item[1])
    xs = ([largest[0]] if largest[1] > 0 else []) + ([smallest[0]] if smallest[1] < 0 else [])
    for face, side in _faces(beam):
        x = face + side * depth
        if any(low < x < high and low <= face <= high for low, high in _regions(beam)):
            xs.append(x)
    unique: list[float] = []
    for x in sorted(xs):
        if not unique or abs(x - unique[-1]) > 1e-6:
            unique.append(x)
    return unique


def _rows(f: dict) -> list[dict]:
    """Capas de barras x (profundidad desde la cara superior): inferior y, si hay, superior. Con estribos, el
    recubrimiento es al estribo y las barras quedan por dentro de él (D-088)."""
    mat = f["bottom"]
    first = mat["first"]
    cover = f["cover"] + (BARS[f["stirrups"]["designation"]][0] if f.get("stirrups") else 0.0)
    d1 = BARS[mat[first]["designation"]][0]
    db, ab = BARS[mat["x"]["designation"]]
    offset = cover + db / 2 if first == "x" else cover + d1 + db / 2
    n = _F._count(f["ly"], cover, db, mat["x"]["spacing"])
    rows = [{"face": "bottom", "depth": f["h"] - offset, "area": n * ab, "spacing": mat["x"]["spacing"], "cc": offset - db / 2}]
    if f.get("top"):
        db, ab = BARS[f["top"]["designation"]]
        n = _F._count(f["ly"], cover, db, f["top"]["spacing"])
        rows.append({"face": "top", "depth": cover + db / 2, "area": n * ab, "spacing": f["top"]["spacing"], "cc": cover})
    return rows


def _state(layers: list[tuple[float, float]], b: float, h: float) -> dict | None:
    """Compatibilidad de deformaciones con el bloque de Whitney y acero elastoplástico, Pu = 0. layers: (profundidad desde
    la cara comprimida, área). Una barra dentro del bloque descuenta el concreto que desplaza. None sin equilibrio."""

    def forces(c: float) -> tuple[float, list[tuple[float, float, float]]]:
        a = min(BETA1 * c, h)
        steel = []
        for depth, area in layers:
            strain = ECU * (depth - c) / c
            stress = max(-FY, min(FY, ES * strain))
            displaced = 0.85 * FC if depth < BETA1 * c else 0.0
            steel.append((depth, area * (stress + displaced), strain))
        return sum(force for _, force, _ in steel) - 0.85 * FC * b * a, steel

    low, high = 1e-9, h / BETA1
    if forces(low)[0] <= 0 or forces(high)[0] >= 0:
        return None
    for _ in range(300):
        middle = (low + high) / 2
        low, high = (middle, high) if forces(middle)[0] > 0 else (low, middle)
    c = (low + high) / 2
    _, steel = forces(c)
    a = min(BETA1 * c, h)
    nominal = sum(force * depth for depth, force, _ in steel) - 0.85 * FC * b * a * a / 2
    deepest = max(depth for depth, _ in layers)
    return {"c": c, "Mn": nominal, "et": ECU * (deepest - c) / c, "strains": [strain for _, _, strain in steel]}


def _oriented(rows: list[dict], h: float, moment: float) -> list[tuple[float, float]]:
    return [(row["depth"] if moment >= 0 else h - row["depth"], row["area"]) for row in rows]


def _design(profile: dict, layers: list[tuple[float, float]], b: float, h: float) -> float:
    state = _state(layers, b, h)
    return 0.0 if state is None else _F._phi(state["et"], profile) * abs(state["Mn"])


def _side_bars(f: dict, rows: list[dict]) -> list[tuple[float, float, float]]:
    """(profundidad, recubrimiento lateral, área de la capa) de las barras en las caras laterales: la piel, a la
    separación declarada desde la capa inferior hacia arriba y por dentro del estribo, y las capas de torsión (D-090)."""
    out = []
    stirrup = BARS[f["stirrups"]["designation"]][0] if f.get("stirrups") else 0.0
    skin = f.get("skin")
    if skin:
        db, ab = BARS[skin["designation"]]
        bottom_row = next(row for row in rows if row["face"] == "bottom")
        top_row = next((row for row in rows if row["face"] == "top"), None)
        limit = top_row["depth"] if top_row else f["cover"] + stirrup + db / 2
        depth = bottom_row["depth"] - skin["spacing"]
        while depth > limit + 1.0:
            out.append((depth, f["cover"] + stirrup, 2 * ab))
            depth -= skin["spacing"]
    for layer in f.get("torsion_layers", []):
        cc = min(min(bar["x"], f["ly"] - bar["x"]) - BARS[bar["designation"]][0] / 2 for bar in layer["bars"])
        out.append((layer["depth"], cc, sum(BARS[bar["designation"]][1] for bar in layer["bars"])))
    return out


def _skin_check(folder: str, f: dict, rows: list[dict], moment: float) -> dict | None:
    """Refuerzo superficial (ACI 9.7.2.3, NSR-10 C.10.6.7) en la viga larga con h > 900 mm: barras en las dos caras a la
    separación vertical declarada desde la capa inferior hacia arriba; en la zona de h/2 desde la cara en tracción, la
    mayor separación entre la capa en tracción, las barras de piel y el límite h/2 frente al control de agrietamiento
    con cc = recubrimiento (cara lateral)."""
    h = f["h"]
    if h <= 900.0 or moment == 0:
        return None
    clause = CLAUSES[folder]["skin"]
    bottom_row = next(row for row in rows if row["face"] == "bottom")
    top_row = next((row for row in rows if row["face"] == "top"), None)
    tension_depth = bottom_row["depth"] if moment > 0 else (top_row["depth"] if top_row else bottom_row["depth"])
    sides = _side_bars(f, rows)
    zone = [(d, cc) for d, cc, _ in sides if (d >= h / 2 if moment > 0 else d <= h / 2)]
    if not zone:
        return {"name": "Flexion: refuerzo superficial", "status": "FAIL", "clause": clause}
    ordered = sorted((d for d, _ in zone), key=lambda d: abs(d - tension_depth))
    points = [tension_depth, *ordered, h / 2]
    gap = max(abs(b - a) for a, b in zip(points, points[1:], strict=False))
    fs = 2 / 3 * FY
    cc = min(c for _, c in zone)
    limit = min(380 * 280 / fs - 2.5 * cc, 300 * 280 / fs)
    return {"name": "Flexion: refuerzo superficial", "status": "PASS" if gap <= limit else "FAIL", "demand": gap,
            "capacity": limit, "clause": clause}


def _flexure_checks(folder: str, f: dict, rows: list[dict], moment: float, width: float | None = None) -> list[dict]:
    """Resistencia, εt (M3), As,min (M3) con la excepción de 4/3 y la separación por fisuración, como en las vigas. width:
    el ancho de la sección (por omisión, el de la viga larga, ly)."""
    profile, b, h = _F.PROFILES[folder], f["ly"] if width is None else width, f["h"]
    layers = _oriented(rows, h, moment)
    state = _state(layers, b, h)
    assert state is not None
    phi = _F._phi(state["et"], profile)
    checks = [{"name": "Flexion: resistencia", "status": "PASS" if phi * state["Mn"] >= abs(moment) else "FAIL",
               "demand": abs(moment), "capacity": phi * state["Mn"], "clause": CLAUSES[folder]["strength"]}]
    if moment == 0:
        # Sin momento, las reglas de vigas igual emiten εt, As,min y fisuración, que cumplen ("sin momento").
        return checks + [{"name": name, "status": "PASS"} for name in ("Flexion: deformacion neta de traccion (M3)",
                                                                      "Flexion: acero minimo (M3)",
                                                                      "Flexion: separacion por fisuracion")]
    checks.append({"name": "Flexion: deformacion neta de traccion (M3)",
        "status": "PASS" if state["et"] >= profile["strain_min"] else "FAIL",
                   "capacity": state["et"]})
    # As,min: solo el acero a tracción del lado en tracción, más allá de h/2 desde la cara comprimida (D-081).
    tension = [(layer, strain > 0 and layer[0] > h / 2) for layer, strain in zip(layers, state["strains"], strict=True)]
    provided = sum(area for (depth, area), pulled in tension if pulled)
    centroid = sum(depth * area for (depth, area), pulled in tension if pulled) / provided
    d = max(centroid, 0.8 * h)
    as_min = max(0.25 * math.sqrt(FC), 1.4) / FY * b * d
    minimum = {"name": "Flexion: acero minimo (M3)", "capacity": provided, "as_min": as_min, "clause": CLAUSES[folder]["min"]}
    if provided >= as_min:
        minimum.update(status="PASS", demand=as_min)
    else:
        def design(k: float) -> float:
            return _design(profile, [(depth, area * k if pulled else area) for (depth, area), pulled in tension], b, h)

        if design(1.0) < abs(moment):
            minimum.update(status="FAIL", demand=as_min)
        else:
            lo, hi = 0.0, 1.0
            for _ in range(200):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if design(mid) < abs(moment) else (lo, mid)
            effective = min(as_min, 4 / 3 * hi * provided)
            minimum.update(status="PASS" if provided >= effective else "FAIL", demand=effective, analysis=hi * provided)
    checks.append(minimum)
    # El refuerzo superficial solo en la viga larga (width None): las franjas no tienen caras laterales libres (D-083).
    skin = _skin_check(folder, f, rows, moment) if width is None else None
    if skin is not None:
        checks.append(skin)
    face = "bottom" if moment > 0 else "top"
    row = next(row for row in rows if row["face"] == face)
    fs = 2 / 3 * FY
    limit = min(380 * 280 / fs - 2.5 * row["cc"], 300 * 280 / fs)
    checks.append({"name": "Flexion: separacion por fisuracion", "status": "PASS" if row["spacing"] <= limit else "FAIL",
                   "demand": row["spacing"], "capacity": limit, "clause": CLAUSES[folder]["crack"]})
    return checks


def _shear_checks(folder: str, f: dict, rows: list[dict], given: tuple[float, float],
                  section: tuple[float, dict | None] | None = None) -> list[dict]:
    """Cortante de vigas en modo cimentación: d y ρw del acero a tracción (d ≥ 0.8h), Vc de cimentación, Vs de los
    estribos (Vs ≤ 0.66√f'c·b·d) y Av,min si Vu > φVc (ACI 7.6.3.1; NSR-10 no lo exige en zapatas)."""
    shear, moment = given
    b, stirrups = (f["ly"], f.get("stirrups")) if section is None else section
    terms = _vc_d(folder, f, rows, given, b)
    if terms is None:
        return [{"name": "Cortante: resistencia", "status": "BLOCKED"}]
    vc, d = terms
    fyt = 420.0
    transverse = 0.0 if stirrups is None else stirrups["legs"] * BARS[stirrups["designation"]][1] / stirrups["spacing"]
    vs = transverse * fyt * d
    capacity = PHI_SHEAR * (vc + min(vs, 0.66 * math.sqrt(FC) * b * d))
    checks = [{"name": "Cortante: resistencia", "status": "PASS" if abs(shear) <= capacity else "FAIL", "demand": abs(shear),
               "capacity": capacity, "clause": CLAUSES[folder]["shear"]}]
    required = folder == "aci_318_25" and abs(shear) > PHI_SHEAR * vc
    if not required:
        checks.append({"name": "Cortante: refuerzo minimo", "status": "PASS", "clause": CLAUSES[folder]["min_shear"]})
    else:
        av_min = max(0.062 * math.sqrt(FC), 0.35) * b / fyt
        checks.append({"name": "Cortante: refuerzo minimo", "status": "PASS" if transverse >= av_min else "FAIL",
                       "demand": av_min, "capacity": transverse, "clause": CLAUSES[folder]["min_shear"]})
    return checks


def _vc_d(folder: str, f: dict, rows: list[dict], given: tuple[float, float], b: float) -> tuple[float, float] | None:
    """Vc de cimentación y d del acero a tracción (d ≥ 0.8h); None si no hay acero a tracción."""
    shear, moment = given
    h = f["h"]
    layers = _oriented(rows, h, moment)
    state = _state(layers, b, h)
    if state is None or not any(strain > 0 for strain in state["strains"]):
        return None
    pulled = [(depth, area) for (depth, area), strain in zip(layers, state["strains"], strict=True) if strain > 0]
    area = sum(a for _, a in pulled)
    d = max(sum(depth * a for depth, a in pulled) / area, 0.8 * h)
    return _S._one_way_vc(folder, b, d, area / (b * d), abs(shear), abs(moment)), d


def _torsion_checks(folder: str, f: dict, rows: list[dict], given: tuple[float, float, float]) -> list[dict] | None:
    """Torsión de la viga larga (D-088); None si Tu < φTth (el cortante se revisa solo)."""
    shear, moment, torque = given
    b, h, cover, phi, fy = f["ly"], f["h"], f["cover"], 0.75, 420.0
    acp, pcp = b * h, 2 * (b + h)
    limit = phi * 0.083 * math.sqrt(FC) * acp**2 / pcp
    tu, vu = abs(torque), abs(shear)
    if tu == 0 or tu < limit:
        return None
    threshold = {"name": "Torsion: umbral", "status": "PASS", "values": {"Tu": tu, "phi Tth": limit}}
    stirrups = f.get("stirrups")
    if stirrups is None:
        return [threshold, {"name": "Torsion: refuerzo transversal", "status": "FAIL"}]
    terms = _vc_d(folder, f, rows, (shear, moment), b)
    assert terms is not None
    vc, d = terms
    ds, ab = BARS[stirrups["designation"]]
    transverse = stirrups["legs"] * ab / stirrups["spacing"]
    x1, y1 = b - 2 * cover - ds, h - 2 * cover - ds
    aoh, ph = x1 * y1, 2 * (x1 + y1)
    a0 = 0.85 * aoh
    at_s = tu / (phi * 2 * a0 * fy)
    av_s = max(vu / phi - vc, 0.0) / (fy * d)
    ok = stirrups["closed"] and av_s + 2 * at_s <= transverse and at_s <= ab / stirrups["spacing"]
    stress = math.hypot(vu / (b * d), tu * ph / (1.7 * aoh**2))
    stress_limit = phi * (vc / (b * d) + 0.66 * math.sqrt(FC))
    base = 0.42 * math.sqrt(FC) * acp / fy
    al_min = max(min(base - at_s * ph, base - 0.175 * b / fy * ph), 0.0)
    al_required = max(tu * ph / (phi * 2 * a0 * fy), al_min)
    al_provided = sum(area for _, _, area in _side_bars(f, rows))  # capas de torsión y piel (D-090)
    minimum = max(0.062 * math.sqrt(FC), 0.35) * b / fy
    return [threshold,
            {"name": "Torsion: dimensiones de la seccion", "status": "PASS" if stress <= stress_limit else "FAIL",
             "demand": stress, "capacity": stress_limit},
            {"name": "Torsion: refuerzo transversal", "status": "PASS" if ok else "FAIL", "demand": av_s + 2 * at_s,
             "capacity": transverse},
            {"name": "Torsion: refuerzo transversal minimo", "status": "PASS" if transverse >= minimum else "FAIL",
             "demand": minimum, "capacity": transverse},
            {"name": "Torsion: refuerzo longitudinal", "status": "PASS" if al_provided >= al_required else "FAIL",
             "demand": al_required, "capacity": al_provided}]


def _expected(folder: str, f: dict, level: str) -> dict:
    rows = _rows(f)
    profile = _F.PROFILES[folder]
    checks, failures, torques = [], [], []
    for load in f["columns"][0]["loads"]:
        if load["kind"] != "factored":
            continue
        case = load["case"]
        beam = _beam(f, case)
        if beam is None:
            failures.append(case)
            continue
        depth = rows[0]["depth"]
        for x in _stations(beam, depth):
            moment = _shear_moment(beam, x)[1]
            # En una cara de columna, el cortante es el de la sección a d hacia el tramo (ACI 9.4.3.2, 13.2.7.2).
            shear_at = x
            for face, side in _faces(beam):
                at_d = face + side * depth
                if abs(face - x) <= 1e-6 * f["lx"] and any(low < at_d < high and low <= face <= high for low, high in _regions(beam)):
                    shear_at = at_d
            shear = _shear_moment(beam, shear_at)[0]
            torque = _torque(beam, shear_at)
            z = x + f["lx"] / 2
            torques.append({"case": case, "x": x, "at": shear_at, "tu_Nmm": torque})
            torsion = _torsion_checks(folder, f, rows, (shear, moment, torque))
            shear_part = _shear_checks(folder, f, rows, (shear, moment)) if torsion is None else torsion
            if moment < 0 and not f.get("top"):
                station = [_F._plain(f, "x", -moment, case, profile, level), *shear_part]
            else:
                station = _flexure_checks(folder, f, rows, moment) + shear_part
            checks += [{**item, "case": case, "z_mm": z} for item in station]
    maximum = min(3 * f["h"], 450.0)
    for row in rows:
        bars = "barras inferiores x" if row["face"] == "bottom" else "barras superiores x"
        checks.append({"name": f"Viga larga: separacion maxima ({bars})", "status": "PASS" if row["spacing"] <= maximum else "FAIL",
                       "demand": row["spacing"], "capacity": maximum, "clause": CLAUSES[folder]["spacing"]})
    return {"checks": checks, "equilibrium_failures": failures, "torques": torques}


def _load(case: str, p: float, dead: float = 1.2, live: float = 1.6, mx: float = 0.0, my: float = 0.0, vx: float = 0.0,
          vy: float = 0.0, seismic: bool = False) -> dict:
    load = {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": vy,
            "Mx_kNm": mx, "My_kNm": my}
    return {**load, "seismic": True} if seismic else load


def _column(name: str, x: float, loads: list[dict], cx: float = 450.0, cy: float = 450.0, y: float = 0.0) -> dict:
    return {"id": name, "cx": cx, "cy": cy, "x": x, "y": y, "loads": loads}


def _footing(columns: list[dict], **changes: object) -> dict:
    data = {"id": "ZC", "lx": 6000.0, "ly": 2000.0, "h": 700.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns,
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#7", "spacing": 150.0},
                       "y": {"designation": "#5", "spacing": 200.0}},
            "top": {"designation": "#7", "spacing": 150.0, "end": "straight"}}
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


CASES = [
    ("simetrica", "dos columnas iguales simétricas: presión uniforme, momento negativo entre columnas y voladizos",
     _footing([_column("C1", -2000.0, [_load("U1", 1300.0)]), _column("C2", 2000.0, [_load("U1", 1300.0)])])),
    ("borde-desigual", "columna de borde y cargas desiguales (como el manual del ACI): presión trapezoidal",
     _footing([_column("C1", -2700.0, [_load("U1", 900.0)], cx=450.0), _column("C2", 1000.0, [_load("U1", 1600.0)], cx=500.0, cy=500.0)],
              lx=6000.0, ly=2400.0, h=800.0, bottom={"first": "x", "end": "straight", "x": {"designation": "#8", "spacing": 150.0},
                                                       "y": {"designation": "#5", "spacing": 200.0}},
              top={"designation": "#8", "spacing": 150.0, "end": "straight"})),
    ("momentos-sismo", "dos casos: gravedad y sismo con My, Vx, pedestal y columnas desplazadas en Y",
     _footing([_column("C1", -2200.0, [_load("U1", 1100.0, mx=20.0), _load("U2", 800.0, dead=1.0, live=0.5, my=250.0,
         vx=90.0, seismic=True)],
                       y=200.0),
               _column("C2", 2100.0, [_load("U1", 1400.0, mx=-30.0), _load("U2", 1000.0, dead=1.0, live=0.5, my=300.0,
                   vx=110.0, seismic=True)],
                       y=-150.0)], pedestal_height=600.0)),
    ("sin-superior", "sin barras superiores: el momento negativo lo resiste el concreto simple (D-072)",
     _footing([_column("C1", -2000.0, [_load("U1", 500.0)]), _column("C2", 2000.0, [_load("U1", 500.0)])], top=None)),
    ("cortante-no-cumple", "zapata delgada y cargas grandes: no cumple el cortante sin estribos",
     _footing([_column("C1", -2000.0, [_load("U1", 2200.0)]), _column("C2", 2000.0, [_load("U1", 2200.0)])], h=450.0)),
    ("cortante-con-estribos", "la misma zapata delgada con estribos: Vs, Av,min (ACI 7.6.3.1) y d del acero a tracción",
     _footing([_column("C1", -2000.0, [_load("U1", 2200.0)]), _column("C2", 2000.0, [_load("U1", 2200.0)])], h=550.0,
              stirrups={"designation": "#4", "legs": 8, "spacing": 250.0, "closed": True},
              top={"designation": "#8", "spacing": 120.0, "end": "straight"})),
    ("alta-con-piel", "h = 1000 mm (> 900): refuerzo superficial en las dos caras a 200 mm",
     _footing([_column("C1", -2000.0, [_load("U1", 1800.0)]), _column("C2", 2000.0, [_load("U1", 1800.0)])], h=1000.0,
              skin={"designation": "#4", "spacing": 200.0})),
    ("alta-sin-piel", "h = 1000 mm sin refuerzo superficial: no cumple 9.7.2.3 / C.10.6.7",
     _footing([_column("C1", -2000.0, [_load("U1", 1800.0)]), _column("C2", 2000.0, [_load("U1", 1800.0)])], h=1000.0)),
    ("minimo-excepcion", "cargas pequeñas: As < As,min de vigas pero ≥ 4/3 del requerido (excepción)",
     _footing([_column("C1", -1500.0, [_load("U1", 250.0)]), _column("C2", 1500.0, [_load("U1", 250.0)])], lx=4500.0,
              bottom={"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 250.0},
                  "y": {"designation": "#5", "spacing": 250.0}},
              top={"designation": "#5", "spacing": 250.0, "end": "straight"})),
    ("minimo-no-cumple", "As menor que As,min y que 4/3 del requerido",
     _footing([_column("C1", -1200.0, [_load("U1", 1300.0)]), _column("C2", 1200.0, [_load("U1", 1300.0)])],
              bottom={"first": "y", "end": "straight", "x": {"designation": "#4", "spacing": 350.0},
                  "y": {"designation": "#5", "spacing": 200.0}},
              top={"designation": "#8", "spacing": 120.0, "end": "straight"})),
    ("torsion-con-estribos", "columna desplazada 400 mm en Y con Mx y Vy: Tu ≥ φTth, estribos cerrados y capas de Aℓ (D-088)",
     _footing([_column("C1", -2000.0, [_load("U1", 1500.0, mx=-60.0, vy=40.0)], y=400.0),
               _column("C2", 2000.0, [_load("U1", 1500.0)])], h=600.0,
              stirrups={"designation": "#5", "legs": 8, "spacing": 100.0, "closed": True},
              torsion_layers=[{"depth": depth, "role": "torsion",
                               "bars": [{"designation": "#8", "x": x} for x in (150.0, 490.0, 830.0, 1170.0, 1510.0, 1850.0)]}
                              for depth in (250.0, 350.0)])),
    ("piel-como-torsion", "h = 1000 mm, columna desplazada en Y y estribos cerrados: la piel #5 c/200 aporta Aℓ (D-090)",
     _footing([_column("C1", -2000.0, [_load("U1", 1800.0, mx=-80.0)], y=450.0), _column("C2", 2000.0, [_load("U1", 1700.0)])],
              h=1000.0, skin={"designation": "#5", "spacing": 200.0},
              stirrups={"designation": "#5", "legs": 8, "spacing": 120.0, "closed": True})),
    ("torsion-como-piel", "h = 1000 mm sin skin: las capas de torsión cerca de las caras cumplen el refuerzo superficial (D-090)",
     _footing([_column("C1", -2000.0, [_load("U1", 1800.0)]), _column("C2", 2000.0, [_load("U1", 1800.0)])], h=1000.0,
              torsion_layers=[{"depth": depth, "role": "torsion",
                               "bars": [{"designation": "#5", "x": 90.0}, {"designation": "#5", "x": 1910.0}]}
                              for depth in (500.0, 650.0, 800.0)])),
    ("torsion-sin-superior", "sin barras superiores y columna desplazada: concreto simple y torsión sin estribos (D-088)",
     _footing([_column("C1", -2000.0, [_load("U1", 900.0)], y=450.0), _column("C2", 2000.0, [_load("U1", 900.0)], y=-450.0)],
              top=None)),
    ("contacto-parcial", "momento grande: contacto parcial, la carga uniforme supera la presión en un voladizo",
     _footing([_column("C1", -2000.0, [_load("U1", 900.0, my=900.0, live=0.0, dead=1.2)]),
               _column("C2", 2000.0, [_load("U1", 400.0, my=900.0, live=0.0, dead=1.2)])])),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = _F.PROFILES[folder]["levels"]["bajo"]
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing, level)}
                 for case_id, text, footing in CASES]
        data = {"description": "Viga en la dirección larga de zapatas combinadas (D-080, V3J.2): diagramas V y M del cuerpo "
                               "libre con la presión de Bellos y Bakas, resistencia de Whitney, As,min de vigas con la "
                               "excepción de 4/3 y cortante sin estribos.",
                "soil": _C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "seismic_level": level, "tolerance_rel": 1e-7, "cases": cases}
        (HERE / folder / "derived_combined_beam.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
