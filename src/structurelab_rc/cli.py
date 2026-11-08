"""Interfaz de línea de comandos."""

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path

from structurelab_rc import __version__
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.engine import design_footings, import_etabs, import_etabs_footings, report_file, validate_file, verify_file
from structurelab_rc.reporting.units import display
from structurelab_rc.setup import load_engine


def _catalog() -> int:
    _print_catalog()
    return 0


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
        where = f"{check.member} z={check.z:.0f}" if check.z is not None else check.member
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


def _import_etabs_footings(service: Path, factored: Path, template: Path, output: Path) -> int:
    project, summary, check = import_etabs_footings(service, factored, template)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    if project is None or summary is None or check.status is Status.FAIL:
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Zapatas: {summary.footings}; casos de servicio: {len(summary.service_cases)}; "
          f"casos mayorados: {len(summary.factored_cases)}")
    print(f"Filas omitidas (no son combinaciones): {summary.skipped_rows}")
    print(f"Proyecto escrito en {output}")
    return 0


def _design_footings(path: Path, output: Path) -> int:
    project, result, check = design_footings(path)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    if project is None or result is None:
        return 1
    output.mkdir(parents=True, exist_ok=True)
    (output / "proyecto.json").write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"fc [MPa]": result.fc, "cost": round(result.cost, 2), "typologies": [
        {"name": item.name, "lx [mm]": item.design.typology.lx, "ly [mm]": item.design.typology.ly,
         "h [mm]": item.design.typology.h, "bottom": item.design.typology.bottom, "top": item.design.typology.top,
         "columns": list(item.columns), "dowels": item.design.dowels, "concrete [m3]": round(item.design.concrete, 3),
         "steel [kg]": round(item.design.steel, 1), "cost": round(item.design.cost, 2)} for item in result.typologies]}
    (output / "tipologias.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"f'c = {result.fc:g} MPa; {len(result.typologies)} tipologias; costo total {result.cost:.2f}")
    for item in result.typologies:
        t = item.design.typology
        print(f"  {item.name}: {t.lx:.0f} x {t.ly:.0f} x {t.h:.0f} mm; {len(item.columns)} columnas: {', '.join(item.columns)}")
    print(f"Proyecto escrito en {output / 'proyecto.json'}; verifiquelo o genere su memoria con report")
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
    footings = commands.add_parser("import-etabs-footings",
                                   help="genera un proyecto de zapatas desde las reacciones de ETABS y una plantilla")
    footings.add_argument("service", type=Path, help="Excel de ETABS con las reacciones de servicio (Joint Reactions)")
    footings.add_argument("factored", type=Path, help="Excel de ETABS con las reacciones mayoradas (Joint Reactions)")
    footings.add_argument("template", type=Path, help="plantilla JSON con los tipos de zapata y el suelo")
    footings.add_argument("--output", type=Path, required=True, help="ruta del proyecto JSON a escribir")
    designer = commands.add_parser("design-footings", help="disena zapatas por tipologias desde un proyecto de diseno")
    designer.add_argument("project", type=Path, help="proyecto de diseno en JSON (columnas y bloque design)")
    designer.add_argument("--output", type=Path, required=True, help="carpeta donde escribir proyecto.json y tipologias.json")
    reporter = commands.add_parser("report", help="verifica un proyecto y escribe resultado.json, memoria.txt y memoria.pdf")
    reporter.add_argument("project", type=Path, help="ruta del archivo JSON")
    reporter.add_argument("--output", type=Path, required=True, help="carpeta de salida, por ejemplo results/mi_proyecto")
    reporter.add_argument("--full", action="store_true", help="incluye en la memoria el detalle de todas las estaciones")
    args = parser.parse_args(argv)
    commands_by_name: dict[str, Callable[[], int]] = {
        "report": lambda: _report(args.project, args.output, args.full),
        "design-footings": lambda: _design_footings(args.project, args.output),
        "import-etabs-footings": lambda: _import_etabs_footings(args.service, args.factored, args.template, args.output),
        "import-etabs": lambda: _import_etabs(args.workbook, args.template, args.output),
        "validate": lambda: _validate(args.project),
        "verify": lambda: _verify(args.project),
        "catalog": _catalog,
    }
    return commands_by_name[args.command]()
