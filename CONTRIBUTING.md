# Cómo contribuir

Las reglas de trabajo completas están en [CLAUDE.md](CLAUDE.md).

## Verificación

Todos estos comandos deben terminar limpios antes de cerrar una tarea:

```console
pytest -n auto
ruff check .
mypy
lint-imports
python -m build
```

`-n auto` reparte las pruebas entre los núcleos del equipo (`pytest-xdist`, extra `dev`; D-124); sin él corren en un solo
proceso, con el mismo resultado. Lo más lento son las huellas de los ejemplos de diseño.

La huella de los ejemplos (`tests/test_fingerprints.py`) debe mantenerse estable. Si un cambio de cálculo la
modifica a propósito, se reporta la diferencia y solo entonces se actualiza, en un solo proceso (en paralelo, varios
procesos escribirían a la vez `tests/fingerprints.json`):

```console
STRUCTURELAB_UPDATE_FINGERPRINTS=1 pytest -n 0 tests/test_fingerprints.py
```

## Oráculos

Todo cambio de cálculo requiere casos en el oráculo independiente del perfil afectado,
`tests/oracles/<perfil>/`:

- El oráculo no importa el paquete `structurelab_rc`.
- No se modifican valores de referencia para hacer pasar un cambio.
- Cada perfil tiene sus propios casos, con el numeral de su propia norma.
- Los casos son archivos JSON que indican su fuente. `tests/test_oracles.py` los compara con el paquete.
- Los casos derivados a mano se generan con `python tests/oracles/derive_flexure_cases.py`, que
  usa solución cerrada y comprueba sus hipótesis. Se marcan como derivados, no como de un manual.
