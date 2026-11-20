# Diseño por tipologías de zapatas, perfil aci-318-25

Diseño por tipologías (D-069): N zapatas tipo que cubren todas las columnas al menor costo, con un solo f'c, desde las
cargas declaradas o desde ETABS; con zapatas combinadas para los pares de columnas declarados (D-153), y la curva
costo-N (D-078). Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md)
y la plantilla de ETABS en [docs/formatos/etabs.md](../../../../docs/formatos/etabs.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `diseno_tipologias.json` | Diseño por tipologías (D-069): 6 columnas, 6 zapatas tipo, f'c de 21, 24.5 y 28 MPa con sus precios. |
| `diseno_tipologias_etabs.json` | Diseño por tipologías desde los Excel compartidos de `examples/etabs/zapatas/`: cada Unique Name es una columna de 500 × 800 mm (cx × cy) con la zapata centrada; 6 tipologías y f'c de 21, 24.5 y 28 MPa. **Datos supuestos.** El diseño de los 73 apoyos tarda varios minutos. |
| `diseno_tipologias_combinadas_etabs.json` | Diseño por tipologías con una zapata combinada (D-153): los 6 apoyos del nivel CIM_ST1''_N-2.918; el par 12-20 va en la combinada ZC1 (`combined_pairs`, dirección principal Y) y los otros 4 por tipologías aisladas, con un solo f'c. Las posiciones del par salen de la tabla de coordenadas. **Datos supuestos.** |
| `curva_tipologias.json` | Curva costo-N (D-078, D-096): el mismo proyecto de `diseno_tipologias.json`, diseñado para N = 1 a 6 (bloque `curve`). |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Las plantillas `<tipo>_etabs.json` leen los Excel
de `examples/etabs/zapatas/` (sus rutas, en `etabs_files`, son relativas a la plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/aci_318_25/zapatas/tipologias/<ejemplo>/` el `proyecto.json` diseñado, `tipologias.json`
(el resumen), el `resultado.json`, las memorias y las figuras; la curva deja `curva.csv`, `curva.svg` y su memoria.

```console
structurelab-rc run examples/aci_318_25/zapatas/tipologias/diseno_tipologias.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/diseno_tipologias_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/diseno_tipologias_combinadas_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/tipologias/curva_tipologias.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/aci_318_25/zapatas/tipologias
structurelab-rc run examples/aci_318_25/zapatas/tipologias/pruebas
```

`diseno_tipologias_etabs.json` (73 apoyos) y `curva_tipologias.json` (el diseño para cada N) tardan minutos; `--workers N`
fija los procesos en paralelo. El diseño usa por defecto el método `milp_iter` (D-077), que requiere
`pip install structurelab-rc[opt]`; `diseno_tipologias_combinadas_etabs.json` usa `dp`.
