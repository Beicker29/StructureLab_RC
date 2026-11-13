# Importación desde ETABS

Los Excel de ejemplo están en `examples/etabs/<elemento>/` y las plantillas, una por perfil con los mismos datos, en
`examples/<perfil>/<elemento>/<tipo>_etabs.json` (D-098); el proyecto generado tiene el formato de [vigas](vigas.md) o de
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
| `etabs_files.workbook` | texto | Ruta del Excel de ETABS, relativa a la plantilla (D-096). La usa `run`, que importa y verifica con un solo comando; `import-etabs` recibe el Excel como argumento. |
| `members[].id` | texto | Identificador de la viga. |
| `members[].type` | texto | `beam`. |
| `members[].etabs_unique_name` | texto | Unique Name del elemento en ETABS. |
| `members[].min_steel_exception` | sí/no | Obligatorio (D-123); ver el proyecto de vigas. Las zapatas combinadas de la plantilla también lo declaran (`combined_footings[].min_steel_exception`) y la plantilla de diseño de la combinada, en `combined_design`. |
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
Solo entran los Unique Name listados en `columns[]`: los demás nudos de los Excel (por ejemplo, apoyos que no son
zapatas céntricas) se ignoran. `exclude_unique_names` (lista, opcional) quita nudos listados sin borrarlos de su grupo;
cada uno debe estar en `columns[]` y no puede quitarlos todos. Los Unique Name de los Excel que no entran, por no estar
listados o por estar excluidos, se avisan al importar y quedan al final de la descripción del proyecto, que la memoria
muestra (D-111).

Con una plantilla que trae el bloque `combined_design` (D-112), el importador genera el proyecto de diseño de una zapata
combinada de dos columnas (ver [zapatas](zapatas.md), diseño de la zapata combinada): `columns[]` son exactamente dos, con
`id`, `etabs_unique_name`, `cx`, `cy`, `x` e `y` (como en la plantilla de verificación de la combinada, sin `dowels` ni
`band`, que propone el diseño) y `loads` solo con los tipos que `loads_source` toma de la plantilla. `load_factors`,
`principal_direction`, `loads_source` y `etabs_files` son como en la verificación; `combined_design.placement_case` nombra
la combinación de ETABS como la escribe el importador (por ejemplo `"SERVICIO 1 (D+L)"`). `run` importa, diseña y
genera la memoria de la zapata diseñada (`diseno.json`, `proyecto.json`, `resumen.json` y la memoria).

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
| `etabs_files` | objeto | `{"service": ..., "factored": ...}`: rutas de los Excel de servicio y de mayoradas, relativas a la plantilla (D-096); uno puede faltar si ninguna zapata toma de ETABS cargas de ese tipo. Las usa `run`; `import-etabs-footings` recibe los Excel como argumentos. También en la plantilla de diseño por tipologías. |
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
