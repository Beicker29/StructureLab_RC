# Cabezales, perfil nsr-10

Cabezales sobre pilotes según NSR-10 Título C (D-138). Los campos de entrada y de salida están en
[docs/formatos/cabezales.md](../../../docs/formatos/cabezales.md). NSR-10 no fija empotramiento, borde ni tolerancia mínima: esas revisiones no aplican y la tolerancia declarada se usa igual.

Los ejemplos van por tipología, cada una con su `LEEME.md` (ejemplos y comandos) y su copia congelada en `pruebas/`:

| Carpeta | Contenido |
| --- | --- |
| [`una_columna/`](una_columna/LEEME.md) | Cabezales de una columna sobre pilotes: verificación (D-138, D-141) y diseño (D-141), con las cargas de la columna o de cada pilote, declaradas o desde ETABS. |
| [`varias_columnas/`](varias_columnas/LEEME.md) | Cabezales de varias columnas sobre pilotes (D-143, D-145): secciones entre columnas, franja de cada columna y punzonamiento por columna. Solo verificación; su diseño está pendiente. |

## Cómo correrlos

Todos los ejemplos para iterar de este elemento (salta las carpetas `pruebas/`):

```console
structurelab-rc run examples/nsr_10/cabezales
```

Las copias congeladas de las pruebas, en orden:

```console
structurelab-rc run examples/nsr_10/cabezales/una_columna/pruebas
structurelab-rc run examples/nsr_10/cabezales/varias_columnas/pruebas
```

Los mismos pasos que hace `run`, por separado (importar de ETABS, verificar y diseñar):

```console
structurelab-rc import-etabs-footings "examples/etabs/cabezales/columna/Joint Reactions - Servicio.xlsx" "examples/etabs/cabezales/columna/Joint Reactions - Ultimas.xlsx" examples/nsr_10/cabezales/una_columna/cabezal_columna_etabs.json --output results/nsr_10/cabezales/etabs.json
structurelab-rc report results/nsr_10/cabezales/etabs.json --output results/nsr_10/cabezales/etabs
structurelab-rc design-pile-caps examples/nsr_10/cabezales/una_columna/diseno_cabezal_columna.json --output results/nsr_10/cabezales/diseno_cabezal_columna
```
