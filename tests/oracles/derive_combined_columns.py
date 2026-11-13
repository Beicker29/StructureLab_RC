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
   la sección a d. Reglas de vigas del oráculo de la viga larga, con el ancho de la franja; capa inferior: el band si lo
   hay (único refuerzo inferior de su zona, D-097) o la malla y; capa superior: las barras superiores transversales que
   caen en la franja (D-097). Momento negativo sin barras superiores: concreto simple. Torsión de placa (D-118): con
   mxy = el mayor |T|/B en los bordes de la franja y mx = 0, Wood-Armer pide abajo M + b·|mxy| y arriba M − b·|mxy|
   (0 si quedan del lado contrario): una estación por cara con momento, el cortante con la primera.
4. Malla y fuera de las franjas: s ≤ min(3h, 450). Torsión de placa (D-118): con my = 0, ±|mxy| por metro en la malla
   y y en las superiores y (o concreto simple sin ellas), con el mayor |mxy| fuera de las franjas. Retracción y
   temperatura por zona (D-097): por metro, inferior más superior de cada dirección ≥ ρ·h (ACI 0.0018; NSR-10 por
   grado, 0.0018 con fy = 420) y cada capa con s ≤ min(5h, 450); zonas: X en todo el ancho, Y fuera de las zonas de
   band y cada zona de band.
5. Desarrollo (con nivel sísmico bajo, para que aplique As requerido/As suministrado en barras rectas): barras x desde
   la sección de mayor momento de su signo; barras inferiores de cada franja (band o malla y) desde la cara de la
   columna con el mayor momento positivo de las caras; superiores transversales con el mayor momento negativo.
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
# Las barras de la zapata combinada se nombran por su dirección (D-101): x es la principal (a lo largo de la viga).
DIRECTIONS = {"x": "direccion principal", "y": "direccion secundaria"}
CLAUSES = {"aci_318_25": {"spacing": "13.3.2.1 y 7.7.2.3", "shrinkage": "24.4.3.2 y 24.4.3.3", "min_spacing": "25.2.1"},
           "nsr_10": {"spacing": "C.10.5.4", "shrinkage": "C.7.12.2.1 y C.7.12.2.2", "min_spacing": "C.7.6.1 y C.3.3.2(c)"}}
AGGREGATE = 19.0  # mm, tamaño máximo nominal del agregado de los casos (D-102)


def _min_spacing(folder: str, f: dict) -> list[dict]:
    """Separación libre mínima (D-102) de cada refuerzo declarado: s − db frente a máx(25 mm, db, 4/3·agregado), igual en
    los dos perfiles (ACI 25.2.1; NSR-10 C.7.6.1 y C.3.3.2(c))."""
    declared = [("barras inferiores, direccion principal", f["bottom"]["x"]),
                ("barras inferiores, direccion secundaria", f["bottom"]["y"])]
    declared += [(f"band, columna {c['id']}", c["band"]) for c in f["columns"] if c.get("band")]
    declared += [(f"band superior, columna {c['id']}", c["band_top"]) for c in f["columns"] if c.get("band_top")]
    top = f.get("top") or {}
    declared += [(f"barras superiores, {DIRECTIONS[d]}", top[d]) for d in ("x", "y") if top.get(d)]
    out = []
    for label, bars in declared:
        db = BARS[bars["designation"]][0]
        clear, required = bars["spacing"] - db, max(25.0, db, 4.0 / 3.0 * AGGREGATE)
        out.append({"name": f"Separacion minima ({label})", "status": "PASS" if clear >= required else "FAIL",
                    "demand": required, "capacity": clear, "clause": CLAUSES[folder]["min_spacing"]})
    return out


def _shrinkage_ratio(folder: str) -> float:
    """ACI 24.4.3.2: 0.0018 para todo fy. NSR-10 C.7.12.2.1 por grado: 0.0020 (fy ≤ 350), 0.0018 (420), 0.0018·420/fy
    ≥ 0.0014 (mayor)."""
    if folder == "aci_318_25":
        return 0.0018
    if FY <= 350.0:
        return 0.0020
    return 0.0018 if FY <= 420.0 else max(0.0018 * 420.0 / FY, 0.0014)


def _limits(f: dict, c: dict, d: float) -> tuple[float, float]:
    return max(c["x"] - c["cx"] / 2 - d / 2, -f["lx"] / 2), min(c["x"] + c["cx"] / 2 + d / 2, f["lx"] / 2)


def _band_positions(f: dict, c: dict, d: float) -> list[float]:
    band = c["band"]
    x0, x1 = _limits(f, c, d)
    db = BARS[band["designation"]][0]
    edge = f["lx"] / 2 - f["cover"] - db / 2
    return _uniform(max(x0 + db / 2, -edge), min(x1 - db / 2, edge), band["spacing"])


def _mesh_y(f: dict) -> list[float]:
    """Posiciones de la malla inferior y fuera de las zonas de band (D-097)."""
    row = _bottom_rows(f)["y"]
    zones = [_limits(f, c, row["depth"]) for c in f["columns"] if c.get("band")]
    return [p for p in row["positions"] if not any(x0 - 1e-6 <= p <= x1 + 1e-6 for x0, x1 in zones)]


def _top_y(f: dict) -> dict | None:
    """Barras superiores y (D-097, D-099): debajo de las x si estas van primero (first, o las únicas x); profundidad desde
    la cara superior."""
    mat = f.get("top") or {}
    top = mat.get("y")
    if not top:
        return None
    db, ab = BARS[top["designation"]]
    nearest = mat.get("first") or "y"
    above = BARS[mat["x"]["designation"]][0] if nearest == "x" and mat.get("x") else 0.0
    half = f["lx"] / 2 - f["cover"] - db / 2
    return {"from_top": f["cover"] + above + db / 2, "db": db, "ab": ab, "spacing": top["spacing"],
            "positions": _uniform(-half, half, top["spacing"]), "cc": f["cover"] + above}


def _band_top(f: dict, c: dict) -> dict | None:
    """El band superior de la columna (D-119): barras y arriba en el ancho de su franja (con la d de la malla y inferior),
    debajo de top.x si esa dirección va más cerca de la cara, como top.y; profundidad desde la cara superior."""
    band = c.get("band_top")
    if not band:
        return None
    db, ab = BARS[band["designation"]]
    mat = f.get("top") or {}
    nearest = mat.get("first") or ("x" if mat.get("x") else "y")
    above = BARS[mat["x"]["designation"]][0] if mat.get("x") and nearest == "x" else 0.0
    x0, x1 = _limits(f, c, _bottom_rows(f)["y"]["depth"])
    edge = f["lx"] / 2 - f["cover"] - db / 2
    positions = _uniform(max(x0 + db / 2, -edge), min(x1 - db / 2, edge), band["spacing"])
    return {"from_top": f["cover"] + above + db / 2, "db": db, "ab": ab, "spacing": band["spacing"], "positions": positions,
            "cc": f["cover"] + above}


def _top_y_outside(f: dict) -> dict | None:
    """top.y fuera de las zonas de band superior (D-119), como la malla y inferior frente al band."""
    top = _top_y(f)
    if top is None:
        return None
    zones = [_limits(f, c, _bottom_rows(f)["y"]["depth"]) for c in f["columns"] if c.get("band_top")]
    return {**top, "positions": [p for p in top["positions"] if not any(x0 - 1e-6 <= p <= x1 + 1e-6 for x0, x1 in zones)]}


def _strip_top(f: dict, c: dict) -> dict | None:
    """Las barras superiores de la franja: el band superior si lo hay (D-119); si no, top.y (D-097)."""
    return _band_top(f, c) or _top_y(f)


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
            low, high, bslab = _S._slab(f, direction, across, centre)
            required = 5 * vuv * bslab * b0 / (PHI * alpha * FY)
            provided = sum(ab for p, ab in _bars(f, direction, spec["indices"]) if low - 1e-6 <= p <= high + 1e-6)
            checks.append({"name": f"Acero minimo por punzonamiento ({DIRECTIONS[direction]})", "case": case, "where": where,
                           "status": "PASS" if provided >= required else "FAIL", "demand": required, "capacity": provided})
    checks += _transfer(folder, f, spec, {"x": (msx, 1 - gx), "y": (msy, 1 - gy)})
    return checks


def _bars(f: dict, direction: str, indices: list[int]) -> list[tuple[float, float]]:
    """(posición, área) de las barras inferiores de una dirección: la malla y (fuera de las zonas de band, D-097) y, en Y,
    el band de las columnas indicadas."""
    rows = _bottom_rows(f)
    row = rows[direction]
    if direction == "x":
        return [(p, row["ab"]) for p in row["positions"]]
    bars = [(p, row["ab"]) for p in _mesh_y(f)]
    for index in indices:
        c = f["columns"][index]
        if c.get("band"):
            bars += [(p, BARS[c["band"]["designation"]][1]) for p in _band_positions(f, c, row["depth"])]
    return bars


def _transfer(folder: str, f: dict, spec: dict, moments: dict[str, tuple[float, float]]) -> list[dict]:
    """γf·|Msc| frente a la malla inferior en bslab (y el band) y su parte negativa frente a las barras superiores en bslab
    (top y band superior) o, sin ellas, al concreto simple si el nivel lo permite; si no alcanzan, no cumple (D-120)."""
    profile = _F.PROFILES[folder]
    rows = _bottom_rows(f)
    cx, cy = spec["c"]
    out = []
    for direction, (msc, gamma_f) in moments.items():
        across, centre = (cy, spec["centre"][1]) if direction == "x" else (cx, spec["centre"][0])
        low, high, bslab = _S._slab(f, direction, across, centre)
        area = sum(ab for p, ab in _bars(f, direction, spec["indices"]) if low - 1e-6 <= p <= high + 1e-6)
        demand = gamma_f * abs(msc)
        nominal, phi, _ = _F._strength(area, bslab, rows[direction]["depth"], profile)
        common = {"case": spec["case"], "where": spec["where"], "demand": demand}
        out.append({**common, "name": f"Transferencia de momento por flexion ({DIRECTIONS[direction]})",
                    "status": "PASS" if demand <= phi * nominal else "FAIL", "capacity": phi * nominal})
        capacity = 0.0
        if direction == "x" and _B.top_x(f):
            top = _B.top_x(f)
            db, ab = BARS[top["designation"]]
            n = _F._count(f["ly"], f["cover"], db, top["spacing"])
            half = f["ly"] / 2 - f["cover"] - db / 2
            start = -half + (2 * half - (n - 1) * top["spacing"]) / 2
            top_area = sum(ab for i in range(n) if low - 1e-6 <= start + i * top["spacing"] <= high + 1e-6)
            nominal, phi, _ = _F._strength(top_area, bslab, f["h"] - f["cover"] - top["above"] - db / 2, profile)
            capacity = phi * nominal
        elif direction == "y" and (tops := [t for t in (_top_y_outside(f), *(_band_top(f, c) for c in f["columns"])) if t]):
            # top.y fuera de las zonas de band superior y el band superior de cada columna (D-119), con la d de la primera.
            top_area = sum(t["ab"] for t in tops for p in t["positions"] if low - 1e-6 <= p <= high + 1e-6)
            if top_area > 0:
                nominal, phi, _ = _F._strength(top_area, bslab, f["h"] - tops[0]["from_top"], profile)
                capacity = phi * nominal
            elif LEVEL[folder] in profile["plain_levels"]:
                capacity = 0.60 * 0.42 * math.sqrt(FC) * bslab * (f["h"] - 50.0) ** 2 / 6
        elif LEVEL[folder] in profile["plain_levels"]:
            capacity = 0.60 * 0.42 * math.sqrt(FC) * bslab * (f["h"] - 50.0) ** 2 / 6
        # D-120: en la combinada la parte negativa la resisten las barras superiores en bslab; si no alcanzan, no cumple.
        out.append({**common, "name": f"Transferencia de momento: parte negativa ({DIRECTIONS[direction]})",
                    "status": "PASS" if demand <= capacity else "FAIL", "capacity": capacity})
    return out


def _strip(f: dict, index: int) -> dict:
    """Ancho de la franja y sus capas de viga: la inferior (el band si lo hay, D-097; si no, la malla y que cae en la
    franja) y la superior (las barras superiores transversales que caen en ella, D-097)."""
    rows = _bottom_rows(f)
    row = rows["y"]
    c = f["columns"][index]
    d = row["depth"]
    x0, x1 = _limits(f, c, d)
    band = c.get("band")
    if band:
        db, ab = BARS[band["designation"]]
        bars = [(p, db, ab) for p in _band_positions(f, c, d)]
    else:
        db, ab = row["db"], row["ab"]
        bars = [(p, db, ab) for p in row["positions"] if x0 - 1e-6 <= p <= x1 + 1e-6]

    def gap(positions: list[float]) -> float:
        ordered = sorted(positions)
        return max((b - a for a, b in zip(ordered, ordered[1:], strict=False)), default=x1 - x0)

    # Barras puntuales para la resistencia biaxial: (x desde el borde −X de la franja, y desde abajo, área).
    points = [(p - x0, f["h"] - d, area) for p, _, area in bars]
    layers = [{"face": "bottom", "depth": d, "area": sum(area for _, _, area in bars), "spacing": gap([p for p, _, _ in bars]),
               "cc": f["h"] - d - db / 2}]
    top = _strip_top(f, c)  # el band superior o top.y (D-119)
    inside = [] if top is None else [p for p in top["positions"] if x0 - 1e-6 <= p <= x1 + 1e-6]
    if inside and top is not None:
        points += [(p - x0, f["h"] - top["from_top"], top["ab"]) for p in inside]
        layers.append({"face": "top", "depth": top["from_top"], "area": len(inside) * top["ab"], "spacing": gap(inside),
                       "cc": top["cc"]})
    return {"x0": x0, "x1": x1, "width": x1 - x0, "depth": d, "bars": points, "layers": layers, "top": bool(inside),
            "bottom_area": layers[0]["area"], "top_area": len(inside) * (top["ab"] if top else 0.0),
            "spacing": band["spacing"] if band else row["spacing"], "band": band, "db": db, "top_bars": top}


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
    """Secciones de la franja con su carga neta (D-095): q(y) = s·forma(y) − w·b, con b el ancho de la franja, w la carga
    uniforme mayorada (zapata, relleno y sobrecargas) y s tal que ∫q dy = F de la columna. Caras, a d de ellas y el mayor
    momento negativo de cada voladizo (64 puntos entre la cara y el borde) si no está en la cara."""
    c = f["columns"][index]
    half = f["ly"] / 2
    shape, _ = _shape(f, beam, index, depth)
    x0, x1 = max(c["x"] - c["cx"] / 2 - depth / 2, -f["lx"] / 2), min(c["x"] + c["cx"] / 2 + depth / 2, f["lx"] / 2)
    uniform = beam["w"] * (x1 - x0)
    scale = (_action(f, beam, index, case)[0] + uniform * f["ly"]) / shape(-half, half)[0]

    def beyond(at: float, side: float) -> tuple[float, float]:
        y0, y1 = (at, half) if side > 0 else (-half, at)
        load, first = shape(y0, y1)
        net = scale * load - uniform * (y1 - y0)
        net_first = scale * first - uniform * (y1**2 - y0**2) / 2
        return side * (net_first - at * net), abs(net)

    out = []
    for side, face, name in ((1.0, c["y"] + c["cy"] / 2, "+Y"), (-1.0, c["y"] - c["cy"] / 2, "-Y")):
        at_d = face + side * depth
        inside = -half < at_d < half
        face_moment, shear = beyond(face, side)
        out.append((face, face_moment, beyond(at_d, side)[1] if inside else shear, f"cara {name}"))
        if inside:
            moment, shear = beyond(at_d, side)
            out.append((at_d, moment, shear, f"a d de la cara {name}"))
        points = [face + side * (half - side * face) * k / 64 for k in range(1, 64)]
        y = min(points, key=lambda point: beyond(point, side)[0])
        moment, shear = beyond(y, side)
        if moment < -1e3 and moment < face_moment:
            out.append((y, moment, shear, f"mayor M negativo hacia el borde {name}"))
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


def strip_twist(f: dict, beam: dict, strip: dict) -> float:
    """|mxy| de la franja (D-118): el mayor |T|/B en sus dos bordes x0 y x1, a cada lado del par de la columna."""
    return max(abs(_B._torque(beam, strip["x0"])), abs(_B._torque(beam, strip["x1"]))) / f["ly"]


def strip_moments(moment: float, width: float, twist: float) -> list[float]:
    """Wood-Armer de la franja con mx = 0 (D-118), escrito aparte: my = M/b; la cara inferior pide my + |mxy| (0 si queda
    negativo) y la superior my − |mxy| (0 si queda positivo). Por b: los que no son nulos; sin ninguno, [M]."""
    bottom, top = max(moment + twist * width, 0.0), min(moment - twist * width, 0.0)
    return [value for value in (bottom, top) if value != 0] or [moment]


def _strip_checks(folder: str, f: dict, beam: dict, index: int, case: str) -> list[dict]:
    strip = _strip(f, index)
    where = f"Franja transversal de la columna {f['columns'][index]['id']}"
    out = []
    twist = strip_twist(f, beam, strip)
    # Cortante por la torsión de placa en la franja (D-119): el salto de T entre sus bordes repartido en su ancho b, por b.
    torsion_shear = abs(_B._torque(beam, strip["x1"]) - _B._torque(beam, strip["x0"])) / f["ly"]
    for y, physical, shear, _ in _strip_sections(f, beam, index, case, strip["depth"]):
        for order, moment in enumerate(strip_moments(physical, strip["width"], twist)):
            # Una estación por cara con momento de Wood-Armer; el cortante (flexión + torsión) con la primera (D-118).
            out += [{**item, "face": "top" if moment < 0 else "bottom"}
                    for item in _strip_station(folder, f, (beam, index, case), (y, moment, shear + torsion_shear, order), where)]
    return out


def _strip_station(folder: str, f: dict, given: tuple[dict, int, str], section: tuple[float, float, float, int],
                   where: str) -> list[dict]:
    """Una estación de la franja: la flexión con el momento de diseño y, en la primera (order 0), el cortante."""
    _, index, case = given
    y, moment, shear, order = section
    strip = _strip(f, index)
    layers = strip["layers"]
    shear_items = _beam_shear(_B._shear_checks(folder, f, layers, (shear, moment), (strip["width"], None))) if order == 0 else []
    if moment < 0 and not strip["top"]:
        # Sin barras superiores transversales: concreto simple en el ancho de la franja (D-072, D-095) y el cortante.
        plain = {**_F._plain({**f, "lx": strip["width"]}, "y", -moment, case, _F.PROFILES[folder], LEVEL[folder]),
                 "name": "Flexion concreto simple (cara superior, direccion secundaria)"}
        items = [plain, *shear_items]
    else:
        items = _B._flexure_checks(folder, f, layers, moment, strip["width"])
        # Resistencia biaxial (D-046): con las barras asimétricas en la franja, el eje neutro se inclina.
        if moment == 0:
            # Sin momento no hay dirección de flexión: la capacidad biaxial no está definida; solo cuenta que cumple.
            items[0] = {"name": items[0]["name"], "status": "PASS"}
        else:
            # Momento negativo: la sección reflejada (y → h − y) con momento positivo.
            bars = strip["bars"] if moment > 0 else [(x, f["h"] - y0, area) for x, y0, area in strip["bars"]]
            nominal, strain = _biaxial(bars, strip["width"], f["h"])
            capacity = _F._phi(strain, _F.PROFILES[folder]) * nominal
            items[0] = {**items[0], "capacity": capacity, "status": "PASS" if capacity >= abs(moment) else "FAIL"}
        if moment < 0:
            # D-116: el momento negativo de la franja lo toma la viga de cimentación; no se exige el As,min por flexión.
            items = [{"name": item["name"], "status": "PASS", "capacity": item["capacity"]}
                     if item["name"] == "Flexion: acero minimo (M3)" else item for item in items]
        items += shear_items
    return [{**item, "case": case, "z_mm": y + f["ly"] / 2, "where": where} for item in items]


def _plate_outside(folder: str, f: dict, beam: dict, case: str) -> list[dict]:
    """Barras y fuera de las franjas con la torsión de placa (D-118): my = 0, así que Wood-Armer pide +|mxy| abajo y
    −|mxy| arriba, por metro, con el mayor |mxy| = |T|/B fuera de las franjas (64 tramos del largo y los bordes de cada
    franja). Abajo, la malla y; arriba, las barras superiores y o, sin ellas, concreto simple por metro (D-072)."""
    rows = _bottom_rows(f)
    zones = [_limits(f, c, rows["y"]["depth"]) for c in f["columns"]]
    half = f["lx"] / 2
    points = [-half + f["lx"] * k / 64 for k in range(65)] + [edge for zone in zones for edge in zone]
    outside = [x for x in points if not any(x0 + 1e-6 < x < x1 - 1e-6 for x0, x1 in zones)]
    twist = max((abs(_B._torque(beam, x)) / f["ly"] for x in outside), default=0.0)
    if twist <= 1.0:
        return []
    demand = twist * 1000.0
    profile = _F.PROFILES[folder]

    def strength(name: str, depth: float, area: float, spacing: float) -> dict:
        per_metre = area * 1000.0 / spacing
        state = _B._state([(depth, per_metre)], 1000.0, f["h"])
        assert state is not None
        capacity = _F._phi(state["et"], profile) * state["Mn"]
        return {"name": name, "status": "PASS" if capacity >= demand else "FAIL", "demand": demand, "capacity": capacity}

    name = "Direccion secundaria: torsion de placa"
    out = [strength(f"{name} (barras inferiores)", rows["y"]["depth"], rows["y"]["ab"], rows["y"]["spacing"])]
    top = _top_y_outside(f)
    # Cortante de placa (D-119): qy = (dT/dx)/B = |∫y·p dy|/B en la línea x (la carga uniforme es simétrica), el mayor
    # fuera de las franjas, frente a φVc por metro con la malla y inferior y Mu = |mxy| en esa sección.
    xs, qy = max(((x, abs(_along_y(beam["plane"], x, -f["ly"] / 2, f["ly"] / 2)[1]) / f["ly"]) for x in outside),
                 key=lambda item: item[1])
    vu = qy * 1000.0
    if vu > 1.0:
        d = rows["y"]["depth"]
        rho = rows["y"]["ab"] * 1000.0 / rows["y"]["spacing"] / (1000.0 * d)
        vc = _S._one_way_vc(folder, 1000.0, d, rho, vu, abs(_B._torque(beam, xs)) / f["ly"] * 1000.0)
        out.append({"name": f"{name}, cortante", "status": "PASS" if vu <= PHI * vc else "FAIL", "demand": vu,
                    "capacity": PHI * vc})
    if top is not None:
        out.append(strength(f"{name} (barras superiores)", f["h"] - top["from_top"], top["ab"], top["spacing"]))
    else:
        out.append({**_F._plain({**f, "lx": 1000.0}, "y", demand, case, profile, LEVEL[folder]),
                    "name": "Direccion secundaria: torsion de placa, concreto simple (cara superior)"})
    return [{**item, "case": case, "where": ""} for item in out]


def _beam_shear(items: list[dict]) -> list[dict]:
    """Franja sin estribos con Vu > φVc (D-103): cumple con DCR = 0.99 (demanda = 0.99·φVc, D-114) y el excedente
    Vu − φVc lo toma el refuerzo transversal de la viga de cimentación; el Av,min que exigiría la franja también."""
    out = []
    for item in items:
        if item["status"] == "FAIL" and item["name"] == "Cortante: resistencia":
            item = {**item, "status": "PASS", "demand": 0.99 * item["capacity"], "excess": item["demand"] - item["capacity"]}
        elif item["status"] == "FAIL" and item["name"] == "Cortante: refuerzo minimo":
            item = {**item, "status": "PASS"}
        out.append(item)
    return out


def _whitney(moment: float, width: float, depth: float) -> float:
    k = 0.85 * FC * width
    return k / FY * (depth - math.sqrt(depth**2 - 2 * moment / (0.9 * k)))


def _ratio(width: float, depth: float, area: float, moment: float, exception: bool) -> float:
    """As requerido / suministrado del desarrollo: el mayor entre el de análisis y el mínimo de vigas; con la excepción de
    4/3 declarada (D-123), el mínimo es el menor entre As,min y 4/3 del de análisis."""
    analysis = _whitney(moment, width, depth)
    as_min = max(0.25 * math.sqrt(FC), 1.4) / FY * width * depth
    minimum = min(as_min, 4 / 3 * analysis) if exception else as_min
    return min(max(analysis, minimum) / area, 1.0)


def _develop(folder: str, f: dict, bar: tuple[float, float, float, str], given: tuple[float, float, str, str], level: str) -> dict:
    """bar = (db, separación, profundidad desde la cara opuesta, capa: "bottom" o "top", cuyo end aplica, D-099); given =
    (razón As, disponible, nombre, nota)."""
    db, spacing, depth, layer = bar
    bottom = layer == "bottom"
    ratio, available, name, _ = given
    hook = (f.get(layer) or f["bottom"])["end"] == "hook"  # el band superior sin top termina como la malla inferior
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
        for x, _ in candidates:
            bottom, top = _B.plate_moments(beam, x)  # Wood-Armer de las barras x (D-118)
            if bottom > positive[0]:
                positive = (bottom, x)
            if -top > negative[0]:
                negative = (-top, x)
    rows = _bottom_rows(f)
    half = f["lx"] / 2
    x_rows = [(positive, rows["x"], "inferiores", "bottom")]
    top_x = _B.top_x(f)
    if top_x:
        db, ab = BARS[top_x["designation"]]
        n = _F._count(f["ly"], f["cover"], db, top_x["spacing"])
        x_rows.append((negative, {"depth": f["h"] - f["cover"] - top_x["above"] - db / 2, "db": db, "ab": ab,
                                  "positions": [0.0] * n, "spacing": top_x["spacing"]}, "superiores", "top"))
    for (moment, x), row, label, bottom in x_rows:
        if moment <= 0:
            continue
        # row["depth"]: la altura efectiva, medida desde la cara opuesta a la fila (inferior: desde arriba; superior: desde abajo).
        area = len(row["positions"]) * row["ab"]
        ratio = _ratio(f["ly"], row["depth"], area, moment, f["min_steel_exception"])
        available = min(x + half, half - x) - f["cover"]
        out.append(_develop(folder, f, (row["db"], row["spacing"], row["depth"], bottom),
                            (ratio, available, f"Desarrollo barras {label}, direccion principal", ""), level))
    hy = f["ly"] / 2
    for index, c in enumerate(f["columns"]):
        strip = _strip(f, index)
        top = strip["top_bars"]  # el band superior o top.y (D-119)
        positive_y = negative_y = 0.0
        for beam, case in zip(beams, cases, strict=True):
            sections = _strip_sections(f, beam, index, case, strip["depth"])
            twist = strip_twist(f, beam, strip)
            design = [(strip_moments(m, strip["width"], twist), label) for _, m, _, label in sections]
            positive_y = max([positive_y, *(v for values, label in design if label.startswith("cara") for v in values)])
            negative_y = max([negative_y, *(-v for values, _ in design for v in values)])
        available = min(hy - (c["y"] + c["cy"] / 2), c["y"] - c["cy"] / 2 + hy) - f["cover"]
        if positive_y > 0 and strip["bottom_area"] > 0:
            ratio = _ratio(strip["width"], strip["depth"], strip["bottom_area"], positive_y, f["min_steel_exception"])
            name = (f"Desarrollo refuerzo band (columna {c['id']})" if strip["band"]
                    else f"Desarrollo barras inferiores, direccion secundaria (franja de la columna {c['id']})")
            out.append(_develop(folder, f, (strip["db"], strip["spacing"], strip["depth"], "bottom"), (ratio, available, name, ""), level))
        if top is not None and negative_y > 1e3 and strip["top_area"] > 0:
            depth = f["h"] - top["from_top"]
            ratio = _ratio(strip["width"], depth, strip["top_area"], negative_y, f["min_steel_exception"])
            name = (f"Desarrollo band superior (columna {c['id']})" if c.get("band_top")
                    else f"Desarrollo barras superiores, direccion secundaria (franja de la columna {c['id']})")
            out.append(_develop(folder, f, (top["db"], top["spacing"], depth, "top"), (ratio, available, name, ""), level))
    return out


def _shrinkage(folder: str, f: dict) -> list[dict]:
    """Retracción y temperatura por zona (D-097): Ab·1000/s sumado de las capas inferior y superior frente a ρ·h·1000 y
    la separación de cada capa frente a min(5h, 450)."""
    ratio, h = _shrinkage_ratio(folder), f["h"]
    required, maximum = ratio * h * 1000.0, min(5 * h, 450.0)
    clause = CLAUSES[folder]["shrinkage"]
    mat = f.get("top") or {}
    top_x = [("superiores", mat["x"])] if mat.get("x") else []
    top_y = [("superiores", mat["y"])] if mat.get("y") else []
    banded = [c for c in f["columns"] if c.get("band") or c.get("band_top")]
    zones = [("x", "en todo el ancho", [("inferiores", f["bottom"]["x"]), *top_x]),
             ("y", "fuera de las zonas de band" if banded else "en todo el largo", [("inferiores", f["bottom"]["y"]), *top_y])]
    # Cada zona de band: abajo el band o la malla y; arriba el band superior o top.y (D-119).
    zones += [("y", f"zona de band de la columna {c['id']}",
               [("band", c["band"]) if c.get("band") else ("inferiores", f["bottom"]["y"]),
                *([("band superior", c["band_top"])] if c.get("band_top") else top_y)]) for c in banded]
    out = []
    for direction, zone, layers in zones:
        provided = sum(BARS[bars["designation"]][1] * 1000.0 / bars["spacing"] for _, bars in layers)
        out.append({"name": f"Retraccion y temperatura: cuantia ({DIRECTIONS[direction]}, {zone})",
                    "status": "PASS" if provided >= required else "FAIL", "demand": required, "capacity": provided,
                    "clause": clause, "where": ""})
        out += [{"name": f"Retraccion y temperatura: separacion ({DIRECTIONS[direction]}, {label}, {zone})",
                 "status": "PASS" if bars["spacing"] <= maximum else "FAIL", "demand": bars["spacing"], "capacity": maximum,
                 "clause": clause, "where": ""} for label, bars in layers]
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
    maximum = min(3 * f["h"], 450.0)
    checks += _shrinkage(folder, f)
    checks.append({"name": "Direccion secundaria: separacion maxima (malla inferior)",
                   "status": "PASS" if rows["y"]["spacing"] <= maximum else "FAIL", "demand": rows["y"]["spacing"],
                   "capacity": maximum, "clause": CLAUSES[folder]["spacing"], "where": ""})
    for case, beam in zip(cases, beams, strict=True):
        checks += _plate_outside(folder, f, beam, case)
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
    data = {"id": "ZC", "min_steel_exception": False,
            "lx": 6000.0, "ly": 2400.0, "h": 750.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns,
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#7", "spacing": 150.0},
                       "y": {"designation": "#6", "spacing": 150.0}},
            "top": _B.top_mat("#7", 150.0, "straight")}
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


BAND = {"designation": "#7", "spacing": 120.0}
CASES = [
    ("interiores", "dos columnas interiores simétricas, con band bajo cada una; barras superiores con gancho y malla recta",
     _footing([_column("C1", -1800.0, [_load("U1", 1300.0)], band=BAND), _column("C2", 1800.0, [_load("U1", 1300.0)], band=BAND)],
              top=_B.top_mat("#7", 150.0, "hook"))),
    ("band-apretado", "el caso anterior con el band de C1 a 50 mm: separación libre 24.6 mm, menor que la mínima (D-102)",
     _footing([_column("C1", -1800.0, [_load("U1", 1300.0)], band={"designation": "#8", "spacing": 50.0}),
               _column("C2", 1800.0, [_load("U1", 1300.0)], band=BAND)], top=_B.top_mat("#7", 150.0, "hook"))),
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
                      "y": {"designation": "#5", "spacing": 300.0}}, top=_B.top_mat("#7", 150.0, "hook"))),
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
    ("negativo-transversal", "Mx grande en las dos columnas (D-095): la presión en la línea de cada columna se anula hacia −Y, "
                             "la carga uniforme manda en ese voladizo y aparece el momento negativo transversal",
     _footing([_column("C1", -1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)]),
               _column("C2", 1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)])], ly=3000.0)),
    ("superior-transversal", "el caso anterior con barras superiores transversales (D-097): el momento negativo de las "
                             "franjas lo toman esas barras; band solo en C1 (único refuerzo inferior de su franja) y la "
                             "malla y fuera de su zona; retracción y temperatura por zona",
     _footing([_column("C1", -1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)], band=BAND),
               _column("C2", 1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)])], ly=3000.0,
              top=_B.top_mat("#7", 150.0, "straight", y=("#5", 200.0), first="x"))),
    ("superior-primero-y", "el caso anterior con las barras superiores y más cerca de la cara superior (top.first = y, "
                           "D-099): las x quedan debajo de ellas y las y suben",
     _footing([_column("C1", -1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)], band=BAND),
               _column("C2", 1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)])], ly=3000.0,
              top=_B.top_mat("#7", 150.0, "straight", y=("#5", 200.0), first="y"))),
    ("band-superior", "D-119: band superior #6 c/150 en C1 (sus barras superiores de franja); top.y #5 c/200 solo fuera de "
                      "su zona; C1 corrida en Y con Mx: torsión de placa, su cortante fuera de las franjas y la retracción "
                      "de la zona con el band superior",
     _footing([_column("C1", -1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)], y=300.0, band=BAND,
                       band_top={"designation": "#6", "spacing": 150.0}),
               _column("C2", 1800.0, [_load("U1", 1000.0, mx=-1100.0, live=0.0)])], ly=3000.0,
              top=_B.top_mat("#7", 150.0, "straight", y=("#5", 200.0), first="x"))),
    ("band-superior-sin-top", "D-119: band superior en las dos columnas y sin barras superiores: fuera de las franjas, la "
                              "torsión de placa superior en concreto simple y el band superior termina como la malla",
     _footing([_column("C1", -1800.0, [_load("U1", 1000.0, mx=-600.0, live=0.0)], y=300.0,
                       band_top={"designation": "#5", "spacing": 150.0}),
               _column("C2", 1800.0, [_load("U1", 1000.0, mx=-600.0, live=0.0)], band_top={"designation": "#5", "spacing": 200.0})],
              ly=3000.0, top=None)),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = LEVELS[folder]["bajo"]
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing, level),
                  "min_spacing": _min_spacing(folder, footing)} for case_id, text, footing in CASES]
        data = {"description": "Zapatas combinadas V3J.3 (D-082): punzonamiento por columna, franjas transversales con las reglas "
                               "de vigas, malla y fuera de las franjas, desarrollo, aplastamiento y pasadores.",
                "soil": _B._C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated",
                                                  "max_aggregate": AGGREGATE},
                "seismic_level": level, "tolerance_rel": 1e-7, "cases": cases}
        (HERE / folder / "derived_combined_columns.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
