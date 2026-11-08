"""Base de cálculo de un elemento: perfil, materiales, catálogo de barras y nivel sísmico declarado.

Común a todos los elementos (zapatas ahora; vigas y columnas después): lo que no cambia entre los miembros de un
proyecto y que varias verificaciones necesitan, como el nivel sísmico para el factor de refuerzo en exceso (D-071).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials


@dataclass(frozen=True)
class Basis:
    profile: Profile
    materials: Materials
    bars: Sequence[RebarSpec]
    seismic_level: str
