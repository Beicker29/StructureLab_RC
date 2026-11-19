"""Arma la plantilla DXF del dibujo (D-150) a partir de un plano de referencia (herramienta de desarrollo; requiere el extra
`cad`): conserva sus capas, tipos de línea, estilos de texto, de cota y de multileader, y quita todo lo que es del proyecto
(entidades, layouts, bloques anónimos). Agrega las capas del modelo de dibujo que el plano no trae (con el color, el grosor
y el tipo de línea de drawing/model.py, que es la fuente de los colores) y el bloque BARRA de la barra cortada.

    python tools/make_dxf_template.py references/zapatas.dxf src/structurelab_rc/data/plantilla.dxf

El plano de referencia está en metros aunque declare mm: la plantilla declara metros ($INSUNITS = 6).
"""

import argparse
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing

from structurelab_rc.drawing.model import BAR_DESIGNATIONS, DISTRIBUTION, LAYERS, OPTIONAL_LAYERS, bar_layer, layer_style

BAR_BLOCK = "BARRA"  # punto relleno de radio 1, en la capa 0: toma el color de la capa en que se inserta
DASHED = "HIDDEN2"
METRES = 6
PAPER = "Plano"
POINT = 46  # separador decimal "."
NO_ROUNDING = 0.0001  # m: redondeo de las cotas a 0.1 mm, que con dos o tres decimales no se ve
_KEEP_BLOCKS = ("*Model_Space", "*Paper_Space", "_DotSmall")
_HISTORY = ("ACAD_LAST_SAVED_VERSION_INFO", "ACAD_CIP_PREVIOUS_PRODUCT_INFO", "ACDB_RECOMPOSE_DATA", "ACAD_ASSOCNETWORK")


def build(source: Path) -> Drawing:
    document = ezdxf.readfile(source)
    document.modelspace().delete_all_entities()
    papers = [layout.name for layout in document.layouts if layout.name != "Model"]
    for name in papers[1:]:  # ezdxf exige un layout de papel: queda uno, vacío y sin el nombre del proyecto
        document.layouts.delete(name)
    document.layouts.get(papers[0]).delete_all_entities()
    document.layouts.rename(papers[0], PAPER)
    for block in list(document.blocks):
        if block.name not in _KEEP_BLOCKS and not block.name.lower().startswith("*paper_space"):
            document.blocks.delete_block(block.name, safe=False)
    for name in [*LAYERS, *OPTIONAL_LAYERS, *(bar_layer(designation) for designation in BAR_DESIGNATIONS)]:
        _, aci, weight = layer_style(name)
        layer = document.layers.get(name) if name in document.layers else document.layers.add(name)
        layer.color = aci
        layer.dxf.lineweight = int(round(weight * 100))
        layer.dxf.linetype = DASHED if name == DISTRIBUTION else "Continuous"
    for style in document.dimstyles:  # cotas como las muestra el plano ("1.25"): punto decimal y sin redondeo
        style.dxf.dimrnd = NO_ROUNDING  # 0 en AutoCAD es "sin redondeo", pero ezdxf lo toma como redondear al entero
        style.dxf.dimdsep = POINT
    block = document.blocks.new(BAR_BLOCK)
    block.add_circle((0.0, 0.0), 1.0, dxfattribs={"layer": "0", "color": 0})
    hatch = block.add_hatch(color=0, dxfattribs={"layer": "0"})  # 0: color del bloque (el de la capa de la inserción)
    hatch.paths.add_edge_path().add_arc((0.0, 0.0), 1.0, 0, 360)
    for key in _HISTORY:  # historia del archivo de origen (rutas, versiones, quién lo guardó)
        entry = document.rootdict.get(key)
        if entry is not None:
            document.rootdict.discard(key)
            document.objects.delete_entity(entry)  # la entrada y su objeto, que si no queda en OBJECTS
    header = document.header
    for name in ("$LASTSAVEDBY", "$HYPERLINKBASE", "$PROJECTNAME"):
        if name in header:
            header[name] = ""
    header["$INSUNITS"] = METRES
    header["$MEASUREMENT"] = 1
    header["$DIMSTYLE"] = "DIM-50"
    header["$CLAYER"] = "0"
    for name in ("$EXTMIN", "$EXTMAX", "$INSBASE"):
        header[name] = (0.0, 0.0, 0.0)
    document.audit()
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="plano DXF de referencia")
    parser.add_argument("target", type=Path, help="plantilla DXF que se escribe")
    args = parser.parse_args(argv)
    document = build(args.source)
    document.saveas(args.target, encoding="utf-8")
    print(f"plantilla en {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
