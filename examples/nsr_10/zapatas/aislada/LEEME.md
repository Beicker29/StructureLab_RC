# Zapata aislada, perfil nsr-10

Zapatas aisladas: verificación y diseño de zapatas céntricas, una por columna, con las cargas declaradas y desde ETABS. El diseño por tipologías y la curva costo-N están en [`tipologias/`](../tipologias/LEEME.md) (D-155). Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_centrica.json` | Ejemplo de zapata aislada céntrica: Z1 de planta cuadrada centrada bajo una columna cuadrada con pedestal. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |
| `zapata_centrica_etabs.json` | Verificación desde los mismos Excel con tres tipos de zapata; cubre 57 de los 73 apoyos. **Dimensiones, columnas, mallas, suelo, relleno y sobrecargas supuestos.** Las combinaciones que entran, con sus factores y si incluyen sismo, salen de `etabs/zapatas/Combinaciones.xlsx` (D-137). La copia de `pruebas/` declara además `etabs_files.locations`, `detailing` y `drawing`, y dibuja la planta de localización (D-130). Para tenerla aquí, agrega esos campos. |
| `diseno_centrica.json` | Diseño de zapatas céntricas con las cargas declaradas (D-155): una zapata por columna (`design.typologies` = 6, las columnas de `tipologias/diseno_tipologias.json`), cada una con sus dimensiones, espesor, f'c y refuerzo de menor costo; método `dp`. |
| `diseno_centrica_etabs.json` | Diseño de zapatas céntricas desde ETABS (D-155): los 6 apoyos del nivel CIM_ST1''_N-2.918, una zapata por apoyo, con la planta de localización de la tabla de coordenadas. **Datos supuestos.** |

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
structurelab-rc run examples/nsr_10/zapatas/aislada/diseno_centrica.json
structurelab-rc run examples/nsr_10/zapatas/aislada/diseno_centrica_etabs.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/nsr_10/zapatas/aislada
structurelab-rc run examples/nsr_10/zapatas/aislada/pruebas
```

El diseño usa `dp`, que no necesita el solucionador; con `milp_iter` (D-077), `pip install structurelab-rc[opt]`.
