"""Carga de las tablas empaquetadas."""

import csv
from dataclasses import dataclass
from importlib import resources

from structurelab_rc.model.catalog import RebarSpec


@dataclass(frozen=True)
class Engine:
    bars: tuple[RebarSpec, ...]


def load_engine() -> Engine:
    text = resources.files("structurelab_rc.data").joinpath("rebar.csv").read_text(encoding="utf-8")
    bars = tuple(RebarSpec.model_validate(row) for row in csv.DictReader(text.splitlines()))
    return Engine(bars=bars)
