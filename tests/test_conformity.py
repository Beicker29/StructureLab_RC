import importlib
import inspect
import pkgutil
from types import ModuleType

from structurelab_rc.codes import aci_318_25, nsr_10


def _public_api(package: ModuleType) -> dict[str, dict[str, str]]:
    api = {}
    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        names = (name for name in vars(module) if not name.startswith("_"))
        api[info.name] = {name: str(inspect.signature(getattr(module, name))) for name in names}
    return api


def test_profiles_expose_the_same_modules_and_names() -> None:
    aci = _public_api(aci_318_25)
    assert aci
    assert aci == _public_api(nsr_10)
