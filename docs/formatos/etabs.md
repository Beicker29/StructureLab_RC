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
| `description`, `profile`, `seismic`, `concrete`, `reinforcement_steel` | | Igual que en el proyecto (ver [vigas](vigas.md), D-139). |
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

**Zapatas combinadas dentro del diseño por tipologías (D-153).** La misma plantilla puede declarar pares de columnas que
van en zapata combinada; los demás nudos siguen por tipologías aisladas:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `combined_pairs[].id` | texto | Identificador de la zapata combinada. |
| `combined_pairs[].etabs_unique_names` | - | Los Unique Name de sus dos nudos. Deben estar en `columns[]` (de allí sale su sección) y no en `exclude_unique_names`; un nudo no puede estar en dos pares. Salen de las tipologías aisladas. |
| `combined_pairs[].principal_direction` | texto | `x` o `y`: el eje global de la viga que une las columnas (D-094). |
| `combined_pairs[].design` | objeto | Opcional: lo propio del par sobre `combined_design` (por ejemplo `placement_case`, `shape` y los campos de la T). |
| `combined_pairs[].property_lines` | mm | Opcional (D-154): los linderos de cada columna del par, por Unique Name: `{"276": {"+y": 0}, "288": {"-x": 300}}`, como `property_lines` de las columnas del diseño de la combinada. |
| `combined_design` | objeto | Obligatorio con pares: el bloque del diseño de la combinada (D-107, D-110, D-113) común a todos los pares, sin `fc_options` ni `prices`, que se toman de `design` (un solo f'c para toda la cimentación). |
| `min_clear_spacing` | mm | Opcional (D-156): separación libre mínima entre zapatas vecinas; pasa al proyecto, que avisa los pares más cercanos con sus nudos. También en la plantilla de verificación. |
| `curve` | objeto | Opcional (D-165): `{"n": "1-6"}`. Con él, `run` corre la curva costo–N desde ETABS en lugar del diseño: N es el número de tipologías de las aisladas y los pares de `combined_pairs` suman su costo (ver [zapatas](zapatas.md), curva costo–N). |

Los nudos de las zapatas aisladas son los de `columns[]` que no están en un par; cualquiera de los dos grupos puede quedar
vacío (todos los nudos en pares, o ningún par), D-156.

Las posiciones de las dos columnas de cada par salen de la tabla de coordenadas (`etabs_files.locations`), que entonces es
obligatoria; sus cargas, de los Excel. El proyecto de diseño lleva cada par en `combined_footings[]` (columnas con `x`,
`y` y `location`, y su `combined_design` ya completo).

Con una plantilla que trae el bloque `combined_design` (D-112), el importador genera el proyecto de diseño de una zapata
combinada (ver [zapatas](zapatas.md), diseño de la zapata combinada): `columns[]` son dos o más (D-163), con
`id`, `etabs_unique_name`, `cx`, `cy`, `x` e `y` (como en la plantilla de verificación de la combinada, sin `dowels` ni
`band`, que propone el diseño; `x` e `y` con cualquier origen), `property_lines` opcional (los linderos de la columna,
D-154; solo en el diseño) y `loads` solo con los tipos que `loads_source` toma de la plantilla. El Excel de
combinaciones, `principal_direction`, `loads_source` y `etabs_files` son como en la verificación; `combined_design.placement_case` nombra
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
| `description`, `profile`, `seismic`, `concrete`, `reinforcement_steel`, `soil` | | Igual que en el proyecto (ver [zapatas](zapatas.md), D-139). |
| `etabs_files` | objeto | `{"service": ..., "factored": ..., "combinations": ...}`: rutas de los Excel de servicio, de mayoradas y de combinaciones, relativas a la plantilla (D-096, D-137); el de servicio o el de mayoradas puede faltar si ninguna zapata toma de ETABS cargas de ese tipo. Las usa `run`; `import-etabs-footings` recibe los Excel como argumentos. También en la plantilla de diseño por tipologías. |
| `etabs_files.locations` | texto | Opcional (D-130). Ruta del Excel con la tabla "Point Object Connectivity" de ETABS. Se leen las columnas `UniqueName`, `Story`, `X` y `Y`; X e Y deben venir en m y se pasan a mm. Cada zapata aislada recibe `location` (x, y, nivel y nudo) y `typology` (el `id` de su grupo); cada columna de una combinada recibe su `location`; en el diseño por tipologías, cada columna. Si falta algún nudo usado, es error. Con `drawing`, el proyecto dibuja la planta de localización. En `import-etabs-footings` se pasa con `--locations`. El diseño de una zapata combinada no la usa. |
| `etabs_files.combinations` | texto | Obligatorio (D-137). Ruta del Excel de combinaciones (ver abajo): qué combinaciones de ETABS entran, de qué tipo y con qué factores. En `import-etabs-footings` se puede pasar o reemplazar con `--combinations`. |
| `footings[].id` | texto | Nombre del tipo de zapata. |
| `footings[].etabs_unique_names` | lista | Unique Name de los apoyos de ETABS que usan este tipo. |
| `footings[].quantity` | - | Obligatorio (D-159): las veces que se construye la zapata de cada apoyo (en los ejemplos, 1). Cada zapata generada lleva `typology` = el `id` del tipo, con o sin coordenadas, y el tipo suma la `quantity` de sus apoyos. |
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
| `combined_footings[].plan` | | Opcional (D-164): planta trapezoidal o en T/L en lugar de `lx` y `ly`, con el formato del proyecto (ver [zapatas](zapatas.md)). |
| `combined_footings[].loads_source` | objeto | `{"service": "etabs" o "json", "factored": "etabs" o "json"}` (por defecto `etabs` los dos): de dónde salen las cargas de cada tipo. Con `etabs`, de la tabla de ese tipo con las combinaciones del Excel de combinaciones; con `json`, de `columns[].loads` de la plantilla, con el formato del proyecto. |
| `combined_footings[].columns[].loads` | lista | Solo los casos de los tipos que vienen de la plantilla; todas las columnas deben terminar con los mismos casos. |

Cada zapata combinada de la plantilla es una zapata del proyecto (su `id` se conserva). Si ninguna zapata pide cargas de
un tipo a ETABS, su Excel puede omitirse escribiendo `-` en su lugar:

```console
structurelab-rc import-etabs-footings "Joint Reactions - Servicio.xlsx" - plantilla.json --output proyecto.json
```

Si una zapata pide un Excel omitido, la importación falla con "Falta el Excel de …". Con un solo Excel, las combinaciones
del otro tipo que estén en el Excel de combinaciones no se reclaman.

### Excel de combinaciones (D-137)

Lista explícita de las combinaciones de ETABS que entran a la verificación o al diseño de las zapatas aisladas,
combinadas y en T invertida (y de los cabezales, cuando existan). Reemplaza el antiguo bloque `load_factors` de la
plantilla. Hoja `Combinaciones`, encabezados en la primera fila y una combinación por fila:

| Columna | Contenido |
| --- | --- |
| `Combinacion` | Nombre exacto del Output Case de las tablas Joint Reactions. No puede repetirse. |
| `Tipo` | `Servicio` o `Última` (`Ultima`). La combinación se lee solo de la tabla de su tipo. |
| `Factor D` | Factor del peso propio, el relleno y la sobrecarga muerta (D-054, D-057). Número ≥ 0; acepta coma decimal. |
| `Factor L` | Factor de la sobrecarga viva. Número ≥ 0. |
| `Sismo` | `Sí` o `No`: si la combinación incluye sismo (D-070). |
| `Usar` | `Sí` o `No`. Solo entran las filas con `Sí`. |

Las tildes y mayúsculas no importan. Una combinación listada con `Usar = Sí` que no aparece en la tabla de su tipo es un
error de importación. Las combinaciones de las tablas que no están listadas, o que están con `No` o con el otro tipo, no
entran: la importación las nombra ("Combinaciones de ETABS ignoradas …") y no fallan. Así, una tabla de ETABS con
combinaciones de más (envolventes, casos de diseño de otros elementos) no contamina la verificación.
