"""Inspección de un DXF a JSON y comparación de dos (herramienta de desarrollo, fuera del paquete; requiere el extra `cad`).

Extrae lo que define el aspecto de un plano: encabezado (versión, unidades, escalas), capas, tipos de línea, estilos de
texto, estilos de cota, bloques, layouts y las entidades de cada espacio agrupadas por capa (tipos, alturas de texto,
estilos usados, bloques insertados, colores y grosores propios) con algunos textos de muestra.

    python tools/dxf_inspect.py plano.dxf                         # JSON a la salida estándar
    python tools/dxf_inspect.py plano.dxf -o plano.json           # JSON a un archivo
    python tools/dxf_inspect.py objetivo.dxf salida.dxf -o dir/   # los dos JSON y el reporte de diferencias en dir/
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing

HEADER_VARS = ("$ACADVER", "$DWGCODEPAGE", "$INSUNITS", "$MEASUREMENT", "$LUNITS", "$LUPREC", "$LTSCALE", "$PSLTSCALE",
               "$CELTSCALE", "$DIMSCALE", "$DIMSTYLE", "$TEXTSTYLE", "$TEXTSIZE", "$CLAYER", "$LWDISPLAY", "$EXTMIN",
               "$EXTMAX", "$INSBASE")
# Variables de cota que definen su aspecto (el resto se lista igual en dimvars_otras).
DIMVARS = ("dimscale", "dimtxt", "dimasz", "dimexe", "dimexo", "dimgap", "dimdli", "dimtxsty", "dimblk", "dimblk1",
           "dimblk2", "dimldrblk", "dimtsz", "dimtad", "dimjust", "dimtih", "dimtoh", "dimtix", "dimtofl", "dimatfit",
           "dimtmove", "dimclrd", "dimclre", "dimclrt", "dimlwd", "dimlwe", "dimltype", "dimlunit", "dimdec", "dimdsep",
           "dimrnd", "dimlfac", "dimpost", "dimzin", "dimse1", "dimse2", "dimsd1", "dimsd2", "dimfxlon", "dimfxl")
MLEADER_VARS = ("char_height", "arrow_head_size", "landing_gap_size", "dogleg_length", "content_type", "text_color",
                "leader_line_color", "scale", "text_left_attachment", "text_right_attachment")
TEXT_SAMPLES = 8
LAYER_COUNTERS = ("tipos", "alturas_texto", "estilos_texto", "estilos_cota", "tipos_cota", "overrides_cota", "bloques",
                  "sombreados", "anchos_polilinea", "colores_propios", "grosores_propios", "tipos_linea_propios")
SUMMARY_KEYS = ("tipos", "alturas_texto", "estilos_texto", "estilos_cota", "tipos_cota", "sombreados", "anchos_polilinea")
DIMTYPES = {0: "lineal", 1: "alineada", 2: "angular", 3: "diametro", 4: "radio", 5: "angular_3p", 6: "ordenada"}
BYLAYER = 256  # color ACI "por capa"
MAX_DEPTH = 3
STANDARD_BLOCKS = ("*Model_Space", "*Paper_Space")


def load(path: Path) -> tuple[Drawing, list[str]]:
    """El documento y los avisos de la lectura (se intenta recuperar un archivo con errores)."""
    try:
        return ezdxf.readfile(path), []
    except ezdxf.DXFStructureError:
        document, auditor = recover.readfile(path)
        return document, [str(error.message) for error in auditor.errors]


def inspect(path: Path) -> dict[str, Any]:
    document, warnings = load(path)
    return {
        "archivo": path.name,
        "avisos_de_lectura": warnings,
        "encabezado": {name: _plain(document.header.get(name)) for name in HEADER_VARS if name in document.header},
        "capas": _layers(document),
        "tipos_de_linea": {lt.dxf.name: {"descripcion": lt.dxf.get("description", ""),
                                         "patron": _plain(lt.pattern_tags.tags) if lt.pattern_tags else None}
                           for lt in document.linetypes},
        "estilos_de_texto": {style.dxf.name: {"fuente": style.dxf.get("font", ""), "fuente_grande": style.dxf.get("bigfont", ""),
                                              "fuente_ttf": _ttf(style), "altura": style.dxf.get("height", 0.0),
                                              "factor_ancho": style.dxf.get("width", 1.0), "oblicuo": style.dxf.get("oblique", 0.0)}
                             for style in document.styles},
        "estilos_de_cota": _dimstyles(document),
        "estilos_de_multileader": _mleader_styles(document),
        "bloques": _blocks(document),
        "layouts": _layouts(document),
        "entidades": {layout.name: _entities(layout) for layout in document.layouts},
    }


def _layers(document: Drawing) -> dict[str, Any]:
    used: Counter[str] = Counter(entity.dxf.layer for layout in document.layouts for entity in layout)
    return {layer.dxf.name: {"color": layer.color, "color_rgb": _rgb(layer.rgb), "tipo_de_linea": layer.dxf.get("linetype", ""),
                             "grosor": layer.dxf.get("lineweight", -3), "imprime": bool(layer.dxf.get("plot", 1)),
                             "encendida": layer.is_on(), "congelada": layer.is_frozen(), "bloqueada": layer.is_locked(),
                             "entidades": used.get(layer.dxf.name, 0)}
            for layer in document.layers}


def _dimstyles(document: Drawing) -> dict[str, Any]:
    styles: dict[str, Any] = {}
    for style in document.dimstyles:
        attributes = {key: _plain(value) for key, value in style.dxfattribs().items() if key not in ("handle", "owner", "name")}
        styles[style.dxf.name] = {"principales": {key: attributes.pop(key) for key in DIMVARS if key in attributes},
                                  "otras": attributes}
    return styles


def _mleader_styles(document: Drawing) -> dict[str, Any]:
    """Por nombre y handle: un DXF puede traer dos estilos con el mismo nombre."""
    return {f"{style.dxf.name} ({style.dxf.handle})": {key: _plain(value) for key, value in style.dxfattribs().items()
                                                       if key in MLEADER_VARS}
            for style in document.objects.query("MLEADERSTYLE")}


def _blocks(document: Drawing) -> dict[str, Any]:
    inserted: Counter[str] = Counter(entity.dxf.name for layout in document.layouts for entity in layout.query("INSERT"))
    named: dict[str, Any] = {}
    anonymous: Counter[str] = Counter()
    for block in document.blocks:
        if block.name in STANDARD_BLOCKS or block.name.lower().startswith("*paper_space"):
            continue
        if block.name.startswith("*"):  # anónimos: cotas (*D), sombreados, tablas; solo se cuentan por prefijo
            anonymous[block.name[:2]] += 1
            continue
        named[block.name] = {"base": _plain(block.base_point), "inserciones": inserted.get(block.name, 0),
                             "atributos": [attdef.dxf.tag for attdef in block.query("ATTDEF")],
                             "entidades": dict(Counter(entity.dxftype() for entity in block)),
                             "capas": sorted({entity.dxf.layer for entity in block})}
    return {"nombrados": named, "anonimos_por_prefijo": dict(anonymous), "insertados": _inserted_tree(document)}


def _inserted_tree(document: Drawing) -> dict[str, Any]:
    """Los bloques insertados en el espacio modelo, con su contenido y lo que insertan adentro (bloques anónimos de AutoCAD
    incluidos: un bloque dinámico exportado llega como *U), agrupados por contenido para no repetir cada instancia."""
    seen: dict[str, Any] = {}

    def describe(name: str, depth: int) -> dict[str, Any]:
        block = document.blocks.get(name)
        if block is None:
            return {"falta": True}
        inner = Counter(entity.dxf.name for entity in block.query("INSERT"))
        return {"entidades": dict(Counter(entity.dxftype() for entity in block if entity.dxftype() != "INSERT")),
                "sombreados": sorted({entity.dxf.pattern_name for entity in block.query("HATCH")}),
                "circulos": sorted({round(entity.dxf.radius, 4) for entity in block.query("CIRCLE")}),
                "inserta": {key: {"veces": count, **(describe(key, depth + 1) if depth < MAX_DEPTH else {})}
                            for key, count in inner.items()}}

    for entity in document.modelspace().query("INSERT"):
        content = describe(entity.dxf.name, 0)
        key = json.dumps(content, sort_keys=True)
        seen.setdefault(key, {"capa": entity.dxf.layer, "instancias": 0, "ejemplo": entity.dxf.name, "contenido": content})
        seen[key]["instancias"] += 1
    return {f"{item['capa']} ({item['ejemplo']})": item for item in seen.values()}


def _layouts(document: Drawing) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for layout in document.layouts:
        data: dict[str, Any] = {"entidades": len(layout)}
        if layout.name != "Model":
            settings = layout.dxf_layout.dxf
            data |= {"papel": settings.get("paper_size", ""), "ancho_papel": settings.get("paper_width", 0.0),
                     "alto_papel": settings.get("paper_height", 0.0), "unidades_papel": settings.get("plot_paper_units", 0),
                     "ventanas": [{"centro": _plain(viewport.dxf.center), "ancho": viewport.dxf.width, "alto": viewport.dxf.height,
                                   "escala": _viewport_scale(viewport), "capa": viewport.dxf.layer}
                                  for viewport in layout.query("VIEWPORT") if viewport.dxf.get("id", 0) != 1]}
        result[layout.name] = data
    return result


def _entities(layout: Any) -> dict[str, Any]:
    by_layer: dict[str, dict[str, Any]] = defaultdict(lambda: {**{key: Counter() for key in LAYER_COUNTERS}, "muestras": []})
    for entity in layout:
        info = by_layer[entity.dxf.layer]
        kind = entity.dxftype()
        info["tipos"][kind] += 1
        if entity.dxf.get("color", BYLAYER) != BYLAYER:
            info["colores_propios"][entity.dxf.color] += 1
        if entity.dxf.get("lineweight", -1) != -1:
            info["grosores_propios"][entity.dxf.lineweight] += 1
        if entity.dxf.get("linetype", "BYLAYER").upper() != "BYLAYER":
            info["tipos_linea_propios"][entity.dxf.linetype] += 1
        if kind in ("TEXT", "MTEXT", "ATTRIB"):
            height = entity.dxf.get("char_height" if kind == "MTEXT" else "height", 0.0)
            info["alturas_texto"][round(height, 2)] += 1
            info["estilos_texto"][entity.dxf.get("style", "Standard")] += 1
            if len(info["muestras"]) < TEXT_SAMPLES:
                text = entity.plain_text() if kind == "MTEXT" else entity.dxf.get("text", "")
                info["muestras"].append(text[:80])
        elif kind == "DIMENSION":
            info["estilos_cota"][entity.dxf.get("dimstyle", "Standard")] += 1
            info["tipos_cota"][DIMTYPES.get(entity.dimtype & 7, str(entity.dimtype & 7))] += 1
            for key, value in entity.override().dimstyle_attribs.items():
                info["overrides_cota"][f"{key}={value}"] += 1
        elif kind == "HATCH":
            info["sombreados"][entity.dxf.pattern_name] += 1
        elif kind == "LWPOLYLINE":
            info["anchos_polilinea"][round(entity.dxf.get("const_width", 0.0), 4)] += 1
        elif kind == "INSERT":
            info["bloques"][entity.dxf.name] += 1
    return {layer: {key: (dict(value) if isinstance(value, Counter) else value) for key, value in info.items() if value}
            for layer, info in sorted(by_layer.items())}


def compare(target: dict[str, Any], current: dict[str, Any]) -> str:
    """Reporte de diferencias en Markdown: lo que tiene el objetivo y falta en la salida, lo que sobra y lo que cambia."""
    lines = [f"# Diferencias DXF: objetivo `{target['archivo']}` contra salida `{current['archivo']}`", ""]
    lines += _section("Encabezado", target["encabezado"], current["encabezado"])
    lines += _section("Capas", target["capas"], current["capas"], ignore=("entidades",))
    lines += _section("Tipos de línea", target["tipos_de_linea"], current["tipos_de_linea"], ignore=("patron",))
    lines += _section("Estilos de texto", target["estilos_de_texto"], current["estilos_de_texto"])
    lines += _section("Estilos de cota (variables principales)", {k: v["principales"] for k, v in target["estilos_de_cota"].items()},
                      {k: v["principales"] for k, v in current["estilos_de_cota"].items()})
    lines += _section("Estilos de multileader", target["estilos_de_multileader"], current["estilos_de_multileader"])
    lines += _section("Bloques nombrados", target["bloques"]["nombrados"], current["bloques"]["nombrados"])
    lines += _section("Bloques insertados en el modelo (por contenido)", target["bloques"]["insertados"], current["bloques"]["insertados"])
    lines += _section("Layouts", target["layouts"], current["layouts"])
    for space in sorted(set(target["entidades"]) | set(current["entidades"])):
        lines += _section(f"Entidades por capa: {space}", _summary(target["entidades"].get(space, {})),
                          _summary(current["entidades"].get(space, {})))
    return "\n".join(lines) + "\n"


def _summary(layers: dict[str, Any]) -> dict[str, Any]:
    return {layer: {key: info[key] for key in SUMMARY_KEYS if key in info}
            for layer, info in layers.items()}


def _section(title: str, target: dict[str, Any], current: dict[str, Any], ignore: tuple[str, ...] = ()) -> list[str]:
    missing = sorted(set(target) - set(current))
    extra = sorted(set(current) - set(target))
    changed = []
    for name in sorted(set(target) & set(current)):
        a, b = target[name], current[name]
        if isinstance(a, dict) and isinstance(b, dict):
            keys = sorted((set(a) | set(b)) - set(ignore))
            delta = [f"{key}: {_short(a.get(key))} → {_short(b.get(key))}" for key in keys if a.get(key) != b.get(key)]
        else:
            delta = [] if a == b else [f"{_short(a)} → {_short(b)}"]
        if delta:
            changed.append(f"- `{name}`: " + "; ".join(delta))
    lines = [f"## {title}", "", f"Objetivo {len(target)}, salida {len(current)}, solo en el objetivo {len(missing)}, "
                                f"solo en la salida {len(extra)}, con diferencias {len(changed)}.", ""]
    if missing:
        lines += ["Solo en el objetivo:", ""] + [f"- `{name}`: {_short(target[name])}" for name in missing] + [""]
    if extra:
        lines += ["Solo en la salida:", ""] + [f"- `{name}`: {_short(current[name])}" for name in extra] + [""]
    if changed:
        lines += ["Diferencias (objetivo → salida):", ""] + changed + [""]
    return lines


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + "…"


def _plain(value: Any) -> Any:
    """Valores de ezdxf (Vec3, tuplas de etiquetas) a JSON."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "x") and hasattr(value, "y"):
        return [round(value.x, 4), round(value.y, 4), round(getattr(value, "z", 0.0), 4)]
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return str(value)


def _rgb(value: Any) -> str | None:
    return None if value is None else "#{:02x}{:02x}{:02x}".format(*value)


def _ttf(style: Any) -> str:
    try:
        return str(style.get_extended_font_data()[0])
    except (AttributeError, IndexError, TypeError):
        return ""


def _viewport_scale(viewport: Any) -> float | None:
    view_height = viewport.dxf.get("view_height", 0.0)
    return None if not view_height else round(viewport.dxf.height / view_height, 6)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dxf", type=Path, nargs="+", help="un DXF, o el objetivo y la salida para compararlos")
    parser.add_argument("-o", "--output", type=Path, help="archivo JSON (un DXF) o carpeta (dos DXF)")
    args = parser.parse_args(argv)
    if len(args.dxf) > 2:  # noqa: PLR2004 - uno o dos archivos
        parser.error("se aceptan uno o dos DXF")
    data = [inspect(path) for path in args.dxf]
    if len(data) == 1:
        text = json.dumps(data[0], indent=2, ensure_ascii=False)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        else:
            sys.stdout.write(text + "\n")
        return 0
    folder = args.output or Path(".")
    folder.mkdir(parents=True, exist_ok=True)
    for path, item in zip(args.dxf, data, strict=True):
        (folder / f"{path.stem}.json").write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "diferencias.md").write_text(compare(*data), encoding="utf-8")
    print(f"JSON y diferencias.md en {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
