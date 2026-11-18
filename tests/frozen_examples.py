"""Rutas de las copias congeladas de los ejemplos (D-098), una sola fuente para las pruebas: viven en
examples/<perfil>/<elemento>/pruebas/ o, en los elementos con varias tipologías, en
examples/<perfil>/<elemento>/<tipología>/pruebas/ (D-146)."""

from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"


def frozen(profile: str, element: str, name: str) -> Path:
    """El ejemplo congelado de un perfil y un elemento por su nombre, en la tipología que lo tenga."""
    found = sorted((EXAMPLES / profile / element).glob(f"**/pruebas/{name}"))
    assert len(found) == 1, (profile, element, name, found)
    return found[0]


def frozen_all(pattern: str = "*.json") -> list[Path]:
    """Todos los ejemplos congelados de los dos perfiles (sin los Excel compartidos de examples/etabs/)."""
    return sorted(path for path in EXAMPLES.glob(f"**/pruebas/{pattern}") if path.relative_to(EXAMPLES).parts[0] != "etabs")


def profile_of(path: Path) -> str:
    return path.relative_to(EXAMPLES).parts[0]


def element_of(path: Path) -> str:
    return path.relative_to(EXAMPLES).parts[1]
