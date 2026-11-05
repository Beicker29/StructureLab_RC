"""Interfaz de línea de comandos."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from structurelab_rc import __version__
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.engine import validate_file, verify_file
from structurelab_rc.reporting.units import display
from structurelab_rc.setup import load_engine


def _print_catalog() -> None:
    print(f"{'Barra':<6}{'Diam (mm)':>10}{'Area (mm2)':>12}{'Masa (kg/m)':>13}")
    for bar in load_engine().bars:
        print(f"{bar.designation:<6}{bar.diameter_mm:>10.1f}{bar.area_mm2:>12.0f}{bar.mass_kg_m:>13.3f}")


def _print_errors(check: Check) -> None:
    for error in check.errors:
        details = f" {error.details}" if error.details else ""
        print(f"  [{error.code}] {error.message}{details}")
    if check.note:
        print(f"  {check.note}")


def _validate(path: Path) -> int:
    check = validate_file(path)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    return 1 if check.status is Status.FAIL else 0


def _verify(path: Path) -> int:
    checks = verify_file(path)
    for check in checks:
        where = f"{check.member} x={check.x:.0f}" if check.x is not None else ""
        demand, capacity = display(check.demand, check.unit), display(check.capacity, check.unit)
        print(f"{where:<16}{check.name:<40}{check.status:<11}{demand:>16}{capacity:>16}  {check.clause}")
        _print_errors(check)
    overall = aggregate(check.status for check in checks)
    print(f"Resultado: {overall}")
    return 1 if overall is Status.FAIL else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="structurelab-rc", description="Concreto reforzado: verificación, diseño y despiece.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="lista las barras del catálogo")
    validate = commands.add_parser("validate", help="valida un proyecto en JSON")
    validate.add_argument("project", type=Path, help="ruta del archivo JSON")
    verify = commands.add_parser("verify", help="verifica las vigas de un proyecto en JSON")
    verify.add_argument("project", type=Path, help="ruta del archivo JSON")
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.project)
    if args.command == "verify":
        return _verify(args.project)
    _print_catalog()
    return 0
