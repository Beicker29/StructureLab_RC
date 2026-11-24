# Zapata combinada, perfil aci-318-25

Zapatas combinadas de dos o más columnas: rectangulares, con verificación (D-080 a D-083, D-163) y diseño (D-107), con las cargas declaradas y desde ETABS; trapezoidales y en planta T o L, con verificación, despiece y dibujo (D-164). Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_combinada.json` | Ejemplo de zapata combinada: ZC1 rectangular de 7.0 × 2.6 m bajo dos columnas (C1 de 500 × 500 mm cerca del borde −X y C2 de 550 × 550 mm desplazada 150 mm en Y), con cargas de servicio y mayoradas, sismo en X, refuerzo transversal (band) bajo cada columna y barras superiores transversales #5 c/300 (top.y, D-097, D-099). La torsión de la viga larga queda bajo φTth (D-088). Datos ilustrativos (D-080 a D-083). |
| `zapata_combinada_trapecio.json` | Zapata combinada trapezoidal (D-164): ZCTR1 de 7.0 m, de 2.6 m de ancho en −X a 1.6 m en +X, con el lado −Y recto (lindero), bajo dos columnas; la planta se declara desde el borde −X y la línea de referencia Y = 0. Presión de Bellos sobre la planta, desarrollo de las barras x con las que alcanzan a desarrollarse y barras de longitud variable con una marca por cada longitud. Datos ilustrativos. |
| `zapata_combinada_trapecio_estribos.json` | La planta de `zapata_combinada_trapecio.json` con h = 1.0 m, estribos y refuerzo superficial (D-167): cada estribo mide el ancho local y cada medida es una marca; la piel va por cada cara larga, inclinada en el lado oblicuo. Datos ilustrativos. |
| `zapata_combinada_planta_l.json` | Zapata combinada en planta L (D-164): ZCL1 de dos tramos de 3.5 m, de 2.6 m y 1.8 m de ancho, alineados por el borde −Y, bajo dos columnas. Datos ilustrativos. |
| `zapata_combinada_planta_t.json` | Zapata combinada en planta T con la viga en la Y global (D-094, D-164): ZCT2 de tres tramos a lo largo de Y (2.6, 1.6 y 2.2 m de ancho), centrados en X = 0; la barra que cruza el tramo angosto queda en dos. Datos ilustrativos. |
| `zapata_combinada_etabs.json` | Zapatas combinadas desde los mismos Excel (D-084): ZC-A toma de ETABS las cargas de servicio y las mayoradas de sus dos nudos y ZC-B solo las de servicio, con las mayoradas escritas en la plantilla; las dos con barras superiores transversales (top.y, D-097, D-099). **Datos supuestos.** |
| `diseno_combinada.json` | Diseño de la zapata combinada (D-107): las columnas y cargas de `zapata_combinada.json` (posiciones con origen en C1); el diseño ubica la base en la resultante de D+L y elige dimensiones, f'c (21 o 28 MPa) y refuerzo de menor costo; C1 con linderos (D-154): al ras en −x y a 600 mm en −y, con barras en gancho de 90°. |
| `diseno_combinada_etabs.json` | Diseño de zapata combinada desde los Excel de `examples/etabs/zapatas/` (D-112): las dos columnas de ZC-A de `zapata_combinada_etabs.json` toman sus cargas de ETABS; la base se ubica con SERVICIO 1 (D+L) (`placement_case`); la columna exterior al ras de su lindero en la dirección principal (D-154), con barras en gancho de 90°. **Datos supuestos.** |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/aci_318_25/zapatas/combinada/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada_trapecio.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada_trapecio_estribos.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada_planta_l.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada_planta_t.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/zapata_combinada_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/diseno_combinada.json
structurelab-rc run examples/aci_318_25/zapatas/combinada/diseno_combinada_etabs.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/aci_318_25/zapatas/combinada
structurelab-rc run examples/aci_318_25/zapatas/combinada/pruebas
```
