import importlib
import inspect
import pkgutil
from types import ModuleType

from structurelab_rc.codes import aci_318_25, nsr_10


def _public_api(package: ModuleType) -> dict[str, dict[str, str]]:
    api = {}
    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        own = {name: obj for name, obj in vars(module).items() if inspect.isfunction(obj) and obj.__module__ == module.__name__}
        api[info.name] = {name: str(inspect.signature(function)) for name, function in own.items() if not name.startswith("_")}
    return api


def test_profiles_expose_the_same_modules_and_names() -> None:
    aci = _public_api(aci_318_25)
    assert aci
    assert aci == _public_api(nsr_10)
