"""Deriva el oráculo de V3J.3 de las zapatas combinadas (D-080, D-082) para los dos perfiles: punzonamiento por columna,
franjas transversales, malla y fuera de las franjas, desarrollo, aplastamiento y pasadores.

No importa el paquete. Unidades: N y mm. Reutiliza los oráculos independientes de la viga larga (presión, reglas de
vigas), del cortante de zapatas (Jc, carga neta) y de las conexiones (ld, ldh, ldc).

1. Acción de cada columna como carga neta equivalente: F (P más su pedestal menos el relleno y las sobrecargas que
   desplaza) y los momentos estáticos ∫x·q = F·x + My + H·Vx y ∫y·q = F·y − Mx + H·Vy, con H = h + pedestal.
2. Punzonamiento: perímetro a d/2 (d promedio de la malla inferior) recortado con la base; Vu y los momentos respecto al
   centroide del perímetro, de la acción de la columna menos la carga neta dentro del área crítica; vu = vuv + Σγv·M·c/J
   frente a φvc del perfil; As,min por punzonamiento (ACI 8.6.1.2).
3. Franja: ancho columna + d/2 a cada lado dentro de la base; F repartida en el ancho B con la forma de la presión en la
   x de la columna (integral exacta de la recta recortada); momentos en las caras ±Y y a d; en la cara, el cortante de
   la sección a d. Reglas de vigas del oráculo de la viga larga, con el ancho de la franja, las barras y de la malla y el
   refuerzo band en una sola capa.
4. Malla y fuera de las franjas: Ab/s ≥ 0.0018·h y s ≤ min(3h, 450).
5. Desarrollo (con nivel sísmico bajo, para que aplique As requerido/As suministrado en barras rectas): barras x desde
   la sección de mayor momento de su signo; barras y de cada franja desde la cara de la columna.
6. Aplastamiento y pasadores por columna, como en la zapata aislada.

Uso: python tests/oracles/derive_combined_columns.py
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
_S = _load_module("derive_footing_shear")
_K = _load_module("derive_footing_connection")
_F = _B._F

FC, FY = _B.FC, _B.FY
BARS = _B.BARS
PHI = _S.PHI
LEVELS = _K.LEVELS
LEVEL = {folder: LEVELS[folder]["bajo"] for folder in LEVELS}
CLAUSES = {"aci_318_25": {"min_y": "13.3.2.1 y 7.6.1.1", "spacing": "13.3.2.1 y 7.7.2.3"},
           "nsr_10": {"min_y": "C.10.5.4 y C.7.12.2.1", "spacing": "C.10.5.4"}}


def _uniform(low: float, high: float, spacing: float) -> list[float]:
    count = math.floor((high - low) / spacing + 1e-6) + 1
    offset = (high - low - (count - 1) * spacing) / 2
    return [low + offset + i * spacing for i in range(count)]


def _bottom_rows(f: dict) -> dict[str, dict]:
    """Filas de la malla inferior: profundidad desde la cara superior, diámetro, área por barra y posiciones (centradas)."""
    mat = f["bottom"]
    first = mat["first"]
    d1 = BARS[mat[first]["designation"]][0]
    rows = {}
    for direction in ("x", "y"):
        db, ab = BARS[mat[direction]["designation"]]
        offset = f["cover"] + db / 2 if direction == first else f["cover"] + d1 + db / 2
        width = f["ly"] if direction == "x" else f["lx"]
        half = width / 2 - f["cover"] - db / 2
        positions = _uniform(-half, half, mat[direction]["spacing"])
        rows[direction] = {"depth": f["h"] - offset, "db": db, "ab": ab, "positions": positions, "spacing": mat[direction]["spacing"]}
    return rows


def _action(f: dict, beam: dict, index: int, case: str) -> tuple[float, float, float]:
    column = f["columns"][index]
    load = next(load for load in column["loads"] if load["case"] == case)
    force = next(c["force"] for c in beam["columns"] if c["id"] == column["id"])
    height = f["h"] + f["pedestal_height"]
    return (force, force * column["x"] + load["My_kNm"] * 1e6 + height * load["Vx_kN"] * 1e3,
            force * column["y"] - load["Mx_kNm"] * 1e6 + height * load["Vy_kN"] * 1e3)


def _depth(f: dict) -> float:
    rows = _bottom_rows(f)
    return (rows["x"]["depth"] + rows["y"]["depth"]) / 2


def _punching(folder: str, f: dict, beam: dict, index: int, case: str) -> list[dict]:
    c = f["columns"][index]
    depth = _depth(f)
    extents = (c["x"] - (c["cx"] + depth) / 2, c["x"] + (c["cx"] + depth) / 2, c["y"] - (c["cy"] + depth) / 2,
               c["y"] + (c["cy"] + depth) / 2)
    return _punch(folder, f, beam, {"extents": extents, "c": (c["cx"], c["cy"]), "centre": (c["x"], c["y"]),
                                    "total": _action(f, beam, index, case), "where": f"Columna {c['id']}", "case": case,
                                    "indices": [index]})


def _group(folder: str, f: dict, beam: dict, case: str) -> list[dict]:
    """Perímetro común (D-086) si los perímetros individuales se traslapan: el menor rectángulo que contiene los dos
    perímetros (calculado aquí desde sus bordes); el área cargada es ese rectángulo menos d/2 por lado."""
    depth = _depth(f)
    boxes = [(c["x"] - (c["cx"] + depth) / 2, c["x"] + (c["cx"] + depth) / 2, c["y"] - (c["cy"] + depth) / 2,
              c["y"] + (c["cy"] + depth) / 2) for c in f["columns"]]
    (l1, r1, b1, t1), (l2, r2, b2, t2) = boxes
    if r1 <= l2 or r2 <= l1 or t1 <= b2 or t2 <= b1:
        return []
    extents = (min(l1, l2), max(r1, r2), min(b1, b2), max(t1, t2))
    size = (extents[1] - extents[0] - depth, extents[3] - extents[2] - depth)
    centre = ((extents[0] + extents[1]) / 2, (extents[2] + extents[3]) / 2)
    actions = [_action(f, beam, index, case) for index in range(2)]
    total = tuple(a + b for a, b in zip(*actions, strict=True))
    names = " y ".join(c["id"] for c in f["columns"])
    return _punch(folder, f, beam, {"extents": extents, "c": size, "centre": centre, "total": total,
                                    "where": f"Columnas {names} (perimetro comun)", "case": case, "indices": [0, 1]})


def _punch(folder: str, f: dict, beam: dict, spec: dict) -> list[dict]:
    """Punzonamiento de un área cargada: extents = bordes del perímetro sin recortar, c = dimensiones del área cargada,
    centre, total = acción (F, ∫x·q, ∫y·q), where y case."""
    depth = _depth(f)
    hx, hy = f["lx"] / 2, f["ly"] / 2
    left, right, bottom, top = spec["extents"]
    case, where = spec["case"], spec["where"]
    cx, cy = spec["c"]
    x0, x1, y0, y1 = max(left, -hx), min(right, hx), max(bottom, -hy), min(top, hy)
    sides, outside = [], 0
    for present, side in ((bottom > -hy, ((x0, bottom), (x1, bottom))), (right < hx, ((right, y0), (right, y1))),
                          (top < hy, ((x0, top), (x1, top))), (left > -hx, ((left, y0), (left, y1)))):
        if present:
            sides.append(side)
        else:
            outside += 1
    lengths = [abs(e[0] - s[0]) + abs(e[1] - s[1]) for s, e in sides]
    b0 = sum(lengths)
    xc = sum(size * (s[0] + e[0]) / 2 for size, (s, e) in zip(lengths, sides, strict=True)) / b0
    yc = sum(size * (s[1] + e[1]) / 2 for size, (s, e) in zip(lengths, sides, strict=True)) / b0
    total = spec["total"]
    inside = _S._net(beam["plane"], beam["w"], (x0, y0, x1, y1))
    vu = total[0] - inside[0]
    msx, msy = (total[1] - inside[1]) - xc * vu, (total[2] - inside[2]) - yc * vu
    b1, b2 = x1 - x0, y1 - y0
    gx, gy = 1 - 1 / (1 + 2 / 3 * math.sqrt(b1 / b2)), 1 - 1 / (1 + 2 / 3 * math.sqrt(b2 / b1))
    jx, jy = _S._jc(sides, depth, 0, xc), _S._jc(sides, depth, 1, yc)
    vuv = vu / (b0 * depth)
    corners = sorted(([x, y, vuv + gx * msx * (x - xc) / jx + gy * msy * (y - yc) / jy] for x, y in {p for side in sides for p in side}),
                     key=lambda corner: (corner[1], corner[0]))
    stress = max(corner[2] for corner in corners)
    alpha = {0: 40.0, 1: 30.0, 2: 20.0}[outside]
    beta = max(cx, cy) / min(cx, cy)
    if folder == "aci_318_25":
        vc = min(0.33, 0.17 + 0.33 / beta, 0.17 + 0.083 * alpha * depth / b0) * math.sqrt(FC)
    else:
        vc = min(0.17 * (1 + 2 / beta), 0.083 * (alpha * depth / b0 + 2), 0.33) * math.sqrt(FC)
    checks = [{"name": "Punzonamiento", "case": case, "where": where, "status": "PASS" if stress <= PHI * vc else "FAIL",
               "demand": stress, "capacity": PHI * vc, "corners": corners}]
    if folder == "aci_318_25" and vuv > PHI * 0.17 * math.sqrt(FC):
        for direction in ("x", "y"):
            across, centre = (cy, spec["centre"][1]) if direction == "x" else (cx, spec["centre"][0])
            bslab = across + 3 * f["h"]
            required = 5 * vuv * bslab * b0 / (PHI * alpha * FY)
            provided = sum(ab for p, ab in _bars(f, direction, spec["indices"]) if abs(p - centre) <= bslab / 2 + 1e-6)
            checks.append({"name": f"Acero minimo por punzonamiento (barras {direction})", "case": case, "where": where,
                           "status": "PASS" if provided >= required else "FAIL", "demand": required, "capacity": provided})
    checks += _transfer(folder, f, spec, {"x": (msx, 1 - gx), "y": (msy, 1 - gy)})
    return checks


def _bars(f: dict, direction: str, indices: list[int]) -> list[tuple[float, float]]:
    """(posición, área) de las barras inferiores de una dirección: la malla y, en Y, el band de las columnas indicadas."""
    rows = _bottom_rows(f)
    row = rows[direction]
    bars = [(p, row["ab"]) for p in row["positions"]]
    if direction == "y":
        for index in indices:
            c = f["columns"][index]
            band = c.get("band")
            if not band:
                continue
            d = row["depth"]
            x0, x1 = max(c["x"] - c["cx"] / 2 - d / 2, -f["lx"] / 2), min(c["x"] + c["cx"] / 2 + d / 2, f["lx"] / 2)
            db, ab = BARS[band["designation"]]
            edge = f["lx"] / 2 - f["cover"] - db / 2
            bars += [(p, ab) for p in _uniform(max(x0 + db / 2, -edge), min(x1 - db / 2, edge), band["spacing"])]
    return bars


def _transfer(folder: str, f: dict, spec: dict, moments: dict[str, tuple[float, float]]) -> list[dict]:
    """γf·|Msc| frente a la malla inferior en bslab (y el band) y su parte negativa frente a las barras superiores en bslab
    (solo en X) o, sin ellas, al concreto simple si el nivel lo permite; la parte negativa siempre cumple (D-087)."""
    profile = _F.PROFILES[folder]
    rows = _bottom_rows(f)
    cx, cy = spec["c"]
    out = []
    for direction, (msc, gamma_f) in moments.items():
        across, centre = (cy, spec["centre"][1]) if direction == "x" else (cx, spec["centre"][0])
        bslab = across + 3 * f["h"]
        area = sum(ab for p, ab in _bars(f, direction, spec["indices"]) if abs(p - centre) <= bslab / 2 + 1e-6)
        demand = gamma_f * abs(msc)
        nominal, phi, _ = _F._strength(area, bslab, rows[direction]["depth"], profile)
        common = {"case": spec["case"], "where": spec["where"], "demand": demand}
        out.append({**common, "name": f"Transferencia de momento por flexion (barras {direction})",
                    "status": "PASS" if demand <= phi * nominal else "FAIL", "capacity": phi * nominal})
        capacity = 0.0
        if direction == "x" and f.get("top"):
            db, ab = BARS[f["top"]["designation"]]
            n = _F._count(f["ly"], f["cover"], db, f["top"]["spacing"])
            half = f["ly"] / 2 - f["cover"] - db / 2
            start = -half + (2 * half - (n - 1) * f["top"]["spacing"]) / 2
            top_area = sum(ab for i in range(n) if abs(start + i * f["top"]["spacing"] - centre) <= bslab / 2 + 1e-6)
            nominal, phi, _ = _F._strength(top_area, bslab, f["h"] - f["cover"] - db / 2, profile)
            capacity = phi * nominal
        elif LEVEL[folder] in profile["plain_levels"]:
            capacity = 0.60 * 0.42 * math.sqrt(FC) * bslab * (f["h"] - 50.0) ** 2 / 6
        negative = {**common, "name": f"Transferencia de momento: parte negativa (barras {direction})", "status": "PASS",
                    "capacity": capacity}
        if demand > capacity:  # la toma la viga: sin demanda (sin razón) en la zapata
            negative.pop("demand")
        out.append(negative)
    return out


def _strip(f: dict, index: int) -> dict:
    """Ancho de la franja y la capa de barras y (malla dentro de la franja más band) como capa de viga."""
    rows = _bottom_rows(f)
    row = rows["y"]
    c = f["columns"][index]
    d = row["depth"]
    x0, x1 = max(c["x"] - c["cx"] / 2 - d / 2, -f["lx"] / 2), min(c["x"] + c["cx"] / 2 + d / 2, f["lx"] / 2)
    bars = [(p, row["db"], row["ab"]) for p in row["positions"] if x0 - 1e-6 <= p <= x1 + 1e-6]
    band = c.get("band")
    if band:
        db, ab = BARS[band["designation"]]
        edge = f["lx"] / 2 - f["cover"] - db / 2
        bars += [(p, db, ab) for p in _uniform(max(x0 + db / 2, -edge), min(x1 - db / 2, edge), band["spacing"])]
    positions = sorted(p for p, _, _ in bars)
    gap = max((b - a for a, b in zip(positions, positions[1:], strict=False)), default=x1 - x0)
    cc = min(f["h"] - d - db / 2 for _, db, _ in bars)
    return {"x0": x0, "x1": x1, "width": x1 - x0, "depth": d, "bars": [(p - x0, f["h"] - d, ab) for p, _, ab in bars],
            "layer": {"face": "bottom", "depth": d, "area": sum(ab for _, _, ab in bars), "spacing": gap, "cc": cc},
            "spacing": min(row["spacing"], band["spacing"] if band else row["spacing"]), "band": band, "db": row["db"]}


def _along_y(plane: list[float], x: float, y0: float, y1: float) -> tuple[float, float]:
    a, b = plane[0] + plane[1] * x, plane[2]
    lo, hi = y0, y1
    if b == 0:
        if a <= 0:
            return 0.0, 0.0
    else:
        root = -a / b
        lo, hi = (max(lo, root), hi) if b > 0 else (lo, min(hi, root))
    if hi <= lo:
        return 0.0, 0.0
    return a * (hi - lo) + b * (hi**2 - lo**2) / 2, a * (hi**2 - lo**2) / 2 + b * (hi**3 - lo**3) / 3


def _shape(f: dict, beam: dict, index: int, depth: float):  # noqa: ANN202
    """Forma de la carga de la franja (D-085): la presión en la línea de la columna; si es nula, la integrada en el ancho
    de la franja (recorte exacto del plano); si también, uniforme. Devuelve (función (y0, y1) → (∫q, ∫y·q), forma)."""
    c = f["columns"][index]
    half = f["ly"] / 2
    plane = beam["plane"]
    if _along_y(plane, c["x"], -half, half)[0] > 0:
        return (lambda y0, y1: _along_y(plane, c["x"], y0, y1)), "linea"
    x0, x1 = max(c["x"] - c["cx"] / 2 - depth / 2, -f["lx"] / 2), min(c["x"] + c["cx"] / 2 + depth / 2, f["lx"] / 2)

    def strip(y0: float, y1: float) -> tuple[float, float]:
        if y1 <= y0:
            return 0.0, 0.0
        poly = _B._P._clip([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], plane)
        if len(poly) < 3:
            return 0.0, 0.0
        m = _B._P._moments(poly)
        return plane[0] * m[0] + plane[1] * m[1] + plane[2] * m[2], plane[0] * m[2] + plane[1] * m[4] + plane[2] * m[5]

    if strip(-half, half)[0] > 0:
        return strip, "franja"
    return (lambda y0, y1: (y1 - y0, (y1**2 - y0**2) / 2)), "uniforme"


def _strip_sections(f: dict, beam: dict, index: int, case: str, depth: float) -> list[tuple[float, float, float, str]]:
    c = f["columns"][index]
    half = f["ly"] / 2
    shape, _ = _shape(f, beam, index, depth)
    scale = _action(f, beam, index, case)[0] / shape(-half, half)[0]

    def beyond(at: float, side: float) -> tuple[float, float]:
        load, first = shape(at, half) if side > 0 else shape(-half, at)
        return scale * side * (first - at * load), scale * load

    out = []
    for side, face, name in ((1.0, c["y"] + c["cy"] / 2, "+Y"), (-1.0, c["y"] - c["cy"] / 2, "-Y")):
        at_d = face + side * depth
        inside = -half < at_d < half
        moment, shear = beyond(face, side)
        out.append((face, moment, beyond(at_d, side)[1] if inside else shear, f"cara {name}"))
        if inside:
            moment, shear = beyond(at_d, side)
            out.append((at_d, moment, shear, f"a d de la cara {name}"))
    return out


def _biaxial(bars: list[tuple[float, float, float]], b: float, h: float) -> tuple[float, float]:
    """Mn y εt con momento positivo puro (Mn2 = 0) en la sección b × h con barras puntuales (x, y desde abajo, área): el
    eje neutro se inclina con la normal n = (sen α, cos α) y se busca α con Mn2 = 0 (como la resistencia biaxial de las
    vigas, D-046). Bloque de Whitney sobre el polígono recortado; acero elastoplástico; concreto desplazado."""
    rect = [(0.0, 0.0), (b, 0.0), (b, h), (0.0, h)]
    beta, ecu, es = _B.BETA1, _B.ECU, _B.ES

    def state(alpha: float, c: float) -> tuple[float, float, float, float]:
        nx, ny = math.sin(alpha), math.cos(alpha)
        top = max(nx * x + ny * y for x, y in rect)
        poly = _B._P._clip(rect, [beta * c - top, nx, ny])
        m = _B._P._moments(poly) if len(poly) >= 3 else [0.0] * 6
        force = 0.85 * FC * m[0]
        m3 = force * ((m[2] / m[0] if m[0] else 0.0) - h / 2)
        m2 = force * ((m[1] / m[0] if m[0] else 0.0) - b / 2)
        net, deepest = -force, 0.0
        for x, y, area in bars:
            depth = top - (nx * x + ny * y)
            strain = ecu * (depth - c) / c
            stress = max(-FY, min(FY, es * strain))
            tension = area * (stress + (0.85 * FC if depth < beta * c else 0.0))
            net += tension
            m3 -= tension * (y - h / 2)
            m2 -= tension * (x - b / 2)
            deepest = max(deepest, depth)
        return net, m3, m2, ecu * (deepest - c) / c

    def solve(alpha: float) -> tuple[float, float, float]:
        low, high = 1e-9, 2 * h / beta
        for _ in range(200):
            middle = (low + high) / 2
            low, high = (middle, high) if state(alpha, middle)[0] > 0 else (low, middle)
        _, m3, m2, strain = state(alpha, (low + high) / 2)
        return m3, m2, strain

    low, high = -0.6, 0.6
    sign = math.copysign(1.0, solve(low)[1])
    for _ in range(200):
        middle = (low + high) / 2
        if math.copysign(1.0, solve(middle)[1]) == sign:
            low = middle
        else:
            high = middle
    m3, _, strain = solve((low + high) / 2)
    return m3, strain


def _strip_checks(folder: str, f: dict, beam: dict, index: int, case: str) -> list[dict]:
    strip = _strip(f, index)
    where = f"Franja transversal de la columna {f['columns'][index]['id']}"
    out = []
    for y, moment, shear, _ in _strip_sections(f, beam, index, case, strip["depth"]):
        items = _B._flexure_checks(folder, f, [strip["layer"]], moment, strip["width"])
        # Resistencia biaxial (D-046): con las barras asimétricas en la franja, el eje neutro se inclina.
        if moment == 0:
            # Sin momento no hay dirección de flexión: la capacidad biaxial no está definida; solo cuenta que cumple.
            items[0] = {"name": items[0]["name"], "status": "PASS"}
        else:
            nominal, strain = _biaxial(strip["bars"], strip["width"], f["h"])
            capacity = _F._phi(strain, _F.PROFILES[folder]) * nominal
            items[0] = {**items[0], "capacity": capacity, "status": "PASS" if capacity >= abs(moment) else "FAIL"}
        items += _B._shear_checks(folder, f, [strip["layer"]], (shear, moment), (strip["width"], None))
        out += [{**item, "case": case, "z_mm": y + f["ly"] / 2, "where": where} for item in items]
    return out


def _whitney(moment: float, width: float, depth: float) -> float:
    k = 0.85 * FC * width
    return k / FY * (depth - math.sqrt(depth**2 - 2 * moment / (0.9 * k)))


def _ratio(width: float, depth: float, area: float, moment: float) -> float:
    analysis = _whitney(moment, width, depth)
    as_min = max(0.25 * math.sqrt(FC), 1.4) / FY * width * depth
    return min(max(analysis, min(as_min, 4 / 3 * analysis)) / area, 1.0)


def _develop(folder: str, f: dict, bar: tuple[float, float, float, bool], given: tuple[float, float, str, str], level: str) -> dict:
    """bar = (db, separación, profundidad desde la cara opuesta, malla inferior); given = (razón As, disponible, nombre, nota)."""
    db, spacing, depth, bottom = bar
    ratio, available, name, _ = given
    hook = (f["bottom"] if bottom else f["top"])["end"] == "hook"
    permitted = level == LEVELS[folder]["bajo"] and (not hook or folder == "nsr_10")
    excess = ratio if permitted else 1.0
    if hook:
        psi_cc = 0.7 if db <= 36 and f["cover"] >= 65 else 1.0
        required, clause = _K._ldh(folder, db, 1.0, psi_cc, excess), _K.CLAUSES[folder]["hook"]
    else:
        cb = min(f["cover"] + db / 2, spacing / 2)
        below = f["h"] - depth if bottom else depth
        required, clause = _K._ld(folder, db, cb, below, 1.0, excess), _K.CLAUSES[folder]["tension"]
    if excess < 1.0:
        clause += "; " + _K.CLAUSES[folder]["excess"]
    return {"name": name, "status": "PASS" if required <= available else "FAIL", "demand": required, "capacity": available,
            "clause": clause, "where": ""}


def _development(folder: str, f: dict, beams: list[dict], cases: list[str], level: str) -> list[dict]:
    out = []
    positive, negative = (0.0, 0.0), (0.0, 0.0)
    for beam in beams:
        candidates = [(x, _B._shear_moment(beam, x)[1]) for x, _ in _B._faces(beam)]
        for low, high in _B._regions(beam):
            candidates += _B._extreme(beam, low, high, 1.0) + _B._extreme(beam, low, high, -1.0)
        for x, moment in candidates:
            if moment > positive[0]:
                positive = (moment, x)
            if -moment > negative[0]:
                negative = (-moment, x)
    rows = _bottom_rows(f)
    half = f["lx"] / 2
    x_rows = [(positive, rows["x"], "inferiores", True)]
    if f.get("top"):
        db, ab = BARS[f["top"]["designation"]]
        n = _F._count(f["ly"], f["cover"], db, f["top"]["spacing"])
        x_rows.append((negative, {"depth": f["h"] - f["cover"] - db / 2, "db": db, "ab": ab, "positions": [0.0] * n,
                                  "spacing": f["top"]["spacing"]}, "superiores", False))
    for (moment, x), row, label, bottom in x_rows:
        if moment <= 0:
            continue
        # row["depth"]: la altura efectiva, medida desde la cara opuesta a la fila (inferior: desde arriba; superior: desde abajo).
        area = len(row["positions"]) * row["ab"]
        ratio = _ratio(f["ly"], row["depth"], area, moment)
        available = min(x + half, half - x) - f["cover"]
        out.append(_develop(folder, f, (row["db"], row["spacing"], row["depth"], bottom),
                            (ratio, available, f"Desarrollo barras {label} x", ""), level))
    hy = f["ly"] / 2
    for index, c in enumerate(f["columns"]):
        strip = _strip(f, index)
        moment = 0.0
        for beam, case in zip(beams, cases, strict=True):
            sections = _strip_sections(f, beam, index, case, strip["depth"])
            moment = max([moment, *(m for _, m, _, label in sections if label.startswith("cara"))])
        ratio = _ratio(strip["width"], strip["depth"], strip["layer"]["area"], moment)
        available = min(hy - (c["y"] + c["cy"] / 2), c["y"] - c["cy"] / 2 + hy) - f["cover"]
        out.append(_develop(folder, f, (strip["db"], strip["spacing"], strip["depth"], True),
                            (ratio, available, f"Desarrollo barras y (franja de la columna {c['id']})", ""), level))
        band = strip["band"]
        if band and BARS[band["designation"]][0] != strip["db"]:
            out.append(_develop(folder, f, (BARS[band["designation"]][0], strip["spacing"], strip["depth"], True),
                                (ratio, available, f"Desarrollo refuerzo band (columna {c['id']})", ""), level))
    return out


def _connection(folder: str, f: dict, cases: list[str]) -> list[dict]:
    """Pasadores y aplastamiento de cada columna."""
    out: list[dict] = []
    rows = _bottom_rows(f)
    hx, hy = f["lx"] / 2, f["ly"] / 2
    for c in f["columns"]:
        where = f"Columna {c['id']}"
        dowels = c.get("dowels")
        area = None
        if dowels is None:
            out.append({"name": "Pasadores: area minima", "status": "INCOMPLETE", "where": where})
        else:
            db, ab = BARS[dowels["designation"]]
            area = dowels["count"] * ab
            required = 0.005 * c["cx"] * c["cy"]
            out.append({"name": "Pasadores: area minima", "status": "PASS" if area >= required else "FAIL", "demand": required,
                        "capacity": area, "where": where})
            available = f["h"] - f["cover"] - rows["x"]["db"] - rows["y"]["db"]
            ldc = _K._ldc(folder, db)
            out.append({"name": "Pasadores: anclaje a compresion", "status": "PASS" if ldc <= available else "FAIL", "demand": ldc,
                        "capacity": available, "where": where})
        gaps = (hx - (c["x"] + c["cx"] / 2), c["x"] - c["cx"] / 2 + hx, hy - (c["y"] + c["cy"] / 2), c["y"] - c["cy"] / 2 + hy)
        k = min(2 * f["h"], *gaps)
        a1, a2 = c["cx"] * c["cy"], (c["cx"] + 2 * k) * (c["cy"] + 2 * k)
        capacity = 0.65 * 0.85 * FC * a1 * min(math.sqrt(a2 / a1), 2.0)
        for case in cases:
            pu = next(load for load in c["loads"] if load["case"] == case)["P_kN"] * 1e3
            if pu <= 0:
                continue
            out.append({"name": "Aplastamiento en la zapata", "case": case, "where": where, "status": "PASS" if pu <= capacity else "FAIL",
                        "demand": pu, "capacity": capacity, "clause": _K.CLAUSES[folder]["bearing"]})
            if pu > capacity:
                if area is None:
                    out.append({"name": "Pasadores: compresion sobre el aplastamiento", "case": case, "where": where,
                                "status": "INCOMPLETE"})
                else:
                    required = (pu - capacity) / (0.65 * FY)
                    out.append({"name": "Pasadores: compresion sobre el aplastamiento", "case": case, "where": where,
                                "status": "PASS" if area >= required else "FAIL", "demand": required, "capacity": area})
    return out


def _expected(folder: str, f: dict, level: str) -> list[dict]:
    cases = [load["case"] for load in f["columns"][0]["loads"] if load["kind"] == "factored"]
    beams = [_B._beam(f, case) for case in cases]
    assert all(beam is not None for beam in beams)
    checks = []
    for case, beam in zip(cases, beams, strict=True):
        for index in range(len(f["columns"])):
            checks += _punching(folder, f, beam, index, case)
        checks += _group(folder, f, beam, case)
    for index in range(len(f["columns"])):
        for case, beam in zip(cases, beams, strict=True):
            checks += _strip_checks(folder, f, beam, index, case)
    rows = _bottom_rows(f)
    required, provided = 0.0018 * f["h"] * 1000.0, rows["y"]["ab"] / rows["y"]["spacing"] * 1000.0
    maximum = min(3 * f["h"], 450.0)
    checks.append({"name": "Malla inferior y: acero minimo fuera de las franjas", "status": "PASS" if provided >= required else "FAIL",
                   "demand": required, "capacity": provided, "clause": CLAUSES[folder]["min_y"], "where": ""})
    checks.append({"name": "Malla inferior y: separacion maxima", "status": "PASS" if rows["y"]["spacing"] <= maximum else "FAIL",
                   "demand": rows["y"]["spacing"], "capacity": maximum, "clause": CLAUSES[folder]["spacing"], "where": ""})
    checks += _development(folder, f, beams, cases, level)
    checks += _connection(folder, f, cases)
    return checks


def _column(name: str, x: float, loads: list[dict], **changes: object) -> dict:
    data = {"id": name, "cx": 450.0, "cy": 450.0, "x": x, "y": 0.0, "loads": loads,
            "dowels": {"designation": "#6", "count": 4}}
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


def _load(case: str, p: float, **changes: float) -> dict:
    return _B._load(case, p, **changes)


def _footing(columns: list[dict], **changes: object) -> dict:
    data = {"id": "ZC", "lx": 6000.0, "ly": 2400.0, "h": 750.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns,
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#7", "spacing": 150.0},
                       "y": {"designation": "#6", "spacing": 150.0}},
            "top": {"designation": "#7", "spacing": 150.0, "end": "straight"}}
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


BAND = {"designation": "#7", "spacing": 120.0}
CASES = [
    ("interiores", "dos columnas interiores simétricas, con band bajo cada una; barras superiores con gancho y malla recta",
     _footing([_column("C1", -1800.0, [_load("U1", 1300.0)], band=BAND), _column("C2", 1800.0, [_load("U1", 1300.0)], band=BAND)],
              top={"designation": "#7", "spacing": 150.0, "end": "hook"})),
    ("borde", "columna de borde (perímetro de 3 lados, αs = 30), cargas desiguales, sin band",
     _footing([_column("C1", -2775.0, [_load("U1", 900.0)]), _column("C2", 1200.0, [_load("U1", 1800.0)], cx=500.0, cy=500.0)])),
    ("momentos", "dos casos con My, Mx, Vx y columnas desplazadas en Y; pedestal",
     _footing([_column("C1", -2000.0, [_load("U1", 1100.0, mx=40.0), _load("U2", 800.0, dead=1.0, live=0.5, my=250.0, vx=90.0, vy=30.0,
                                                                           seismic=True)], y=200.0, band=BAND),
               _column("C2", 2000.0, [_load("U1", 1400.0, mx=-30.0), _load("U2", 1000.0, dead=1.0, live=0.5, my=300.0, vx=110.0,
                                                                            seismic=True)], y=-150.0)], pedestal_height=600.0)),
    ("ganchos-pasadores", "barras con gancho; columna pequeña y carga alta: el aplastamiento no alcanza y toman los pasadores",
     _footing([_column("C1", -1800.0, [_load("U1", 2600.0)], cx=300.0, cy=300.0, dowels={"designation": "#8", "count": 8}),
               _column("C2", 1800.0, [_load("U1", 2600.0)], cx=300.0, cy=300.0, dowels=None)],
              bottom={"first": "y", "end": "hook", "x": {"designation": "#8", "spacing": 120.0},
                      "y": {"designation": "#5", "spacing": 300.0}}, top={"designation": "#7", "spacing": 150.0, "end": "hook"})),
    ("presion-nula-franja", "C1 en la zona sin presión: su franja toca la zona en contacto (forma integrada en la franja)",
     _footing([_column("C1", -2300.0, [_load("U1", 300.0, live=0.0)], dowels=None),
               _column("C2", 1800.0, [_load("U1", 2500.0, mx=500.0, my=1500.0, live=0.0)], dowels=None)])),
    ("presion-nula-uniforme", "C1 en la zona sin presión y toda su franja sin contacto (carga uniforme F/B)",
     _footing([_column("C1", -2400.0, [_load("U1", 300.0, live=0.0)], dowels=None),
               _column("C2", 1800.0, [_load("U1", 2500.0, my=1500.0, live=0.0)], dowels=None)])),
    ("columnas-juntas", "columnas a 350 mm de cara a cara (menos que d): perímetros traslapados y perímetro común",
     _footing([_column("C1", -400.0, [_load("U1", 1500.0, my=60.0)]), _column("C2", 450.0, [_load("U1", 1800.0, mx=80.0)], cx=500.0)],
              lx=3600.0, ly=2600.0)),
    ("delgada", "zapata delgada: punzonamiento, flexión y cortante de las franjas no cumplen; C2 grande, con A2/A1 < 4",
     _footing([_column("C1", -1800.0, [_load("U1", 2200.0)]), _column("C2", 1800.0, [_load("U1", 2200.0)], cx=1000.0, cy=1000.0)],
              h=450.0)),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = LEVELS[folder]["bajo"]
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing, level)}
                 for case_id, text, footing in CASES]
        data = {"description": "Zapatas combinadas V3J.3 (D-082): punzonamiento por columna, franjas transversales con las reglas "
                               "de vigas, malla y fuera de las franjas, desarrollo, aplastamiento y pasadores.",
                "soil": _B._C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "seismic_level": level, "tolerance_rel": 1e-7, "cases": cases}
        (HERE / folder / "derived_combined_columns.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
