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
_SIZES = {"title": 13.0, "h1": 10.5, "h2": 8.5, "body": 7.0}
_LINE = 3.6


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

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        pdf = self.pdf
        width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.set_font(self.font, "B", _SIZES["body"])
        heads = [pdf.get_string_width(self.clean(str(header))) for header in headers]
        pdf.set_font(self.font, "", _SIZES["body"])
        natural = [max(heads[index], *(pdf.get_string_width(self.clean(str(row[index]))) for row in rows)) + 2 * pdf.c_margin + 1
                   for index in range(len(headers))]
        scale = min(1.0, width / sum(natural))
        widths = [w * scale for w in natural]
        for row, bold in ((headers, True), *((row, False) for row in rows)):
            pdf.set_font(self.font, "B" if bold else "", _SIZES["body"])
            texts = [self.clean(str(cell)) for cell in row]
            counts = [self.lines(w, text) for w, text in zip(widths, texts, strict=True)]
            height = max(counts) * _LINE
            if pdf.get_y() + height > pdf.page_break_trigger:
                pdf.add_page()
            y = pdf.get_y()
            x = pdf.l_margin
            for w, text, count in zip(widths, texts, counts, strict=True):
                pdf.set_xy(x, y)
                if count == 1:
                    pdf.cell(w, height, text, border=1)
                else:
                    pdf.multi_cell(w, _LINE, text, border=1)
                x += w
            pdf.set_xy(pdf.l_margin, y + height)
        pdf.ln(1)

    def lines(self, width: float, text: str) -> int:
        """Renglones de una celda; solo se simula el ajuste de línea si el texto no cabe en uno (lo poco común)."""
        if self.pdf.get_string_width(text) <= width - 2 * self.pdf.c_margin:
            return 1
        return len(self.pdf.multi_cell(width, _LINE, text, dry_run=True, output="LINES"))

    def block(self, block: dict[str, Any]) -> None:
        kind = block["kind"]
        if kind == "title":
            self.text(f"Memoria de cálculo — {block['element']}", _SIZES["title"], bold=True)
            for key, value in block["meta"]:
                self.text(f"{key}: {value}", _SIZES["body"])
            ratio = "" if block["ratio"] is None else f"   DCR máx. = {block['ratio']:.3f}"
            self.text(f"RESULTADO: {block['status']} ({block['status_text']}){ratio}", _SIZES["h1"], bold=True, gap=1.5)
        elif kind == "summary":
            for item in block["items"]:
                self.text(item, _SIZES["body"])
        elif kind in ("h1", "h2"):
            self.text(block["text"], _SIZES[kind], bold=True, gap=2.0)
        elif kind == "table":
            self.table(block["headers"], block["rows"])
        elif kind == "kv":
            for key, value in block["items"]:
                self.text(f"{key}: {value}", _SIZES["body"])
        elif kind in ("p", "note", "alert"):
            prefix = {"p": "", "note": "• ", "alert": "! "}[kind]
            self.text(prefix + block["text"], _SIZES["body"])


def write_pdf(documents: list[list[dict[str, Any]]], path: Path) -> bool:
    """Escribe el PDF con una memoria por elemento, cada una desde una página nueva; False si fpdf2 no está instalado."""
    try:
        from fpdf import FPDF  # noqa: PLC0415 - dependencia opcional
    except ImportError:
        return False
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)  # avisos al incrustar la fuente
    document = FPDF(orientation="L", format="A4")
    document.set_auto_page_break(auto=True, margin=10)
    renderer = _Renderer(document)
    for blocks in documents:
        document.add_page()
        for block in blocks:
            renderer.block(block)
    document.output(str(path))
    return True
