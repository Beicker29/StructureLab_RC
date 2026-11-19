"""Cartilla DL-NET (.dli) para el pedido de acero figurado (D-133): traduce la cartilla del despiece (detailing/schedule,
el mismo modelo para zapatas, vigas y los elementos que vengan) a un archivo que DL-NET (PazdelRío) abre directamente.

Formato (deducido por ingeniería inversa de archivos guardados por DL-NET 2026; ver docs/formatos/dlnet.md):

- Secuencia de registros [puntero float64 LE][n uint16 LE][texto n bytes latin-1][cola 2 bytes], con
  puntero = offset del registro + 12 + n + 1 (la posición, en base 1, del registro siguiente). El último registro es
  FINALDEARCHIVORANDOM, sin cola, y su puntero repite el del anterior. La cola parece residuo de búfer y se conserva.
- Orden: encabezado, librería de barras, librería de mallas, bloque de elementos (" N" y, por elemento, su nombre,
  " k" y k líneas) y la cola del archivo: los grupos (" G" y, por grupo, nombre, marca y la pertenencia de cada
  elemento) y lo demás.
- El encabezado, las librerías y lo que sigue a los grupos se copian de la plantilla (un archivo real de DL-NET, que
  lleva la licencia del usuario y por eso no se versiona). La pertenencia de cada grupo se rehace con el número de
  elementos.
"""

import struct
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from structurelab_rc.detailing.schedule import HOOK_ROUNDING, HOOK_SHAPE, STIRRUP_SHAPE, STRAIGHT_SHAPE, ScheduleRow, round_up

ENCODING = "latin-1"
FINAL = b"FINALDEARCHIVORANDOM"
_HEADER = struct.Struct("<dH")  # puntero y largo del texto
_TAIL = 2
_TEXT_TAIL = b"\x00\x00"  # cola de los nombres y las líneas en los archivos que escribe este módulo
_COUNT_TAIL = b"NA"  # cola de los contadores
_MM_PER_M = 1000.0

# Sintaxis de las líneas (docs/formatos/dlnet.md). Verificadas: barra con gancho de 90° en los dos extremos ("L"), barra
# recta, un gancho de 90°, gancho "U" y estribo "E" (abren en DL-NET: n_12.dli y PRUEBA_StructureLab.dli).
# "U" es el gancho de 180° (confirmado por el usuario, D-147).
HOOK_CODES = {90: "L", 180: "U"}
STIRRUP_ANGLE = 135  # gancho de cierre del estribo
STIRRUP_FIELD = "F0/90"  # TODO D-133: significado del campo F del estribo sin confirmar; se copia del ejemplo real
# La longitud de la línea es la total de la cartilla, tramo + L o U por gancho, y L y U van a 50 mm (convención de DL-NET,
# D-147). TODO D-133: confirmar que b*h del estribo son sus dimensiones exteriores; así las da la cartilla.
GROUP_MEMBER = " 1 "  # TODO D-133: la pertenencia de un elemento a un grupo de la cola (inferida: " 1  1 " con dos elementos)


class DliError(ValueError):
    """Un archivo .dli o una plantilla que no se puede leer, o una barra que DL-NET no puede representar."""


@dataclass(frozen=True)
class Record:
    """Un registro del archivo: su texto y la cola de 2 bytes que le sigue (vacía en FINALDEARCHIVORANDOM)."""

    text: bytes
    tail: bytes = _TEXT_TAIL

    @property
    def value(self) -> str:
        return self.text.decode(ENCODING)


@dataclass(frozen=True)
class DliElement:
    """Un elemento de la cartilla DL-NET: su nombre y sus líneas de barras."""

    name: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class DliFile:
    """Un archivo .dli: el prefijo (encabezado y librerías), los elementos, la cola y, si se leyó de un archivo, las
    colas originales del bloque de elementos (para reescribirlo idéntico)."""

    prefix: tuple[Record, ...]
    elements: tuple[DliElement, ...]
    suffix: tuple[Record, ...]
    block_tails: tuple[bytes, ...] | None = None


def read_records(data: bytes) -> list[Record]:
    """Los registros de un archivo .dli, hasta FINALDEARCHIVORANDOM; lo que siga se ignora (DL-NET deja ahí el residuo
    del archivo anterior cuando guarda encima de uno más largo)."""
    records, offset = [], 0
    while offset < len(data):
        if offset + _HEADER.size > len(data):
            raise DliError("archivo .dli truncado: falta FINALDEARCHIVORANDOM")
        _, size = _HEADER.unpack_from(data, offset)
        start = offset + _HEADER.size
        text = data[start:start + size]
        if text == FINAL:
            records.append(Record(text, b""))
            return records
        records.append(Record(text, data[start + size:start + size + _TAIL]))
        offset = start + size + _TAIL
    raise DliError("archivo .dli sin FINALDEARCHIVORANDOM (¿es un archivo del formato anterior, comprimido?)")


def write_records(records: Sequence[Record]) -> bytes:
    """Los bytes de una secuencia de registros, con sus punteros."""
    buffer, pointer = bytearray(), 0.0
    for record in records:
        if record.text != FINAL:
            pointer = float(len(buffer) + _HEADER.size + len(record.text) + _TAIL + 1)
        buffer += _HEADER.pack(pointer, len(record.text)) + record.text + record.tail
    return bytes(buffer)


def _count(record: Record) -> int:
    try:
        return int(record.value)
    except ValueError as error:
        raise DliError(f"se esperaba un contador y se leyó {record.value!r}") from error


def read_dli(data: bytes) -> DliFile:
    """Un archivo .dli: el bloque de elementos empieza después del último registro de librería (texto entre comillas)."""
    records = read_records(data)
    library = [index for index, record in enumerate(records) if record.text.startswith(b'"')]
    if not library:
        raise DliError("el archivo .dli no tiene librería de barras")
    index = library[-1] + 1
    start, elements = index, []
    for _ in range(_count(records[index])):
        name, size = records[index + 1].value, _count(records[index + 2])
        elements.append(DliElement(name, tuple(record.value for record in records[index + 3:index + 3 + size])))
        index += 2 + size
    end = index + 1
    return DliFile(tuple(records[:start]), tuple(elements), tuple(records[end:]), tuple(record.tail for record in records[start:end]))


def write_dli(file: DliFile) -> bytes:
    """Los bytes del archivo; con block_tails (archivo leído y sin cambios), idénticos al original."""
    block = [Record(f" {len(file.elements)}".encode(ENCODING), _COUNT_TAIL)]
    for element in file.elements:
        block.append(Record(element.name.encode(ENCODING), _TEXT_TAIL))
        block.append(Record(f" {len(element.lines)}".encode(ENCODING), _COUNT_TAIL))
        block += [Record(line.encode(ENCODING), _TEXT_TAIL) for line in element.lines]
    if file.block_tails is not None and len(file.block_tails) == len(block):
        block = [replace(record, tail=tail) for record, tail in zip(block, file.block_tails, strict=True)]
    return write_records([*file.prefix, *block, *file.suffix])


def bar_names(prefix: Sequence[Record]) -> dict[str, str]:
    """Nombre DL-NET de cada barra (el primer alias de su fila en la librería de barras de la plantilla), por cada uno de
    sus alias: "#5" -> "5/8''". La librería de barras va entre los dos primeros contadores "n + m"."""
    counters = [index for index, record in enumerate(prefix) if " + " in record.value and record.value.replace("+", "").split()
                and all(part.isdigit() for part in record.value.replace("+", " ").split())]
    if len(counters) < 2:  # noqa: PLR2004 - la librería de barras y la de mallas
        raise DliError("la plantilla no tiene la librería de barras de DL-NET")
    names: dict[str, str] = {}
    for record in prefix[counters[0] + 1:counters[1]]:
        aliases = [alias for alias in record.value.split('"')[1::2] if alias]
        for alias in aliases:
            names.setdefault(alias, aliases[0])
    return names


def number(value: float) -> str:
    """Un número en metros al estilo de DL-NET: sin cero inicial ni ceros sobrantes (0.50 -> .5, 6.00 -> 6)."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text[1:] if text.startswith("0.") else text


def _metres(value: float) -> float:
    return value / _MM_PER_M


def row_line(row: ScheduleRow, names: dict[str, str]) -> str:
    """La línea DL-NET de una marca de la cartilla, con las dimensiones de la cartilla (exteriores, redondeadas hacia
    arriba a 50 mm) y la longitud de corte como longitud total."""
    piece = row.piece
    if piece.designation not in names:
        raise DliError(f"la barra {piece.designation} de la marca {row.mark} no está en la librería de la plantilla DL-NET")
    bar = names[piece.designation]
    dimensions = {name: round_up(value) for name, value in piece.dimensions}
    if piece.shape == STIRRUP_SHAPE:
        if piece.angles != (STIRRUP_ANGLE, STIRRUP_ANGLE):
            raise DliError(f"marca {row.mark}: DL-NET solo representa estribos con ganchos de {STIRRUP_ANGLE}°")
        width, height, hook = (number(_metres(dimensions[name])) for name in ("A", "B", "C"))
        return f'{piece.count}  E  "{bar}"  {width}*{height}   G{hook}   {STIRRUP_FIELD}'
    if piece.shape != STRAIGHT_SHAPE and not set(piece.shape.split("-")) <= set(HOOK_SHAPE.values()):
        raise DliError(f"marca {row.mark}: la forma {piece.shape!r} no está soportada en la cartilla DL-NET")
    line = f'{piece.count}  "{bar}"  {number(_metres(piece.cut_length))}'
    legs = [name for name in ("B", "C") if name in dimensions]
    for angle, leg in zip([angle for angle in piece.angles if angle is not None], legs, strict=True):
        if angle not in HOOK_CODES:
            raise DliError(f"marca {row.mark}: DL-NET no tiene la sintaxis del gancho de {angle}°")
        line += f"   {HOOK_CODES[angle]}{number(_metres(round_up(dict(piece.dimensions)[leg], HOOK_ROUNDING)))}"
    return line


def schedule_dli(elements: Sequence[tuple[str, Sequence[ScheduleRow]]], template: Path) -> bytes:
    """La cartilla DL-NET de los elementos (nombre y cartilla de cada uno) sobre la plantilla: su encabezado, sus
    librerías y su cola, con la pertenencia de cada grupo rehecha para estos elementos."""
    base = read_dli(template.read_bytes())
    names = bar_names(base.prefix)
    built = tuple(DliElement(name, tuple(row_line(row, names) for row in rows)) for name, rows in elements)
    return write_dli(DliFile(base.prefix, built, _groups(base.suffix, len(built))))


def _groups(suffix: tuple[Record, ...], elements: int) -> tuple[Record, ...]:
    """La cola con la pertenencia de cada grupo rehecha: todos los elementos en cada grupo (" G" y, por grupo, nombre,
    marca y pertenencia)."""
    groups = _count(suffix[0])
    if len(suffix) < 1 + 3 * groups:
        raise DliError("la cola de la plantilla DL-NET no tiene los grupos esperados")
    records = list(suffix)
    for group in range(groups):
        index = 3 + 3 * group
        records[index] = Record((GROUP_MEMBER * elements).encode(ENCODING), records[index].tail)
    return tuple(records)


TEMPLATE_VARIABLE = "STRUCTURELAB_DLNET_TEMPLATE"
TEMPLATE_PATH = Path("references") / "dlnet" / "plantilla.dli"


def find_template(start: Path, environment: dict[str, str]) -> Path | None:
    """La plantilla DL-NET (D-133): la de la variable de entorno STRUCTURELAB_DLNET_TEMPLATE si se declara; si no,
    references/dlnet/plantilla.dli en la carpeta de start o en la superior más cercana que la tenga (references/ no se
    versiona: la plantilla lleva la licencia del usuario). None si no hay ninguna o la declarada no existe."""
    declared = environment.get(TEMPLATE_VARIABLE)
    if declared:
        return Path(declared) if Path(declared).is_file() else None
    for folder in [start.resolve(), *start.resolve().parents]:
        if (folder / TEMPLATE_PATH).is_file():
            return folder / TEMPLATE_PATH
    return None
