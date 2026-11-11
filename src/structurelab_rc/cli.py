"""Interfaz de línea de comandos."""

import argparse
import io
import json
import os
import platform
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from structurelab_rc import __version__
from structurelab_rc.design.footing.typologies import Iteration, MilpInfo
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.engine import (
    RUN_KINDS,
    RunError,
    RunPlan,
    design_footings,
    import_etabs,
    import_etabs_footings,
    profile_footings,
    report_file,
    run_plan,
    typology_curve_file,
    validate_file,
    verify_file,
)
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


def _optional_path(value: str) -> Path | None:
    """Un Excel de ETABS, o "-" para omitirlo (D-084)."""
    return None if value == "-" else Path(value)


def _import_etabs_footings(service: str, factored: str, template: Path, output: Path) -> int:
    project, summary, check = import_etabs_footings(_optional_path(service), _optional_path(factored), template)
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


def _iterations(items: Sequence[Iteration]) -> list[dict[str, Any]]:
    return [{"number": item.number, "candidates": item.candidates, "cost": round(item.cost, 2), "status": item.status,
             "seconds": round(item.seconds, 1)} for item in items]


def _design_footings(path: Path, output: Path, workers: int | None, profile: bool, method: str | None) -> int:
    processes = workers or os.cpu_count() or 1
    measurement = None
    if profile:
        project, result, check, measurement = profile_footings(path, processes, method)
    else:
        project, result, check = design_footings(path, processes, method)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    if measurement is not None:
        output.mkdir(parents=True, exist_ok=True)
        data = {"environment": _environment(processes), "project": str(path), **measurement}
        (output / "medicion.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Medicion escrita en {output / 'medicion.json'}")
    if project is None or result is None:
        return 1
    output.mkdir(parents=True, exist_ok=True)
    (output / "proyecto.json").write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"method": result.method, "fc [MPa]": result.fc, "cost": round(result.cost, 2),
               **({"milp": _milp_summary(result.milp)} if result.milp is not None else {}),
               **({"iterations": _iterations(result.iterations)} if result.iterations else {}),
               "cost_before_reassignment": round(result.cost_before_reassignment, 2),
               "distinct_count": result.distinct_count,
               "duplicates": [{"typologies": list(group.typologies), "at_limit": list(group.at_limit)} for group in result.duplicates],
               "reassigned": [{"column": move.column, "from": move.source, "to": move.target, "saving": round(move.saving, 2)}
                              for move in result.reassigned],
               "by_fc": [{"fc [MPa]": option.fc, "cost": None if option.cost is None else round(option.cost, 2),
                          "distinct_count": option.distinct_count, **({"failure": option.failure} if option.failure else {}),
                          **({"milp": _milp_summary(option.milp)} if option.milp is not None else {}),
                          **({"iterations": _iterations(option.iterations)} if option.iterations else {})}
                         for option in result.options],
               "typologies": [
        {"name": item.name, "lx [mm]": item.design.typology.lx, "ly [mm]": item.design.typology.ly,
         "h [mm]": item.design.typology.h, "bottom": item.design.typology.bottom, "top": item.design.typology.top,
         "columns": list(item.columns), "dowels": item.design.dowels, "concrete [m3]": round(item.design.concrete, 3),
         "steel [kg]": round(item.design.steel, 1), "cost": round(item.design.cost, 2)} for item in result.typologies]}
    (output / "tipologias.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"f'c = {result.fc:g} MPa; {len(result.typologies)} tipologias; costo total {result.cost:.2f}")
    for item in result.typologies:
        t = item.design.typology
        print(f"  {item.name}: {t.lx:.0f} x {t.ly:.0f} x {t.h:.0f} mm; {len(item.columns)} columnas: {', '.join(item.columns)}")
    if result.reassigned:
        print(f"Reasignadas {len(result.reassigned)} columnas; costo antes de reasignar {result.cost_before_reassignment:.2f}")
    if result.milp is not None:
        milp = result.milp
        print(f"MILP: {milp.status}; costo DP {milp.dp_cost:.2f} ({milp.dp_distinct_count} distintas); "
              f"{milp.candidates} candidatos; {milp.seconds:.1f} s" + (f"; {milp.note}" if milp.note else ""))
    for step in result.iterations:
        print(f"Iteracion {step.number}: {step.candidates} candidatos; costo {step.cost:.2f}; {step.status}; {step.seconds:.1f} s")
    for group in result.duplicates:
        limit = f" (en el limite {', '.join(group.at_limit)})" if group.at_limit else ""
        print(f"ADVERTENCIA: tipologias repetidas {' = '.join(group.typologies)}{limit}; "
              f"{result.distinct_count} distintas de {len(result.typologies)}")
    print(f"Proyecto escrito en {output / 'proyecto.json'}; verifiquelo o genere su memoria con report")
    return 0


def _milp_summary(milp: MilpInfo) -> dict[str, Any]:
    return {"status": milp.status, "dp_cost": round(milp.dp_cost, 2), "dp_distinct_count": milp.dp_distinct_count,
            "milp_cost": None if milp.milp_cost is None else round(milp.milp_cost, 2), "candidates": milp.candidates,
            "seconds": round(milp.seconds, 1), "note": milp.note}


def _environment(workers: int) -> dict[str, Any]:
    """Configuración de la medición: SHA, máquina, sistema operativo y procesos."""
    return {"sha": _git_sha(), "machine": platform.processor() or platform.machine(), "cpu_count": os.cpu_count(),
            "os": platform.platform(), "python": platform.python_version(), "workers": workers}


def _git_sha() -> str:
    """SHA del HEAD leído de .git (no exige git instalado); no detecta cambios sin commit."""
    for folder in (Path.cwd(), *Path.cwd().parents):
        git = folder / ".git"
        if not (git / "HEAD").exists():
            continue
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        ref = head.removeprefix("ref: ")
        if (git / ref).exists():
            return (git / ref).read_text(encoding="utf-8").strip()
        packed = git / "packed-refs"
        lines = packed.read_text(encoding="utf-8").splitlines() if packed.exists() else []
        return next((line.split()[0] for line in lines if line.endswith(f" {ref}")), "desconocido")
    return "desconocido"


def _report(project: Path, output: Path, full: bool) -> int:
    report = report_file(project, output, full=full)
    print(f"Resultado: {report.status}")
    for path in report.files:
        print(f"  {path}")
    if not report.pdf_written:
        print("  memoria.pdf no se genero: instale el extra con  pip install structurelab-rc[pdf]")
    return 1 if report.status == Status.FAIL else 0


def _counts(text: str) -> list[int]:
    """N de la curva: "1-12", "2,4,6" o una combinación ("1-4,8")."""
    counts: set[int] = set()
    try:
        for part in text.split(","):
            low, _, high = part.strip().partition("-")
            counts.update(range(int(low), int(high or low) + 1))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"valores de N no validos: {text}") from error
    return sorted(counts)


def _typology_curve(path: Path, output: Path, counts: list[int] | None, workers: int | None, method: str | None) -> int:
    report, check = typology_curve_file(path, output, counts, workers or os.cpu_count() or 1, method)
    print(f"{check.name}: {check.status}")
    _print_errors(check)
    if report is None:
        return 1
    data = report.data
    print(f"Curva costo-N ({data['method']}, {data['seconds']:.0f} s)")
    for row in data["points"]:
        if row["cost"] is None:
            print(f"  N = {row['N']:2d}: sin solucion")
            continue
        saving = "" if row["saving"] is None else f"; ahorro {row['saving']:.2f} ({row['saving [%]']:.2f} %)"
        flags = (" SUBE" if row["rises"] else "") + (" (repetidas)" if row["duplicates"] else "")
        print(f"  N = {row['N']:2d}: f'c {row['fc [MPa]']:g} MPa; costo {row['cost']:.2f}{saving}{flags}")
    for path_written in report.files:
        print(f"  {path_written}")
    return 0


def _run_one(path: Path, output: Path | None, workers: int | None, full: bool) -> int:
    """Un ejemplo de punta a punta (D-096): importa de ETABS si es una plantilla, diseña si es un diseño por tipologías y
    deja en una sola carpeta resultado.json, memoria.txt, memoria.pdf y las figuras (o la curva costo-N)."""
    try:
        plan = run_plan(path, output)
    except RunError as error:
        print(error)
        return 1
    out = plan.output
    print(f"Ejemplo: {path} ({RUN_KINDS[plan.kind]}); salida en {out}")
    if plan.kind == "project":
        return _report(path, out, full)
    if plan.kind == "curve":
        return _typology_curve(path, out, None, workers, None)
    if plan.kind == "design":
        return _design_footings(path, out, workers, False, None) or _report(out / "proyecto.json", out, full)
    return _run_etabs(plan, workers, full)


def _run_etabs(plan: RunPlan, workers: int | None, full: bool) -> int:
    """Plantilla de ETABS: importa sus Excel (etabs_files) y verifica el proyecto, o lo diseña si es de diseño."""
    out = plan.output
    imported = out / ("diseno.json" if plan.kind == "etabs_design" else "proyecto.json")
    if plan.kind == "etabs_beams":
        assert plan.workbook is not None
        code = _import_etabs(plan.workbook, plan.path, imported)
    else:
        code = _import_etabs_footings(str(plan.service or "-"), str(plan.factored or "-"), plan.path, imported)
    if code:
        return code
    if plan.kind == "etabs_design":
        return _design_footings(imported, out, workers, False, None) or _report(out / "proyecto.json", out, full)
    return _report(imported, out, full)


def _run(target: Path, output: Path | None, workers: int | None, full: bool) -> int:
    """Un ejemplo, o todos los de una carpeta (cada uno en su carpeta de salida; con --output, debajo de ella)."""
    if not target.is_dir():
        return _run_one(target, output, workers, full)
    examples = sorted(path for path in target.rglob("*.json") if "results" not in path.parts)
    codes = []
    for path in examples:
        own = None if output is None else output / path.parent.relative_to(target) / path.stem
        print(f"\n=== {path}")
        codes.append((path, _run_one(path, own, workers, full)))
    print("\nResumen (0: cumple; 1: no cumple o error):")
    for path, code in codes:
        print(f"  {code}  {path}")
    return 1 if any(code for _, code in codes) else 0


def _tolerant_console() -> None:
    """Una consola que no tiene un carácter (por ejemplo, "≤" en cp1252 de Windows con la salida redirigida) lo reemplaza
    en lugar de interrumpir el comando cuando los resultados ya están escritos."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _tolerant_console()
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
    footings.add_argument("service", help="Excel de ETABS con las reacciones de servicio (Joint Reactions), o - para omitirlo")
    footings.add_argument("factored", help="Excel de ETABS con las reacciones mayoradas (Joint Reactions), o - para omitirlo")
    footings.add_argument("template", type=Path, help="plantilla JSON con los tipos de zapata y el suelo")
    footings.add_argument("--output", type=Path, required=True, help="ruta del proyecto JSON a escribir")
    designer = commands.add_parser("design-footings", help="disena zapatas por tipologias desde un proyecto de diseno")
    designer.add_argument("project", type=Path, help="proyecto de diseno en JSON (columnas y bloque design)")
    designer.add_argument("--output", type=Path, required=True, help="carpeta donde escribir proyecto.json y tipologias.json")
    designer.add_argument("--workers", type=int, help="procesos en paralelo (por defecto, los nucleos del equipo; 1: sin paralelo)")
    designer.add_argument("--profile", action="store_true",
                          help="escribe ademas medicion.json: tiempos por tarea y analisis de la solucion (no cambia el resultado)")
    designer.add_argument("--method", choices=("dp", "milp", "milp_iter"),
                          help="dp (particion), milp (asignacion optima) o milp_iter (iterativo, sin tabla de tramos); los dos "
                               "ultimos requieren structurelab-rc[opt]; reemplaza design.method")
    curve = commands.add_parser("typology-curve", help="curva costo-N del diseno por tipologias (D-078)")
    curve.add_argument("project", type=Path, help="proyecto de diseno en JSON (columnas y bloque design)")
    curve.add_argument("--output", type=Path, required=True, help="carpeta de salida: resultado.json, curva.csv, curva.svg y la memoria")
    curve.add_argument("--n", type=_counts, help="valores de N, por ejemplo 1-12 o 2,4,6 (por defecto, de 1 a 12 o al numero de columnas)")
    curve.add_argument("--workers", type=int, help="procesos en paralelo (por defecto, los nucleos del equipo; 1: sin paralelo)")
    curve.add_argument("--method", choices=("dp", "milp", "milp_iter"), help="reemplaza design.method")
    runner = commands.add_parser("run", help="corre un ejemplo de punta a punta (o todos los de una carpeta): resultado.json, "
                                             "memorias PDF y TXT y figuras (D-096)")
    runner.add_argument("target", type=Path, help="ejemplo JSON (proyecto, diseno, curva o plantilla de ETABS) o carpeta")
    runner.add_argument("--output", type=Path, help="carpeta de salida (por defecto results/<perfil>/<elemento>/<nombre>)")
    runner.add_argument("--workers", type=int, help="procesos en paralelo para el diseno y la curva")
    runner.add_argument("--full", action="store_true", help="incluye en la memoria el detalle de todas las estaciones")
    reporter = commands.add_parser("report", help="verifica un proyecto y escribe resultado.json, memoria.txt y memoria.pdf")
    reporter.add_argument("project", type=Path, help="ruta del archivo JSON")
    reporter.add_argument("--output", type=Path, required=True, help="carpeta de salida, por ejemplo results/mi_proyecto")
    reporter.add_argument("--full", action="store_true", help="incluye en la memoria el detalle de todas las estaciones")
    args = parser.parse_args(argv)
    commands_by_name: dict[str, Callable[[], int]] = {
        "report": lambda: _report(args.project, args.output, args.full),
        "run": lambda: _run(args.target, args.output, args.workers, args.full),
        "design-footings": lambda: _design_footings(args.project, args.output, args.workers, args.profile, args.method),
        "typology-curve": lambda: _typology_curve(args.project, args.output, args.n, args.workers, args.method),
        "import-etabs-footings": lambda: _import_etabs_footings(args.service, args.factored, args.template, args.output),
        "import-etabs": lambda: _import_etabs(args.workbook, args.template, args.output),
        "validate": lambda: _validate(args.project),
        "verify": lambda: _verify(args.project),
        "catalog": _catalog,
    }
    return commands_by_name[args.command]()
