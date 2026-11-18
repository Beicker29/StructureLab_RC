# Zapata combinada en T invertida, perfil nsr-10

Zapatas combinadas en T invertida de dos columnas: verificación (D-093, D-106) y diseño (D-113), desde ETABS y con las cargas declaradas. Los campos de entrada y de salida están en [docs/formatos/zapatas.md](../../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_t_invertida_etabs.json` | Zapata combinada en T invertida desde los mismos Excel (D-093): ZT-1 toma de ETABS las cargas de servicio y mayoradas de los nudos 15 y 1659; viga de 1000 × 1700 mm sobre zarpa de 9.0 × 3.6 × 0.6 m. **Datos supuestos.** |
| `diseno_t_invertida.json` | Diseño de zapata combinada en T invertida (D-113): las columnas y cargas de `diseno_combinada.json`, alma desde la columna más ancha más 50 mm a cada lado, viga de 700 a 1200 mm y zarpa de 250 a 400 mm. |
| `diseno_t_invertida_etabs.json` | Diseño de zapata combinada en T invertida desde los Excel de `examples/etabs/zapatas/` (D-113, D-114): las columnas C15 y C1659 de ZT-1 toman sus cargas de ETABS; la base se ubica con SERVICIO 1 (D+L). **Datos supuestos.** |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098). Nombres: `<tipo>.json` con las cargas
declaradas y `<tipo>_etabs.json` con las cargas de los Excel de ETABS (sus rutas, en `etabs_files`, son relativas a la
plantilla).

## Cómo correrlos

Cada ejemplo deja en `results/nsr_10/zapatas/t_invertida/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y
`memoria.pdf` y las figuras; los diseños dejan además el `proyecto.json` diseñado y su resumen.

```console
structurelab-rc run examples/nsr_10/zapatas/t_invertida/zapata_t_invertida_etabs.json
structurelab-rc run examples/nsr_10/zapatas/t_invertida/diseno_t_invertida.json
structurelab-rc run examples/nsr_10/zapatas/t_invertida/diseno_t_invertida_etabs.json
```

Todos los de esta carpeta (salta `pruebas/`), o su copia congelada:

```console
structurelab-rc run examples/nsr_10/zapatas/t_invertida
structurelab-rc run examples/nsr_10/zapatas/t_invertida/pruebas
```
