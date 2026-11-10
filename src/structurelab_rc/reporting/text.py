"""Memoria de cálculo en texto: dibuja los bloques de document.py (D-068)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

_SEPARATOR = "=" * 100


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    cells = [headers, *rows]
    widths = [max(len(str(row[index])) for row in cells) for index in range(len(headers))]

    def line(row: list[str]) -> str:
        return "  ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()

    return [line(headers), "  ".join("-" * width for width in widths), *(line(row) for row in rows)]


def _title(block: dict[str, Any]) -> list[str]:
    lines = [f"# Memoria de cálculo — {block['element']}", *(f"{key}: {value}" for key, value in block["meta"])]
    ratio = "" if block["ratio"] is None else f"   DCR máx. = {block['ratio']:.3f}"
    return [*lines, "", f"RESULTADO: {block['status']} ({block['status_text']}){ratio}"]


_RENDER: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "title": _title,
    "summary": lambda block: list(block["items"]),
    "h1": lambda block: ["", f"## {block['text']}"],
    "h2": lambda block: ["", f"### {block['text']}"],
    "table": lambda block: _table(block["headers"], block["rows"]),
    "kv": lambda block: [f"{key}: {value}" for key, value in block["items"]],
    "p": lambda block: [block["text"]],
    "note": lambda block: [f"- {block['text']}"],
    "alert": lambda block: [f"! {block['text']}"],
    "image": lambda block: [f"[Gráfica: {block['caption']}; archivo {Path(block['path']).name}]"],
}


def render_text(documents: list[list[dict[str, Any]]]) -> str:
    """Todas las memorias del proyecto, una tras otra, separadas por una línea."""
    out: list[str] = []
    for index, blocks in enumerate(documents):
        if index:
            out += ["", _SEPARATOR, ""]
        for block in blocks:
            out += _RENDER[block["kind"]](block)
    return "\n".join(out) + "\n"
