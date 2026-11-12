"""Momentos de diseño de una placa con momento torsor, por el método de Wood-Armer (Wood 1968, Armer 1968; D-118).

mx y my son los momentos flectores por unidad de ancho de las barras x e y, y mxy el momento torsor por unidad de ancho
(N·mm/mm o cualquier unidad consistente). M > 0 tracciona la cara inferior, como en el resto del paquete. Las barras
inferiores se diseñan con mx*, my* ≥ 0 y las superiores con mx*, my* ≤ 0:

    inferior: mx* = mx + |mxy|,  my* = my + |mxy|
              si mx* < 0: mx* = 0, my* = my + |mxy²/mx|;  si my* < 0: my* = 0, mx* = mx + |mxy²/my|
    superior: mx* = mx − |mxy|,  my* = my − |mxy|
              si mx* > 0: mx* = 0, my* = my − |mxy²/mx|;  si my* > 0: my* = 0, mx* = mx − |mxy²/my|

Un valor que tras la corrección queda del lado contrario se anula: esa cara no necesita refuerzo en esa dirección.
No conoce φ ni numerales.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceMoments:
    """Momentos de diseño de una cara (por unidad de ancho): x para las barras x e y para las barras y."""

    x: float
    y: float


@dataclass(frozen=True)
class WoodArmer:
    bottom: FaceMoments  # ≥ 0
    top: FaceMoments  # ≤ 0


def wood_armer(mx: float, my: float, mxy: float) -> WoodArmer:
    """Momentos de diseño de las caras inferior y superior por Wood-Armer."""
    bottom = _face(mx, my, abs(mxy))
    top = _face(-mx, -my, abs(mxy))  # la cara superior es la inferior de la placa con los momentos cambiados de signo
    return WoodArmer(bottom, FaceMoments(-top.x if top.x else 0.0, -top.y if top.y else 0.0))


def _face(mx: float, my: float, twist: float) -> FaceMoments:
    """La cara traccionada por los momentos positivos: twist es |mxy|."""
    x, y = mx + twist, my + twist
    if x < 0:
        x, y = 0.0, my + twist**2 / abs(mx)
    elif y < 0:
        x, y = mx + twist**2 / abs(my), 0.0
    return FaceMoments(max(x, 0.0), max(y, 0.0))
