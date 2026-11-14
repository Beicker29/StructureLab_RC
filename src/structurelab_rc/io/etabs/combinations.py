"""Excel de combinaciones (D-137): la lista explícita de las combinaciones de ETABS que entran a la verificación o al
diseño de las cimentaciones, con su tipo y sus factores. Reemplaza el bloque load_factors de las plantillas.

Hoja "Combinaciones", encabezados en la primera fila y una combinación por fila:

| Combinacion | Tipo | Factor D | Factor L | Sismo | Usar |

- Combinacion: el nombre exacto del Output Case de las tablas Joint Reactions.
- Tipo: Servicio o Última (Ultima). Cada combinación se lee solo de la tabla de su tipo.
- Factor D: multiplica el peso propio, el relleno y la sobrecarga muerta; Factor L, la sobrecarga viva (D-054, D-057).
- Sismo: Sí o No (D-070).
- Usar: Sí o No. Solo entran las filas con Sí; las combinaciones de las tablas que no estén listadas, o estén con No, se
  ignoran y la importación dice cuáles omitió.
"""

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from structurelab_rc.errors import StructuredError, invalid_input
from structurelab_rc.io.etabs.importer import EtabsImportError
from structurelab_rc.io.etabs.xlsx import read_rows
from structurelab_rc.model.template import LoadFactors

SHEET = "Combinaciones"
COLUMNS = ("Combinacion", "Tipo", "Factor D", "Factor L", "Sismo", "Usar")
_KINDS = {"servicio": "service", "ultima": "factored"}
_YES_NO = {"si": True, "no": False}


@dataclass(frozen=True)
class Combination:
    """Una combinación que entra: su tipo (service o factored) y sus factores."""

    name: str
    kind: str
    factors: LoadFactors


def _plain(text: str) -> str:
    """Sin tildes ni mayúsculas: Última -> ultima, Sí -> si."""
    return "".join(char for char in unicodedata.normalize("NFD", text.strip().lower()) if unicodedata.category(char) != "Mn")


def _number(row: dict[str, str], column: str, where: str, errors: list[StructuredError]) -> float:
    try:
        value = float(row[column].replace(",", "."))
    except ValueError:
        errors.append(invalid_input(f"{where}: '{column}' debe ser un numero; viene '{row[column]}'"))
        return 0.0
    if value < 0:
        errors.append(invalid_input(f"{where}: '{column}' no puede ser negativo"))
    return value


def _choice(row: dict[str, str], column: str, options: dict[str, object], where: str, errors: list[StructuredError]) -> object:
    value = options.get(_plain(row[column]))
    if value is None:
        errors.append(invalid_input(f"{where}: '{column}' debe ser {' o '.join(options)}; viene '{row[column]}'"))
    return value


def read_combinations(path: Path) -> dict[str, Combination]:
    """Las combinaciones con Usar = Sí, por nombre; lanza EtabsImportError con todos los problemas del libro."""
    headers, rows = read_rows(path, SHEET)
    errors = [invalid_input(f"Falta la columna '{column}' en el Excel de combinaciones") for column in COLUMNS
              if column not in headers]
    if errors:
        raise EtabsImportError(tuple(errors))
    combinations: dict[str, Combination] = {}
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        name, where = row["Combinacion"], f"Excel de combinaciones, fila {index}"
        if not name:
            errors.append(invalid_input(f"{where}: falta el nombre de la combinacion"))
            continue
        if name in seen:
            errors.append(invalid_input(f"{where}: la combinacion '{name}' esta repetida"))
            continue
        seen.add(name)
        before = len(errors)
        kind = _choice(row, "Tipo", dict(_KINDS), where, errors)
        dead, live = _number(row, "Factor D", where, errors), _number(row, "Factor L", where, errors)
        seismic = _choice(row, "Sismo", dict(_YES_NO), where, errors)
        use = _choice(row, "Usar", dict(_YES_NO), where, errors)
        if use is True and len(errors) == before and isinstance(kind, str) and isinstance(seismic, bool):
            combinations[name] = Combination(name, kind, LoadFactors(dead=dead, live=live, seismic=seismic))
    if not errors and not combinations:
        errors.append(invalid_input("El Excel de combinaciones no tiene ninguna combinacion con Usar = Si"))
    if errors:
        raise EtabsImportError(tuple(errors))
    return combinations
