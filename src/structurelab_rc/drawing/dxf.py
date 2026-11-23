"""Salida DXF del modelo de dibujo (D-126, D-150) con ezdxf (extra `cad`), sobre la plantilla de los planos de despiece
(data/plantilla.dxf): sus capas, tipos de línea, estilos de texto, de cota y de multileader y el bloque de la barra
cortada.

- Unidades: el modelo está en mm y el DXF en metros, como la plantilla; la conversión ocurre solo aquí.
- Escala (D-158): el modelo ya trae los tamaños en papel × escala; lo que viene de la plantilla, pensada para 1:50, se
  multiplica por escala/50: los estilos de cota, la escala del tipo de línea de cada entidad y la flecha, la separación
  del texto y el quiebre de los MULTILEADER.
- Cotas: entidades DIMENSION con el estilo de la escala (DIM-50 a 1:50; a otra, DIM-<escala> igual a DIM-50 escalado),
  que miden en metros con dos decimales (tres si la medida no es múltiplo de 1 cm).
- Líneas de distribución (capa de proyecciones): DIMENSION sin texto con el estilo DIM-75 de la plantilla (escalado a la
  escala) y flechas cerradas en los dos extremos, como el plano de referencia (D-158).
- Rótulos de las barras: en planta MTEXT y en los cortes MULTILEADER con una línea a cada barra. Cada L se escribe como
  un campo de AutoCAD (\\AcObjProp ... .Length, dos decimales), como el plano de referencia, ligado a la polilínea de su
  marca (Text.marks y Leader.marks con Polyline.mark) en el mismo elemento: la de la misma vista o, para las barras
  cortadas de un corte, la de la planta (D-158, D-166).
- Barras cortadas y marcas de las barras: el bloque BARRA
  escalado al radio del punto, en la capa de su diámetro. Columnas en planta: sombreado sólido en su capa y contorno en
  la del concreto. Títulos y escala con el estilo de texto ARIAL de la plantilla.
- Composición, como el plano de referencia (D-158): por elemento, arriba las plantas del refuerzo inferior y superior,
  debajo el alzado o los cortes y el título del elemento ("ZC_m h=0.80") con la escala; a la derecha, la planta de
  geometría y la cartilla. Los elementos lado a lado y un marco alrededor. Las vistas con dxf = False (los cortes
  transversales de la combinada) no entran.
"""

import io
import math
from pathlib import Path
from typing import Any

from structurelab_rc.drawing.model import (
    BASE_SCALE,
    DIAMETER,
    DIMENSIONS,
    DISTRIBUTION,
    LABELS,
    OUTLINE,
    PAPER_ARROW,
    PAPER_TEXT,
    PAPER_TITLE,
    SUBTITLE,
    TITLE,
    Circle,
    Dimension,
    Drawing,
    Entity,
    Leader,
    Line,
    Polyline,
    Text,
    View,
    dimension_line,
)

_M_PER_MM = 0.001
_PAPER_GAP = 20.0  # mm de papel: separación entre vistas, filas y elementos
_FRAME = 10.0  # mm de papel: margen del marco
_BASE_STYLE = "DIM-50"  # estilo de cota de la plantilla del que se escala el de otra escala
_DISTRIBUTION_STYLE = "DIM-75"  # estilo de las líneas de distribución en la plantilla, a 1:50 (D-158)
_SCALED_DIMVARS = ("dimtxt", "dimasz", "dimexe", "dimexo", "dimgap", "dimdli", "dimfxl", "dimdle", "dimcen")
_ARROWS = {"dimsah": 1, "dimblk": "", "dimblk1": "", "dimblk2": ""}  # flechas cerradas, como el plano de referencia
_BAR_BLOCK = "BARRA"  # punto relleno de radio 1 en la plantilla
_DASHED = "HIDDEN2"
_TEXT_STYLE = "Standard"  # Arial en la plantilla
_TITLE_STYLE = "ARIAL"  # títulos y escala, como el plano de referencia (D-158)
_MLEADER_STYLE = "LEADER"  # la clave del estilo de multileader que usa la plantilla (su nombre interno es Standard)
_CM = 10.0  # mm
_ROUND_OFF = 0.05  # mm
_PLANS = "planta_"  # las plantas del refuerzo: la fila de arriba de cada elemento
_SIDE = ("geometria", "geometria_ejes", "cartilla", "cuadro_pilotes")  # a la derecha de cada elemento (D-158, D-166)
_FIELD_FORMAT = "%lu2%pr2"  # decimal con dos decimales, como el plano de referencia
_UPRIGHT = 90.0  # grados: una cota con el sentido entre −90° y 90° tiene el texto derecho
_BOTTOM_CENTER = 8  # MTEXT: punto de inserción abajo al centro
_BOTTOM_LEFT = 7


def available() -> bool:
    try:
        import ezdxf  # noqa: F401, PLC0415 - dependencia opcional
    except ImportError:
        return False
    return True


def write_dxf(drawing: Drawing, path: Path, template: str) -> bool:
    """Escribe el DXF sobre la plantilla (su texto); False si ezdxf no está instalado."""
    if not available():
        return False
    import ezdxf  # noqa: PLC0415 - dependencia opcional

    document = ezdxf.read(io.StringIO(template))
    writer = _Writer(document, drawing, _dimension_styles(document, drawing.scale))
    left, frame = 0.0, [math.inf, math.inf, -math.inf, -math.inf]
    for element, views in drawing.views.items():
        shown = [view for view in views if view.dxf]
        if shown:
            box = writer.element(element, shown, left)
            frame = [min(frame[0], box[0]), min(frame[1], box[1]), max(frame[2], box[2]), max(frame[3], box[3])]
            left = box[2] + _PAPER_GAP * drawing.scale
    if math.isfinite(frame[0]):
        margin = _FRAME * drawing.scale
        x0, y0, x1, y1 = frame[0] - margin, frame[1] - margin, frame[2] + margin, frame[3] + margin
        writer.polyline(DIMENSIONS, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)
        document.set_modelspace_vport(height=(y1 - y0) * _M_PER_MM * 1.05, center=((x0 + x1) / 2 * _M_PER_MM, (y0 + y1) / 2 * _M_PER_MM))
    path.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(path, encoding="utf-8")
    return True


def _dimension_styles(document: Any, scale: float) -> tuple[str, str]:
    """Los estilos de cota de la escala: el de las cotas (DIM-<escala>) igual a DIM-50 y el de las líneas de distribución
    (DIM-<1.5·escala>) igual a DIM-75, con los tamaños multiplicados por escala/50. Un estilo de la plantilla con el
    mismo nombre se rehace desde la base, porque los de otras escalas (DIM-20, DIM-25, DIM-125) no son proporcionales a
    DIM-50."""
    dimstyles = document.dimstyles
    sizes = {base: {key: dimstyles.get(base).dxf.get(key) for key in _SCALED_DIMVARS if dimstyles.get(base).dxf.hasattr(key)}
             for base in (_BASE_STYLE, _DISTRIBUTION_STYLE)}  # antes de tocar nada: a 1:75 las cotas se llaman DIM-75
    names = []
    for base, factor in ((_BASE_STYLE, 1.0), (_DISTRIBUTION_STYLE, 1.5)):
        name = f"DIM-{scale * factor:g}"
        if scale != BASE_SCALE:  # a 1:50 los nombres son las bases mismas
            if name in dimstyles:
                dimstyles.remove(name)
            style = dimstyles.duplicate_entry(base, name)
            for key, value in sizes[base].items():
                style.dxf.set(key, value * scale / BASE_SCALE)
        names.append(name)
    return names[0], names[1]


class _Writer:
    """Escribe las entidades del modelo (mm, en las coordenadas de su vista) en el espacio modelo (m), desplazadas."""

    def __init__(self, document: Any, drawing: Drawing, dimstyles: tuple[str, str]) -> None:
        self.document = document
        self.space = document.modelspace()
        self.drawing = drawing
        self.dimstyle, self.distribution_style = dimstyles
        self.ratio = drawing.scale / BASE_SCALE  # los tamaños de la plantilla (a 1:50) a la escala del dibujo
        self.leader_style = document.mleader_styles.get(_MLEADER_STYLE)
        self.dx, self.dy = 0.0, 0.0
        self.bars: dict[tuple[str, str], Any] = {}  # (vista o "" para el elemento, marca) -> polilínea escrita
        self.labels: list[tuple[Any, str, tuple[str, ...], str]] = []  # (entidad escrita, texto, marcas, vista)

    def element(self, element: str, views: list[View], left: float) -> tuple[float, float, float, float]:
        """Las vistas de un elemento desde la abscisa left (mm), como el plano de referencia (D-158): arriba las plantas
        del refuerzo, debajo el alzado o los cortes y el título con la escala, y a la derecha la planta de geometría y la
        cartilla una sobre otra; devuelve lo que ocupa (x0, y0, x1, y1) en mm."""
        gap = _PAPER_GAP * self.drawing.scale
        side = [view for view in views if view.name in _SIDE]
        rows = [[view for view in views if view.name.startswith(_PLANS)],
                [view for view in views if view not in side and not view.name.startswith(_PLANS)]]
        widths = [sum(view.bounds()[2] - view.bounds()[0] for view in row) + gap * (len(row) - 1) for row in rows if row]
        block = max(widths, default=0.0)
        top = 0.0
        for row in (row for row in rows if row):
            width = sum(view.bounds()[2] - view.bounds()[0] for view in row) + gap * (len(row) - 1)
            column, tallest = left + (block - width) / 2, 0.0  # cada fila centrada en el bloque
            for view in row:
                x0, y0, x1, y1 = view.bounds()
                self.place(view, (column - x0, top - y1))
                column += (x1 - x0) + gap
                tallest = max(tallest, y1 - y0)
            top -= tallest + gap
        self.dx, self.dy = 0.0, 0.0  # el título va en coordenadas del plano, no de la última vista
        bottom = top
        title = self.drawing.titles.get(element)
        if title is not None:
            middle = left + block / 2
            title_height, scale_height = self.drawing.paper(PAPER_TITLE), self.drawing.paper(PAPER_TEXT)
            self.text(Text(TITLE, (middle, top), title, title_height, align="center"))
            bottom = top - 1.6 * scale_height
            self.text(Text(SUBTITLE, (middle, bottom), f"ESC 1:{self.drawing.scale:g}", scale_height, align="center"))
        right, stack = left + block, 0.0
        for view in side:
            x0, y0, x1, y1 = view.bounds()
            self.place(view, (left + block + gap - x0, stack - y1))
            stack -= (y1 - y0) + gap
            right = max(right, left + block + gap + (x1 - x0))
            bottom = min(bottom, stack + gap)
        self.dx, self.dy = 0.0, 0.0
        self.link()
        return left, bottom, right, 0.0

    def place(self, view: View, shift: tuple[float, float]) -> None:
        """Las entidades de una vista desplazadas shift (mm); anota las barras con marca y los rótulos con marcas, que
        link() liga al terminar el elemento."""
        self.dx, self.dy = shift
        for entity in view.entities:
            written = self.entity(entity)
            if isinstance(entity, Polyline) and entity.mark:
                self.bars.setdefault((view.name, entity.mark), written)
                self.bars.setdefault(("", entity.mark), written)
            elif isinstance(entity, (Text, Leader)) and entity.marks:
                self.labels.append((written, entity.text, entity.marks, view.name))

    def link(self) -> None:
        """Liga cada L de los rótulos del elemento a la longitud de la polilínea de su marca (D-158, D-166): la de la misma
        vista si la hay (la barra representativa en planta, la paralela al corte, el pasador) y si no, la del elemento (la
        barra de la planta, para las barras cortadas de un corte). Sin polilínea para alguna L (empalmes, estribos), el
        rótulo queda con su texto."""
        for written, text, marks, view in self.labels:
            polylines = [self.bars.get((view, mark), self.bars.get(("", mark))) for mark in marks]
            head, found, tail = text.partition("L=")
            values, _, rest = tail.partition(" ")
            count = len(values.split("+"))
            if not found or count != len(polylines) or any(polyline is None for polyline in polylines):
                continue
            code = head + "L=" + "+".join(f"%<\\_FldIdx {index}>%" for index in range(count)) + (f" {rest}" if rest else "")
            _length_fields(self.document, written, polylines, code)
        self.bars.clear()
        self.labels.clear()

    def attributes(self, layer: str) -> dict[str, Any]:
        """La capa y la escala del tipo de línea: los trazos de la plantilla (HIDDEN2, a 1:50) a la escala del dibujo."""
        return {"layer": layer, "ltscale": self.ratio}

    def point(self, point: tuple[float, float]) -> tuple[float, float]:
        return (point[0] + self.dx) * _M_PER_MM, (point[1] + self.dy) * _M_PER_MM

    def polyline(self, layer: str, points: list[tuple[float, float]], closed: bool = False, dashed: bool = False,
                 color: int | None = None) -> Any:
        attributes = {**self.attributes(layer), **({"linetype": _DASHED} if dashed else {}),
                      **({"color": color} if color is not None else {})}
        return self.space.add_lwpolyline([self.point(p) for p in points], close=closed, dxfattribs=attributes)

    def text(self, text: Text) -> Any:
        """Un título, una escala o un texto de tabla como TEXT; un rótulo (capa de rótulos) como MTEXT."""
        if text.layer == LABELS:
            return self.mtext(text, text.text)
        from ezdxf.enums import TextEntityAlignment  # noqa: PLC0415 - dependencia opcional

        aligns = {"left": TextEntityAlignment.LEFT, "center": TextEntityAlignment.CENTER, "right": TextEntityAlignment.RIGHT}
        style = _TITLE_STYLE if text.layer in (TITLE, SUBTITLE) else _TEXT_STYLE
        entity = self.space.add_text(text.text, height=text.height * _M_PER_MM, rotation=text.rotation,
                                     dxfattribs={"layer": text.layer, "style": style})
        entity.set_placement(self.point(text.at), align=aligns[text.align])
        return entity

    def mtext(self, text: Text, content: str) -> Any:
        attachment = _BOTTOM_CENTER if text.align == "center" else _BOTTOM_LEFT
        return self.space.add_mtext(content, dxfattribs={"layer": text.layer, "style": _TEXT_STYLE, "char_height": text.height * _M_PER_MM,
                                                         "insert": self.point(text.at), "rotation": text.rotation,
                                                         "attachment_point": attachment})

    def shape(self, entity: Polyline) -> Any:
        if entity.filled:  # columna: sombreado en su capa y contorno en la del concreto
            hatch = self.space.add_hatch(color=256, dxfattribs={"layer": entity.layer})  # 256: color de la capa
            hatch.paths.add_polyline_path([self.point(p) for p in entity.points], is_closed=True)
            return self.polyline(OUTLINE, list(entity.points), closed=True)
        return self.polyline(entity.layer, list(entity.points), closed=entity.closed, dashed=entity.dashed, color=entity.color)

    def circle(self, entity: Circle) -> Any:
        radius = entity.radius * _M_PER_MM
        if entity.filled:  # barra cortada o marca de barra: el bloque de la plantilla
            attributes = {"layer": entity.layer, "xscale": radius, "yscale": radius}
            return self.space.add_blockref(_BAR_BLOCK, self.point(entity.center), dxfattribs=attributes)
        attributes = {**self.attributes(entity.layer), **({"linetype": _DASHED} if entity.dashed else {})}
        return self.space.add_circle(self.point(entity.center), radius, dxfattribs=attributes)

    def entity(self, entity: Entity) -> Any:
        if isinstance(entity, Line):
            return self.space.add_line(self.point(entity.start), self.point(entity.end), dxfattribs=self.attributes(entity.layer))
        if isinstance(entity, Polyline):
            return self.shape(entity)
        if isinstance(entity, Circle):
            return self.circle(entity)
        if isinstance(entity, Text):
            return self.text(entity)
        if isinstance(entity, Leader):
            return self.leader(entity)
        return self.dimension(entity)

    def dimension(self, dimension: Dimension) -> Any:
        """Una cota (o, en la capa de proyecciones, una línea de distribución: sin texto y con flechas, D-158; o la del
        diámetro de un pilote, D-166)."""
        start, end = dimension.start, dimension.end
        if dimension.kind == "diameter":
            centre = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            radius = math.hypot(end[0] - start[0], end[1] - start[1]) / 2 * _M_PER_MM
            diameter = self.space.add_diameter_dim(center=self.point(centre), radius=radius,
                                                   angle=math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])),
                                                   text=dimension.text.replace(DIAMETER, "%%c"),  # Ø de AutoCAD
                                                   dimstyle=self.dimstyle,
                                                   dxfattribs=self.attributes(dimension.layer))
            diameter.render()
            return diameter.dimension
        base, _ = dimension_line(dimension)
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        if not -_UPRIGHT < angle <= _UPRIGHT:  # la misma línea en el otro sentido: el texto queda legible, no al revés
            angle -= math.copysign(2 * _UPRIGHT, angle)
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if dimension.layer == DISTRIBUTION:
            style, override, text = self.distribution_style, dict(_ARROWS), " "
        else:
            style, text = self.dimstyle, "<>"
            override = {} if abs(length - round(length / _CM) * _CM) < _ROUND_OFF else {"dimdec": 3}
        built = self.space.add_linear_dim(base=self.point(base), p1=self.point(start), p2=self.point(end), angle=angle, text=text,
                                          dimstyle=style, override=override, dxfattribs=self.attributes(dimension.layer))
        built.render()
        if built.dimension.dxf.get("text_midpoint") is None:  # sin texto: el punto medio de la línea, que los lectores piden
            first, second = dimension_line(dimension)
            built.dimension.dxf.text_midpoint = self.point(((first[0] + second[0]) / 2, (first[1] + second[1]) / 2))
        return built.dimension

    def leader(self, leader: Leader) -> Any:
        """MULTILEADER con el estilo de la plantilla: el texto a la derecha de at y una línea a cada barra con la flecha
        cerrada (D-158). La flecha, la separación del texto y el quiebre van a la escala del dibujo; ezdxf no copia la
        flecha al contexto de la entidad (la deja en 4.0) si no se fija aquí."""
        from ezdxf.math import Vec2  # noqa: PLC0415 - dependencia opcional
        from ezdxf.render import mleader  # noqa: PLC0415 - dependencia opcional

        builder = self.space.add_multileader_mtext(_MLEADER_STYLE, dxfattribs={"layer": leader.layer})
        builder.set_content(leader.text, char_height=leader.height * _M_PER_MM, alignment=mleader.TextAlignment.left)
        builder.set_arrow_properties(size=self.drawing.paper(PAPER_ARROW) * _M_PER_MM)
        style = self.leader_style.dxf
        builder.set_connection_properties(landing_gap=style.landing_gap_size * self.ratio, dogleg_length=style.dogleg_length * self.ratio)
        for target in leader.targets:
            builder.add_leader_line(mleader.ConnectionSide.left, [Vec2(self.point(target))])
        builder.build(insert=Vec2(self.point(leader.at)))
        return builder.multileader


def _length_fields(document: Any, label: Any, polylines: list[Any], code: str) -> None:
    """Liga un MTEXT o un MULTILEADER a la longitud de cada polilínea con campos de AutoCAD, como el plano de referencia
    (D-158, D-166, los dos igual): en su diccionario de extensión, ACAD_FIELD/TEXT es un campo "_text" con el texto code
    (cada %<\\_FldIdx i>% es un valor) y un campo hijo AcObjProp por polilínea (\\AcObjProp Object(...).Length, formato
    %lu2%pr2). ezdxf no trae API para los campos: se escriben como objetos con sus etiquetas."""
    from ezdxf.entities import DXFTagStorage  # noqa: PLC0415 - dependencia opcional
    from ezdxf.lldxf.extendedtags import ExtendedTags  # noqa: PLC0415 - dependencia opcional
    from ezdxf.lldxf.types import DXFTag  # noqa: PLC0415 - dependencia opcional

    def add(handle: str, owner: str, tags: list[tuple[int, Any]]) -> None:
        raw = [DXFTag(0, "FIELD"), DXFTag(5, handle), DXFTag(102, "{ACAD_REACTORS"), DXFTag(330, owner), DXFTag(102, "}"),
               DXFTag(330, owner), DXFTag(100, "AcDbField"), *(DXFTag(group, value) for group, value in tags)]
        entity = DXFTagStorage.load(ExtendedTags(raw), document)
        document.entitydb.add(entity)
        document.objects.add_object(entity)

    def value_tags(name: str, kind: int, value: list[tuple[int, Any]]) -> list[tuple[int, Any]]:
        return [(6, name), (93, 2), (90, kind), *value, (94, 0), (300, ""), (302, ""), (304, "ACVALUE_END")]

    fields = label.new_extension_dict().dictionary.add_new_dict("ACAD_FIELD")
    parent = document.entitydb.next_handle()
    children = [document.entitydb.next_handle() for _ in polylines]
    for child, polyline in zip(children, polylines, strict=True):
        points = list(polyline.get_points("xy"))
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:], strict=False))
        shown = f"{length:.2f}"
        add(child, parent, [
            (1, "AcObjProp"), (2, f'\\AcObjProp Object(%<\\_ObjIdx 0>%).Length \\f "{_FIELD_FORMAT}"'), (90, 0), (97, 1),
            (331, polyline.dxf.handle), (91, 63), (92, 0), (94, 59), (95, 2), (96, 0), (300, ""), (93, 2),
            *value_tags("ObjectPropertyId", 64, [(330, polyline.dxf.handle)]), *value_tags("ObjectPropertyName", 4, [(1, "Length")]),
            (7, "ACFD_FIELD_VALUE"), (93, 4), (90, 2), (140, length), (94, 0), (300, _FIELD_FORMAT), (302, shown),
            (304, "ACVALUE_END"), (301, shown), (98, len(shown))])
    add(parent, fields.dxf.handle, [
        (1, "_text"), (2, code), (90, len(children)), *((360, child) for child in children), (97, 0), (91, 63), (92, 0), (94, 13),
        (95, 2), (96, 0), (300, ""), (93, 1), *value_tags("ACFD_FIELDTEXT_CHECKSUM", 2, [(140, 0.0)]), (7, "ACFD_FIELD_VALUE"),
        (93, 3), (90, 0), (94, 0), (300, ""), (302, ""), (304, "ACVALUE_END"), (301, ""), (98, 0)])
    fields["TEXT"] = document.entitydb[parent]
