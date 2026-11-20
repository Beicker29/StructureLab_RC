"""Huella de los ejemplos (D-051): SHA-256 de resultado.json, memoria.txt (con la cartilla, D-125) y
<nombre>_drawing.json (el modelo de dibujo, D-126), que no llevan fecha. Nunca del DXF ni del PDF.

Un cambio de cálculo intencional cambia la huella. Después de reportarlo, se actualiza con:

    STRUCTURELAB_UPDATE_FINGERPRINTS=1 pytest tests/test_fingerprints.py

Nunca se actualiza para hacer pasar una prueba.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest
from frozen_examples import frozen_all

from structurelab_rc.engine import (
    design_combined_file,
    design_footings,
    design_pile_caps_file,
    import_etabs,
    import_etabs_footings,
    report_file,
)

ROOT = Path(__file__).parent.parent
FINGERPRINTS = Path(__file__).parent / "fingerprints.json"
# Las pruebas usan solo las copias congeladas de pruebas/ (D-098; por tipología, D-146): los ejemplos de afuera
# son para que el usuario itere. Los mismos ejemplos para los dos perfiles (D-073). Las plantillas de ETABS
# (<tipo>_etabs.json, D-098) leen los Excel de examples/etabs/<elemento>/pruebas/; entran en la huella la de vigas,
# las de zapatas combinadas (D-084), en T invertida (D-093) y del diseño de la combinada (D-112), que importan pocas
# zapatas, y la verificación de zapatas aisladas (57 apoyos, con la planta de localización, D-130); el diseño por
# tipologías desde ETABS (73 apoyos) tarda minutos y no entra.
# La curva costo-N (curva_*.json, D-096) repite el diseño para cada N: tarda minutos con un proceso y no entra en la huella.
EXAMPLES = sorted(str(path.relative_to(ROOT).as_posix()) for path in frozen_all()
                  if not path.stem.endswith("_etabs") and not path.name.startswith("curva_"))
ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                     for path in (ROOT / "examples").glob("*/vigas/pruebas/viga_rectangular_etabs.json")))
COMBINED_ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                              for name in ("zapata_combinada_etabs.json", "zapata_t_invertida_etabs.json",
                                           "diseno_combinada_etabs.json", "diseno_t_invertida_etabs.json",
                                           "zapata_centrica_etabs.json")
                              for path in (ROOT / "examples").glob(f"*/zapatas/**/pruebas/{name}")))
# Cabezales desde ETABS (D-138): cargas de la columna (Joint Reactions) o de los pilotes (Element Forces - Columns);
# las plantillas de diseño (diseno_*, D-141) se diseñan después de importarlas.
CAP_ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                         for path in (ROOT / "examples").glob("*/cabezales/**/pruebas/*_etabs.json")))
# Diseños por tipologías desde ETABS con 6 apoyos de un nivel de los Excel de pruebas y la tabla de coordenadas: con una
# zapata combinada (D-153) y una zapata céntrica por apoyo (D-155); se importan, se diseñan y se verifican.
TYPOLOGY_ETABS = tuple(sorted(str(path.relative_to(ROOT).as_posix())
                              for name in ("diseno_tipologias_combinadas_etabs.json", "diseno_centrica_etabs.json")
                              for path in (ROOT / "examples").glob(f"*/zapatas/**/pruebas/{name}")))
WORKBOOK = ROOT / "examples" / "etabs" / "vigas" / "pruebas" / "Element Forces - Beams.xlsx"
REACTIONS = (ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Servicio.xlsx",
             ROOT / "examples" / "etabs" / "zapatas" / "pruebas" / "Joint Reactions - Ultimas.xlsx")
UPDATE = os.environ.get("STRUCTURELAB_UPDATE_FINGERPRINTS") == "1"


def _fingerprint(name: str, work: Path) -> dict[str, str]:
    project = ROOT / name
    files = ("resultado.json", "memoria.txt")
    if Path(name).name.startswith("diseno_") and name not in (*COMBINED_ETABS, *CAP_ETABS, *TYPOLOGY_ETABS):
        # Diseño por tipologías (D-069), de la zapata combinada (D-107, un proceso por f'c, sin cambiar el resultado) o de
        # cabezales (D-141):
        # huella del proyecto diseñado y de su verificación.
        raw = json.loads(project.read_text(encoding="utf-8"))
        if "pile_cap_design" in raw:  # diseño de cabezales (D-141)
            data = design_pile_caps_file(project)[0]
        elif "combined_design" in raw:  # D-107, D-113
            data = design_combined_file(project, workers=2)[0]
        else:
            data = design_footings(project)[0]
        assert data is not None, name
        project = work / "proyecto.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        report_file(project, work / Path(name).stem)
        return {"proyecto.json": hashlib.sha256(project.read_bytes()).hexdigest(), **_digests(work / Path(name).stem, files)}
    if name in TYPOLOGY_ETABS:
        declared = json.loads(project.read_text(encoding="utf-8"))["etabs_files"]
        excel = {key: (project.parent / value).resolve() for key, value in declared.items()}
        imported = import_etabs_footings(excel["service"], excel["factored"], project, excel["locations"])[0]
        assert imported is not None, name
        project = work / "etabs.json"
        project.write_text(json.dumps(imported, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        designed = design_footings(project)[0]
        assert designed is not None, name
        project = work / "proyecto.json"
        project.write_text(json.dumps(designed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        report_file(project, work / Path(name).stem)
        return {"proyecto.json": hashlib.sha256(project.read_bytes()).hexdigest(), **_digests(work / Path(name).stem, files)}
    if name in CAP_ETABS:
        excel = json.loads(project.read_text(encoding="utf-8"))["etabs_files"]
        service, factored = ((project.parent / excel[key]).resolve() for key in ("service", "factored"))
        data = import_etabs_footings(service, factored, project)[0]
        assert data is not None, name
        project = work / "etabs.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        if Path(name).name.startswith("diseno_"):  # diseño de cabezales desde ETABS (D-141)
            designed = design_pile_caps_file(project)[0]
            assert designed is not None, name
            project = work / "proyecto.json"
            project.write_text(json.dumps(designed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if name in ETABS or name in COMBINED_ETABS:
        data = import_etabs(WORKBOOK, project)[0] if name in ETABS else import_etabs_footings(*REACTIONS, project, _locations(project))[0]
        project = work / "etabs.json"
        project.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        if Path(name).name.startswith("diseno_"):  # diseño de la combinada o la T desde ETABS (D-112, D-114)
            designed = design_combined_file(project, workers=2)[0]
            assert designed is not None, name
            project = work / "proyecto.json"
            project.write_text(json.dumps(designed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report_file(project, work / Path(name).stem)
    return _digests(work / Path(name).stem, files)


def _locations(template: Path) -> Path | None:
    """La tabla de coordenadas que declara la plantilla en etabs_files.locations (D-130), relativa a ella."""
    files = json.loads(template.read_text(encoding="utf-8")).get("etabs_files") or {}
    return None if "locations" not in files else (template.parent / files["locations"]).resolve()


def _digests(folder: Path, files: tuple[str, ...]) -> dict[str, str]:
    names = [*files, *sorted(path.name for path in folder.glob("*_drawing.json"))]
    return {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in names}


@pytest.mark.parametrize("name", [*EXAMPLES, *ETABS, *COMBINED_ETABS, *CAP_ETABS, *TYPOLOGY_ETABS])
def test_fingerprint_is_stable(name: str, tmp_path: Path) -> None:
    current = _fingerprint(name, tmp_path)
    stored = json.loads(FINGERPRINTS.read_text(encoding="utf-8")) if FINGERPRINTS.exists() else {}
    if UPDATE:
        stored[name] = current
        FINGERPRINTS.write_text(json.dumps(dict(sorted(stored.items())), indent=2) + "\n", encoding="utf-8", newline="\n")
        return
    assert name in stored, f"Sin huella registrada para {name}; ver la documentación de este módulo"
    assert current == stored[name]
