# Cómo contribuir

Las reglas de trabajo completas están en [AGENTS.md](AGENTS.md).

## Verificación

Todos estos comandos deben terminar limpios antes de cerrar una tarea:

```console
pytest
ruff check .
mypy
lint-imports
python -m build
```

La huella de los ejemplos (`tests/test_fingerprints.py`) debe mantenerse estable. Si un cambio de cálculo la
modifica a propósito, se reporta la diferencia y solo entonces se actualiza:

```console
STRUCTURELAB_UPDATE_FINGERPRINTS=1 pytest tests/test_fingerprints.py
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
