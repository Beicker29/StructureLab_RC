# Importación de vigas desde ETABS

Las columnas que se leen de ETABS, la conversión de signos y los campos de la plantilla están en
[docs/formatos/etabs.md](../../../docs/formatos/etabs.md); el proyecto generado sigue
[docs/formatos/vigas.md](../../../docs/formatos/vigas.md).

| Archivo | Contenido |
| --- | --- |
| `Element Forces - Beams.xlsx` | Tabla "Element Forces - Beams" exportada de ETABS a Excel (vigas B34 y B37 del 2.º piso). |
| `plantilla_vigas_nsr10.json` | Plantilla con lo que ETABS no exporta: perfil, nivel sísmico, materiales, secciones y armado por tramos. |

## Cómo correrlo

```console
structurelab-rc import-etabs "examples/etabs/vigas/Element Forces - Beams.xlsx" examples/etabs/vigas/plantilla_vigas_nsr10.json --output results/etabs/vigas/etabs.json
structurelab-rc report results/etabs/vigas/etabs.json --output results/etabs/vigas/reporte
```
