"""Deriva el oráculo del despiece (D-125) para los dos perfiles. No importa el paquete.

Datos de la norma, leídos de los PDF:
- ACI 318-25, Tabla 25.3.1: doblado 6db (No. 10–25), 8db (No. 29–36); extensión 12db (90°), máx(4db, 65 mm) (180°).
  Tabla 25.3.2 (estribos): doblado 4db (No. 10–16), 6db (No. 19–25); 135° con máx(6db, 75 mm).
  25.5.2.1: máx(1.0ℓd, 300) clase A, máx(1.3ℓd, 300) clase B; 25.5.5.1: máx(0.071fy·db, 300) con fy ≤ 420 MPa.
- NSR-10, C.7.1 y Tabla C.7.2: los mismos doblados y extensiones de ganchos estándar; estribos No. 5 y menores con
  doblado 4db; 135° con 6db, sin mínimo de 75 mm (C.7.1.3(c)). C.12.15.1 y C.12.16.1: los mismos empalmes.

Geometría (independiente de detailing/schedule.py), convención de DL-NET (decisión del usuario, D-147):
- Barra con ganchos y tramo horizontal exterior A: longitud total = A (hacia arriba a 10 mm) + la de cada gancho (hacia
  arriba a 50 mm): L = extensión + π·(D + 0.5db)/8 con 90° y U = extensión + 0.5·π·(D + 0.5db) − 0.5·(D + 0.5db) con 180°.
- Estribo cerrado de W × H exteriores con ganchos de 135°, como DL-NET (decisión del usuario, D-160):
  g = extensión + (3π/4)·(D/2 + db/2) − 0.5·(D + 0.5db), hacia arriba a 10 mm; L = 2(W + H) + 2g, con W y H hacia
  arriba a 10 mm.
- Barra recta de largo L > longitud comercial S con traslapo t: el patrón A corta S, S, …; el patrón B empieza con S/2;
  cada pieza hacia arriba a 10 mm.

Clase del empalme (D-129): ACI Tabla 25.5.2.1 y NSR-10 C.12.15.2, clase A si As provisto / As requerido por análisis
≥ 2 y se empalma la mitad o menos. As requerido de una sección rectangular b × h con una capa a d, bloque de Whitney
(β1 = 0.85 con f'c = 28 MPa), controlada por tracción (φ = 0.9, se comprueba εt ≥ 0.005):
    Mu = φ·As·fy·(d − As·fy/(1.7·f'c·b))  →  As = [d − √(d² − 2Mu/(φ·0.85·f'c·b))]·0.85·f'c·b/fy.

Uso: python tests/oracles/derive_detailing.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
BARS = {"#4": 12.7, "#5": 15.9, "#6": 19.1, "#9": 28.7}  # mm
FY, FC = 420.0, 28.0


def round_up(x: float, step: float = 10.0) -> float:
    return math.ceil(x / step - 1e-9) * step


def hook(folder: str, db: float) -> dict:
    bend = (6.0 if db <= 25.9 else 8.0) * db
    return {"bend": bend, "ext90": 12.0 * db, "ext180": max(4.0 * db, 65.0)}


def stirrup(folder: str, db: float) -> dict:
    bend = (4.0 if db <= 16.4 else 6.0) * db
    ext135 = max(6.0 * db, 75.0) if folder == "aci_318_25" else 6.0 * db
    return {"bend": bend, "ext135": ext135}


def u_bar(folder: str, db: float, a: float, angle: int = 90) -> dict:
    """Barra con el mismo gancho en los dos extremos (90° o 180°), convención de DL-NET (D-147)."""
    h = hook(folder, db)
    base = h["bend"] + 0.5 * db
    raw = h["ext90"] + math.pi * base / 8 if angle == 90 else h["ext180"] + 0.5 * math.pi * base - 0.5 * base
    leg = round_up(raw, 50.0)
    return {"cut": round_up(a) + 2 * leg, "leg": leg}


def closed_stirrup(folder: str, db: float, w: float, h_: float) -> dict:
    s = stirrup(folder, db)
    g = round_up(s["ext135"] + 0.75 * math.pi * (s["bend"] / 2 + db / 2) - 0.5 * (s["bend"] + 0.5 * db))
    return {"g": g, "cut": 2 * (round_up(w) + round_up(h_)) + 2 * g}


def spliced(length: float, stock: float, lap: float, first: float) -> list[float]:
    cuts, start, size = [], 0.0, first
    while start + size < length:
        cuts.append(size)
        start, size = start + size - lap, stock
    cuts.append(length - start)
    return [round_up(c) for c in cuts]


def tension_lap(db: float, cb: float) -> dict:
    """ℓd de una barra inferior sin recubrimiento epóxico, concreto normal (λ = 1), Ktr = 0, sin el mínimo de 300 mm:
    ACI 25.4.2.4a y NSR-10 (C.12-1) coinciden para fy = 420 MPa (ψg = 1): fy/(1.1√f'c)·ψs/(cb/db)·db."""
    psi_s = 0.8 if db < 21.0 else 1.0
    ld = FY / (1.1 * math.sqrt(FC)) * psi_s / min(cb / db, 2.5) * db
    return {"ld": ld, "A": max(ld, 300.0), "B": max(1.3 * ld, 300.0)}


def required_steel(b: float, d: float, mu: float) -> float:
    """As por análisis con φ = 0.9 (comprueba que la sección queda controlada por tracción)."""
    k = 0.85 * FC * b
    area = (d - math.sqrt(d * d - 2.0 * mu / (0.9 * k))) * k / FY
    c = area * FY / k / 0.85
    assert 0.003 * (d - c) / c >= 0.005, "la sección no queda controlada por tracción"
    return area


def splice_cases() -> list[dict]:
    """Malla de 1000 × 500 mm con d = 420 mm y As = 1000 mm²: momento bajo (clase A), alto (clase B) y nulo."""
    cases = []
    for name, mu in (("momento bajo", 60e6), ("momento alto", 150e6)):
        required = required_steel(1000.0, 420.0, mu)
        ratio = 1000.0 / required
        cases.append({"name": name, "b": 1000.0, "h": 500.0, "d": 420.0, "provided": 1000.0, "Mu": mu,
                      "required": required, "ratio": ratio, "class": "A" if ratio >= 2.0 else "B"})
    cases.append({"name": "sin momento", "b": 1000.0, "h": 500.0, "d": 420.0, "provided": 1000.0, "Mu": 0.0,
                  "required": 0.0, "ratio": None, "class": "A"})
    return cases


def derive(folder: str) -> dict:
    return {
        "source": "derive_detailing.py (D-125, D-129)",
        "hooks": {name: hook(folder, db) for name, db in BARS.items()},
        "stirrups": {name: stirrup(folder, db) for name, db in BARS.items() if name in ("#4", "#5")},
        "u_bar": {"designation": "#6", "A": 2850.0, **u_bar(folder, BARS["#6"], 2850.0)},
        "u_bar_180": {"designation": "#9", "A": 3127.0, **u_bar(folder, BARS["#9"], 3127.0, 180)},
        "closed_stirrup": {"designation": "#4", "W": 851.0, "H": 1550.0, **closed_stirrup(folder, BARS["#4"], 851.0, 1550.0)},
        "spliced": {"length": 6850.0, "stock": 6000.0, "lap": 833.0,
                    "pattern_a": spliced(6850.0, 6000.0, 833.0, 6000.0), "pattern_b": spliced(6850.0, 6000.0, 833.0, 3000.0)},
        "tension_lap": {"designation": "#6", "cb": 84.55, **tension_lap(BARS["#6"], 84.55)},
        "compression_lap": {"designation": "#6", "length": max(0.071 * FY * BARS["#6"], 300.0)},
        "splice_class": splice_cases(),
    }


if __name__ == "__main__":
    for folder in ("aci_318_25", "nsr_10"):
        target = HERE / folder / "derived_detailing.json"
        target.write_text(json.dumps(derive(folder), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("escrito", target)
