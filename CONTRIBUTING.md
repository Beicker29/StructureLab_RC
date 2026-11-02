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

Cuando existan ejemplos, también debe mantenerse estable su huella.

## Oráculos

Todo cambio de cálculo requiere casos en el oráculo independiente del perfil afectado,
`tests/oracles/<perfil>/`:

- El oráculo no importa el paquete `structurelab_rc`.
- No se modifican valores de referencia para hacer pasar un cambio.
- Cada perfil tiene sus propios casos, con el numeral de su propia norma.
