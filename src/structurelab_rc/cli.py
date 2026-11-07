"""Interfaz de línea de comandos."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from structurelab_rc import __version__
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.engine import import_etabs, report_file, validate_file, verify_file
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
        where = f"{check.member} z={check.z:.0f}" if check.z is not None else ""
        demand, capacity = display(check.demand, check.unit), display(check.capacity, check.unit)
        print(f"{where:<16}{check.name:<50}{check.status:<11}{demand:>16}{capacity:>16}  {check.clause}")
        _print_errors(check)
    overall = aggregate(check.status for check in checks)
    print(f"Resultado: {overall}")
    return 1 if overall is Status.FAIL else 0


def _import_etabs(workbook: Path, template: Path, output: Path) -> int:
    project, summary, check = import_etabs(workbook, template)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    if project is None or summary is None or check.status is Status.FAIL:
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Miembros: {summary.members}; estaciones: {summary.stations}; estados de carga: {len(summary.cases)}")
    print(f"Filas omitidas (no son combinaciones o no se pidieron): {summary.skipped_rows}")
    print(f"Proyecto escrito en {output}")
    return 0


def _report(project: Path, output: Path, full: bool) -> int:
    report = report_file(project, output, full=full)
    print(f"Resultado: {report.status}")
    for path in report.files:
        print(f"  {path}")
    if not report.pdf_written:
        print("  memoria.pdf no se genero: instale el extra con  pip install structurelab-rc[pdf]")
    return 1 if report.status == Status.FAIL else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="structurelab-rc", description="Concreto reforzado: verificación, diseño y despiece.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="lista las barras del catálogo")
    validate = commands.add_parser("validate", help="valida un proyecto en JSON")
    validate.add_argument("project", type=Path, help="ruta del archivo JSON")
    verify = commands.add_parser("verify", help="verifica las vigas de un proyecto en JSON")
    verify.add_argument("project", type=Path, help="ruta del archivo JSON")
    importer = commands.add_parser("import-etabs", help="genera un proyecto JSON desde el Excel de ETABS y una plantilla")
    importer.add_argument("workbook", type=Path, help="Excel exportado de ETABS (Element Forces - Beams)")
    importer.add_argument("template", type=Path, help="plantilla JSON con secciones y tramos de armado")
    importer.add_argument("--output", type=Path, required=True, help="ruta del proyecto JSON a escribir")
    reporter = commands.add_parser("report", help="verifica un proyecto y escribe resultado.json, memoria.txt y memoria.pdf")
    reporter.add_argument("project", type=Path, help="ruta del archivo JSON")
    reporter.add_argument("--output", type=Path, required=True, help="carpeta de salida, por ejemplo results/mi_proyecto")
    reporter.add_argument("--full", action="store_true", help="incluye en la memoria el detalle de todas las estaciones")
    args = parser.parse_args(argv)
    if args.command == "report":
        return _report(args.project, args.output, args.full)
    if args.command == "import-etabs":
        return _import_etabs(args.workbook, args.template, args.output)
    if args.command == "validate":
        return _validate(args.project)
    if args.command == "verify":
        return _verify(args.project)
    _print_catalog()
    return 0
