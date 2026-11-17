"""Dibujo del cabezal (D-138): las vistas de la zapata aislada (domain/footing/drawing.py) con los pilotes: su
contorno y su nombre en las plantas y, en los cortes, el tramo empotrado y un trozo bajo el cabezal de los pilotes que
corta el plano."""

from structurelab_rc.detailing.schedule import BarRun, ScheduleRow
from structurelab_rc.domain.footing.drawing import footing_views
from structurelab_rc.drawing.model import Circle, Drawing, Polyline, Text, View
from structurelab_rc.drawing.views import rectangle
from structurelab_rc.model.pile_cap import PileCap

LAYER = "PILOTES"


def _plan_piles(drawing: Drawing, cap: PileCap) -> list[Circle | Text]:
    size = cap.pile.size
    entities: list[Circle | Text] = []
    for pile in cap.piles:
        if cap.pile.shape == "circular":
            entities.append(Circle(LAYER, (pile.x, pile.y), size / 2, filled=False))
        entities.append(Text(LAYER, (pile.x - size / 2, pile.y + size / 2 + drawing.text_height(small=True) / 2), pile.id,
                             drawing.text_height(small=True)))
    return entities


def pile_cap_views(drawing: Drawing, cap: PileCap, runs: list[BarRun], rows: tuple[list[ScheduleRow], float]) -> list[View]:
    """Planta de geometría, plantas del refuerzo, cortes X-X e Y-Y por las columnas y cartilla, con los pilotes."""
    views = footing_views(drawing, cap, runs, rows)
    if cap.clipped_corners:  # D-141: el contorno real en lugar del rectángulo
        rectangle_outline = rectangle("CONCRETO", (-cap.lx / 2, -cap.ly / 2), (cap.lx / 2, cap.ly / 2))
        polygon = Polyline("CONCRETO", cap.outline, closed=True)
        for view in views:
            view.entities[:] = [polygon if entity == rectangle_outline else entity for entity in view.entities]
    size, stub = cap.pile.size, cap.pile.size / 2
    for view in views:
        if view.name == "geometria" or view.name.startswith("planta_"):
            view.entities.extend(_plan_piles(drawing, cap))
            if cap.pile.shape == "square":
                view.entities.extend(rectangle(LAYER, (pile.x - size / 2, pile.y - size / 2), (pile.x + size / 2, pile.y + size / 2),
                                               dashed=True) for pile in cap.piles)
        elif view.name in ("corte_x", "corte_y"):
            middle = (sum(c.offset_x for c in cap.columns) / len(cap.columns), sum(c.offset_y for c in cap.columns) / len(cap.columns))
            along, across, cut = (0, 1, middle[1]) if view.name == "corte_x" else (1, 0, middle[0])
            for pile in cap.piles:
                position = (pile.x, pile.y)
                if abs(position[across] - cut) <= size / 2:
                    view.entities.append(rectangle(LAYER, (position[along] - size / 2, -stub),
                                                   (position[along] + size / 2, cap.pile.embedment)))
    return views
