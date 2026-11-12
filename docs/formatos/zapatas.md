# Formato de zapatas

Referencia de la entrada y la salida de la verificación de zapatas aisladas (v3, en curso), común a los dos perfiles. Los ejemplos están en `examples/<perfil>/zapatas/`. La presión del suelo sigue la solución de Bellos y Bakas (2017) para una zapata rígida sin tracción en el contacto.

## Convenciones

- Ejes globales de ETABS con origen en el centroide de la base: X a lo largo de `lx`, Y a lo largo de `ly`, Z hacia
  arriba. Las zapatas aisladas rotadas aún no se admiten. Las zapatas combinadas y en T invertida declaran con
  `principal_direction` si su viga va en la X o en la Y global y se escriben, como todo, en ejes globales (D-094).
- Las fuerzas son las que la columna aplica sobre la zapata, en la base de la columna (a la altura h + pedestal):
  `P_kN` positiva en compresión, `Vx_kN` y `Vy_kN` horizontales, `Mx_kNm` y `My_kNm` con la regla de la mano derecha.
  Una fuerza P aplicada en x > 0 produce My > 0.
- Cada caso es de servicio (`service`) o mayorado (`factored`). Los de servicio verifican el suelo; los mayorados
  servirán para el diseño estructural. La aplicación no genera combinaciones.

## Entrada

### Proyecto

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `description` | texto | Descripción libre; sale en la memoria. |
| `profile` | texto | Perfil normativo: `aci-318-25` o `nsr-10`. Todo el cálculo sale de él; nunca se mezcla con el otro perfil. |
| `seismic.level` | texto | Nivel sísmico declarado por el ingeniero, en el vocabulario del perfil: `none`, `ordinary`, `intermediate`, `special` (ACI) o `DMI`, `DMO`, `DES` (NSR-10). La aplicación no lo deriva. |
| `seismic.justification` | texto | Justificación del nivel sísmico; sale en la memoria. |
| `materials.fc` | MPa | Resistencia especificada del concreto, f'c. |
| `materials.fy` | MPa | Fluencia del refuerzo longitudinal. |
| `materials.fyt` | MPa | Fluencia del refuerzo transversal (estribos). Se declara aunque el ejemplo no lo use. |
| `materials.concrete` | texto | `normalweight` (peso normal) o `lightweight` (liviano); define λ. |
| `materials.coating` | texto | Recubrimiento de las barras: `uncoated` (sin recubrimiento), `galvanized`, `epoxy` o `zinc_epoxy` (dual de zinc y epóxico); cambia la longitud de desarrollo (ψe, D-071). |
| `materials.max_aggregate` | mm | Tamaño máximo nominal del agregado grueso (dagg). Sin él, la separación mínima de las barras queda INCOMPLETE: no se supone (D-102). También en el diseño por tipologías. |
| `soil` | objeto | Datos del suelo y de los pesos propios (abajo). Obligatorio con zapatas. |
| `footings` | lista | Zapatas del proyecto. |

### Suelo (`soil`); todos los campos son obligatorios salvo `passive_factor`

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `allowable_pressure_kPa` | kPa | Presión admisible **bruta** del suelo, qa. Se compara con la presión que incluye los pesos propios y las sobrecargas. |
| `min_contact_fraction` | - | Fracción mínima de la base que debe quedar en contacto con el suelo en los casos de servicio (0 a 1). |
| `unit_weight_concrete_kNm3` | kN/m³ | Peso unitario del concreto de la zapata y del pedestal. |
| `unit_weight_fill_kNm3` | kN/m³ | Peso unitario del relleno sobre la zapata; también el del suelo para el empuje pasivo. |
| `friction_coefficient` | - | Coeficiente de fricción μ en la interfaz suelo–zapata (D-070). |
| `adhesion_kPa` | kPa | Adherencia c_a suelo–zapata; actúa solo sobre el área en contacto (puede ser 0). |
| `passive_coefficient` | - | Coeficiente de empuje pasivo Kp, dato del estudio de suelos. |
| `cohesion_kPa` | kPa | Cohesión c del suelo para el empuje pasivo (2c·√Kp; puede ser 0). |
| `passive_factor` | - | Factor que afecta el empuje pasivo al sumarlo a la fricción (0 a 1; por defecto 0.5). |
| `sliding_safety_factor`, `sliding_safety_factor_seismic` | - | Factores de seguridad mínimos al deslizamiento, sin sismo y con sismo. |
| `overturning_safety_factor`, `overturning_safety_factor_seismic` | - | Factores de seguridad mínimos al volcamiento, sin sismo y con sismo. |
| `seismic_bearing_factor` | - | Opcional (por defecto 1.0, no menor que 1.0): factor que aumenta qa en los casos de servicio marcados `seismic` (D-079). |

### Zapata (`footings[]`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `id` | texto | Identificador único. |
| `lx`, `ly` | mm | Dimensiones en planta a lo largo de X y de Y. |
| `h` | mm | Espesor de la zapata. |
| `cover` | mm | Recubrimiento libre de las mallas. |
| `fill_height` | mm | Altura del relleno sobre la zapata. |
| `pedestal_height` | mm | Altura del pedestal, con la sección de la columna (0 si no hay). |
| `surcharge_dead_kNm2` | kN/m² | Sobrecarga superimpuesta muerta sobre el relleno (0 si no hay). |
| `surcharge_live_kNm2` | kN/m² | Sobrecarga superimpuesta viva sobre el relleno (0 si no hay). |
| `column.cx`, `column.cy` | mm | Dimensiones de la columna a lo largo de X y de Y. |
| `column.offset_x`, `column.offset_y` | mm | Posición del eje de la columna respecto al centroide de la base. |
| `column.dowels.designation`, `column.dowels.count` | -, - | Pasadores entre la columna y la zapata: barra del catálogo y número. Si faltan, sus verificaciones salen `INCOMPLETE`. |
| `bottom` | objeto | Malla inferior (abajo). |
| `top` | objeto o `null` | Malla superior, o `null` si no hay. |
| `loads` | lista | Casos de carga (abajo). |

El relleno y las sobrecargas ocupan el área de la base menos la de la columna.

### Malla (`bottom`, `top`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `first` | texto | Dirección de las barras más cercanas a la cara de la zapata: `x` o `y`. Define la d de cada dirección. |
| `end` | texto | Cómo terminan las barras: `straight` (rectas) o `hook` (gancho estándar); define la longitud de desarrollo. |
| `x.designation`, `x.spacing` | -, mm | Barras paralelas a X: designación del catálogo y separación centro a centro. |
| `y.designation`, `y.spacing` | -, mm | Barras paralelas a Y. |
| `x.band_spacing` o `y.band_spacing` | mm | Opcional, solo en la dirección corta de una zapata rectangular: separación en la franja central de ancho igual al lado corto, centrada en la columna; fuera de ella rige `spacing`. |

### Caso de carga (`loads[]`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `case` | texto | Nombre de la combinación. |
| `kind` | texto | `service` o `factored`. |
| `dead_factor` | - | Factor de carga muerta de la combinación; multiplica el peso de la zapata, del pedestal y del relleno y la sobrecarga muerta. |
| `live_factor` | - | Factor de carga viva de la combinación; multiplica la sobrecarga viva (0 si la combinación no tiene viva). |
| `seismic` | sí/no | Opcional (por defecto `false`): la combinación incluye sismo; el deslizamiento y el volcamiento usan los factores de seguridad sísmicos (D-070). |
| `P_kN`, `Vx_kN`, `Vy_kN` | kN | Fuerzas de la columna sobre la zapata. |
| `Mx_kNm`, `My_kNm` | kN·m | Momentos de la columna sobre la zapata. |

### Propiedades calculadas (no se declaran)

Área A, inercias Ix e Iy, módulos de sección Sx y Sy, núcleo central (lx/6, ly/6), pesos de la zapata, del pedestal
y del relleno, y fuerzas de las sobrecargas. Salen en `resultado.json`, en `footings[].properties`.

## Zapata combinada (`combined_footings[]`, D-080)

Zapata rectangular de dos columnas, solo verificación. La **dirección principal** es la de la viga que une las columnas
(`principal_direction`, X o Y global) y la **dirección secundaria** la transversal (D-101). Las verificaciones nombran
las barras por su dirección ("dirección principal", "dirección secundaria"), no por un eje; la memoria agrega el eje
global, por ejemplo "Dirección principal (Y global)". Usa el mismo `soil` que las zapatas aisladas. Se verifican la parte
geotécnica con la resultante de las dos columnas (V3J.1) y, con los casos mayorados:

- la viga de la dirección principal con las verificaciones de vigas en sus secciones críticas (V3J.2, D-081): cada
  check lleva `z`, la posición a lo largo de la viga desde su borde negativo (−X o −Y global), y en `note` la sección
  ("cara +X de la columna …"); Vc y Av,min de cimentación; separación de 3h y 450 mm;
- por columna (V3J.3, D-082): el punzonamiento (y el del perímetro común si los de las dos columnas se traslapan,
  D-086), la franja transversal de la dirección secundaria (también con las verificaciones de vigas, con `z` desde el
  borde negativo de la dirección secundaria y `note` "Franja transversal de la columna …, cara ±Y", "a d de la cara ±Y"
  o "mayor M negativo hacia el borde ±Y", con el eje de la dirección secundaria; en una cara de columna, Vu es el
  de la sección a d; su carga es la neta: la fuerza de la columna con la forma de la presión menos los pesos y las
  sobrecargas, D-095; abajo lleva el band si lo hay o, si no, la malla de la dirección secundaria, y arriba las barras de
  `top` de esa dirección que caen en ella; el momento negativo, sin esas barras, es de concreto simple, D-072, D-097), el
  aplastamiento y los pasadores (`note` "Columna …"); la separación de la malla de la dirección secundaria (3h y
  450 mm); retracción y temperatura por zona (D-097): por metro, inferior más superior de cada dirección ≥ ρ·h y cada
  capa a s ≤ min(5h, 450 mm), en la principal en todo el ancho y en la secundaria fuera de las zonas de band y en cada
  zona de band (ACI 24.4.3.2 y 24.4.3.3; NSR-10 C.7.12.2.1 y C.7.12.2.2); el desarrollo de las barras de la dirección
  principal desde la sección de mayor momento de su signo y, en cada franja, de las barras inferiores (band o malla) y de
  las superiores de la dirección secundaria (con momento negativo) desde la cara de la columna.

Toda la salida (`resultado.json`, memoria y figuras) va en los ejes globales declarados (D-101): dimensiones, columnas,
cargas, mallas, caras y bordes de las notas, posiciones `z`, excentricidades, presiones en las esquinas, punzonamiento
y diagramas. El cálculo trabaja en ejes de la viga y sus resultados se convierten; con `principal_direction: "x"`
coinciden.

Las verificaciones de resistencia traen en `values` los datos con que se calculan (D-097): flexión, b, h, d, As, f'c, fy,
β1 y a (en zapatas, además c y εt); cortante, bw, d, ρw, λ y f'c; concreto simple, b, h de cálculo, Sm y f'c.

Las notas de las secciones de la viga y de las franjas terminan con el signo del momento ("momento positivo" o
"momento negativo"); la memoria revisa por separado el momento positivo y el negativo en las dos direcciones y trae los
diagramas envolventes de momento y cortante (D-095, D-104): `diagrams.principal` y `diagrams.secondary` en
`resultado.json` y un SVG por magnitud y elemento (`diagrama_<zapata>_<elemento>_cortante.svg` y `_momento.svg`). La memoria y el ejemplo `zapata_combinada.json` (V3J.4) están en
los dos perfiles.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `id`, `lx`, `ly`, `h`, `cover`, `fill_height`, `pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2` | | Como en la zapata aislada. |
| `principal_direction` | texto | Dirección principal (la de la viga que une las columnas) en ejes globales de ETABS: `x` (por defecto) o `y` (D-094). Todo se escribe en ejes globales, como está la zapata en planta: con `y`, `ly` es la dimensión paralela a la viga, las columnas van a distintas `y` y `bottom.y` y `top.y` son las barras paralelas a la viga (D-099). Estribos, refuerzo superficial, capas de torsión, `band` y la viga de la T no tienen dirección propia: van paralelos o transversales a la viga. El cálculo trabaja en ejes de la viga (X = +Y global, Y = −X global): con `y`, al cargar se intercambian lx y ly, las columnas pasan a x = y, y = −x, con cx = cy y cy = cx, las barras x e y (y `first`) de `bottom` y de `top` se intercambian y las cargas pasan a Vx = Vy, Vy = −Vx, Mx = My y My = −Mx. La salida vuelve a los ejes declarados con el giro inverso (D-101); `resultado.json` trae `principal_direction` en `geometry [mm]`. |
| `columns[]` | lista | Exactamente dos columnas. |
| `columns[].id` | texto | Identificador de la columna. |
| `columns[].cx`, `columns[].cy` | mm | Sección (cx a lo largo de X). |
| `columns[].x`, `columns[].y` | mm | Posición del eje de la columna respecto al centroide de la base. |
| `columns[].dowels` | | Pasadores, como en la zapata aislada (opcional; sin ellos sus verificaciones quedan INCOMPLETE). |
| `columns[].band` | | Refuerzo transversal inferior bajo la columna, paralelo a Y, en el ancho de su franja (columna + d/2 a cada lado, dentro de la base), a la profundidad de las barras y de la malla inferior: `designation` y `spacing` (opcional). Es el único refuerzo inferior transversal de esa zona: la malla inferior y va solo fuera de las zonas de band (D-097). |
| `columns[].band_top` | | Band superior (D-119): barras transversales arriba en el ancho de la franja, `designation` y `spacing` (opcional, sin `band_spacing`); toman el momento negativo de la franja y el de la torsión de placa. Van como `top.y` (debajo de `top.x` si esa dirección va más cerca de la cara) y son la capa superior de la franja; donde lo hay, `top.y` va solo fuera de esa zona. Sin `top`, terminan como la malla inferior. No aplica en la T invertida. |
| `columns[].loads` | lista | Casos de carga de la columna, como en la zapata aislada; las dos columnas deben tener los mismos casos, con los mismos factores y la misma marca de sismo. |
| `bottom` | | Malla inferior en las dos direcciones (sin `band_spacing`). |
| `top` | | Barras superiores con la estructura de `bottom` (D-099), opcional: `end` (`straight` o `hook`, para las dos direcciones), `x` (paralelas a X, a lo largo de la viga) e `y` (paralelas a Y, uniformes en todo el largo, D-097), cada una `{designation, spacing}` y opcional, con al menos una; `first`, la dirección más cercana a la cara superior, obligatoria si se declaran las dos. Sin barras superiores en la dirección principal, el momento negativo de la viga se revisa como concreto simple (D-072); sin ellas en la secundaria, el de las franjas transversales. Con `principal_direction: "y"`, `x`, `y` y `first` están en ejes globales y se intercambian como en `bottom`. En la T invertida, `top` es la malla superior de la zarpa (D-114; el refuerzo de la viga va en `beam.layers`): con `top.y`, el momento negativo de las aletas se revisa con esas barras por metro y se revisa su desarrollo desde la cara de la viga; sin ellas, de concreto simple. |
| `stirrups` | | Estribos de la viga de la dirección principal, como en las vigas (`designation`, `legs`, `spacing`, `closed`), opcional (D-081); solo para el cortante: la torsión de la combinada rectangular es de placa (D-118). |
| `skin` | | Refuerzo superficial en las caras largas (`designation`, `spacing` vertical), al recubrimiento de la cara, desde la capa inferior hacia arriba; se exige con h > 900 mm (D-083). |
| `deep_beam` | sí/no | La viga de la dirección principal es de gran altura (declarado por el usuario): se verifican los criterios de vigas altas como en las vigas (D-089). |
| `beam` | mm | T invertida (D-093, D-106): `width` (bw) y `height` (H, altura total desde la base) de la viga centrada en Y sobre la zarpa de espesor `h`; `layers`, las capas de la viga como en las vigas (`depth` desde la cara superior de la viga, `role` flexure/skin/torsion, `bars` con x desde la cara −Y del alma, o solo la lista de barras, por ejemplo `["#6", "#6", "#6", "#6"]`, D-114); `stirrups`, sus estribos; `end` (`straight` o `hook`), cómo terminan sus barras; `bottom_width` (opcional), el ancho centrado en el alma que cubre la capa de flexión más profunda, que puede salir del alma sobre la zarpa (por defecto, el ala efectiva). Con solo la lista de barras, la capa inferior se reparte a igual separación en ese ancho (al recubrimiento si llega al borde de la base; por dentro del estribo si el ala no cuenta) y las demás capas entre las esquinas del estribo, como en las vigas. Las columnas deben caber en bw; `stirrups` y `skin` de la zapata no se usan (van en `beam`); `top` es la malla superior de la zarpa; `band` no aplica. La malla `bottom` es la de la zarpa: sus barras x van solo fuera del ancho cubierto y las y son las de las aletas. |

**Torsión de placa (D-118).** Mx, Vy y la posición en Y de las columnas producen la torsión T(x) de la combinada
rectangular. Se diseña como de placa, por Wood-Armer, con mxy = T/B uniforme en el ancho:

- **Barras x:** con mx = M/B y my = 0, la cara inferior pide máx(M + |T|, 0) y la superior mín(M − |T|, 0), por B. Son
  los momentos de las estaciones de la viga larga; la nota de su flexión trae M, T y mxy.
- **Franjas:** con my = M/b y mx = 0, abajo M + b·|mxy| y arriba M − b·|mxy|, con |mxy| el mayor en los bordes de la
  franja. Una estación por cara con momento; el cortante se revisa una vez.
- **Barras y fuera de las franjas:** my = 0 y, por metro, +|mxy| abajo ("Direccion secundaria: torsion de placa (barras
  inferiores)") y −|mxy| arriba (barras superiores y o, sin ellas, concreto simple, D-072).
- **Cortante fuera de las franjas (D-119):** qy = ∂mxy/∂x = (dT/dx)/B, con dT/dx = ∫y·p dy de la presión en la sección,
  por metro, frente a φVc de cimentación con la malla y inferior ("Direccion secundaria: torsion de placa, cortante").

La memoria de la combinada rectangular trae, además de los capítulos de las franjas, tres de la dirección secundaria
fuera de las franjas band: momento positivo, momento negativo y fuerza cortante (D-119). Su índice DCR tiene una fila
por verificación, dirección y signo de momento.

No hay torsión de vigas: `torsion_layers` se rechaza. La T invertida conserva la torsión de vigas en su alma.

## Diseño por tipologías (`diseno_*.json`, comando `design-footings`)

En lugar de zapatas, el proyecto de diseño trae columnas y un bloque `design` (D-069). `materials` declara solo `fy`,
`fyt`, `concrete` y `coating`: f'c es una variable del diseño. `soil` es igual que en la verificación.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `columns[].id` | texto | Identificador de la columna. |
| `columns[].cx`, `columns[].cy` | mm | Sección de la columna (la zapata la centra). |
| `columns[].loads` | lista | Casos de carga, iguales a los de una zapata. |
| `design.typologies` | - | Número de zapatas tipo que deben cubrir todas las columnas. |
| `design.fc_options` | MPa | Lista de f'c que se evalúan (D-072); cada uno comercial (21, 24.5, 28, 31.5, 35, 42, 48) y con precio. El diseño elige el de menor costo total. |
| `design.prices.concrete_per_m3` | moneda/m³ | Precio del concreto por f'c; las claves son f'c comerciales y pueden incluir más resistencias que `fc_options`. |
| `design.prices.steel_per_kg` | moneda/kg | Precio del acero. |
| `design.shape` | texto | `square` (por defecto), `equal_cantilevers` o `ratio` (con `design.ratio` = lx/ly). |
| `design.plan_step`, `design.plan_max` | mm | Paso y máximo de las dimensiones en planta. |
| `design.h_min`, `design.h_step`, `design.h_max` | mm | Espesor mínimo, paso y máximo. |
| `design.cover`, `design.fill_height`, `design.pedestal_height` | mm | Recubrimiento, relleno y pedestal de todas las zapatas. |
| `design.surcharge_dead_kNm2`, `design.surcharge_live_kNm2` | kN/m² | Sobrecargas superimpuestas. |
| `design.bars`, `design.spacing_step`, `design.end` | -, mm, texto | Barras permitidas para las mallas, paso de separación y extremo de las barras. |
| `design.dowel_bars` | - | Barras permitidas para los pasadores. |
| `design.method` | texto | `milp_iter` (por defecto desde E3b: iterativo, sin tabla de tramos, D-077), `milp` (asignación óptima sobre la tabla completa de tramos, D-075) o `dp` (solo la partición y la reasignación). `milp_iter` y `milp` requieren `pip install structurelab-rc[opt]`. `--method` en la CLI lo reemplaza. |
| `design.milp_time_limit_s` | s | Límite de tiempo del MILP (por f'c con `milp`; por solución con `milp_iter`; por defecto 120). |
| `design.iter_max` | - | Con `milp_iter`: iteraciones por f'c (por defecto 10). |
| `design.iter_time_limit_s` | s | Con `milp_iter`: tiempo por f'c (por defecto 600). |
| `curve.n` | - | Solo en el ejemplo de la curva costo-N (`curva_*.json`, D-096): los valores de N, como lista o como texto (`"1-6"`, `"2,4,6"`, `"1-4,8"`). Con `curve`, `run` corre la curva en lugar del diseño; `typology-curve --n` lo reemplaza. |

Cada tipología se diseña con la planta (la primera viable y dos más), el espesor y las mallas de menor costo que aprueban
todas las verificaciones (D-069, D-076). Los tramos de la tabla usan el menor espesor con solución; los diseños
individuales y los grupos elegidos recorren además los espesores mayores, y un grupo elegido se reemplaza por su
rediseño si baja de costo. Después de la partición, cada columna pasa a la tipología elegida más barata
que la cubre si baja el costo y su grupo conserva al menos una columna (D-074). Las tipologías repetidas se permiten y se marcan.

Con `milp`, después de la DP se arma el catálogo (diseños individuales y de tramo, sin repetidas), se calcula con qué
pasadores cubre cada candidato a cada columna y un MILP elige N tipologías distintas y la asignación de menor costo,
sin la restricción de tramos continuos, con brecha 0 y desempate por acero y por el orden del catálogo. Arranca desde la
DP si esta no tiene repetidas; en ese caso se exige `C_MILP ≤ C_DP` (en pesos enteros) y, si no se cumple, el f'c se
rechaza. El resultado del MILP no se reasigna.

Salida: `proyecto.json` (una zapata por columna, nombrada `<tipología>-<columna>`, lista para `verify` y `report`; si
hay tipologías repetidas, su `description` termina con una advertencia que la memoria muestra en el encabezado) y
`tipologias.json`:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `method` | texto | `dp`, `milp` o `milp_iter`. |
| `fc [MPa]` | MPa | f'c elegido: el de menor costo total. |
| `cost` | moneda | Costo total (con `dp`, después de la reasignación; con `milp`, el del MILP, o el de la DP si el MILP no tiene solución). |
| `milp` | objeto | Solo con `milp`: `status` (`optimal`: óptimo certificado en el catálogo; `time_limit`: sin certificar; `infeasible`: sin N tipologías distintas, queda la DP), `dp_cost`, `dp_distinct_count`, `milp_cost`, `candidates`, `seconds` (matriz y solucionador) y `note`. |
| `iterations` | lista | Solo con `milp_iter`: cada iteración del f'c elegido con `number`, `candidates`, `cost`, `status` y `seconds` (también en `by_fc`). |
| `cost_before_reassignment` | moneda | Costo de la partición, antes de reasignar (con `milp`, igual a `cost`). |
| `distinct_count` | - | Tipologías distintas; menor que el número pedido si hay repetidas. |
| `duplicates` | lista | Grupos de tipologías idénticas (mismos f'c, lx, ly, h y mallas): `typologies` (nombres) y `at_limit` (`plan_max` si el paso siguiente de planta lo supera, `h_max` si el de espesor lo supera; vacía si ninguno). |
| `reassigned` | lista | Columnas reasignadas: `column`, `from`, `to` (nombres de tipología) y `saving` (moneda). |
| `by_fc` | lista | Cada f'c evaluado: `fc [MPa]`, `cost` y `distinct_count` (null si no tiene solución, con `failure`); con `milp`, también su bloque `milp`. |
| `typologies` | lista | Por tipología: `name`, dimensiones, mallas, `columns`, `dowels`, concreto, acero y `cost`. |

Si nada cumple dentro de los límites, el comando termina con FAIL y el motivo. `--workers N` fija los procesos en paralelo (por defecto, los núcleos del equipo; `--workers 1`, sin paralelo); no cambia el resultado.
`--profile` escribe además `medicion.json` (etapa E0 de [plan-tipologias](../planes/plan-tipologias.md)): configuración
(SHA, máquina, procesos), número y tiempo de las tareas `single`, `covers`, `design`, `reassign` (coberturas de la
reasignación) y `matrix` (matriz del MILP) por f'c, tramos cubiertos y rediseñados (la tabla tiene todos los tramos,
n(n+1)/2, porque no depende de N), tiempo del proceso principal entre lotes (`main_s`), una
muestra fija de 500 pares columna–candidato con la extrapolación a la matriz completa de cobertura, y las tipologías
repetidas y columnas reasignables de la solución. No cambia `proyecto.json` ni `tipologias.json`.

### Curva costo–N (comando `typology-curve`, D-078)

`structurelab-rc typology-curve <proyecto de diseño> --output <carpeta> [--n 1-12] [--workers N] [--method ...]` diseña
con cada N pedido (por defecto de 1 a 12, o hasta el número de columnas; `--n` acepta `1-12`, `2,4,6` o `1-4,8`) y
escribe:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | `method`, `seconds` y `points`: por N, `N`, `fc [MPa]`, `cost`, `saving` y `saving [%]` (frente al N anterior), `saving_from_first` y `saving_from_first [%]` (acumulado frente al primer N), `rises` (el costo sube), `status` y `certified` (estado del MILP del f'c elegido; null con `dp`), `distinct_count`, `duplicates` (con `at_limit`) y `failure` si no tiene solución. |
| `curva.csv` | Los mismos puntos, separados por punto y coma. |
| `curva.svg` | Costo total frente a N: puntos naranjas con tipologías repetidas, rojos si el costo sube. |
| `memoria.txt`, `memoria.pdf` | Memoria de la curva: datos del proyecto, la gráfica (incrustada en el PDF), la tabla de puntos y su lectura. |

Lo que no depende de N se calcula una vez por f'c y se conserva entre valores de N: con `milp_iter`, el catálogo y su
cobertura, que siguen creciendo (un punto puede salir igual o más barato que el diseño suelto con ese N); con `milp` y
`dp`, la tabla de tramos (cada punto es igual al diseño suelto). El valor de `design.typologies` del proyecto se ignora.
El diseño del N elegido se obtiene con `design-footings` y se reverifica con `report`.

## Diseño de la zapata combinada (`diseno_combinada.json`, comando `design-combined`, D-107)

Diseña una zapata combinada rectangular de dos columnas: ubica la base, propone largo, ancho, espesor, f'c y todo el
refuerzo, y elige la solución de menor costo que aprueba la verificación de la combinada. `materials` declara solo `fy`,
`fyt`, `concrete`, `coating` y, opcional, `max_aggregate`: f'c es una variable del diseño. `soil` es igual que en la
verificación. Las dos columnas deben tener los mismos casos de carga, con al menos un caso de servicio sin sismo y casos
mayorados.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `principal_direction` | texto | `x` (por defecto) o `y`: eje global en que va la viga que une las columnas (D-094). |
| `columns[]` | lista | Exactamente dos columnas: `id`, `cx` y `cy` (mm, sección en ejes globales), `x` e `y` (mm, eje de la columna en ejes globales con cualquier origen; el diseño ubica la base) y `loads` (casos de carga, iguales a los de una zapata). |
| `combined_design.fc_options`, `combined_design.prices` | MPa, moneda | Como en el diseño por tipologías: f'c comerciales con su precio por m³ y precio del acero por kg. |
| `combined_design.plan_step`, `combined_design.plan_max` | mm | Paso de las dimensiones en planta y máximo del largo y del ancho. |
| `combined_design.h_min`, `combined_design.h_step`, `combined_design.h_max` | mm | Espesor mínimo, paso y máximo. |
| `combined_design.cover`, `combined_design.fill_height`, `combined_design.pedestal_height` | mm | Recubrimiento, relleno y pedestal. |
| `combined_design.surcharge_dead_kNm2`, `combined_design.surcharge_live_kNm2` | kN/m² | Sobrecargas superimpuestas. |
| `combined_design.bars`, `combined_design.spacing_step`, `combined_design.end` | -, mm, texto | Barras permitidas para todo el refuerzo, paso de separación y extremo de las barras. |
| `combined_design.dowel_bars` | - | Barras permitidas para los pasadores. |
| `combined_design.max_cantilever_start`, `combined_design.max_cantilever_end` | mm | Opcionales: voladizo máximo más allá de la cara exterior de la columna de cada extremo, a lo largo de la dirección principal (`start`: la columna con la menor coordenada). Por ejemplo, 0 en una columna de lindero. |
| `combined_design.stirrup_bars` | - | Opcional (D-110): barras permitidas para estribos cerrados de la viga larga, por ejemplo `["#3", "#4"]`. Con ellas, el cortante (y en la T, la torsión del alma, con Aℓ en la piel) pueden tomarlos estribos en lugar de un espesor mayor; gana lo más barato. Sin ellas no se proponen estribos. En la combinada rectangular la torsión es de placa (D-118): la toman las barras x e y. |
| `combined_design.shape` | texto | `rectangular` (por defecto) o `inverted_t` (D-113): con la T, `h_min`, `h_step` y `h_max` son los del espesor de la zarpa. |
| `combined_design.web_margin`, `combined_design.web_step` | mm | Solo con `inverted_t`: el alma parte de la columna más ancha (respecto a la resultante transversal) más `web_margin` a cada lado y crece de a `web_step`. |
| `combined_design.beam_h_min`, `combined_design.beam_h_step`, `combined_design.beam_h_max` | mm | Solo con `inverted_t`: alto total de la viga; `beam_h_min` debe superar `h_min`. |
| `combined_design.placement_case` | texto | Opcional (D-108): el caso de servicio sin sismo cuya resultante ubica la base, por ejemplo `"D+L"`. Debe existir en las dos columnas, ser de servicio y no tener sismo. Sin él, se usa el de servicio sin sismo de mayor carga total. |

Búsqueda (cada solución la aprueba `combined_footing_checks`; el diseño no tiene fórmulas propias):

1. **Ubicación:** el centroide de la base va sobre la resultante de las fuerzas de las columnas en el caso
   `placement_case` (o, sin él, en el de servicio sin sismo de mayor carga), con los momentos y los cortantes llevados a
   la base (h + pedestal): en ese caso la presión queda uniforme. Si un voladizo máximo
   lo impide, la base se corre lo necesario y queda excéntrica.
2. **Largo:** el menor que cubre las dos columnas, al paso de la planta; luego los mayores (el primero con solución y dos
   más). **Ancho:** el menor, al paso, que cumple presión, contacto, deslizamiento y volcamiento.
3. **Espesor:** el menor con solución, por bisección, y los mayores mientras el costo del concreto solo no alcance el
   mejor.
4. **Refuerzo** (barras rectas de borde a borde, sin cortes): barras inferiores x y superiores x de la viga larga
   (continuas), `band` de cada columna, `band_top` si el momento negativo de su franja lo pide (D-119), malla inferior
   y fuera de las franjas, barras superiores y (si hacen falta),
   refuerzo superficial si h pasa el límite del perfil y pasadores de cada columna. Cada grupo empieza en la opción más
   liviana que ya cumple los límites del perfil (acero mínimo, As,min de vigas, separación máxima y de fisuración) y,
   si una verificación suya falla, pasa a la más liviana que no repetiría la falla. Los momentos de las barras x, de
   los band y de las barras y fuera de las franjas son los de Wood-Armer (D-118). Con `stirrup_bars`, las fallas de
   cortante, Av,min y separación de estribos de la viga larga las toman estribos (más ramas si falla la separación
   entre ramas a lo ancho); en la T, también la torsión del alma (barra mayor o menor separación si falla At/s en la
   rama exterior) y Aℓ, la piel. El espesor menor con estribos compite por costo con el mayor sin ellos. Las
   fallas de dimensiones de la sección, punzonamiento y deformación unitaria (y el cortante sin `stirrup_bars`) piden
   más espesor. Si un band o las barras y no se desarrollan, se prueba el ancho siguiente. Las barras superiores faltan solo si
   el perfil permite concreto simple con el nivel sísmico (D-072) o no hay momento negativo.
5. **T invertida** (`shape: inverted_t`, D-113): el alto de la viga es la variable de la bisección; para cada alto, la
   zarpa parte de `h_min` y crece si fallan las aletas (cortante, deformación unitaria, concreto simple o altura
   mínima) y el alma parte de la mínima y crece si fallan las dimensiones de la sección. El refuerzo de la viga va en
   sus capas (D-106): la superior por dentro de los estribos y la inferior en el alma por dentro del estribo y, si el ala
   cuenta, sobre la zarpa hasta el ancho cubierto; las barras x de la zarpa van fuera de ese ancho y las y son las de las
   aletas. Si la luz libre entre columnas sobre el alto es ≤ 4 (ACI 9.9.1.1, NSR-10 C.11.7.1), la propuesta se declara
   `deep_beam` y se revisa con los criterios de D-089, sin puntal-tensor (D-109). La solución pasa también la
   validación de entrada del proyecto.
6. **f'c:** se repite para cada f'c de la lista y gana el de menor costo. Si nada cumple, termina con FAIL y el motivo de
   cada f'c, sin ampliar los límites.

Salida: `proyecto.json` (un proyecto de verificación con la zapata `ZC1` en ejes globales, con las posiciones de las
columnas respecto al centroide de la base; lo verifica `run`, `verify` o `report`) y `resumen.json`:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `fc [MPa]` | MPa | f'c elegido. |
| `length [mm]`, `width [mm]`, `h [mm]` | mm | Largo (dirección principal), ancho y espesor (el de la zarpa en la T). |
| `web [mm]`, `beam height [mm]`, `deep_beam` | mm, -, - | Solo en la T: ancho del alma, alto total de la viga y si se declaró de gran altura. |
| `base_center [mm]` | mm | Centroide de la base en los ejes globales de las columnas de entrada. |
| `placement_case` | texto | El caso que ubicó la base; la descripción de `proyecto.json` (y la memoria) dice además si se declaró o se eligió por la regla. |
| `reinforcement` | objeto | Refuerzo en ejes de la viga: `bottom_x`, `bottom_y`, `top_x`, `top_y`, `skin`, `stirrups` (null si no hay), `bands`, `band_tops` (band superior, null si no hace falta, D-119) y `dowels` por columna. En la T: `top_x` y `bottom_x` son las capas superior e inferior de la viga (separación), `mat_x` las barras x de la zarpa y `bottom_y` las de las aletas. |
| `concrete [m3]`, `steel [kg]`, `cost` | m³, kg, moneda | Cantidades y costo, con barras rectas de borde a borde menos el recubrimiento y pasadores hasta la malla inferior. |
| `by_fc` | lista | Cada f'c: `cost`, dimensiones, o `cost` null y `failure`. |

`--workers N` reparte los f'c entre procesos (por defecto, los núcleos del equipo); no cambia el resultado. `run`
reconoce el ejemplo por el bloque `combined_design`, diseña y genera la memoria de verificación de la zapata diseñada.

## Salida

`report` escribe estos archivos en la carpeta de salida:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | Todo el detalle en unidades de presentación (kN, kN·m, kPa, mm, MPa), redondeado a 6 cifras significativas. Es la fuente de la memoria. |
| `memoria.txt` | Memoria de cálculo de cada elemento, una tras otra (D-068): resultado y DCR máximo, capítulos fijos con cada revisión en su ubicación gobernante, índices DCR y notas y limitaciones. |
| `memoria.pdf` | Los mismos bloques en PDF, cada elemento desde una página nueva; requiere el extra `pdf` (`pip install structurelab-rc[pdf]`). |
| `presion_<zapata>.svg` | Planta de cada zapata con la presión del suelo en cada esquina del caso de servicio que gobierna la presión admisible (D-080); el PDF la incrusta en el capítulo de solicitaciones, junto con la tabla de esquinas de todos los casos de servicio. Las presiones vienen en los valores de cada verificación de presión admisible (`p esquina -x-y`, `+x-y`, `+x+y` y `-x+y`, en kPa). |
| `diagrama_<zapata>_<elemento>_cortante.svg`, `diagrama_<zapata>_<elemento>_momento.svg` | Solo zapatas combinadas y en T invertida (D-095, D-104): un diagrama por magnitud y elemento (`principal`, `franja_<columna>` o `aletas`), envolvente de los casos mayorados (máximo en azul, mínimo en rojo). La memoria los muestra en 3.5 "Solicitaciones internas", cada uno con la tabla de sus secciones críticas; los datos vienen en `resultado.json`, en `combined_footings[].diagrams` (`principal` y `secondary`: `positions [mm]`, `M max [kN-m]`, `M min [kN-m]`, `V max [kN]`, `V min [kN]`, `segments`, `marks`, `extremes` con el valor, la posición y el caso de cada extremo, y `sections`: por sección crítica, `label`, `position [mm]` y el máximo y el mínimo de M y de V con su caso). M > 0 tracciona la cara inferior; V es el del cuerpo libre a la izquierda. |

Cada verificación de `resultado.json` tiene:

| Campo | Descripción |
| --- | --- |
| `name` | Nombre de la verificación. |
| `status` | `PASS` (cumple), `FAIL` (no cumple o entrada inválida), `INCOMPLETE` (faltan datos) o `BLOCKED` (aún no implementado). El estado de un grupo es el más severo: FAIL > INCOMPLETE > BLOCKED > PASS. |
| `clause` | Numeral de la norma del perfil, o la decisión del proyecto que define el criterio (`D-0xx`, en `docs/decisions.md`). |
| `demand`, `capacity`, `unit` | Demanda y capacidad en la unidad indicada. |
| `ratio` | demand / capacity; la verificación cumple con razón ≤ 1. |
| `values` | Valores intermedios con su unidad entre corchetes, por ejemplo `phi`, `Vc [kN]` o `ex [mm]`. Los factores φ se leen de aquí. |
| `note` | Aclaración, por ejemplo la región de contacto de la zapata. |
| `errors` | Errores estructurados (`code`, `message`, `details`) cuando el estado no es PASS. |

En zapatas, `resultado.json` agrega `soil` (datos del suelo en kPa y kN/m³) y `footings`, con la geometría, las
propiedades calculadas, el número de casos y las verificaciones, y `foundation_beam_moments` (caso, columna, dirección
de la viga y `M [kN-m]`): los momentos transferidos que debe tomar la viga de cimentación (D-087). Las zapatas
combinadas van en `combined_footings`: la
geometría, las columnas (`columns[]`, cada una con sus cargas), las propiedades calculadas de la base, el armado
(`bottom`, `top`, `stirrups`, `skin`), `deep_beam`, `two_way_warning` (B, ℓn y B/ℓn si B ≥ ℓn, la luz
libre entre las caras de las columnas: puede trabajar en dos direcciones, D-091; null si no), `foundation_beam_shears`
(caso, columna, sección de la franja y `V [kN]`: el cortante de las franjas que excede φVc y debe tomar el refuerzo
transversal de la viga de cimentación, D-103) y las verificaciones, cada
una con su `case`, su `z [mm]` (posición a lo largo de la viga desde su borde negativo, o en la franja desde el borde
negativo de la dirección secundaria, en ejes declarados; nula en las demás) y en `note` la sección, la franja o la
columna. Su memoria separa la dirección principal (flexión con los momentos de Wood-Armer y cortante, D-118; en la T, también
la torsión de vigas del alma, D-088) de la secundaria (franjas o aletas) y trae la planta de presiones con las dos columnas y la tabla de esfuerzos de punzonamiento en cada esquina.

## Verificaciones de zapatas

Para cada caso de servicio, la resultante en el centroide de la base suma la columna, los pesos propios y las
sobrecargas con los factores del caso: N, Mx base = Mx − P·oy − H·Vy y My base = My + P·ox + H·Vx, con
H = h + altura del pedestal. Las excentricidades son ex = My base/N y ey = −Mx base/N.

| Verificación | Qué compara | Numeral |
| --- | --- | --- |
| Presión admisible del suelo | Presión máxima bruta frente a qa (kPa). La nota indica la región de contacto: C total, B pentagonal, D o E trapezoidal, A triangular. | ACI 13.3.1.1; NSR-10 C.15.2.2 |
| Contacto con el suelo | Fracción mínima exigida (`demand`) frente a la fracción de la base en contacto (`capacity`); cumple con razón ≤ 1. | D-052 |
| Deslizamiento | FS·V (`demand`) frente a R = μ·N + c_a·A_contacto + f_p·P_p (`capacity`), en la dirección de la resultante del cortante y en cada eje; gobierna la mayor razón y la nota dice cuál. Valores: N, contacto, μ·N, c_a·A_c, P_p en X y en Y, V, R, FS mínimo y FS obtenido. La pasiva actúa sobre el espesor h, con la sobrecarga del relleno. | ACI 13.2.6.1; NSR-10 remite al Título H (D-070) |
| Volcamiento | FS·Mo (`demand`) frente a Mr = N·L/2 (`capacity`) alrededor del borde de cada eje; Mo es el momento en la base, que incluye el cortante por h + pedestal. La pasiva no se cuenta. | ACI 13.2.6.1; NSR-10 remite al Título H (D-070) |
| Zapata: equilibrio con cargas mayoradas | FAIL si un caso mayorado no tiene equilibrio con el suelo (D-054). | D-054 |
| Flexión malla inferior / superior (barras x o y) | Por caso mayorado: el mayor momento de la carga neta en las caras de la columna frente a φMn de la franja de ancho total. La superior solo aparece si hay momento negativo. | ACI 13.2.6.6 y 13.2.7.1; NSR-10 C.15.4.1 y C.15.4.2 |
| Flexión concreto simple (cara superior, barras x o y) | Momento negativo sin malla superior: Mu frente a φMn = 0.60·0.42λ√f'c·Sm, Sm = b(h − 50)²/6 en todo el ancho. Con ACI special o NSR-10 DES el concreto simple no se permite en cimentaciones: FAIL "requiere malla superior" (D-072). | ACI 14.5.2.1, 14.5.1.7, 14.1.3; NSR-10 C.22.5.1, C.22.4.7, C.22.10.1 |
| Deformación neta de tracción malla … | εt de la malla frente a la mínima del perfil. | ACI 8.3.3.1; NSR-10 C.10.3.5 |
| Acero mínimo malla … | As frente a la cuantía mínima por el área bruta del ancho total. | ACI 8.6.1.1; NSR-10 C.10.5.4 y C.7.12.2.1 |
| Separación máxima malla … | Separación (y la de la franja) frente al máximo del perfil. | ACI 8.7.2.2; NSR-10 C.10.5.4 |
| Separación mínima (…) | Cada refuerzo declarado (cada malla y dirección, la franja central; en la combinada, las barras inferiores y superiores de cada dirección y el band de cada columna): separación libre s − db frente al mínimo (25 mm, db y 4/3·dagg). Sin `materials.max_aggregate`, INCOMPLETE (D-102). | ACI 25.2.1; NSR-10 C.7.6.1 y C.3.3.2(c) |
| Franja central malla … | Zapata rectangular: As en la franja frente a γs·As. | ACI 13.3.3.3; NSR-10 C.15.4.4.2 |
| Altura mínima de la zapata | 150 mm, medidos como pide cada perfil. | ACI 13.3.1.2; NSR-10 C.15.7 |
| Cortante en una dirección (barras x o y) | Por caso mayorado: Vu de la carga neta más allá de la sección a d de cada cara frente a φVc, con la d de esa dirección. | ACI 13.2.6.2(a) y 13.2.7.2; NSR-10 C.15.5 y C.11.2 |
| Punzonamiento | Por caso mayorado: esfuerzo máximo vu = Vu/(b0·d) + γv·Msc·c/Jc en los dos ejes, en el perímetro a d/2 (recortado con la base: αs = 40, 30 o 20), frente a φvc. Valores: Vu, b0, d, αs, γv, vuv, Msc y Jc en cada eje, el centroide del perímetro (xc, yc) y el esfuerzo en cada esquina (`esquina i x`, `esquina i y`, `esquina i v`, D-083). | ACI 22.6.5.2, 22.6.5.3 y 8.4.4.2; NSR-10 C.11.11.2.1 y C.11.11.7 |
| Transferencia de momento por flexión (barras x o y) | Por caso mayorado: γf·|Msc| frente a φMn de la malla inferior dentro de bslab = c + 1.5h a cada lado, sin pasar de los bordes de la zapata: a cada lado, el menor entre 1.5h y la distancia de la cara al borde (D-102; si recorta, el valor `bslab sin recortar` da c + 3h); en la combinada, más el band. No se suma al momento de la zapata. | ACI 8.4.2.2 (13.3.3.1); NSR-10 C.11.11.7.1 y C.13.5.3.2 (D-087) |
| Transferencia de momento: parte negativa (barras x o y) | La misma γf·|Msc| frente a la malla superior en bslab o, sin ella, al concreto simple si el nivel lo permite. Siempre CUMPLE: lo que la zapata no resiste lo debe tomar la viga de cimentación (valor `para la viga`, sin razón demanda/capacidad) y queda en `foundation_beam_moments` y en la memoria. | Ídem (D-087) |
| Fuera de la franja central malla … | Zapata rectangular: As fuera de la franja frente a (1 − γs)·As. | ACI 13.3.3.3(b); NSR-10 C.15.4.4.2 (D-087) |
| Acero mínimo por punzonamiento (barras x o y) | Solo ACI, cuando vuv > φ0.17√f'c: As,min de 8.6.1.2 (con el bslab recortado por los bordes, D-102) frente a las barras de la malla inferior dentro de bslab. | ACI 8.6.1.2 |
| Desarrollo malla … (barras x o y) | Longitud de desarrollo (recta o con gancho) frente a la disponible desde la cara de la columna hasta el extremo de la barra. La superior, solo con momento negativo. | ACI 25.4.2 y 25.4.3; NSR-10 C.12.2 y C.12.5 |
| Pasadores: área mínima | Área de los pasadores frente a 0.005 por el área de la columna. | ACI 16.3.4.1; NSR-10 C.15.8.2.1 |
| Pasadores: anclaje a compresión | ldc frente al espacio hasta la malla inferior. | ACI 25.4.9; NSR-10 C.12.3 |
| Aplastamiento en la zapata | Por caso mayorado: Pu frente a φ·0.85f'c·A1·√(A2/A1) ≤ 2 (A2 del tronco de pirámide 1:2). | ACI 22.8.3.2; NSR-10 C.10.14.1 |
| Pasadores: compresión sobre el aplastamiento | Si Pu > φBn: área de los pasadores frente a (Pu − φBn)/(φ·fy). | ACI 16.3.3.4; NSR-10 C.15.8.1.2(a) |

Si la resultante cae fuera de la base o N no es de compresión, ambas verificaciones del caso son FAIL ("Sin
equilibrio con el suelo"). Sin casos de servicio, la presión admisible sale INCOMPLETE.
