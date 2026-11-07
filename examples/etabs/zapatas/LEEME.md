# Importación de zapatas desde ETABS

Las columnas que se leen de ETABS, la conversión de signos y los campos de la plantilla están en
[docs/formatos/etabs.md](../../../docs/formatos/etabs.md); el proyecto generado sigue
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Archivo | Contenido |
| --- | --- |
| `Joint Reactions - Servicio.xlsx` | Tabla "Joint Reactions" de ETABS con las combinaciones de servicio (65 apoyos del nivel CIM_SOT1_N-3.53). |
| `Joint Reactions - Ultimas.xlsx` | Tabla "Joint Reactions" con las combinaciones mayoradas de los mismos apoyos. |
| `plantilla_zapatas_nsr10.json` | Plantilla con lo que ETABS no exporta. **Sus dimensiones, columnas, mallas, suelo, relleno y sobrecargas son datos supuestos** para probar la importación. |

## Cómo correrlo

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/etabs/zapatas/plantilla_zapatas_nsr10.json --output results/etabs/zapatas/zapatas.json
structurelab-rc report results/etabs/zapatas/zapatas.json --output results/etabs/zapatas/reporte
```
