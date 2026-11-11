# Formato de zapatas

Referencia de la entrada y la salida de la verificación de zapatas aisladas (v3, en curso), común a los dos perfiles. Los ejemplos están en `examples/<perfil>/zapatas/`. La presión del suelo sigue la solución de Bellos y Bakas (2017) para una zapata rígida sin tracción en el contacto.

## Convenciones

- Ejes globales de ETABS con origen en el centroide de la base: X a lo largo de `lx`, Y a lo largo de `ly`, Z hacia
  arriba. Las zapatas rotadas aún no se admiten.
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

Zapata rectangular de dos columnas, solo verificación. X es la dirección larga: las dos columnas van a distintas x. Usa
el mismo `soil` que las zapatas aisladas. Se verifican la parte geotécnica con la resultante de las dos columnas
(V3J.1) y, con los casos mayorados:

- la viga en la dirección larga con las verificaciones de vigas en sus secciones críticas (V3J.2, D-081): cada check
  lleva `z`, la posición desde el borde −X, y en `note` la sección; Vc y Av,min de cimentación; separación de 3h y
  450 mm;
- por columna (V3J.3, D-082): el punzonamiento (y el del perímetro común si los de las dos columnas se traslapan,
  D-086), la franja transversal (también con las verificaciones de vigas, con
  `z` desde el borde −Y y `note` "Franja transversal de la columna …, cara ±Y" o "a d de la cara ±Y"), el aplastamiento
  y los pasadores (`note` "Columna …"); la malla y fuera de las franjas (mínimo de losa y separación); el desarrollo de
  las barras x desde la sección de mayor momento de su signo y de las barras y de cada franja desde la cara de la
  columna.

La memoria y el ejemplo `zapata_combinada.json` (V3J.4) están en los dos perfiles.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `id`, `lx`, `ly`, `h`, `cover`, `fill_height`, `pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2` | | Como en la zapata aislada. |
| `columns[]` | lista | Exactamente dos columnas. |
| `columns[].id` | texto | Identificador de la columna. |
| `columns[].cx`, `columns[].cy` | mm | Sección (cx a lo largo de X). |
| `columns[].x`, `columns[].y` | mm | Posición del eje de la columna respecto al centroide de la base. |
| `columns[].dowels` | | Pasadores, como en la zapata aislada (opcional; sin ellos sus verificaciones quedan INCOMPLETE). |
| `columns[].band` | | Refuerzo transversal adicional bajo la columna, paralelo a Y, en el ancho de su franja (columna + d/2 a cada lado, dentro de la base), a la profundidad de las barras y de la malla inferior: `designation` y `spacing` (opcional). |
| `columns[].loads` | lista | Casos de carga de la columna, como en la zapata aislada; las dos columnas deben tener los mismos casos, con los mismos factores y la misma marca de sismo. |
| `bottom` | | Malla inferior en las dos direcciones (sin `band_spacing`). |
| `top` | | Barras superiores paralelas a X (`designation`, `spacing`, `end`: `straight` o `hook`, como el `end` de la malla), opcional: sin ellas, el momento negativo se revisa como concreto simple (D-072). |
| `stirrups` | | Estribos de la dirección larga, como en las vigas (`designation`, `legs`, `spacing`, `closed`), opcional (D-081). |
| `skin` | | Refuerzo superficial en las caras largas (`designation`, `spacing` vertical), al recubrimiento de la cara, desde la capa inferior hacia arriba; se exige con h > 900 mm (D-083). |
| `torsion_layers` | | Capas de Aℓ de la viga larga con el formato de las capas de vigas (`depth` desde la cara superior, `role: "torsion"`, `bars` con x desde la cara −Y); opcional; sin ellas, Aℓ = 0 (D-088). |

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
| `curva.json` | `method`, `seconds` y `points`: por N, `N`, `fc [MPa]`, `cost`, `saving` y `saving [%]` (frente al N anterior), `saving_from_first` y `saving_from_first [%]` (acumulado frente al primer N), `rises` (el costo sube), `status` y `certified` (estado del MILP del f'c elegido; null con `dp`), `distinct_count`, `duplicates` (con `at_limit`) y `failure` si no tiene solución. |
| `curva.csv` | Los mismos puntos, separados por punto y coma. |
| `curva.svg` | Costo total frente a N: puntos naranjas con tipologías repetidas, rojos si el costo sube. |
| `memoria_curva.txt`, `memoria_curva.pdf` | Memoria de la curva: datos del proyecto, la gráfica (incrustada en el PDF), la tabla de puntos y su lectura. |

Lo que no depende de N se calcula una vez por f'c y se conserva entre valores de N: con `milp_iter`, el catálogo y su
cobertura, que siguen creciendo (un punto puede salir igual o más barato que el diseño suelto con ese N); con `milp` y
`dp`, la tabla de tramos (cada punto es igual al diseño suelto). El valor de `design.typologies` del proyecto se ignora.
El diseño del N elegido se obtiene con `design-footings` y se reverifica con `report`.

## Salida

`report` escribe estos archivos en la carpeta de salida:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | Todo el detalle en unidades de presentación (kN, kN·m, kPa, mm, MPa), redondeado a 6 cifras significativas. Es la fuente de la memoria. |
| `memoria.txt` | Memoria de cálculo de cada elemento, una tras otra (D-068): resultado y DCR máximo, capítulos fijos con cada revisión en su ubicación gobernante, índices DCR y notas y limitaciones. |
| `memoria.pdf` | Los mismos bloques en PDF, cada elemento desde una página nueva; requiere el extra `pdf` (`pip install structurelab-rc[pdf]`). |
| `presion_<zapata>.svg` | Planta de cada zapata con la presión del suelo en cada esquina del caso de servicio que gobierna la presión admisible (D-080); el PDF la incrusta en el capítulo de solicitaciones, junto con la tabla de esquinas de todos los casos de servicio. Las presiones vienen en los valores de cada verificación de presión admisible (`p esquina -x-y`, `+x-y`, `+x+y` y `-x+y`, en kPa). |

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
(`bottom`, `top`, `stirrups`, `skin`, `torsion_layers`) y las verificaciones, cada una con su `case`, su `z [mm]` (posición en la viga
larga desde −X o en la franja desde −Y; nula en las demás) y en `note` la sección, la franja o la columna. Su memoria
separa la viga larga (flexión, cortante y torsión, D-088) de las franjas transversales y trae la planta de presiones con las dos columnas y la tabla de
esfuerzos de punzonamiento en cada esquina.

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
| Franja central malla … | Zapata rectangular: As en la franja frente a γs·As. | ACI 13.3.3.3; NSR-10 C.15.4.4.2 |
| Altura mínima de la zapata | 150 mm, medidos como pide cada perfil. | ACI 13.3.1.2; NSR-10 C.15.7 |
| Cortante en una dirección (barras x o y) | Por caso mayorado: Vu de la carga neta más allá de la sección a d de cada cara frente a φVc, con la d de esa dirección. | ACI 13.2.6.2(a) y 13.2.7.2; NSR-10 C.15.5 y C.11.2 |
| Punzonamiento | Por caso mayorado: esfuerzo máximo vu = Vu/(b0·d) + γv·Msc·c/Jc en los dos ejes, en el perímetro a d/2 (recortado con la base: αs = 40, 30 o 20), frente a φvc. Valores: Vu, b0, d, αs, γv, vuv, Msc y Jc en cada eje, el centroide del perímetro (xc, yc) y el esfuerzo en cada esquina (`esquina i x`, `esquina i y`, `esquina i v`, D-083). | ACI 22.6.5.2, 22.6.5.3 y 8.4.4.2; NSR-10 C.11.11.2.1 y C.11.11.7 |
| Transferencia de momento por flexión (barras x o y) | Por caso mayorado: γf·|Msc| frente a φMn de la malla inferior dentro de bslab = c + 1.5h a cada lado (en la combinada, más el band). No se suma al momento de la zapata. | ACI 8.4.2.2 (13.3.3.1); NSR-10 C.11.11.7.1 y C.13.5.3.2 (D-087) |
| Transferencia de momento: parte negativa (barras x o y) | La misma γf·|Msc| frente a la malla superior en bslab o, sin ella, al concreto simple si el nivel lo permite. Siempre CUMPLE: lo que la zapata no resiste lo debe tomar la viga de cimentación (valor `para la viga`, sin razón demanda/capacidad) y queda en `foundation_beam_moments` y en la memoria. | Ídem (D-087) |
| Fuera de la franja central malla … | Zapata rectangular: As fuera de la franja frente a (1 − γs)·As. | ACI 13.3.3.3(b); NSR-10 C.15.4.4.2 (D-087) |
| Acero mínimo por punzonamiento (barras x o y) | Solo ACI, cuando vuv > φ0.17√f'c: As,min de 8.6.1.2 frente a las barras de la malla inferior dentro de bslab. | ACI 8.6.1.2 |
| Desarrollo malla … (barras x o y) | Longitud de desarrollo (recta o con gancho) frente a la disponible desde la cara de la columna hasta el extremo de la barra. La superior, solo con momento negativo. | ACI 25.4.2 y 25.4.3; NSR-10 C.12.2 y C.12.5 |
| Pasadores: área mínima | Área de los pasadores frente a 0.005 por el área de la columna. | ACI 16.3.4.1; NSR-10 C.15.8.2.1 |
| Pasadores: anclaje a compresión | ldc frente al espacio hasta la malla inferior. | ACI 25.4.9; NSR-10 C.12.3 |
| Aplastamiento en la zapata | Por caso mayorado: Pu frente a φ·0.85f'c·A1·√(A2/A1) ≤ 2 (A2 del tronco de pirámide 1:2). | ACI 22.8.3.2; NSR-10 C.10.14.1 |
| Pasadores: compresión sobre el aplastamiento | Si Pu > φBn: área de los pasadores frente a (Pu − φBn)/(φ·fy). | ACI 16.3.3.4; NSR-10 C.15.8.1.2(a) |

Si la resultante cae fuera de la base o N no es de compresión, ambas verificaciones del caso son FAIL ("Sin
equilibrio con el suelo"). Sin casos de servicio, la presión admisible sale INCOMPLETE.
