# Importación desde ETABS

Los Excel de ejemplo están en `examples/etabs/<elemento>/` y las plantillas, una por perfil con los mismos datos, en
`examples/<perfil>/<elemento>/plantilla_*_etabs.json`; el proyecto generado tiene el formato de [vigas](vigas.md) o de
[zapatas](zapatas.md).

## Vigas

### Tabla de ETABS

Columnas requeridas: `Unique Name`, `Output Case`, `Case Type`, `Step Type`, `Station` (m), `P`, `V2`, `V3` (kN),
`T`, `M2`, `M3` (kN-m). Solo se importan las filas de tipo `Combination`. Las filas Max y Min de una envolvente son
dos estados de carga distintos. P cambia de signo para que la compresión sea positiva; Station pasa de m a mm.

### Plantilla

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `description`, `profile`, `seismic`, `materials` | | Igual que en el proyecto (ver [vigas](vigas.md)). |
| `combinations` | lista | Combinaciones a importar; si falta, se importan todas. |
| `members[].id` | texto | Identificador de la viga. |
| `members[].type` | texto | `beam`. |
| `members[].etabs_unique_name` | texto | Unique Name del elemento en ETABS. |
| `members[].statically_determinate` | sí/no | Opcional; ver el proyecto de vigas. |
| `members[].length` | mm | Longitud. |
| `members[].section` | objeto | Sección, igual que en el proyecto. |
| `members[].segments[].from`, `to` | mm | Tramo de armado, desde la estación 0 de ETABS. |
| `members[].segments[].layout` | objeto | Armado del tramo, igual que `layout` en el proyecto. |

## Zapatas

Con una plantilla que trae el bloque `design` (ver [zapatas](zapatas.md), diseño por tipologías), el importador genera el
proyecto de diseño en lugar del de verificación: cada Unique Name es una columna; `columns[]` agrupa los de igual sección
(`etabs_unique_names`, `cx` a lo largo de X y `cy` a lo largo de Y, en mm) y cada nudo se vuelve una columna con id igual
a su Label de ETABS. Las cargas de cada columna salen de los dos Excel; el diseño centra la zapata bajo la columna.

### Tablas de ETABS

Columnas requeridas: `Label`, `Unique Name`, `Output Case`, `Case Type`, `Step Type`, `FX`, `FY`, `FZ` (kN), `MX`,
`MY` (kN-m). Solo se importan las filas de tipo `Combination`; las filas Max y Min son estados distintos.

ETABS reporta la fuerza del apoyo sobre la estructura. Sobre la zapata actúa la opuesta:

| Proyecto | ETABS |
| --- | --- |
| `P_kN` | FZ |
| `Vx_kN`, `Vy_kN` | −FX, −FY |
| `Mx_kNm`, `My_kNm` | −MX, −MY |

### Plantilla

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `description`, `profile`, `seismic`, `materials`, `soil` | | Igual que en el proyecto (ver [zapatas](zapatas.md)). |
| `load_factors` | objeto | Para cada combinación de las dos tablas, `{"dead": ..., "live": ...}`: factores de carga muerta y viva, y `"seismic": true` si la combinación incluye sismo (D-070; por defecto `false`). Una combinación sin factores es un error de importación. |
| `footings[].id` | texto | Nombre del tipo de zapata. |
| `footings[].etabs_unique_names` | lista | Unique Name de los apoyos de ETABS que usan este tipo. |
| `footings[].lx`, `ly`, `h`, `cover`, `fill_height`, `pedestal_height` | mm | Igual que en el proyecto. |
| `footings[].surcharge_dead_kNm2`, `surcharge_live_kNm2` | kN/m² | Sobrecargas superimpuestas muerta y viva. |
| `footings[].column`, `bottom`, `top` | objeto | Columna y mallas, igual que en el proyecto. |

`footings[]` y `combined_footings[]` son opcionales, pero la plantilla trae al menos uno. Un Unique Name no puede
repetirse entre zapatas.

### Zapatas combinadas (D-084)

`combined_footings[]` tiene el formato de la zapata combinada del proyecto (ver [zapatas](zapatas.md)), con dos
diferencias:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `combined_footings[].principal_direction` | texto | `x` (por defecto) o `y`: eje global de ETABS en que va la viga de la zapata combinada o en T invertida (D-094). La plantilla se escribe en ejes globales (con `y`, `ly` es la dimensión paralela a la viga) y los Excel no se modifican: geometría y fuerzas pasan al proyecto tal cual y se rotan a los ejes de la viga al cargarlo. |
| `combined_footings[].columns[].etabs_unique_name` | texto | Unique Name del nudo de ETABS del que salen las reacciones de la columna. |
| `combined_footings[].loads_source` | objeto | `{"service": "etabs" o "json", "factored": "etabs" o "json"}` (por defecto `etabs` los dos): de dónde salen las cargas de cada tipo. Con `etabs`, de la tabla de ese tipo con los factores de `load_factors`; con `json`, de `columns[].loads` de la plantilla, con el formato del proyecto. |
| `combined_footings[].columns[].loads` | lista | Solo los casos de los tipos que vienen de la plantilla; las dos columnas deben terminar con los mismos casos. |

Cada zapata combinada de la plantilla es una zapata del proyecto (su `id` se conserva). Si ninguna zapata pide cargas de
un tipo a ETABS, su Excel puede omitirse escribiendo `-` en su lugar:

```console
structurelab-rc import-etabs-footings "Joint Reactions - Servicio.xlsx" - plantilla.json --output proyecto.json
```

Si una zapata pide un Excel omitido, la importación falla con "Falta el Excel de …". Con un solo Excel, las combinaciones
del otro que estén en `load_factors` no se reclaman.
