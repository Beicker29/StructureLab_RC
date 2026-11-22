# Diseño por tipologías de zapatas, perfil aci-318-25

Diseño por tipologías (D-069): N zapatas tipo que cubren todas las columnas al menor costo, con un solo f'c, desde las
cargas declaradas o desde ETABS; con zapatas combinadas para los pares de columnas que el usuario declara (D-153), agrupadas en N tipos si se pide (D-157), y el aviso de zapatas más
cercanas que la separación mínima (D-156), y la curva costo-N (D-078). Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md)
y la plantilla de ETABS en [docs/formatos/etabs.md](../../../../docs/formatos/etabs.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `diseno_tipologias.json` | Diseño por tipologías con las cargas declaradas (D-069): 6 columnas, 6 zapatas tipo, f'c de 21, 24.5 y 28 MPa con sus precios. `combined_footings` vacío: para unir un par se declaran allí sus dos columnas (posición, sección y cargas) y su `combined_design` (D-153, D-156). |
| `diseno_tipologias_etabs.json` | Diseño por tipologías desde los Excel de `examples/etabs/zapatas/`: los nudos de las zapatas aisladas van en `columns` (por grupos de sección) y los pares de las combinadas en `combined_pairs` (D-153), cualquiera de los dos puede quedar vacío; un solo f'c; `min_clear_spacing` avisa las zapatas más cercanas, con sus nudos (D-156). Aquí 67 apoyos aislados y los pares 150-1599, 28-1604 y 6-19 en un solo tipo de combinada (`combined_typologies` = 1, D-157); la copia de `pruebas/` usa los 6 apoyos de CIM_ST1''_N-2.918 con el par 12-20. **Datos supuestos.** Tarda varios minutos. |
| `curva_tipologias.json` | Curva costo-N (D-078, D-096): el mismo proyecto de `diseno_tipologias.json`, diseñado para N = 1 a 6 (bloque `curve`). |
| `curva_tipologias_aisladas_etabs.json` | Curva costo-N desde ETABS con todas las zapatas aisladas (D-165): los nudos se declaran en `columns`, por grupos de sección (los 70 apoyos de `examples/etabs/zapatas/`, N = 4 a 8; la copia de `pruebas/`, los 6 apoyos de CIM_ST1''_N-2.918, N = 1 a 4). **Datos supuestos.** Tarda varios minutos. |
| `curva_tipologias_combinadas_etabs.json` | Curva costo-N desde ETABS con zapatas aisladas y combinadas (D-165): los nudos de las aisladas en `columns` y los de cada par en `combined_pairs` (los pares 150-1599, 28-1604 y 6-19 en un tipo, `combined_typologies` = 1; la copia de `pruebas/`, el par 12-20). El tipo de combinada se declara en `combined_design.shape` (`rectangular`, `inverted_t`; `trapezoid` y `stepped` se declaran, pero su diseño aún no existe) y cada par puede cambiarlo en su `design`. N es el número de tipologías de las aisladas; las combinadas suman su costo. **Datos supuestos.** Tarda varios minutos. |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Las plantillas `<tipo>_etabs.json` leen los Excel
de `examples/etabs/zapatas/` (sus rutas, en `etabs_files`, son relativas a la plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/aci_318_25/zapatas/tipologias/<ejemplo>/` el `proyecto.json` diseñado, `tipologias.json`
(el resumen), el `resultado.json`, las memorias y las figuras; la curva deja `curva.csv`, `curva.svg` y su memoria.

```console
structurelab-rc run examples/aci_318_25/zapatas/tipologias/diseno_tipologias.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/diseno_tipologias_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/curva_tipologias.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/curva_tipologias_aisladas_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/curva_tipologias_combinadas_etabs.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/aci_318_25/zapatas/tipologias
structurelab-rc run examples/aci_318_25/zapatas/tipologias/pruebas
```

`diseno_tipologias_etabs.json` (73 apoyos) y `curva_tipologias.json` (el diseño para cada N) tardan minutos; `--workers N`
fija los procesos en paralelo. El diseño usa por defecto el método `milp_iter` (D-077), que requiere
`pip install structurelab-rc[opt]`.
