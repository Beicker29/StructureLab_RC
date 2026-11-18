# Zapata combinada de dos columnas, perfil nsr-10

Zapatas combinadas rectangulares de dos columnas: verificación (D-080 a D-083) y diseño (D-107), con las cargas declaradas y desde ETABS. Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_combinada.json` | Ejemplo de zapata combinada: ZC1 rectangular de 7.0 × 2.6 m bajo dos columnas (C1 de 500 × 500 mm cerca del borde −X y C2 de 550 × 550 mm desplazada 150 mm en Y), con cargas de servicio y mayoradas, sismo en X, refuerzo transversal (band) bajo cada columna y barras superiores transversales #5 c/300 (top.y, D-097, D-099). La torsión de la viga larga queda bajo φTth (D-088). Datos ilustrativos (D-080 a D-083). |
| `zapata_combinada_etabs_A.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `zapata_combinada_etabs_BK.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `zapata_combinada_etabs_cgl.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `zapata_combinada_etabs_FH.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `zapata_combinada_etabs_j.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `zapata_combinada_etabs_m.json` | Plantilla para iterar de un par de columnas de ETABS (del usuario). |
| `diseno_combinada.json` | Diseño de la zapata combinada (D-107): las columnas y cargas de `zapata_combinada.json` (posiciones con origen en C1); el diseño ubica la base en la resultante de D+L y elige dimensiones, f'c (21 o 28 MPa) y refuerzo de menor costo. |
| `diseno_combinada_etabs.json` | Diseño de zapata combinada desde los Excel de `examples/etabs/zapatas/` (D-112): las dos columnas de ZC-A de `zapata_combinada_etabs.json` toman sus cargas de ETABS; la base se ubica con SERVICIO 1 (D+L) (`placement_case`). **Datos supuestos.** |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/nsr_10/zapatas/combinada/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_A.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_BK.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_cgl.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_FH.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_j.json
structurelab-rc run examples/nsr_10/zapatas/combinada/zapata_combinada_etabs_m.json
structurelab-rc run examples/nsr_10/zapatas/combinada/diseno_combinada.json
structurelab-rc run examples/nsr_10/zapatas/combinada/diseno_combinada_etabs.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/nsr_10/zapatas/combinada
structurelab-rc run examples/nsr_10/zapatas/combinada/pruebas
```
