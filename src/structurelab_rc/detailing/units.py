"""Elementos tipo y sus N unidades (D-159). Neutro y común a todos los elementos (zapatas, cabezales y los que vengan):
recibe la cartilla de cada elemento y devuelve una cartilla por tipo, con las veces que se construye.

- El tipo de un elemento es su typology declarada o, sin ella, su id. Su cartilla se calcula con el nombre del tipo, así
  que las marcas son las del tipo ("Z3-01").
- N es la suma de quantity de los elementos del tipo: en la verificación y el diseño de un elemento, la declarada; en el
  diseño por tipologías, una por columna o par (cada uno es una zapata).
- Los elementos de un tipo se unen solo si sus cartillas coinciden barra por barra (marca, barra, forma, dimensiones,
  longitud de corte, cantidad y ganchos). El grupo y la nota no cuentan, porque nombran las columnas de cada elemento; el
  tipo conserva los del primero. Un elemento que no coincide queda como su propio tipo, con su id, y un aviso.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.detailing.schedule import ScheduleRow


@dataclass(frozen=True)
class Member:
    """Un elemento con su tipo, las veces que se construye y su cartilla (con las marcas del tipo)."""

    id: str
    typology: str
    quantity: int
    rows: tuple[ScheduleRow, ...]


@dataclass(frozen=True)
class Unit:
    """Un tipo: su nombre, los elementos que lo construyen, N (las unidades) y la cartilla de una unidad."""

    name: str
    members: tuple[str, ...]
    quantity: int
    rows: tuple[ScheduleRow, ...]


def _bars(rows: Sequence[ScheduleRow]) -> list[tuple[object, ...]]:
    """Lo que debe coincidir entre los elementos de un tipo: marca y barra cortada, sin el grupo ni la nota."""
    return [(row.mark, row.piece.designation, row.piece.shape, row.piece.dimensions, row.piece.cut_length, row.piece.count,
             row.piece.angles) for row in rows]


def _renamed(member: Member) -> tuple[ScheduleRow, ...]:
    """La cartilla de un elemento con las marcas de su id en lugar de las del tipo ("Z3-01" -> "Z3-150-01")."""
    prefix = f"{member.typology}-"
    return tuple(replace(row, mark=member.id + "-" + row.mark.removeprefix(prefix)) for row in member.rows)


def units(members: Sequence[Member]) -> tuple[list[Unit], list[str]]:
    """Los tipos, en el orden en que aparecen sus elementos, y un aviso por cada elemento que no coincide con su tipo."""
    found: dict[str, Unit] = {}
    warnings: list[str] = []
    for member in members:
        unit = found.get(member.typology)
        if unit is None:
            found[member.typology] = Unit(member.typology, (member.id,), member.quantity, member.rows)
        elif _bars(member.rows) == _bars(unit.rows):
            found[member.typology] = replace(unit, members=(*unit.members, member.id), quantity=unit.quantity + member.quantity)
        else:
            warnings.append(f"{member.id} declara el tipo {member.typology} pero su refuerzo no coincide con el de "
                            f"{unit.members[0]}: su cartilla va aparte, con su id (D-159)")
            found[member.id] = Unit(member.id, (member.id,), member.quantity, _renamed(member))
    return list(found.values()), warnings


def scaled(rows: Sequence[ScheduleRow], quantity: int) -> list[ScheduleRow]:
    """La cartilla de N unidades: la cantidad de cada marca por N (el peso de la fila sale de la cantidad)."""
    return [replace(row, piece=replace(row.piece, count=row.piece.count * quantity)) for row in rows]
