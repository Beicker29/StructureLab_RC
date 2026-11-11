"""Huella de los ejemplos (D-051): SHA-256 de resultado.json y memoria.txt, que no llevan fecha.

Un cambio de cálculo intencional cambia la huella. Después de reportarlo, se actualiza con:

    STRUCTURELAB_UPDATE_FINGERPRINTS=1 pytest tests/test_fingerprints.py

Nunca se actualiza para hacer pasar una prueba.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from structurelab_rc.engine import design_footings, import_etabs, import_etabs_footings, report_file

ROOT = Path(__file__).parent.parent
FINGERPRINTS = Path(__file__).parent / "fingerprints.json"
# Las pruebas usan solo las copias congeladas de examples/<perfil>/<elemento>/pruebas/ (D-098): los ejemplos de afuera
# son para que el usuario itere. Los mismos ejemplos para los dos perfiles (D-073). Las plantillas de ETABS
# (<tipo>_etabs.json, D-098) leen los Excel de examples/etabs/<elemento>/pruebas/; entran en la huella la de vigas y
# las de zapatas combinadas (D-084) y en T invertida (D-093), que importan pocas zapatas (las de zapatas aisladas
# importan 57 a 73 apoyos y su diseño tarda minutos).
# La curva costo-N (curva_*.json, D-096) repite el diseño para cada N: tarda minutos con un proceso y no entra en la huella.
EXAMPLES = sorted(str(path.relative_to(ROOT).as_posix()) for path in (ROOT / "examples").glob("*/*/pruebas/*.json")
                  if path.parts[-4] != "etabs" and not path.stem.endswith("_etabs") and not path.name.startswith("curva_"))
ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                     for path in (ROOT / "examples").glob("*/vigas/pruebas/viga_rectangular_etabs.json")))
COMBINED_ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                              for name in ("zapata_combinada_etabs.json", "zapata_t_invertida_etabs.json")
                              for path in (ROOT / "examples").glob(f"*/zapatas/pruebas/{name}")))
WORKBOOK = ROOT / "examples" / "etabs" / "vigas" / "pruebas" / "Element Forces - Beams.xlsx"
REACTIONS = (ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Servicio.xlsx",
             ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Ultimas.xlsx")
UPDATE = os.environ.get("STRUCTURELAB_UPDATE_FINGERPRINTS") == "1"


def _fingerprint(name: str, work: Path) -> dict[str, str]:
    project = ROOT / name
    files = ("resultado.json", "memoria.txt")
    if Path(name).name.startswith("diseno_"):
        # Diseño por tipologías (D-069): huella del proyecto diseñado y de su verificación.
        data, _, _ = design_footings(project)
        project = work / "proyecto.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        report_file(project, work / "salida")
        digests = {file: hashlib.sha256((work / "salida" / file).read_bytes()).hexdigest() for file in files}
        return {"proyecto.json": hashlib.sha256(project.read_bytes()).hexdigest(), **digests}
    if name in ETABS or name in COMBINED_ETABS:
        data = import_etabs(WORKBOOK, project)[0] if name in ETABS else import_etabs_footings(*REACTIONS, project)[0]
        project = work / "etabs.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report_file(project, work / "salida")
    return {file: hashlib.sha256((work / "salida" / file).read_bytes()).hexdigest() for file in ("resultado.json", "memoria.txt")}


@pytest.mark.parametrize("name", [*EXAMPLES, *ETABS, *COMBINED_ETABS])
def test_fingerprint_is_stable(name: str, tmp_path: Path) -> None:
    current = _fingerprint(name, tmp_path)
    stored = json.loads(FINGERPRINTS.read_text(encoding="utf-8")) if FINGERPRINTS.exists() else {}
    if UPDATE:
        stored[name] = current
        FINGERPRINTS.write_text(json.dumps(dict(sorted(stored.items())), indent=2) + "\n", encoding="utf-8", newline="\n")
        return
    assert name in stored, f"Sin huella registrada para {name}; ver la documentación de este módulo"
    assert current == stored[name]
