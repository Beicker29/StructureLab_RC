# Zapata combinada en T invertida, perfil aci-318-25

Zapatas combinadas en T invertida: verificación (D-093, D-106) y diseño (D-113), y la zarpa trapezoidal o en planta T/L con verificación, despiece y dibujo (D-167), desde ETABS y con las cargas declaradas. Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_t_invertida_etabs.json` | Zapata combinada en T invertida desde los mismos Excel (D-093): ZT-1 toma de ETABS las cargas de servicio y mayoradas de los nudos 15 y 1659; viga de 1000 × 1700 mm sobre zarpa de 9.0 × 3.6 × 0.6 m. **Datos supuestos.** |
| `zapata_t_invertida_trapecio.json` | T invertida trapezoidal (D-167): ZTT1 con zarpa de 9.0 m, de 3.6 m a 2.6 m de ancho, alma de 1000 × 1700 mm con su eje declarado (`beam.axis`) y la capa inferior de la viga declarada solo con sus barras (se reparte en el ala efectiva más angosta del largo). Datos ilustrativos. |
| `diseno_t_invertida.json` | Diseño de zapata combinada en T invertida (D-113): las columnas y cargas de `diseno_combinada.json`, alma desde la columna más ancha más 50 mm a cada lado, viga de 700 a 1200 mm y zarpa de 250 a 400 mm. |
| `diseno_t_invertida_etabs.json` | Diseño de zapata combinada en T invertida desde los Excel de `examples/etabs/zapatas/` (D-113, D-114): las columnas C15 y C1659 de ZT-1 toman sus cargas de ETABS; la base se ubica con SERVICIO 1 (D+L). **Datos supuestos.** |
| `diseno_t_invertida_formas.json` | Diseño de la T invertida entre sus formas con alma (D-170): `shapes` = `inverted_t`, `inverted_t_trapezoid` e `inverted_t_stepped`, con los datos de `diseno_t_invertida.json` y el lindero de C1 de `diseno_combinada_formas.json`; se queda con la más barata, con el alma sobre la línea de las columnas. |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/aci_318_25/zapatas/t_invertida/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/zapata_t_invertida_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/zapata_t_invertida_trapecio.json
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/diseno_t_invertida.json
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/diseno_t_invertida_etabs.json
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/diseno_t_invertida_formas.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/aci_318_25/zapatas/t_invertida
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/pruebas
```
