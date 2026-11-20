# Zapata aislada, perfil nsr-10

Zapatas aisladas: verificación con las cargas declaradas y desde ETABS, diseño por tipologías (D-069) y curva costo-N (D-078). Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_centrica.json` | Ejemplo de zapata aislada céntrica: Z1 de planta cuadrada centrada bajo una columna cuadrada con pedestal. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |
| `zapata_centrica_etabs.json` | Verificación desde los mismos Excel con tres tipos de zapata; cubre 57 de los 73 apoyos. **Dimensiones, columnas, mallas, suelo, relleno y sobrecargas supuestos.** Las combinaciones que entran, con sus factores y si incluyen sismo, salen de `etabs/zapatas/Combinaciones.xlsx` (D-137). La copia de `pruebas/` declara además `etabs_files.locations`, `detailing` y `drawing`, y dibuja la planta de localización (D-130). Para tenerla aquí, agrega esos campos. |
| `diseno_tipologias.json` | Diseño por tipologías (D-069): 6 columnas, 6 zapatas tipo, f'c de 21, 24.5 y 28 MPa con sus precios. |
| `diseno_tipologias_etabs.json` | Diseño por tipologías desde los Excel compartidos de `examples/etabs/zapatas/`: cada Unique Name es una columna de 500 × 800 mm (cx × cy) con la zapata centrada; 6 tipologías y f'c de 21, 24.5 y 28 MPa. **Datos supuestos.** El diseño de los 73 apoyos tarda varios minutos. |
| `diseno_tipologias_combinadas_etabs.json` | Diseño por tipologías con una zapata combinada (D-153): los 6 apoyos del nivel CIM_ST1''_N-2.918; el par 12-20 va en la combinada ZC1 (`combined_pairs`, dirección principal Y) y los otros 4 por tipologías aisladas, con un solo f'c. Las posiciones del par salen de la tabla de coordenadas. **Datos supuestos.** |
| `curva_tipologias.json` | Curva costo-N (D-078, D-096): el mismo proyecto de `diseno_tipologias.json`, diseñado para N = 1 a 6 (bloque `curve`). |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/nsr_10/zapatas/aislada/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/nsr_10/zapatas/aislada/zapata_centrica.json
structurelab-rc run examples/nsr_10/zapatas/aislada/zapata_centrica_etabs.json
structurelab-rc run examples/nsr_10/zapatas/aislada/diseno_tipologias.json
structurelab-rc run examples/nsr_10/zapatas/aislada/diseno_tipologias_etabs.json
structurelab-rc run examples/nsr_10/zapatas/aislada/diseno_tipologias_combinadas_etabs.json
structurelab-rc run examples/nsr_10/zapatas/aislada/curva_tipologias.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/nsr_10/zapatas/aislada
structurelab-rc run examples/nsr_10/zapatas/aislada/pruebas
```

`diseno_tipologias_etabs.json` (73 apoyos) y `curva_tipologias.json` (el diseño para cada N) tardan minutos; `--workers N` fija los procesos en paralelo. El diseño usa por defecto el método `milp_iter` (D-077), que requiere `pip install structurelab-rc[opt]`.
