"""Memoria de cálculo en PDF con fpdf2 (extra opcional `pdf`): dibuja los mismos bloques que el texto (D-068).

Usa una fuente TrueType del sistema para φ, ², · y demás símbolos. Si no encuentra ninguna, usa las fuentes básicas del
PDF, que solo admiten Latin-1, y escribe los demás caracteres con un equivalente en ASCII.
"""

import logging
import unicodedata
from pathlib import Path
from typing import Any

_LATIN1_LIMIT = 256
_EQUIVALENTS = {"≥": ">=", "≤": "<=", "φ": "phi", "ϕ": "phi", "β": "beta", "ε": "eps", "λ": "lambda", "ρ": "rho",
                "θ": "theta", "γ": "gamma", "α": "alfa", "Σ": "suma", "·": ".", "√": "raiz", "ℓ": "l", "−": "-", "×": "x",
                "²": "2", "³": "3", "⁴": "4", "°": " grados", "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}
_FONTS = (("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
          ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
          ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
          ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"))
_SIZES = {"title": 14.0, "h1": 11.0, "h2": 9.0, "h3": 8.0, "body": 7.0, "small": 6.0}
_LINE = 3.6
# Estilo de la memoria (D-105): sobrio y formal, con un azul oscuro de acento.
_ACCENT = (31, 56, 100)  # títulos, reglas y encabezado de las tablas
_HEADER_TEXT = (255, 255, 255)
_ZEBRA = (244, 246, 249)  # filas alternas de las tablas
_RULE = (200, 206, 216)  # bordes de las tablas
_MUTED = (90, 98, 110)  # notas y rótulos
_STATUS_COLORS = {"PASS": (46, 125, 50), "FAIL": (192, 0, 0), "INCOMPLETE": (191, 120, 0), "BLOCKED": (110, 110, 110)}
_DANGER = (192, 0, 0)  # rojo de los avisos de la viga de cimentación
_IMAGE_FRACTION = 0.75  # ancho de una gráfica respecto al ancho útil de la página


def latin1(text: str) -> str:
    """Texto representable en Latin-1: equivalentes en ASCII y, como último recurso, '?'."""
    replaced = "".join(_EQUIVALENTS.get(char, char) for char in text)
    out = []
    for char in replaced:
        if ord(char) < _LATIN1_LIMIT:
            out.append(char)
            continue
        base = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode("ascii")
        out.append(base or "?")
    return "".join(out)


class _Renderer:
    def __init__(self, document: Any) -> None:
        self.pdf = document
        fonts = next(((regular, bold) for regular, bold in _FONTS if Path(regular).is_file() and Path(bold).is_file()), None)
        if fonts is None:
            self.font, self.clean = "Helvetica", latin1
        else:
            document.add_font("Body", "", fonts[0])
            document.add_font("Body", "B", fonts[1])
            self.font, self.clean = "Body", (lambda text: text)

    def text(self, text: str, size: float, bold: bool = False, gap: float = 0.0) -> None:
        pdf = self.pdf
        pdf.set_font(self.font, "B" if bold else "", size)
        pdf.ln(gap)
        content, height = self.clean(text) or " ", size * 0.5 + 1
        # cell es mucho más rápida que multi_cell; el ajuste de línea solo hace falta si el texto no cabe en un renglón.
        if pdf.get_string_width(content) <= pdf.w - pdf.l_margin - pdf.r_margin - 2 * pdf.c_margin:
            pdf.cell(0, height, content, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(0, height, content, new_x="LMARGIN", new_y="NEXT")

    def table(self, headers: list[str], rows: list[list[str]], emphasis: frozenset[tuple[int, int]] = frozenset()) -> None:
        """Tabla con el encabezado en el color de acento, filas alternas sombreadas y bordes tenues; las celdas de
        emphasis (fila, columna) van en negrilla. El encabezado se repite al cambiar de página."""
        pdf = self.pdf
        widths = self.widths(headers, rows, pdf.w - pdf.l_margin - pdf.r_margin)
        pdf.set_draw_color(*_RULE)
        pdf.set_line_width(0.15)
        head = self._height(headers, widths, True)
        if pdf.get_y() + head + self._height(rows[0], widths, False) > pdf.page_break_trigger if rows else False:
            pdf.add_page()
        self._row(headers, widths, (True, False, frozenset()))
        for index, row in enumerate(rows):
            if pdf.get_y() + self._height(row, widths, False) > pdf.page_break_trigger:
                pdf.add_page()
                self._row(headers, widths, (True, False, frozenset()))
            bold = frozenset(column for r, column in emphasis if r == index)
            self._row(row, widths, (False, index % 2 == 1, bold))
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.ln(1.5)

    def _height(self, row: list[str], widths: list[float], header: bool) -> float:
        self.pdf.set_font(self.font, "B" if header else "", _SIZES["body"])
        texts = [self.clean(str(cell)) for cell in row]
        return max(self.lines(w, text) for w, text in zip(widths, texts, strict=True)) * _LINE + 0.6

    def _row(self, row: list[str], widths: list[float], style: tuple[bool, bool, frozenset[int]]) -> None:
        """Una fila; style = (encabezado, sombreada, columnas en negrilla)."""
        header, shade, bold = style
        pdf = self.pdf
        height = self._height(row, widths, header)
        y, x = pdf.get_y(), pdf.l_margin
        fill = _ACCENT if header else (_ZEBRA if shade else None)
        for column, (w, cell) in enumerate(zip(widths, row, strict=True)):
            text = self.clean(str(cell))
            pdf.set_xy(x, y)
            pdf.set_font(self.font, "B" if header or column in bold else "", _SIZES["body"])
            pdf.set_text_color(*(_HEADER_TEXT if header else (0, 0, 0)))
            if fill is not None:
                pdf.set_fill_color(*fill)
            count = self.lines(w, text)
            if count == 1:
                pdf.cell(w, height, text, border=1, fill=fill is not None)
            else:
                # Celda de varios renglones: el fondo y el borde ocupan toda la altura de la fila.
                pdf.rect(x, y, w, height, style="DF" if fill is not None else "D")
                pdf.set_xy(x, y + 0.3)
                pdf.multi_cell(w, _LINE, text, border=0)
            x += w
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(pdf.l_margin, y + height)

    def widths(self, headers: list[str], rows: list[list[str]], width: float) -> list[float]:
        """Ancho de cada columna: el natural (su texto más largo en un renglón) si todo cabe; si no, cada columna conserva
        al menos su palabra más larga (no se parten palabras como CUMPLE o los números) y el ancho que sobra se reparte
        entre las columnas en proporción a lo que les falta para su ancho natural."""
        pdf = self.pdf
        pad = 2 * pdf.c_margin + 1
        natural, minimum = [], []
        for index, header in enumerate(headers):
            pdf.set_font(self.font, "B", _SIZES["body"])
            head = self.clean(str(header))
            # Solo el espacio común separa palabras: el de no separación las une (signo, número y unidad).
            longest, word = pdf.get_string_width(head), max((pdf.get_string_width(part) for part in head.split(" ")), default=0.0)
            pdf.set_font(self.font, "", _SIZES["body"])
            for row in rows:
                text = self.clean(str(row[index]))
                longest = max(longest, pdf.get_string_width(text))
                word = max(word, *(pdf.get_string_width(part) for part in text.split(" ")), 0.0)
            natural.append(longest + pad)
            minimum.append(min(word, longest) + pad)
        if sum(natural) <= width:
            return natural
        spare = width - sum(minimum)
        if spare <= 0:
            return [w * width / sum(minimum) for w in minimum]
        wanting = [n - m for n, m in zip(natural, minimum, strict=True)]
        return [m + spare * want / sum(wanting) for m, want in zip(minimum, wanting, strict=True)]

    def lines(self, width: float, text: str) -> int:
        """Renglones de una celda; solo se simula el ajuste de línea si el texto no cabe en uno (lo poco común)."""
        if self.pdf.get_string_width(text) <= width - 2 * self.pdf.c_margin:
            return 1
        return len(self.pdf.multi_cell(width, _LINE, text, dry_run=True, output="LINES"))

    def title(self, block: dict[str, Any]) -> None:
        """Bloque de título: el nombre del elemento, sus datos en dos columnas y un cuadro con el resultado y el DCR."""
        pdf = self.pdf
        pdf.set_text_color(*_ACCENT)
        self.text("Memoria de cálculo", _SIZES["small"], bold=True)
        self.text(block["element"], _SIZES["title"], bold=True)
        pdf.set_text_color(0, 0, 0)
        y = pdf.get_y() + 1
        pdf.set_draw_color(*_ACCENT)
        pdf.set_line_width(0.5)
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.set_y(y + 2)
        for key, value in block["meta"]:
            pdf.set_font(self.font, "B", _SIZES["body"])
            pdf.set_text_color(*_MUTED)
            pdf.cell(48, _LINE + 0.4, self.clean(key))
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(self.font, "", _SIZES["body"])
            pdf.multi_cell(0, _LINE + 0.4, self.clean(str(value)), new_x="LMARGIN", new_y="NEXT")
        ratio = "" if block["ratio"] is None else f"     DCR máx. = {block['ratio']:.3f}"
        color = _STATUS_COLORS.get(block["status"], _MUTED)
        pdf.ln(2)
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(self.font, "B", _SIZES["h1"])
        pdf.cell(0, 8, self.clean(f"  RESULTADO: {block['status_text']}{ratio}"), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.ln(2)

    def heading(self, kind: str, text: str) -> None:
        """Títulos en el color de acento; el de capítulo con una regla debajo."""
        pdf = self.pdf
        # Un título no queda solo al pie de la página: necesita sitio para lo que sigue.
        if pdf.get_y() + {"h1": 30, "h2": 25, "h3": 20}[kind] > pdf.page_break_trigger:
            pdf.add_page()
        pdf.set_text_color(*(_ACCENT if kind != "h3" else _MUTED))
        self.text(text, _SIZES[kind], bold=True, gap={"h1": 4.0, "h2": 2.5, "h3": 1.5}[kind])
        pdf.set_text_color(0, 0, 0)
        if kind == "h1":
            y = pdf.get_y() + 0.5
            pdf.set_draw_color(*_ACCENT)
            pdf.set_line_width(0.3)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)
            pdf.ln(2)

    def block(self, block: dict[str, Any]) -> None:
        kind = block["kind"]
        if kind == "title":
            self.title(block)
        elif kind == "summary":
            for item in block["items"]:
                self.text(f"• {item}", _SIZES["body"])
        elif kind in ("h1", "h2", "h3"):
            self.heading(kind, block["text"])
        elif kind == "table":
            self.table(block["headers"], block["rows"], frozenset((row, column) for row, column in block.get("bold", [])))
        elif kind == "kv":
            pdf = self.pdf
            for key, value in block["items"]:
                pdf.set_font(self.font, "B", _SIZES["body"])
                pdf.cell(pdf.get_string_width(self.clean(f"{key}: ")) + 1, _LINE + 0.4, self.clean(f"{key}: "))
                pdf.set_font(self.font, "", _SIZES["body"])
                pdf.multi_cell(0, _LINE + 0.4, self.clean(str(value)), new_x="LMARGIN", new_y="NEXT")
        elif kind == "alert" and block.get("tone") == "danger":
            # Avisos que el analista debe llevar al diseño de la viga de cimentación: rojo y negrilla (D-103).
            self.pdf.set_text_color(*_DANGER)
            self.text(block["text"], _SIZES["body"], bold=True)
            self.pdf.set_text_color(0, 0, 0)
        elif kind == "note":
            self.pdf.set_text_color(*_MUTED)
            self.text(f"• {block['text']}", _SIZES["body"])
            self.pdf.set_text_color(0, 0, 0)
        elif kind in ("p", "alert"):
            self.text(("! " if kind == "alert" else "") + block["text"], _SIZES["body"])
        elif kind == "image":
            self.image(block)

    def image(self, block: dict[str, Any]) -> None:
        """Gráfica (SVG o imagen) centrada, con su rótulo numerado debajo; desde una página nueva si no cabe (D-105)."""
        pdf = self.pdf
        width = (pdf.w - pdf.l_margin - pdf.r_margin) * _IMAGE_FRACTION
        height = width * block["aspect"]
        tallest = pdf.page_break_trigger - pdf.t_margin - 12  # una figura alta (la cartilla, D-126) cabe en una página
        if height > tallest:
            width, height = tallest / block["aspect"], tallest
        if pdf.get_y() + height + 8 > pdf.page_break_trigger:
            pdf.add_page()
        pdf.ln(1)
        pdf.image(block["path"], x=(pdf.w - width) / 2, w=width, h=height)
        caption = f"Figura {block['number']}. {block['caption']}" if block.get("number") else block["caption"]
        pdf.set_text_color(*_MUTED)
        pdf.set_font(self.font, "B", _SIZES["body"])
        pdf.cell(0, _LINE + 1, self.clean(caption), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)


def write_pdf(documents: list[list[dict[str, Any]]], path: Path) -> bool:
    """Escribe el PDF con una memoria por elemento, cada una desde una página nueva; False si fpdf2 no está instalado."""
    try:
        from fpdf import FPDF  # noqa: PLC0415 - dependencia opcional
    except ImportError:
        return False
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)  # avisos al incrustar la fuente

    class _Document(FPDF):  # type: ignore[misc]
        """Encabezado con el elemento y la norma, y pie con el número de página (D-105)."""

        running = ""

        def header(self) -> None:
            if self.page_no() == 1 and not self.running:
                return
            self.set_font(renderer.font, "", _SIZES["small"])
            self.set_text_color(*_MUTED)
            self.cell(0, 4, renderer.clean(self.running), new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*_RULE)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.set_draw_color(0, 0, 0)
            self.set_text_color(0, 0, 0)
            self.ln(3)

        def footer(self) -> None:
            self.set_y(-10)
            self.set_font(renderer.font, "", _SIZES["small"])
            self.set_text_color(*_MUTED)
            self.cell(0, 4, renderer.clean(f"StructureLab_RC · página {self.page_no()}"), align="R")
            self.set_text_color(0, 0, 0)

    document = _Document(orientation="P", format="A4")  # vertical (pedido del usuario, D-114)
    document.set_margins(15, 12, 15)
    document.set_auto_page_break(auto=True, margin=14)
    renderer = _Renderer(document)
    for blocks in documents:
        title = next((block for block in blocks if block["kind"] == "title"), None)
        norma = next((value for key, value in title["meta"] if key == "Norma"), "") if title else ""
        document.running = f"Memoria de cálculo — {title['element']}" + (f" · {norma}" if norma else "") if title else ""
        document.add_page()
        for block in blocks:
            renderer.block(block)
    document.output(str(path))
    return True
