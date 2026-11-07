"""Memoria en PDF con fpdf2 (extra opcional `pdf`); el contenido es el mismo de la memoria en texto.

Las fuentes básicas del PDF solo admiten Latin-1: los caracteres fuera de ese rango, que pueden venir en los textos
del usuario (descripción, justificación), se escriben con un equivalente en ASCII.
"""

import unicodedata
from pathlib import Path

_FONT_SIZE = 7
_LINE_HEIGHT = 3.2
_LATIN1_LIMIT = 256
_EQUIVALENTS = {"≥": ">=", "≤": "<=", "φ": "phi", "ϕ": "phi", "β": "beta", "ε": "eps", "λ": "lambda", "ρ": "rho",
                "θ": "theta", "·": ".", "√": "raiz", "ℓ": "l", "−": "-", "×": "x", "²": "2", "³": "3", "°": " grados",
                "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}


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


def write_pdf(text: str, path: Path) -> bool:
    """Escribe el PDF; devuelve False si fpdf2 no está instalado."""
    try:
        from fpdf import FPDF  # noqa: PLC0415 - dependencia opcional
    except ImportError:
        return False
    document = FPDF(orientation="L", format="A4")
    document.set_auto_page_break(auto=True, margin=10)
    document.add_page()
    document.set_font("Courier", size=_FONT_SIZE)
    for line in text.splitlines():
        document.multi_cell(0, _LINE_HEIGHT, latin1(line) or " ", new_x="LMARGIN", new_y="NEXT")
    document.output(str(path))
    return True
