# Importación de zapatas desde ETABS

Las columnas que se leen de ETABS, la conversión de signos y los campos de la plantilla están en
[docs/formatos/etabs.md](../../../docs/formatos/etabs.md); el proyecto generado sigue
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Archivo | Contenido |
| --- | --- |
| `Joint Reactions - Servicio.xlsx` | Tabla "Joint Reactions" de ETABS con las combinaciones de servicio (73 apoyos en 4 niveles de cimentación). |
| `Joint Reactions - Ultimas.xlsx` | Tabla "Joint Reactions" con las combinaciones mayoradas de los mismos apoyos. |
| `plantilla_diseno_zapatas_nsr10.json` | Ejemplo de diseño por tipologías (D-069): cada Unique Name de los Excel es una columna; las 73 se toman de 500 × 800 mm (cx × cy) con la zapata centrada; bloque `design` con 4 tipologías y f'c de 21, 24.5 y 28 MPa. **Datos supuestos.** |
| `plantilla_zapatas_nsr10.json` | Plantilla de verificación con lo que ETABS no exporta; cubre 57 de los 73 apoyos. **Sus dimensiones, columnas, mallas, suelo, relleno y sobrecargas son datos supuestos** para probar la importación. |

En las dos plantillas, las combinaciones con sismo (EX, EY) van marcadas `"seismic": true` en `load_factors`, y el suelo trae los
datos supuestos de deslizamiento y volcamiento (D-070).

## Cómo correrlo

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/etabs/zapatas/plantilla_zapatas_nsr10.json --output results/etabs/zapatas/zapatas.json
structurelab-rc report results/etabs/zapatas/zapatas.json --output results/etabs/zapatas/reporte
```

Diseño por tipologías:

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/etabs/zapatas/plantilla_diseno_zapatas_nsr10.json --output results/etabs/zapatas/diseno.json
structurelab-rc design-footings results/etabs/zapatas/diseno.json --output results/etabs/zapatas/diseno
```
