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

from structurelab_rc.engine import import_etabs, report_file

ROOT = Path(__file__).parent.parent
FINGERPRINTS = Path(__file__).parent / "fingerprints.json"
# examples/<perfil>/<elemento>/*.json; los ejemplos de ETABS están aparte, en examples/etabs/<elemento>/.
EXAMPLES = sorted(str(path.relative_to(ROOT).as_posix()) for path in (ROOT / "examples").glob("*/*/*.json")
                  if path.parts[-3] != "etabs")
ETABS = "examples/etabs/vigas/plantilla_vigas_nsr10.json"
WORKBOOK = ROOT / "examples" / "etabs" / "vigas" / "Element Forces - Beams.xlsx"
UPDATE = os.environ.get("STRUCTURELAB_UPDATE_FINGERPRINTS") == "1"


def _fingerprint(name: str, work: Path) -> dict[str, str]:
    project = ROOT / name
    if name == ETABS:
        data, _, _ = import_etabs(WORKBOOK, project)
        project = work / "etabs.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report_file(project, work / "salida")
    return {file: hashlib.sha256((work / "salida" / file).read_bytes()).hexdigest() for file in ("resultado.json", "memoria.txt")}


@pytest.mark.parametrize("name", [*EXAMPLES, ETABS])
def test_fingerprint_is_stable(name: str, tmp_path: Path) -> None:
    current = _fingerprint(name, tmp_path)
    stored = json.loads(FINGERPRINTS.read_text(encoding="utf-8")) if FINGERPRINTS.exists() else {}
    if UPDATE:
        stored[name] = current
        FINGERPRINTS.write_text(json.dumps(dict(sorted(stored.items())), indent=2) + "\n", encoding="utf-8", newline="\n")
        return
    assert name in stored, f"Sin huella registrada para {name}; ver la documentación de este módulo"
    assert current == stored[name]
