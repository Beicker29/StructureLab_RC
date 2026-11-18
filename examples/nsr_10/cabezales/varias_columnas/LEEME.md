# Cabezales de varias columnas, perfil nsr-10

Cabezales de varias columnas sobre pilotes (D-143, D-145): secciones entre columnas, franja de cada columna y punzonamiento por columna. Solo verificación; su diseño está pendiente. Los campos de entrada y de salida están en [docs/formatos/cabezales.md](../../../../docs/formatos/cabezales.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `cabezal_dos_columnas.json` | Dos columnas de 500 × 500 a 1400 mm entre ejes sobre seis pilotes de 400 mm en malla 3 × 2 (D-143), con las fuerzas de cada columna: secciones entre columnas, franja de cada columna y punzonamiento por columna. Datos ilustrativos. |
| `cabezal_cuatro_columnas.json` | Cuatro columnas de 500 × 500 en cuadrícula 2 × 2 a 1400 mm entre ejes sobre nueve pilotes de 400 mm en malla 3 × 3 (D-145): franjas en las dos direcciones, con la columna vecina dentro de la franja. Datos ilustrativos. |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/nsr_10/cabezales/varias_columnas/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/nsr_10/cabezales/varias_columnas/cabezal_dos_columnas.json
structurelab-rc run examples/nsr_10/cabezales/varias_columnas/cabezal_cuatro_columnas.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/nsr_10/cabezales/varias_columnas
structurelab-rc run examples/nsr_10/cabezales/varias_columnas/pruebas
```
