"""Deriva el oráculo del despiece (D-125) para los dos perfiles. No importa el paquete.

Datos de la norma, leídos de los PDF:
- ACI 318-25, Tabla 25.3.1: doblado 6db (No. 10–25), 8db (No. 29–36); extensión 12db (90°), máx(4db, 65 mm) (180°).
  Tabla 25.3.2 (estribos): doblado 4db (No. 10–16), 6db (No. 19–25); 135° con máx(6db, 75 mm).
  25.5.2.1: máx(1.0ℓd, 300) clase A, máx(1.3ℓd, 300) clase B; 25.5.5.1: máx(0.071fy·db, 300) con fy ≤ 420 MPa.
- NSR-10, C.7.1 y Tabla C.7.2: los mismos doblados y extensiones de ganchos estándar; estribos No. 5 y menores con
  doblado 4db; 135° con 6db, sin mínimo de 75 mm (C.7.1.3(c)). C.12.15.1 y C.12.16.1: los mismos empalmes.

Geometría (independiente de detailing/schedule.py): longitud por el eje = tramos rectos + arcos de radio D/2 + db/2.
- Barra con gancho de 90° en cada extremo y dimensión exterior A: recto = A − 2(D/2 + db); cada gancho agrega el arco
  π/2·(D/2 + db/2) y la extensión. Pata exterior = extensión + D/2 + db.
- Estribo cerrado de W × H exteriores con ganchos de 135°: 2(W − D − 2db) + 2(H − D − 2db) + 3 arcos de 90° + 2 arcos de
  135° + 2 extensiones.
- Barra recta de largo L > longitud comercial S con traslapo t: el patrón A corta S, S, …; el patrón B empieza con S/2.
Todas las longitudes de corte se redondean hacia arriba a 50 mm.

Uso: python tests/oracles/derive_detailing.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
BARS = {"#4": 12.7, "#5": 15.9, "#6": 19.1, "#9": 28.7}  # mm
FY, FC = 420.0, 28.0


def round_up(x: float) -> float:
    return math.ceil(x / 50.0 - 1e-9) * 50.0


def hook(folder: str, db: float) -> dict:
    bend = (6.0 if db <= 25.9 else 8.0) * db
    return {"bend": bend, "ext90": 12.0 * db, "ext180": max(4.0 * db, 65.0)}


def stirrup(folder: str, db: float) -> dict:
    bend = (4.0 if db <= 16.4 else 6.0) * db
    ext135 = max(6.0 * db, 75.0) if folder == "aci_318_25" else 6.0 * db
    return {"bend": bend, "ext135": ext135}


def u_bar(folder: str, db: float, a: float) -> dict:
    h = hook(folder, db)
    r = h["bend"] / 2
    arc = math.pi / 2 * (r + db / 2)
    axis = a - 2 * (r + db) + 2 * (arc + h["ext90"])
    return {"cut": round_up(axis), "leg": h["ext90"] + r + db}


def closed_stirrup(folder: str, db: float, w: float, h_: float) -> float:
    s = stirrup(folder, db)
    r = s["bend"] / 2
    axis = (2 * (w - 2 * (r + db)) + 2 * (h_ - 2 * (r + db)) + 3 * math.pi / 2 * (r + db / 2)
            + 2 * math.radians(135) * (r + db / 2) + 2 * s["ext135"])
    return round_up(axis)


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


def derive(folder: str) -> dict:
    return {
        "source": "derive_detailing.py (D-125)",
        "hooks": {name: hook(folder, db) for name, db in BARS.items()},
        "stirrups": {name: stirrup(folder, db) for name, db in BARS.items() if name in ("#4", "#5")},
        "u_bar": {"designation": "#6", "A": 2850.0, **u_bar(folder, BARS["#6"], 2850.0)},
        "closed_stirrup": {"designation": "#4", "W": 850.0, "H": 1550.0, "cut": closed_stirrup(folder, BARS["#4"], 850.0, 1550.0)},
        "spliced": {"length": 6850.0, "stock": 6000.0, "lap": 833.0,
                    "pattern_a": spliced(6850.0, 6000.0, 833.0, 6000.0), "pattern_b": spliced(6850.0, 6000.0, 833.0, 3000.0)},
        "tension_lap": {"designation": "#6", "cb": 84.55, **tension_lap(BARS["#6"], 84.55)},
        "compression_lap": {"designation": "#6", "length": max(0.071 * FY * BARS["#6"], 300.0)},
    }


if __name__ == "__main__":
    for folder in ("aci_318_25", "nsr_10"):
        target = HERE / folder / "derived_detailing.json"
        target.write_text(json.dumps(derive(folder), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("escrito", target)
