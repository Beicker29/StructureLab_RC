# Formato de zapatas

Referencia de la entrada y la salida de las zapatas aisladas, combinadas y en T invertida, común a los dos perfiles. Los ejemplos están en `examples/<perfil>/zapatas/<carpeta>/` (`aislada`, `combinada`, `t_invertida` y `tipologias`, este con el diseño por tipologías y la curva costo–N, D-155).

Supuestos:

- La presión del suelo es lineal y sin tracción bajo la zapata rígida (Bellos y Bakas, 2017).
- El empuje pasivo del deslizamiento actúa solo sobre el espesor de la zapata; el pedestal no aporta pasiva (D-092).
- No hay nivel freático: la presión, el contacto, la estabilidad y la revisión estructural se calculan sin subpresión
  ni pesos sumergidos. Su implementación está pendiente en la [hoja de ruta](../ROADMAP.md) (D-092).

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
| `concrete.fc` | MPa | Resistencia especificada del concreto, f'c (en los diseños no va: f'c es una variable del diseño). |
| `concrete.type` | texto | `normalweight` (peso normal) o `lightweight` (liviano); define λ. |
| `concrete.max_aggregate` | mm | Tamaño máximo nominal del agregado grueso (dagg), opcional. Sin él, la separación mínima de las barras queda INCOMPLETE: no se supone (D-102). |
| `concrete.unit_weight_kNm3` | kN/m³ | Peso unitario del concreto de la zapata y del pedestal (zapatas y cabezales; D-139, antes en `soil`). |
| `reinforcement_steel.fy` | MPa | Fluencia del refuerzo longitudinal. |
| `reinforcement_steel.fyt` | MPa | Fluencia del refuerzo transversal (estribos). Se declara aunque el ejemplo no lo use. |
| `reinforcement_steel.coating` | texto | Recubrimiento de las barras: `uncoated` (sin recubrimiento), `galvanized`, `epoxy` o `zinc_epoxy` (dual de zinc y epóxico); cambia la longitud de desarrollo (ψe, D-071). |
| `soil` | objeto | Datos del suelo y de los pesos propios (abajo). Obligatorio con zapatas. |
| `footings` | lista | Zapatas del proyecto. |
| `min_clear_spacing` | mm | Opcional (D-156): la separación libre mínima admisible entre los bordes de zapatas vecinas del mismo nivel (con `location`). Solo informa: `resultado.json` (`close_footings`), las notas de `run` y la planta de localización listan los pares más cercanos, y los traslapados aunque no se declare, con sus nudos de ETABS; el usuario decide si los une con una zapata combinada. También en el diseño por tipologías y en las plantillas de ETABS, que lo pasan al proyecto. |

### Suelo (`soil`); todos los campos son obligatorios salvo `passive_factor`

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `allowable_pressure_kPa` | kPa | Presión admisible **bruta** del suelo, qa. Se compara con la presión que incluye los pesos propios y las sobrecargas. |
| `min_contact_fraction` | - | Fracción mínima de la base que debe quedar en contacto con el suelo en los casos de servicio (0 a 1). |
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
| `quantity` | - | Obligatorio (D-159): las veces que se construye (entero ≥ 1; en los ejemplos, 1). La cartilla de su tipo se reporta para una unidad y para las N unidades. |
| `lx`, `ly` | mm | Dimensiones en planta a lo largo de X y de Y. |
| `h` | mm | Espesor de la zapata. |
| `cover` | mm | Recubrimiento libre de las mallas. |
| `fill_height` | mm | Altura del relleno sobre la zapata. |
| `pedestal_height` | mm | Altura del pedestal, con la sección de la columna (0 si no hay). |
| `surcharge_dead_kNm2` | kN/m² | Sobrecarga superimpuesta muerta sobre el relleno (0 si no hay). |
| `surcharge_live_kNm2` | kN/m² | Sobrecarga superimpuesta viva sobre el relleno (0 si no hay). |
| `column.cx`, `column.cy` | mm | Dimensiones de la columna a lo largo de X y de Y. |
| `column.offset_x`, `column.offset_y` | mm | Posición del eje de la columna respecto al centroide de la base. |
| `column.dowels.designation`, `column.dowels.count`, `column.dowels.end` | -, -, texto | Pasadores entre la columna y la zapata: barra del catálogo, número y cómo termina su pie (`straight`, `hook90` o `hook180`; obligatorio, D-134). Si faltan, sus verificaciones salen `INCOMPLETE`. |
| `bottom` | objeto | Malla inferior (abajo). |
| `top` | objeto o `null` | Malla superior, o `null` si no hay. |
| `loads` | lista | Casos de carga (abajo). |
| `location` | objeto | Opcional (D-130): `{"x", "y", "story", "joint"}`, el eje de la columna en el proyecto (x e y globales en mm, el nivel y el nudo de ETABS). Lo llena el importador con `etabs_files.locations` o se declara. Solo lo usa la planta de localización. También en `combined_footings[].columns[]`, en ejes globales aunque la viga vaya en Y, y en las columnas del diseño por tipologías, que lo pasan a su zapata. |
| `typology` | texto | Opcional (D-130): el tipo que rotula la planta de localización y agrupa el cuadro de tipologías (el grupo de la plantilla o la tipología del diseño). Sin él, el `id`. Con despiece, las zapatas del mismo tipo comparten una cartilla y un despiece, con N = la suma de sus `quantity` (D-159). |

El relleno y las sobrecargas ocupan el área de la base menos la de la columna.

### Malla (`bottom`, `top`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `first` | texto | Dirección de las barras más cercanas a la cara de la zapata: `x` o `y`. Define la d de cada dirección. |
| `x.designation`, `x.spacing`, `x.end` | -, mm, texto | Barras paralelas a X: designación del catálogo, separación centro a centro y cómo terminan (obligatorio, D-134). |
| `y.designation`, `y.spacing`, `y.end` | -, mm, texto | Barras paralelas a Y. |

**Extremos (`end`, D-134).** Cada grupo de barras declara el suyo, sin valor por defecto: `straight` (recta), `hook90`
o `hook180`. Con 90° y 180° la barra se desarrolla con gancho estándar (ℓdh; ACI 25.4.3, NSR-10 C.12.5; el factor de
recubrimiento 0.7 pide el recubrimiento sobre la extensión solo con 90°) y el despiece usa la extensión y el doblado del
gancho estándar (ACI Tabla 25.3.1, NSR-10 C.7.1 y C.7.2). Las barras no llevan gancho de 135°: `hook135` en una barra es
un error de entrada (D-161). Los estribos declaran su gancho de cierre en `stirrups.end`: `hook90`, `hook135` o
`hook180` (este último no existe en NSR-10, C.7.1.3). Con un número impar de ramas, la rama impar es un estribo de una rama
(stirrup, ACI 318-25 cap. 2) del alto exterior de los estribos con sus ganchos; cada gancho mide la g del estribo (D-160,
D-161).
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

Zapata rectangular de dos o más columnas alineadas a lo largo de la viga (D-163), solo verificación. La **dirección principal** es la de la viga que une las columnas
(`principal_direction`, X o Y global) y la **dirección secundaria** la transversal (D-101). Las verificaciones nombran
las barras por su dirección ("dirección principal", "dirección secundaria"), no por un eje; la memoria agrega el eje
global, por ejemplo "Dirección principal (Y global)". Usa el mismo `soil` que las zapatas aisladas. Se verifican la parte
geotécnica con la resultante de las columnas (V3J.1) y, con los casos mayorados:

- la viga de la dirección principal con las verificaciones de vigas en sus secciones críticas (V3J.2, D-081): cada
  check lleva `z`, la posición a lo largo de la viga desde su borde negativo (−X o −Y global), y en `note` la sección
  ("cara +X de la columna …"); Vc y Av,min de cimentación; separación de 3h y 450 mm. El cortante, solo a d de las caras
  (D-149), con la d del cortante de esa misma sección (el centroide de fuerzas del acero a tracción, D-131), que se
  encuentra por iteración (D-151);
- por columna (V3J.3, D-082): el punzonamiento (y el del perímetro común de cada grupo de columnas cuyos perímetros se
  traslapan, directamente o encadenados, D-086, D-163), la franja transversal de la dirección secundaria (también con las verificaciones de vigas, con `z` desde el
  borde negativo de la dirección secundaria y `note` "Franja transversal de la columna …, cara ±Y", "a d de la cara ±Y"
  o "mayor M negativo hacia el borde ±Y", con el eje de la dirección secundaria; el cortante solo a d de la cara (D-148),
  a la d del cortante de esa sección (D-131, D-151); su carga es la neta: la fuerza de la columna con la forma de la
  presión menos los pesos y las sobrecargas, D-095; la flexión con el ancho de franja (columna + d/2 a cada lado) y Vc
  con el ancho de cortante (columna + d a cada lado, sin pasar el borde ni la mitad del espacio libre hasta la columna
  vecina, D-151) y las barras que caen en él; abajo lleva el band si lo hay o, si no, la malla de la dirección secundaria, y arriba las barras de
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
| `id`, `quantity`, `typology`, `lx`, `ly`, `h`, `cover`, `fill_height`, `pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2` | | Como en la zapata aislada. |
| `principal_direction` | texto | Dirección principal (la de la viga que une las columnas) en ejes globales de ETABS: `x` (por defecto) o `y` (D-094). Todo se escribe en ejes globales, como está la zapata en planta: con `y`, `ly` es la dimensión paralela a la viga, las columnas van a distintas `y` y `bottom.y` y `top.y` son las barras paralelas a la viga (D-099). Estribos, refuerzo superficial, capas de torsión, `band` y la viga de la T no tienen dirección propia: van paralelos o transversales a la viga. El cálculo trabaja en ejes de la viga (X = +Y global, Y = −X global): con `y`, al cargar se intercambian lx y ly, las columnas pasan a x = y, y = −x, con cx = cy y cy = cx, las barras x e y (y `first`) de `bottom` y de `top` se intercambian y las cargas pasan a Vx = Vy, Vy = −Vx, Mx = My y My = −Mx. La salida vuelve a los ejes declarados con el giro inverso (D-101); `resultado.json` trae `principal_direction` en `geometry [mm]`. |
| `columns[]` | lista | Dos o más columnas a lo largo de la viga (D-163), sin traslaparse entre vecinas. Con más de dos, los tramos interiores se rotulan "entre columnas C1 y C2"; cada franja transversal llega hasta el punto medio entre las caras si se monta con la de la columna vecina, y el aviso de dos direcciones (D-091) usa el tramo interior más corto (`two_way_warning.tramo`). |
| `columns[].id` | texto | Identificador de la columna. |
| `columns[].cx`, `columns[].cy` | mm | Sección (cx a lo largo de X). |
| `columns[].x`, `columns[].y` | mm | Posición del eje de la columna respecto al centroide de la base; con `plan`, en el sistema de la planta (ver abajo). |
| `plan` | | Opcional (D-164): planta trapezoidal o en T/L, en lugar de `lx` y `ly` (que entonces se calculan, como la caja de la planta). Ver "Planta trapezoidal o en T/L". |
| `columns[].dowels` | | Pasadores, como en la zapata aislada (opcional; sin ellos sus verificaciones quedan INCOMPLETE). |
| `columns[].band` | | Refuerzo transversal inferior bajo la columna, paralelo a Y, en el ancho de su franja (columna + d/2 a cada lado, dentro de la base), a la profundidad de las barras y de la malla inferior: `designation`, `spacing` y `end` (opcional). Es el único refuerzo inferior transversal de esa zona: la malla inferior y va solo fuera de las zonas de band (D-097). |
| `columns[].band_top` | | Band superior (D-119): barras transversales arriba en el ancho de la franja, `designation`, `spacing` y `end` (opcional, sin `band_spacing`); toman el momento negativo de la franja y el de la torsión de placa. Van como `top.y` (debajo de `top.x` si esa dirección va más cerca de la cara) y son la capa superior de la franja; donde lo hay, `top.y` va solo fuera de esa zona. Sin `top`, terminan como la malla inferior. No aplica en la T invertida. |
| `columns[].loads` | lista | Casos de carga de la columna, como en la zapata aislada; todas las columnas deben tener los mismos casos, con los mismos factores y la misma marca de sismo. |
| `bottom` | | Malla inferior en las dos direcciones (sin `band_spacing`). |
| `top` | | Barras superiores con la estructura de `bottom` (D-099), opcional: `x` (paralelas a X, a lo largo de la viga) e `y` (paralelas a Y, uniformes en todo el largo, D-097), cada una `{designation, spacing, end}` y opcional, con al menos una; `first`, la dirección más cercana a la cara superior, obligatoria si se declaran las dos. Sin barras superiores en la dirección principal, el momento negativo de la viga se revisa como concreto simple (D-072); sin ellas en la secundaria, el de las franjas transversales. Con `principal_direction: "y"`, `x`, `y` y `first` están en ejes globales y se intercambian como en `bottom`. En la T invertida, `top` es la malla superior de la zarpa (D-114; el refuerzo de la viga va en `beam.layers`): con `top.y`, el momento negativo de las aletas se revisa con esas barras por metro y se revisa su desarrollo desde la cara de la viga; sin ellas, de concreto simple. |
| `stirrups` | | Estribos de la viga de la dirección principal, como en las vigas (`designation`, `legs`, `spacing`, `closed`) más su gancho de cierre `end` (obligatorio, D-134), opcional (D-081); solo para el cortante: la torsión de la combinada rectangular es de placa (D-118). |
| `skin` | | Refuerzo superficial en las caras largas (`designation`, `spacing` vertical, `end`), al recubrimiento de la cara, desde la capa inferior hacia arriba; se exige con h > 900 mm (D-083). |
| `min_steel_exception` | sí/no | Obligatorio (D-123): si el As,min de flexión admite la excepción de 4/3 del As requerido por análisis (ACI 9.6.1.3, NSR-10 C.10.5.3) en la viga de la dirección principal, en las franjas y en la viga de la T; sin él, la entrada es inválida. No aplica a las mallas ni a las aletas, que usan el mínimo de losa. |
| `deep_beam` | sí/no | La viga de la dirección principal es de gran altura (declarado por el usuario): se verifican los criterios de vigas altas como en las vigas (D-089). |
| `beam` | mm | T invertida (D-093, D-106): `width` (bw) y `height` (H, altura total desde la base) de la viga centrada en Y sobre la zarpa de espesor `h`; `layers`, las capas de la viga como en las vigas (`depth` desde la cara superior de la viga, `role` flexure/skin/torsion, `bars` con x desde la cara −Y del alma, o solo la lista de barras, por ejemplo `["#6", "#6", "#6", "#6"]`, D-114, y `end`, obligatorio en cada capa, D-134); `stirrups`, sus estribos, con su gancho de cierre `end`; `bottom_width` (opcional), el ancho centrado en el alma que cubre la capa de flexión más profunda, que puede salir del alma sobre la zarpa (por defecto, el ala efectiva). Con solo la lista de barras, la capa inferior se reparte a igual separación en ese ancho (al recubrimiento si llega al borde de la base; por dentro del estribo si el ala no cuenta) y las demás capas entre las esquinas del estribo, como en las vigas. Las columnas deben caber en bw; `stirrups` y `skin` de la zapata no se usan (van en `beam`); `top` es la malla superior de la zarpa; `band` no aplica. La malla `bottom` es la de la zarpa: sus barras x van solo fuera del ancho cubierto y las y son las de las aletas. Con `plan` (D-167), `axis` (opcional) es la coordenada t del eje del alma en el sistema de la planta (sin ella, el centroide); el alma va de borde a borde y debe caber en la planta en todo su largo. |

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

- **Cortante en las franjas (D-119, D-151):** Vu = |V por flexión + V por torsión|. V por flexión es la carga neta hacia
  arriba entre la sección y el borde; V por torsión, ±(T(x1) − T(x0))/B, el salto de T entre los bordes de la franja, con
  signo: la viga equilibra ese momento con un par que alivia el voladizo de un lado (−, en +Y si el salto es positivo) y
  carga el del otro (+). Vc, con el ancho de cortante (columna + d a cada lado).

La memoria de la combinada rectangular (D-119) trae:

- los capítulos de las franjas con un subcapítulo por columna;
- tres capítulos de la dirección secundaria fuera de las franjas band: momento positivo, momento negativo y fuerza
  cortante. Cada revisión muestra "Composición de Mu: M flexión + M torsión" o "Composición de Vu: V flexión +
  V torsión", con los valores `M flexion`, `M torsion`, `V flexion` y `V torsion`;
- la tabla de Wood-Armer en 3.6, con `mx`, `my`, `mxy`, `mx* inf`, `mx* sup`, `my* inf` y `my* sup` en kN·m/m;
- un índice DCR con una fila por verificación, dirección y signo de momento.

No hay torsión de vigas: `torsion_layers` se rechaza. La T invertida conserva la torsión de vigas en su alma.

### Planta trapezoidal o en T/L (`plan`, D-164)

La planta se declara en ejes globales, con `principal_direction`, igual que la rectangular. Su sistema: `a` a lo largo de
la dirección principal desde el borde negativo de la zapata (a = 0) y `t` en el eje global transversal (Y si la viga va
en X; X si va en Y) desde una línea de referencia que elige el usuario (t = 0), por ejemplo el lindero o el eje de las
columnas. Las columnas (`x`, `y`) se dan en ese mismo sistema global. El área, el centroide, las inercias y el núcleo se
calculan; el centroide sale en la memoria y en `geometry [mm].centroid` (a, t).

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `plan.shape` | texto | `trapezoid` o `stepped`. |
| `plan.length` | mm | Trapecio: el largo a lo largo de la dirección principal. |
| `plan.start`, `plan.end` | mm | Trapecio: `{low, high}`, las coordenadas `t` mínima y máxima del extremo negativo (a = 0) y del positivo (a = length). Con el mismo `low` (o `high`) en los dos extremos, ese lado queda recto. |
| `plan.parts[]` | mm | Planta en T, L u otra escalonada: dos o más tramos en orden a lo largo de la dirección principal, cada uno `{length, low, high}`. Centrados queda en T; con un borde común, en L. Cada tramo debe compartir ancho con el siguiente. |

Ejemplo (viga en la Y global, trapecio con el lado −X recto):

```json
"principal_direction": "y",
"plan": {"shape": "trapezoid", "length": 7000, "start": {"low": -1300, "high": 1300}, "end": {"low": -1300, "high": 300}}
```

Con `plan`, el cálculo:

- **Presión:** las ecuaciones de equilibrio de Bellos y Bakas resueltas sobre la planta. La memoria da la presión en cada
  vértice (`p vertice i`, numerados en la planta desde el centroide) y si el contacto es total o parcial. Sin equilibrio,
  la resultante cae fuera de la envolvente convexa.
- **Volcamiento:** alrededor de cada lado de la envolvente convexa (los oblicuos incluidos). La pasiva del deslizamiento
  usa el ancho proyectado (lx, ly de la caja).
- **Viga longitudinal:** el cuerpo libre se integra sobre la planta. Cada sección usa el ancho local B(x) y solo las
  barras x que pasan por ella; la torsión de placa, mxy = T/B(x). En el desarrollo de las barras x desde la sección de
  mayor momento cuentan solo las que alcanzan a desarrollarse hasta el extremo real de su tramo: deben bastar para el As
  requerido de esa sección; si no, la revisión no cumple (decisión del usuario, D-164).
- **Franjas:** los voladizos van hasta los bordes locales en el eje de la columna; si la franja cruza un escalón, hasta
  los del tramo más angosto.
- **Punzonamiento:** el perímetro rectangular a d/2 se recorta con la planta y b0 suma lo que queda dentro. αs sale de
  las esquinas del perímetro dentro de la planta: 4 → 40, 3 → 30 (un borde corta una esquina), 2 → 30 (borde), 1 → 20.
- **Aviso de dos direcciones (D-091):** ℓn de cada tramo contra el mayor ancho dentro de ese tramo.

- **Despiece:** cada barra va de borde a borde de la planta menos el recubrimiento a lo largo de la barra, como en el
  cabezal con esquinas recortadas (D-141); las de longitud distinta van en grupos aparte, con una marca cada una
  ("malla inferior y (1)", "(2)", …). En una planta con dos tramos anchos, la barra que cruza el angosto queda en dos.
  La cartilla, el `.dli` y el DXF las llevan como cualquier otra barra.
- **Dibujo:** las plantas con el contorno real, el recubrimiento como contorno interior, la cadena de cotas del largo de
  cada tramo y el ancho de cada lado transversal; el alzado con el largo real y cada corte con el ancho de la base en la
  columna.

- **Estribos y refuerzo superficial (D-167):** cada estribo cerrado mide el ancho local en su abscisa, con las ramas
  declaradas repartidas en él, y el cortante de cada sección se revisa con ellos en el ancho local. Cada medida
  distinta es una marca aparte (se piden y se arman distinto). La piel va por cada cara larga con su largo real
  (inclinada, paralela al lado oblicuo, en el trapecio); las caras cortas de los escalones no llevan. En cada corte se
  dibuja el estribo de esa sección.

El diseño (D-169, D-170) y la planta de localización (D-170) están más abajo, en el diseño de la combinada y en el
dibujo.

**T invertida con `plan` (D-167).** La zarpa sigue la planta y el alma, de ancho constante, va de borde a borde con su
eje en `beam.axis`. Las aletas van de las caras del alma a los bordes locales en cada x. El ala efectiva es la del
perfil sin pasar del ancho local, centrada en el alma, en cada sección; la capa inferior de la viga se reparte en la más
angosta del largo. Si el alma no está en el centroide, su peso da momento en la resultante y torsión en la viga.

## Diseño por tipologías (`diseno_*.json`, comando `design-footings`)

En lugar de zapatas, el proyecto de diseño trae columnas y un bloque `design` (D-069). `concrete` no declara `fc`: f'c es
una variable del diseño. `soil` es igual que en la verificación.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `columns[].id` | texto | Identificador de la columna de una zapata aislada. `columns` puede quedar vacío si hay `combined_footings` (D-156). |
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
| `design.bars`, `design.spacing_step` | -, mm | Barras permitidas para las mallas y paso de separación. |
| `design.ends` | objeto | Cómo terminan las barras que se diseñan (D-134): `bottom` (malla inferior), `top` (malla superior) y `dowels` (pie de los pasadores), cada uno `straight`, `hook90` o `hook180` (D-161). |
| `design.dowel_bars` | - | Barras permitidas para los pasadores. |
| `design.method` | texto | `milp_iter` (por defecto desde E3b: iterativo, sin tabla de tramos, D-077), `milp` (asignación óptima sobre la tabla completa de tramos, D-075) o `dp` (solo la partición y la reasignación). `milp_iter` y `milp` requieren `pip install structurelab-rc[opt]`. `--method` en la CLI lo reemplaza. |
| `combined_footings[]` | lista | Opcional (D-153): pares de columnas en zapata combinada, una por par: `id`, `principal_direction`, `combined_design` (el bloque del [diseño de la combinada](#diseño-de-la-zapata-combinada-diseno_combinadajson-comando-design-combined-d-107), con los mismos `fc_options` que `design`) y las dos `columns` (`id`, `cx`, `cy`, `x`, `y` en ejes globales, `location` opcional y `loads`). Lo arma el importador desde `combined_pairs` de la plantilla ([ETABS](etabs.md)). |
| `design.combined_typologies` | - | Opcional (D-157): número de zapatas combinadas tipo para los pares de `combined_footings`. Sin él, una combinada por par (D-153). |

**Con zapatas combinadas (D-153).** Cada par se diseña con el diseño de la combinada en todos los f'c, y el diseño por
tipologías elige el f'c de menor costo total (aisladas más combinadas): un solo f'c para toda la cimentación. El
proyecto diseñado lleva `footings` y `combined_footings` (cada combinada con la ubicación de sus columnas), y
`tipologias.json` agrega `combined_footings` (el resumen de cada una en el f'c elegido), `combined_cost` y `total_cost`.
La planta de localización avisa si dos zapatas del mismo nivel se traslapan: el diseño no revisa la interacción entre
zapatas vecinas.

**Tipos de combinadas (`design.combined_typologies` = N, D-157).** Los pares se agrupan en a lo más N zapatas tipo:
- Solo comparten tipo los pares de una misma familia: la misma dirección principal, la misma separación entre columnas
  (a 1 mm, en orden a lo largo de la dirección principal), las mismas secciones y linderos en ese orden y el mismo
  `combined_design`, sin volteo. Si hay más familias que N, es error (antes de diseñar).
- El tipo de un grupo es una combinada diseñada con los casos de todos sus pares (cada caso con su par, `"ZC2: COMB1"`):
  cumple con cualquiera de ellos. Su base se busca en una rejilla cada `plan_step` en X y en Y, entre la menor y la
  mayor de las resultantes de `placement_case` de los pares, y gana la más barata. Un grupo de un solo par es su diseño
  individual.
- En cada familia, los pares en orden de su costo individual se parten en grupos seguidos, y los N tipos se reparten
  entre las familias para el menor costo total (cada par construye una zapata de su tipo).
- Cada combinada del proyecto diseñado lleva la geometría y el refuerzo de su tipo bajo sus columnas, con `typology`
  (`ZCT1`, `ZCT2`, …), que rotula la planta de localización; `tipologias.json` da el tipo de cada una.
- Las búsquedas (cada par y f'c; cada grupo, f'c y posición de la base) se reparten entre los procesos de `--workers`
  sin cambiar el resultado.
| `design.milp_time_limit_s` | s | Límite de tiempo del MILP (por f'c con `milp`; por solución con `milp_iter`; por defecto 120). |
| `design.iter_max` | - | Con `milp_iter`: iteraciones por f'c (por defecto 10). |
| `design.iter_time_limit_s` | s | Con `milp_iter`: tiempo por f'c (por defecto 600). |
| `curve.n` | - | Solo en el ejemplo de la curva costo-N (`curva_*.json`, D-096): los valores de N, como lista o como texto (`"1-6"`, `"2,4,6"`, `"1-4,8"`). Con `curve`, `run` corre la curva en lugar del diseño; `typology-curve --n` lo reemplaza. |
| `typology_alerts` | objeto | Opcional (D-172): las [alertas de tipologías atípicas](#alertas-de-tipologías-atípicas-typology_alerts-d-172). Sin él, no se calculan y ninguna salida cambia. No se declara con `curve`. |

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
| `cost_basis` | texto | De dónde sale el acero del costo (D-127): `cartilla` si el proyecto declara `detailing`, o `estimado (barras rectas, sin ganchos ni traslapos)`. |
| `milp` | objeto | Solo con `milp`: `status` (`optimal`: óptimo certificado en el catálogo; `time_limit`: sin certificar; `infeasible`: sin N tipologías distintas, queda la DP), `dp_cost`, `dp_distinct_count`, `milp_cost`, `candidates`, `seconds` (matriz y solucionador) y `note`. |
| `iterations` | lista | Solo con `milp_iter`: cada iteración del f'c elegido con `number`, `candidates`, `cost`, `status` y `seconds` (también en `by_fc`). |
| `cost_before_reassignment` | moneda | Costo de la partición, antes de reasignar (con `milp`, igual a `cost`). |
| `distinct_count` | - | Tipologías distintas; menor que el número pedido si hay repetidas. |
| `duplicates` | lista | Grupos de tipologías idénticas (mismos f'c, lx, ly, h y mallas): `typologies` (nombres) y `at_limit` (`plan_max` si el paso siguiente de planta lo supera, `h_max` si el de espesor lo supera; vacía si ninguno). |
| `reassigned` | lista | Columnas reasignadas: `column`, `from`, `to` (nombres de tipología) y `saving` (moneda). |
| `by_fc` | lista | Cada f'c evaluado: `fc [MPa]`, `cost` y `distinct_count` (null si no tiene solución, con `failure`); con `milp`, también su bloque `milp`. |
| `typologies` | lista | Por tipología: `name`, dimensiones, mallas, `columns`, `dowels`, concreto, acero y `cost`. |

Si nada cumple dentro de los límites, el comando termina con FAIL y el motivo. `--workers N` fija los procesos en paralelo (por defecto, los núcleos del equipo; `--workers 1`, sin paralelo); no cambia el resultado.
`--profile` escribe además `medicion.json` (la medición E0 de D-074): configuración
(SHA, máquina, procesos), número y tiempo de las tareas `single`, `covers`, `design`, `reassign` (coberturas de la
reasignación) y `matrix` (matriz del MILP) por f'c, tramos cubiertos y rediseñados (la tabla tiene todos los tramos,
n(n+1)/2, porque no depende de N), tiempo del proceso principal entre lotes (`main_s`), una
muestra fija de 500 pares columna–candidato con la extrapolación a la matriz completa de cobertura, y las tipologías
repetidas y columnas reasignables de la solución. No cambia `proyecto.json` ni `tipologias.json`.

Además (D-171), `medicion.json` lleva `design_wall_s` y `stages`: el tiempo de pared y las llamadas de cada etapa del
diseño en el proceso principal (combinadas: diseño de cada par, tipos de los grupos y reparto; aisladas: diseños
individuales, tabla de tramos, catálogo inicial y coberturas de `milp_iter`, costeo de los pares nuevos, matriz de
costos, MILP, refinado y reasignación; una etapa anidada cuenta también dentro de la que la llama). Con pares
(`combined_footings`), el diseño es el mismo de siempre, con las combinadas, y solo se miden las etapas; sin ellos, se
agrega el detalle por tarea de arriba.

`structurelab-rc run <ejemplo> --profile` (D-171) escribe `medicion.json` en la carpeta de salida de cada ejemplo: el
total (`total_s`) y el tiempo de cada etapa de la corrida completa (importación de ETABS, las del diseño, verificación,
despiece y modelo de dibujo, figuras, dibujo SVG y DXF, memoria TXT y PDF, `.dli`), sin cambiar ninguna salida.

### Alertas de tipologías atípicas (`typology_alerts`, D-172)

Métricas sobre el resultado del diseño por tipologías para alertar al analista. Solo leen el resultado: no cambian
`proyecto.json`, `tipologias.json`, `resultado.json`, la cartilla ni el dibujo, y no vuelven a diseñar. La solución la
decide el analista en el proyecto: declarar las columnas en zapata combinada (`combined_pairs`, D-153) o quitarlas del
diseño por tipologías (`exclude_unique_names`, D-111) y tratarlas aparte. Todos los campos son obligatorios:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `fa_threshold` | - | Umbral del factor de amplificación FA = A(P, M)/A(P, 0) (> 1). |
| `eccentricity_threshold` | - | Umbral de e/B en cada dirección (B/6 = 0.1667). |
| `min_relative_p` | - | P_min/P_max de servicio por debajo del cual la carga axial es baja. |
| `tukey_k` | - | k del límite de Tukey Q3 + k·IQR. |
| `z_threshold` | - | Umbral del z robusto (x − mediana)/(1.4826·MAD). |
| `small_typology_max_columns` | - | Columnas, como máximo, de una tipología atípica pequeña. |
| `min_typologies_for_statistics` | - | Tipologías mínimas para calcular la estadística (≥ 2). |
| `pareto_fraction` | - | Fracción de las columnas que más consumen, para la concentración (0 a 1). |

- **Por columna**, con la zapata de su diseño individual (el que la búsqueda ya calculó):
  - e/B = |ex|/lx y |ey|/ly máximos de los casos de servicio, con su caso, y la menor fracción en contacto (la misma
    revisión del suelo);
  - FA: el área de la planta por suelo con sus casos sobre la de los mismos casos con Mx = My = 0 (Vx y Vy se
    conservan), en el espesor del diseño individual. La planta por suelo es la primera de la búsqueda que cumple
    presión, contacto, deslizamiento, volcamiento y equilibrio, sin diseñar mallas;
  - es candidata si FA ≥ `fa_threshold`, si e/B > `eccentricity_threshold` en alguna dirección, si un caso de servicio
    no tiene equilibrio con el suelo, si P ≤ 0 (levantamiento) o si P_min < `min_relative_p`·P_max en los casos de
    servicio.
- **Por tipología aislada** (los tipos de combinadas no entran):
  - área y volumen de una zapata, columnas, costo y candidatas;
  - atípica por área o por volumen si supera el límite de Tukey (cuartiles inclusivos) o el umbral del z robusto. Con
    menos tipologías que `min_typologies_for_statistics`, ninguno se calcula; con MAD = 0, el z no se define. La
    memoria dice por qué;
  - pequeña: atípica y con ≤ `small_typology_max_columns` columnas;
  - sobrecosto por agrupación: su costo menos la suma de los diseños individuales de sus columnas;
  - señalada: atípica y con al menos una candidata.
- **Concentración:** la parte del concreto y del costo de las aisladas que consume la fracción `pareto_fraction` de las
  columnas que más consumen (hacia arriba, al menos una), con el costo de cada columna en su tipología.

Salidas, en la carpeta de salida: `tipologias_estadistica.csv` (una fila por tipología), `alertas_columnas.csv` (una
fila por columna candidata: columna, nudo de ETABS, tipología, P de servicio, FA, e/B con su caso, contacto y motivos),
`alertas_tipologias.json` (los mismos datos con los parámetros, la estadística y la concentración) y, con `run`, una
sección al final de la memoria TXT y PDF con los parámetros, el resumen, las tipologías señaladas y las candidatas. Una
corrida sin la sección borra las alertas que hubiera dejado una anterior en la misma carpeta.

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

**Con zapatas combinadas (D-165).** Los pares se declaran como en el diseño por tipologías: en el proyecto,
`combined_footings`, y desde ETABS, `combined_pairs`. Las demás columnas son las aisladas.
- N es el número de tipologías de las **aisladas** (decisión del usuario), entre 1 y el número de columnas aisladas.
- Las combinadas se diseñan una sola vez, con sus pares y su `combined_typologies`, porque no dependen de N. Su costo,
  constante en cada f'c, entra en la elección del f'c de cada punto y en el ahorro.
- `resultado.json` agrega `combined` (`pairs` y `types`) y, en cada punto, `isolated_cost` y `combined_cost`; `cost` es
  el de toda la cimentación. `curva.csv` agrega las columnas `costo_aisladas` y `costo_combinadas`, y la memoria, las
  columnas "Aisladas" y "Combinadas".
- Una plantilla de diseño de ETABS con el bloque `curve` (`curva_*_etabs.json`) corre la curva desde los Excel: `run`
  importa la plantilla (deja `diseno.json`) y corre la curva.

## Diseño de la zapata combinada (`diseno_combinada.json`, comando `design-combined`, D-107)

Diseña una zapata combinada de dos o más columnas alineadas (D-163), rectangular, en T invertida, trapezoidal o escalonada (`shapes`, D-169): ubica la base, propone largo, ancho, espesor, f'c y todo el
refuerzo, y elige la solución de menor costo que aprueba la verificación de la combinada. `concrete` no declara `fc`:
f'c es una variable del diseño. `soil` es igual que en la
verificación. Las columnas deben tener los mismos casos de carga, con al menos un caso de servicio sin sismo y casos
mayorados.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `principal_direction` | texto | `x` (por defecto) o `y`: eje global en que va la viga que une las columnas (D-094). |
| `quantity` | - | Obligatorio (D-159): las veces que se construye la combinada; pasa al proyecto diseñado. |
| `columns[]` | lista | Dos o más columnas (D-163): `id`, `cx` y `cy` (mm, sección en ejes globales), `x` e `y` (mm, eje de la columna en ejes globales con **cualquier origen**: solo cuenta la posición de las columnas entre sí; el diseño ubica la base y el proyecto diseñado da las columnas respecto al centro de la base), `property_lines` (opcional, linderos, ver abajo) y `loads` (casos de carga, iguales a los de una zapata). |
| `columns[].property_lines` | mm | Opcional (D-154): los linderos (medianería) de la columna, `{"-x", "+x", "-y", "+y"}` en ejes globales; cada valor (≥ 0) es el voladizo máximo de la base más allá de la cara de esa columna en ese lado (0: la cara al ras del lindero). Un lado sin declarar no limita; si varias columnas declaran un lado, rige el más restrictivo, y el lindero debe dejar cubrir todas las columnas. Solo en el diseño: en la verificación los linderos los controlan las dimensiones de la zapata y la posición de las columnas. |
| `combined_design.fc_options`, `combined_design.prices` | MPa, moneda | Como en el diseño por tipologías: f'c comerciales con su precio por m³ y precio del acero por kg. |
| `combined_design.plan_step`, `combined_design.plan_max` | mm | Paso de las dimensiones en planta y máximo del largo y del ancho. |
| `combined_design.h_min`, `combined_design.h_step`, `combined_design.h_max` | mm | Espesor mínimo, paso y máximo. |
| `combined_design.cover`, `combined_design.fill_height`, `combined_design.pedestal_height` | mm | Recubrimiento, relleno y pedestal. |
| `combined_design.surcharge_dead_kNm2`, `combined_design.surcharge_live_kNm2` | kN/m² | Sobrecargas superimpuestas. |
| `combined_design.bars`, `combined_design.spacing_step` | -, mm | Barras permitidas para todo el refuerzo y paso de separación. |
| `combined_design.ends` | objeto | Cómo terminan las barras que se diseñan (D-134): `bottom` (malla inferior, band y capa inferior de la viga de la T), `top` (barras superiores, band superior y capa superior de la viga), `dowels` (pie de los pasadores) y `skin` (piel), cada uno `straight`, `hook90` o `hook180` (D-161); y `stirrups` (`hook90`, `hook135` o `hook180`), obligatorio con `stirrup_bars`. |
| `combined_design.dowel_bars` | - | Barras permitidas para los pasadores. |
| `combined_design.min_steel_exception` | sí/no | Obligatorio (D-123): lo mismo para la zapata que se diseña; el diseño parte del As,min con o sin la excepción y lo escribe en `proyecto.json`. |
| `combined_design.stirrup_bars` | - | Opcional (D-110): barras permitidas para estribos cerrados de la viga larga, por ejemplo `["#3", "#4"]`. Con ellas, el cortante (y en la T, la torsión del alma, con Aℓ en la piel) pueden tomarlos estribos en lugar de un espesor mayor; gana lo más barato. Sin ellas no se proponen estribos. En la combinada rectangular la torsión es de placa (D-118): la toman las barras x e y. |
| `combined_design.shapes` | lista | Las formas permitidas (D-169), por defecto `["rectangular"]`: `rectangular`, `inverted_t` (D-113: con la T, `h_min`, `h_step` y `h_max` son los del espesor de la zarpa), `trapezoid` y `stepped` (planta en T o L, o en I, D-164), e `inverted_t_trapezoid` e `inverted_t_stepped` (la T invertida con esas plantas, D-170). Con varias, el diseño busca cada una y se queda con la de menor costo; sin solución, da el motivo de cada forma. Reemplaza al campo `shape` anterior, que ahora se rechaza con un mensaje. En el diseño por tipologías y en la curva, cada par puede cambiarlo en su `design`. |
| `combined_design.web_margin`, `combined_design.web_step`, `combined_design.web_max` | mm | Solo con una forma con alma (`inverted_t`, `inverted_t_trapezoid`, `inverted_t_stepped`): el alma parte de la columna más ancha más `web_margin` a cada lado y crece de a `web_step` (respecto a la resultante transversal en la T rectangular y a la línea de las columnas en la no rectangular, D-170). El alma crece hasta `web_max`, obligatorio con la T (D-136). |
| `combined_design.beam_h_min`, `combined_design.beam_h_step`, `combined_design.beam_h_max` | mm | Solo con una forma con alma: alto total de la viga; `beam_h_min` debe superar `h_min`. |
| `combined_design.placement_case` | texto | Opcional (D-108): el caso de servicio sin sismo cuya resultante ubica la base, por ejemplo `"D+L"`. Debe existir en todas las columnas, ser de servicio y no tener sismo. Sin él, se usa el de servicio sin sismo de mayor carga total. |

Búsqueda (cada solución la aprueba `combined_footing_checks`; el diseño no tiene fórmulas propias):

1. **Ubicación:** el centroide de la base va sobre la resultante de las fuerzas de las columnas en el caso
   `placement_case` (o, sin él, en el de servicio sin sismo de mayor carga), con los momentos y los cortantes llevados a
   la base (h + pedestal): en ese caso la presión queda uniforme. Si un voladizo máximo
   lo impide, la base se corre lo necesario y queda excéntrica.
2. **Largo:** el menor que cubre las columnas, al paso de la planta; luego los mayores (el primero con solución y dos
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
5. **T invertida** (`inverted_t`, D-113): el alto de la viga es la variable de la bisección; para cada alto, la
   zarpa parte de `h_min` y crece si fallan las aletas (cortante, deformación unitaria, concreto simple o altura
   mínima) y el alma parte de la mínima y crece si fallan las dimensiones de la sección. El refuerzo de la viga va en
   sus capas (D-106): la superior por dentro de los estribos y la inferior en el alma por dentro del estribo y, si el ala
   cuenta, sobre la zarpa hasta el ancho cubierto; las barras x de la zarpa van fuera de ese ancho y las y son las de las
   aletas. Si la luz libre entre columnas sobre el alto es ≤ 4 (ACI 9.9.1.1, NSR-10 C.11.7.1), la propuesta se declara
   `deep_beam` y se revisa con los criterios de D-089, sin puntal-tensor (D-109). La solución pasa también la
   validación de entrada del proyecto.
6. **Trapezoidal y escalonada** (`trapezoid`, `stepped`, D-169): el largo es el menor que cubre las columnas (y los
   mayores, como en la rectangular), dentro de los linderos. Los anchos ponen el centroide de la planta en la
   resultante a lo largo, con el área del ancho medio: el trapecio con A = L·(B1 + B2)/2 y x̄ = L·(B1 + 2B2)/(3·(B1 +
   B2)); la T o L con un límite s entre dos tramos (A = b1·s + b2·(L − s), A·x̄ = b1·s²/2 + b2·(L − s)·(L + s)/2); la I
   con dos límites, el tramo central del ancho que cubre las columnas y los extremos de las mismas dos condiciones.
   Cada ancho cubre las columnas y va al paso de la planta, hasta `plan_max`. La planta es simétrica respecto a la
   resultante transversal y se corre lo mínimo para quedar dentro de los linderos; si aun así cruza uno, ese lado queda
   recto en él. El ancho medio crece de a un paso hasta que cumple la revisión geotécnica y el refuerzo. La escalonada
   prueba la T o L con el límite al 25, 50 y 75 % de la luz libre entre las columnas extremas y la I con los límites al
   20 y 35 % desde cada una (al paso de la planta), y se queda con la de menor costo. El refuerzo sigue el punto 4 sobre
   la planta (D-164). El proyecto diseñado declara la planta en `plan`, con t = 0 en la resultante transversal.
7. **T invertida trapezoidal y escalonada** (`inverted_t_trapezoid`, `inverted_t_stepped`, D-170): la búsqueda del
   punto 5 (alto de la viga, zarpa y alma) con la planta del punto 6 en cada zarpa y alma. El alma va sobre la línea de
   las columnas (`beam.axis` en el proyecto diseñado), con el ancho mínimo que las cubre más `web_margin` a cada lado;
   ningún ancho de la planta baja del alma más el recubrimiento a cada lado, y la planta que no contiene el alma en todo
   su largo se descarta (D-167). La verificación es la de la T no rectangular (D-167: peso del alma excéntrico, aletas
   hasta los bordes locales, ala efectiva con el ancho local).
8. **f'c:** se repite para cada f'c de la lista y gana el de menor costo. Si nada cumple, termina con FAIL y el motivo de
   cada f'c, sin ampliar los límites.

Salida: `proyecto.json` (un proyecto de verificación con la zapata `ZC1` en ejes globales, con las posiciones de las
columnas respecto al centroide de la base; lo verifica `run`, `verify` o `report`) y `resumen.json`:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `fc [MPa]` | MPa | f'c elegido. |
| `shape` | texto | La forma elegida entre `shapes` (D-169). |
| `plan` | objeto | Solo en la trapezoidal o la escalonada: la planta diseñada, como en `plan` de la verificación. |
| `length [mm]`, `width [mm]`, `h [mm]` | mm | Largo (dirección principal), ancho (en la planta, el de su caja) y espesor (el de la zarpa en la T). |
| `web [mm]`, `beam height [mm]`, `deep_beam` | mm, -, - | Solo en la T: ancho del alma, alto total de la viga y si se declaró de gran altura. |
| `base_center [mm]` | mm | Centroide de la base en los ejes globales de las columnas de entrada. |
| `placement_case` | texto | El caso que ubicó la base; la descripción de `proyecto.json` (y la memoria) dice además si se declaró o se eligió por la regla. |
| `reinforcement` | objeto | Refuerzo en ejes de la viga: `bottom_x`, `bottom_y`, `top_x`, `top_y`, `skin`, `stirrups` (null si no hay), `bands`, `band_tops` (band superior, null si no hace falta, D-119) y `dowels` por columna. En la T: `top_x` y `bottom_x` son las capas superior e inferior de la viga (separación), `mat_x` las barras x de la zarpa y `bottom_y` las de las aletas. |
| `concrete [m3]`, `steel [kg]`, `cost` | m³, kg, moneda | Cantidades y costo: con `detailing`, el acero de la cartilla (ganchos, empalmes por la longitud comercial, longitudes redondeadas); sin él, barras rectas de borde a borde menos el recubrimiento y pasadores hasta la malla inferior (D-127). |
| `cost_basis` | texto | `cartilla` o `estimado (barras rectas, sin ganchos ni traslapos)` (D-127). |
| `by_fc` | lista | Cada f'c: `cost`, `shape`, dimensiones, o `cost` null y `failure`. |

`--workers N` reparte los f'c entre procesos (por defecto, los núcleos del equipo); no cambia el resultado. `run`
reconoce el ejemplo por el bloque `combined_design`, diseña y genera la memoria de verificación de la zapata diseñada.

**Linderos (D-154).** El largo se centra en la resultante y el ancho en la resultante transversal; si un borde pasa un
lindero, la base se corre hacia dentro hasta él, y cuando el diseño pide más ancho (suelo o desarrollo transversal), crece
solo hacia el lado libre. Con linderos en los dos lados de una dirección, el tamaño no pasa de la distancia entre ellos.
Si un lado está al ras de su lindero, el ancho solo crece por desarrollo mientras el voladizo libre sea menor que el del
lindero (después crecer no ayuda: lo que falla es el lado del lindero). La base excéntrica la revisan la presión, el
contacto y las franjas como siempre. Junto a un lindero cercano conviene declarar las barras con gancho (`ends`): el
desarrollo usa entonces ℓdh (D-134). La descripción del proyecto diseñado y `resumen.json`
(`property_line_gaps [mm]`) dan la distancia de cada borde a su lindero.


## Despiece (`detailing`, D-125)

Bloque opcional del proyecto de verificación (y de las plantillas de ETABS de zapatas, que lo pasan al proyecto). Sin él
no se despieza.

En los proyectos de diseño (por tipologías y de la combinada o la T, y en sus plantillas de ETABS), `detailing` y
`drawing` también son opcionales (D-127):

- **Costo:** con `detailing`, el acero del costo sale de la cartilla de cada candidata. En la combinada y la T, con
  ella se comparan todas las candidatas de la búsqueda. En las tipologías, con ella se arma la tabla con que se agrupan
  las columnas y se calcula el costo de cada tipología; la malla dentro de cada tamaño de zapata se sigue eligiendo con
  el acero estimado. Sin `detailing`, el costo es el estimado de barras rectas, como antes.
- **Salida:** el proyecto diseñado lleva los dos bloques, así que `run` genera su cartilla, sus planos y su memoria.
- **Base del costo:** la descripción del proyecto diseñado y los resúmenes (`cost_basis`) dicen de dónde sale el
  acero.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `detailing.stock_length_mm` | mm | Longitud comercial de las barras: las más largas se parten en tramos con empalme por traslapo. |

Con el bloque, `report` y `run` agregan a cada zapata su cartilla (`detailing` en `resultado.json`), escriben
`cartilla.csv` (separado por punto y coma) y `<caso>.dli` (la cartilla en el formato de DL-NET para el pedido de acero,
si hay plantilla; ver [dlnet.md](dlnet.md), D-133), y la memoria lleva el capítulo "Despiece y cantidades":

- **Barras:** las mismas filas que revisa la verificación; las mallas de borde a borde menos el recubrimiento, con gancho
  el gancho que declara cada grupo en su `end` (D-134). En la combinada, el band y el band superior de cada columna,
  las barras superiores (top.y fuera de las zonas de band superior), la piel y los estribos; en la T, las capas de la
  viga, sus estribos, la malla de la zarpa (las barras x fuera del ancho que cubre la capa inferior de la viga) y la malla
  superior de la zarpa. Pasadores rectos hasta la malla inferior con gancho de 90° al pie, el pedestal y el empalme a
  compresión del propio pasador. Estribos cerrados con ganchos de 135°; con más de dos ramas, estribos de dos ramas
  anidados.
- **Ganchos, doblados y empalmes del perfil** (ACI 25.3, 25.5.2.1 y 25.5.5.1; NSR-10 C.7.1, C.7.2, C.12.15 y C.12.16):
  empalme clase A si As provisto ≥ 2 As requerido por análisis y se empalma la mitad o menos del acero; si no, clase
  B. El As requerido, sin el mínimo, sale del mayor momento del grupo de barras en todos los casos, el de su
  verificación (D-129):
  - en la aislada, las caras de la columna;
  - en la combinada, la viga larga para las barras x, la franja de cada columna para su band y su band superior, y
    |mxy| por metro para las barras y fuera de las franjas;
  - en la T, la viga para sus capas y el voladizo para las aletas.

  La nota de la cartilla dice la clase y la razón ("empalme clase A (As/As req = 2.62)"). Las barras sin demanda por
  análisis (la malla x de la zarpa de la T fuera del ala, la piel) y las zapatas sin casos mayorados en equilibrio
  quedan en clase B ("sin As requerido por analisis en la zona del empalme").
- **Longitudes (convención de DL-NET, D-147):** la longitud total (de corte) de una barra es su tramo horizontal
  exterior A, redondeado hacia arriba a 1 cm, más la longitud de cada gancho, redondeada hacia arriba a 50 mm, con D el
  diámetro interior de doblado del perfil:
  - 90°: L = extensión (12db) + π·(D + 0.5·db)/8;
  - 180°: U = extensión (4db, no menos de 65 mm) + 0.5·π·(D + 0.5·db) − 0.5·(D + 0.5·db).

  El gancho de 135° de una barra se mide por el eje de la barra, con la longitud total a 1 cm. El estribo cerrado se
  mide como DL-NET (D-160): L = 2·(b + h) + 2·g, con b × h exteriores a 1 cm y g (la C de la cartilla y la G del `.dli`)
  = extensión + arco del doblez por el eje − 0.5·(D + 0.5·db), hacia arriba a 10 mm. El peso
  sale de la longitud total. Los empalmes de barras vecinas se escalonan: la mitad empieza con medio tramo
  comercial.
- **Forma (D-150):** se nombra por sus extremos con la notación de DL-NET: `recta` sin ganchos; un código por gancho,
  `L` (90°), `U` (180°) o `135` (135°), unidos por un guion en el orden de los extremos (`L`, `L-L`, `U-U`, `L-U`, …); y
  `E`, el estribo cerrado. Así la cartilla, el plano y el `.dli` usan el mismo vocabulario.
- **Marcas:** `<tipo>-01`, `-02`, … Barras iguales (designación, forma, dimensiones y longitud de corte) comparten
  marca y la fila nombra los grupos que reúne.
- **Tipos y unidades (D-159):** el tipo de un elemento es su `typology` o, sin ella, su `id`. Los elementos del mismo tipo
  comparten una cartilla, un despiece en el dibujo y un elemento del `.dli`, si sus cartillas coinciden barra por barra
  (el grupo y la nota no cuentan). Si no coinciden, el elemento va con su propia cartilla, marcada con su `id`, y `run`
  lo avisa.
- **Columnas en los grupos y las notas (D-162):** el grupo y la nota de una marca nombran la columna ("band columna …",
  "band superior columna …", "columna …: empotramiento …"):
  - sin `typology`, con el `id` de la columna (`columns[].id`; desde ETABS, la etiqueta del nudo; con una sola columna,
    el `id` del elemento), por ejemplo "band columna C_Ext";
  - con `typology`, con su posición, "band columna 1", "band superior columna 2", "columna 1: empotramiento …", porque
    la cartilla del tipo vale para todos sus elementos, que tienen otras columnas. En la combinada y la T, la numeración
    sigue el orden a lo largo de la viga, el mismo con que el tipo se traslada a cada par (D-157); en un cabezal, el
    orden declarado.
- **Unidades:** N, las unidades del tipo, es la suma de `quantity` de sus elementos. En el diseño
  por tipologías cada columna o par es una zapata (`quantity` 1), así que N es el número de zapatas del tipo. Se reportan
  la cartilla de una unidad y la de las N unidades: en la memoria, el plano (segunda tabla si N > 1), `cartilla.csv`
  (columnas `unidades`, `cantidad total` y `peso total (kg)`) y `resultado.json` (`total`). En el `.dli`, el tipo entra
  en cada grupo con sus N unidades.

| Campo de `detailing` en el resultado | Unidad | Descripción |
| --- | --- | --- |
| `element`, `members`, `units` | | El tipo (D-159), los elementos que lo construyen y N, sus unidades. |
| `stock_length [mm]` | mm | Longitud comercial declarada. |
| `rows` | lista | Una por marca: `mark`, `group`, `designation`, `shape` (`recta`, `L`, `L-L`, `U-U`, `L-U`, `135`, …, `E`; D-150), `count`, `dimensions [mm]` (A, B, C), `cut_length [mm]`, `mass [kg/m]`, `mass [kg]` y `note` (tramo y traslapo, clase del empalme). |
| `steel_by_designation [kg]`, `steel [kg]` | kg | Acero por designación y total. |
| `concrete [m3]` | m³ | Volumen de concreto de la zapata y los pedestales (en la T, con el alma). |
| `total` | | Las N unidades (D-159): `rows` (`mark`, `count` y `mass [kg]` por N), `steel_by_designation [kg]`, `steel [kg]` y `concrete [m3]`. |

## Dibujo del refuerzo (`drawing`, D-126, D-132, D-150, D-158)

Bloque opcional del proyecto de verificación (y de las plantillas de ETABS de zapatas, que lo pasan al proyecto); requiere
`detailing`, porque el dibujo rotula las marcas de la cartilla. Sin él no se dibuja.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `drawing.scale` | - | Escala de impresión (50 para 1:50). El modelo va a escala 1:1 en mm; los textos miden en papel 6 mm (título del elemento, en el DXF), 3 mm (título de cada vista), 2.5 mm (escala) y 2.0 mm (rótulos, cotas y cartilla), por la escala. |

Con el bloque, `report` y `run` escriben:

- `<caso>_drawing.json` (`<caso>` es el nombre de la carpeta de salida, como en `<caso>.dli`): el modelo de dibujo neutro (capas, y por elemento sus vistas con líneas, polilíneas, círculos,
  textos y cotas en mm, redondeados a 0.1 mm). Entra en la huella.
- `<zapata>_<vista>.svg`: una vista previa por vista, que la memoria incrusta en "Despiece y cantidades" después de la
  cartilla.
- `<caso>.dxf` si está instalado el extra `cad` (`pip install structurelab-rc[cad]`), sobre la plantilla de los planos
  de despiece (`src/structurelab_rc/data/plantilla.dxf`, D-150):
  - en **metros** (`$INSUNITS` = 6), con las capas, los tipos de línea, los estilos de texto, de cota y de multileader
    de la plantilla;
  - todos los tamaños a la escala del bloque `drawing` (D-158): alturas de texto, flechas, puntos de las barras,
    separaciones y trazos se dan en mm de papel y se multiplican por la escala. Lo que trae la plantilla, pensada para
    1:50, se multiplica por escala/50: los estilos de cota, la escala del tipo de línea de cada entidad y la flecha, la
    separación del texto y el quiebre de los `MULTILEADER`;
  - cotas `DIMENSION` con el estilo de la escala (`DIM-50` a 1:50; a otra escala, `DIM-<escala>` igual a `DIM-50`
    escalado, aunque la plantilla traiga uno con ese nombre), que miden con dos decimales (tres si la medida no es
    múltiplo de 1 cm), siempre con el texto derecho;
  - líneas de distribución como cotas sin texto con el estilo `DIM-75` a 1:50 (`DIM-<1.5·escala>` igual a `DIM-75`
    escalado a otra escala) y flechas cerradas, en la capa `PROYECCIONES` (D-158);
  - el contorno del concreto en la capa `ZAPATA` (aislada, combinada, T invertida, trapecio y planta en T o L) o
    `CABEZAL` (cabezales), también en la planta de localización; la capa `0` queda para las columnas y sus arranques
    (D-166);
  - rótulos de las barras en planta como `MTEXT` y en los cortes y alzados como `MULTILEADER`, con cada L como **campo de
    AutoCAD** ligado a la longitud de la polilínea de su barra (`\AcObjProp ... .Length`, dos decimales): si se edita la
    barra en CAD, el rótulo se actualiza (D-158, D-166). En los cortes, las barras paralelas y los pasadores se ligan a
    su polilínea y las barras cortadas (los puntos) a su barra de la planta. El texto guardado es la longitud de la
    cartilla. Las barras empalmadas y los estribos llevan texto fijo, porque su polilínea no mide esa longitud;
  - barras cortadas y marcas de las barras con el bloque `BARRA` en la capa de su diámetro, columnas en planta con
    sombreado sólido; títulos y escala con el estilo `ARIAL`;
  - por elemento, como el plano de despiece de referencia (D-158): arriba las plantas del refuerzo inferior y superior,
    debajo el alzado (o los cortes X-X e Y-Y de la aislada) y el título (`ZC1 h=0.80`) con la escala (`ESC 1:50`); a la
    derecha, la planta de geometría, la cartilla y, en los cabezales, el cuadro de pilotes. Los elementos lado a lado
    dentro de un marco. Los cortes transversales de la combinada y la T van solo en el SVG y la memoria.

  La plantilla se arma con `python tools/make_dxf_template.py <plano de referencia>.dxf
  src/structurelab_rc/data/plantilla.dxf`, que quita todo lo del proyecto (entidades, layouts, historia del archivo) y
  agrega las capas y los colores del modelo de dibujo. `python tools/dxf_inspect.py objetivo.dxf salida.dxf -o carpeta`
  compara dos DXF (capas, estilos, bloques y entidades por capa).

Vistas de cada zapata, como el plano de despiece de referencia (D-158). Las plantas de la combinada van en los ejes
globales del proyecto: con la viga en la Y global (`principal_direction: "y"`), la viga queda vertical; el alzado va a lo
largo de la viga. Las cotas y los rótulos van en metros, como los planos de despiece: dos decimales (tres si no es
múltiplo de 1 cm) y sin el cero inicial (`3.40`, `.15`, `.075`, D-150).

**Consistencia con la cartilla y el `.dli`:** cada barra se dibuja con las dimensiones A, B y C de su fila de la cartilla
(tramo exterior y patas L o U de DL-NET, D-147), en planta y en los cortes (las barras paralelas al corte y los pasadores,
D-166), así que la barra dibujada mide la longitud de corte, la misma del `.dli`, del peso y del costo; las cotas de las
patas son las B y C de la cartilla.

- **Planta de geometría** (`<zapata>_geometria.svg`, D-132): contorno de la base (y el alma en la T), columnas con sus
  ejes, el recubrimiento (línea a trazos y su valor) y cotas en cadena: abajo, de los bordes a las caras de las columnas
  en x; a la izquierda, una cadena en y por cada columna (y otra por el alma); y los totales. Una nota da el espesor, el
  pedestal y, en la T, la viga.
- **Plantas del refuerzo inferior y, si lo hay, superior** (`REFUERZO INFERIOR`, `REFUERZO SUPERIOR`; D-132, D-158):
  - las barras de un grupo se parten en zonas donde el hueco entre dos barras vecinas supera 1.5 separaciones (la malla y
    de la combinada queda a los lados de los band); cada zona se dibuja con una barra representativa (en las barras a lo
    largo de x, la segunda desde el borde alto de la zona; en las de y, la de un cuarto), con sus patas abatidas (abajo
    en las barras a lo largo de x, a la derecha en las de y) y la cota de cada pata;
  - cada barra representativa lleva su rótulo sobre ella (girado en las barras a lo largo de y), en el tramo de la barra
    que no cruza columnas: la cantidad de su zona, la barra, la separación, la longitud de corte de cada marca, de la
    cartilla, y las marcas: `22#6 C/.15 L=6.65 (ZC1-01)`; un grupo empalmado nombra la longitud de cada marca
    (`L=6.00+3.25`), los pasadores dicen `pasadores` y los estribos llevan `E` delante de la barra (D-150);
  - cada zona lleva su línea de distribución entre sus límites (a 0.16 del ancho desde −X en las barras a lo largo de x;
    en el tramo más largo sin columnas en las de y) y la marca de la barra sobre ella (punto relleno en la capa de la
    barra y círculo en `DIM`);
  - las zonas se separan con líneas a trazos grises (ACI 252) en el punto medio entre sus barras, redondeado a 1 cm, y
    se acotan en cadena: a la derecha las de las barras a lo largo de x y abajo las de las barras a lo largo de y;
  - cada columna se acota con su ancho y la distancia de su cara al borde +X (debajo de ella) y con su alto y la
    distancia al borde más cercano en Y (a su derecha); la base, con su ancho arriba y su largo a la izquierda;
  - una barra empalmada se dibuja en sus tramos, desplazados y traslapados, con el rótulo `traslapo <m>`;
  - el refuerzo superficial (piel) va en las caras laterales: se ve en el alzado, no en las plantas.
- **Alzado y cortes:** en la aislada, X-X e Y-Y por el eje de la columna; en la combinada y la T, alzado longitudinal por
  el eje de la viga (con los estribos, sin título, como la referencia) y un corte transversal por cada columna. Cada
  columna arranca con sus dos caras hasta 18 mm de papel y el símbolo de corte. Las barras paralelas al plano llevan las
  patas de su cartilla (hacia adentro) y su cota; las perpendiculares son puntos de tamaño fijo en papel (radio 0.293
  mm, D-150) y cada zona lleva su rótulo con una llamada a una de sus barras, arriba las superiores y abajo las
  inferiores, cada uno a su altura. Cotas: arriba, la cadena de los bordes y las caras de las columnas; abajo, la de las
  zonas y el largo total. Los pasadores se dibujan en dos caras de la columna, a un recubrimiento de ellas
  (esquemático: su disposición no está en la entrada), con el gancho del pie hacia dentro de la columna y su rótulo a la
  derecha. Cada rótulo es un `MULTILEADER` con la flecha cerrada del estilo de la plantilla (0.125 m, como la
  referencia) en la barra señalada; en el SVG, una flecha rellena.
- **Cartilla** como tabla, con el nombre y el croquis de cada forma (cada gancho según su ángulo: 90° pata vertical, 180°
  vuelta completa, 135° pata inclinada) y sus dimensiones A, B y C y la longitud de corte en metros (la memoria y
  `cartilla.csv` siguen en mm).

**Planta de localización (D-130).** Si alguna zapata tiene `location` (en la combinada, todas sus columnas), el dibujo
agrega el elemento `localizacion`, que va en el SVG, el DXF y el modelo de dibujo pero no en la memoria:

- **Una planta por nivel** (`localizacion_<nivel>.svg`), en ejes globales.
  - Cada zapata aislada se dibuja a escala, centrada en su nudo menos el desplazamiento de su columna, con la
    columna, el tipo (`typology`) y el nudo.
  - La combinada se ubica por sus columnas, dos o más: el centroide de la base es el promedio de lo que da cada una. Si
    difieren en más de 10 mm (la mayor distancia entre ellas; la distancia de ETABS no cuadra con la declarada), el
    plano lo avisa. Cada zapata va con su contorno real: el rectángulo, el recortado del cabezal o la planta
    trapezoidal, en T, L o I de la combinada y de la T invertida (D-166, D-170).
  - La separación mínima entre vecinas (`min_clear_spacing`, D-156) se mide entre los contornos reales (D-170): una
    zapata en la muesca de una L se mide hasta el borde de la muesca, no hasta la caja que contiene la L.
- **El cuadro de tipologías** (`localizacion_cuadro_tipologias.svg`): tipo, dimensiones, mallas inferior y superior en
  ejes globales, y cantidad. Las dimensiones son lx × ly × h; en la combinada trapezoidal o escalonada, la forma, el
  largo, el ancho de cada extremo o tramo en orden y h (`trapecio 6.00 x 1.80-3.00 x 0.80`, `T/L 6.00 x 2.40-1.20 x
  0.80`, `I 7.00 x 2.60-1.20-2.60 x 0.80`); en la T invertida, además, `; viga b x h` (h, el de la zarpa).

Capas de la plantilla y una por diámetro de barra (D-150; `drawing/model.py` es la fuente de los colores y una prueba la
compara con la plantilla):

| Capa | Color (ACI) | Grosor (mm) | Contenido |
| --- | --- | --- | --- |
| `0` | 7 | 0.35 | Los pedestales y las columnas; arranque de las columnas en los cortes. |
| `ZAPATA` | 7 | 0.35 | Contorno del concreto de las zapatas aisladas, combinadas y T invertidas, y el alma (D-166). |
| `CABEZAL` | 7 | 0.35 | Contorno del concreto de los cabezales (D-166). |
| `ACH ESTRUCTURA` | 252 | 0.18 | Relleno sólido de las columnas en planta. |
| `Borde_<barra>` | uno por diámetro | 0.35 | Todas las barras de ese diámetro (`Borde_#5`): en planta, paralelas al corte, cortadas, estribos y pasadores. Color por el número de la barra: #4 (32), #5 (170), #6 (14), #7 (190) y #8 (220), los de la plantilla; #3 (4), #9 (130), #10 (150), #11 (50), #14 (6), #18 (3); otra barra, gris (251). |
| `DIM` | 1 | 0.18 | Cotas y rótulos de los cortes con sus líneas de llamada. |
| `PROYECCIONES` | 1, `HIDDEN2` | 0.18 | Líneas de distribución de las barras y recubrimiento. |
| `TEXTO` | 2 | 0.18 | Rótulos de las barras en planta, nombres de las columnas, notas y traslapos. |
| `TXT TITULO` | 161 | 0.35 | Título de cada elemento (DXF). |
| `TXT ESCALA` | 1 | 0.25 | Título de cada vista y escala del elemento. |
| `EJES` | 9 | 0.13 | Ejes de las columnas en la planta de geometría. |
| `CARTILLA` | 7 | 0.18 | Tabla y croquis de la cartilla. |
| `PILOTES` | 34 | 0.25 | Pilotes de los cabezales. |

## Salida

`report` escribe estos archivos en la carpeta de salida:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | Todo el detalle en unidades de presentación (kN, kN·m, kPa, mm, MPa), redondeado a 6 cifras significativas. Es la fuente de la memoria. |
| `memoria.txt` | Memoria de cálculo de cada elemento, una tras otra (D-068): resultado y DCR máximo, capítulos fijos con cada revisión en su ubicación gobernante, índices DCR y notas y limitaciones. |
| `memoria.pdf` | Los mismos bloques en PDF, cada elemento desde una página nueva; requiere el extra `pdf` (`pip install structurelab-rc[pdf]`). |
| `presion_<zapata>.svg` | Planta de cada zapata con la presión del suelo en cada esquina del caso de servicio que gobierna la presión admisible (D-080); el PDF la incrusta en el capítulo de solicitaciones, junto con la tabla de esquinas de todos los casos de servicio. Las presiones vienen en los valores de cada verificación de presión admisible (`p esquina -x-y`, `+x-y`, `+x+y` y `-x+y`, en kPa). |
| `resultado.json` → `close_footings` | Solo si hay pares (D-156): por cada par de zapatas del mismo nivel más cercanas que `min_clear_spacing` o traslapadas, `first`, `second`, `story`, `joints` (los nudos de las dos), `clear [mm]` (negativa si se traslapan), `minimum [mm]` y el aviso en `text`. La separación es entre bordes: en diagonal, la distancia entre las esquinas. |
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
combinadas van en `combined_footings`, sin `foundation_beam_moments`: allí la parte negativa de γf·Msc la revisan las
barras superiores (D-120). Traen la
geometría, las columnas (`columns[]`, cada una con sus cargas), las propiedades calculadas de la base, el armado
(`bottom`, `top`, `stirrups`, `skin`), `deep_beam`, `two_way_warning` (B, ℓn y B/ℓn si B ≥ ℓn, la luz
libre entre las caras de las columnas: puede trabajar en dos direcciones, D-091; null si no), `foundation_beam_shears`
(caso, columna, sección de la franja y `V [kN]`: el cortante de las franjas que excede φVc y debe tomar el refuerzo
transversal de la viga de cimentación, D-103) y las verificaciones, cada
una con su `case`, su `z [mm]` (posición a lo largo de la viga desde su borde negativo, o en la franja desde el borde
negativo de la dirección secundaria, en ejes declarados; nula en las demás) y en `note` la sección, la franja o la
columna. Su memoria separa la dirección principal (flexión con los momentos de Wood-Armer y cortante, D-118; en la T, también
la torsión de vigas del alma, D-088) de la secundaria (franjas o aletas) y trae la planta de presiones con las columnas y la tabla de esfuerzos de punzonamiento en cada esquina.

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
| Zapata: equilibrio con cargas mayoradas | Una por caso mayorado: máx(\|ex\|/lx, \|ey\|/ly) (`demand`) frente a 1/2 (`capacity`); FAIL si la resultante cae fuera de la base o N no es de compresión (sin `demand`). Valores: N, Mx y My en la base, ex, ey, `ex/lx`, `ey/ly` y, con equilibrio, la presión en cada esquina; la nota dice la región de contacto. La memoria la lleva al capítulo 4 y a la tabla de presiones de las combinaciones mayoradas (D-128). | D-054 |
| Flexión malla inferior / superior (barras x o y) | Por caso mayorado: el mayor momento de la carga neta en las caras de la columna frente a φMn de la franja de ancho total. La superior solo aparece si hay momento negativo. | ACI 13.2.6.6 y 13.2.7.1; NSR-10 C.15.4.1 y C.15.4.2 |
| Flexión concreto simple (cara superior, barras x o y) | Momento negativo de la zapata aislada sin malla superior o, con ella, primero el concreto simple (D-140: si alcanza, la malla superior no se exige): Mu frente a φMn = 0.60·0.42λ√f'c·Sm, Sm = b(h − 50)²/6 en todo el ancho. Con ACI special o NSR-10 DES el concreto simple no se permite en cimentaciones: FAIL "requiere malla superior" (D-072). | ACI 14.5.2.1, 14.5.1.7, 14.1.3; NSR-10 C.22.5.1, C.22.4.7, C.22.10.1 |
| Deformación neta de tracción malla … | εt de la malla frente a la mínima del perfil. | ACI 8.3.3.1; NSR-10 C.10.3.5 |
| Acero mínimo malla … | As frente a la cuantía mínima por el área bruta del ancho total. | ACI 8.6.1.1; NSR-10 C.10.5.4 y C.7.12.2.1 |
| Separación máxima malla … | Separación (y la de la franja) frente al máximo del perfil. | ACI 8.7.2.2; NSR-10 C.10.5.4 |
| Separación mínima (…) | Cada refuerzo declarado (cada malla y dirección, la franja central; en la combinada, las barras inferiores y superiores de cada dirección y el band de cada columna): separación libre s − db frente al mínimo (25 mm, db y 4/3·dagg). Sin `concrete.max_aggregate`, INCOMPLETE (D-102). | ACI 25.2.1; NSR-10 C.7.6.1 y C.3.3.2(c) |
| Franja central malla … | Zapata rectangular: As en la franja frente a γs·As. Si entre la franja y el borde no cabe ninguna barra, frente a todo As (reparto uniforme, D-142). | ACI 13.3.3.3; NSR-10 C.15.4.4.2 |
| Altura mínima de la zapata | 150 mm, medidos como pide cada perfil. | ACI 13.3.1.2; NSR-10 C.15.7 |
| Cortante en una dirección (barras x o y) | Por caso mayorado: Vu de la carga neta más allá de la sección a d de cada cara frente a φVc, con la d de esa dirección. | ACI 13.2.6.2(a) y 13.2.7.2; NSR-10 C.15.5 y C.11.2 |
| Punzonamiento | Por caso mayorado: esfuerzo máximo vu = Vu/(b0·d) + γv·Msc·c/Jc en los dos ejes, en el perímetro a d/2 (recortado con la base: αs = 40, 30 o 20), frente a φvc. Valores: Vu, b0, d, αs, γv, vuv, Msc y Jc en cada eje, el centroide del perímetro (xc, yc) y el esfuerzo en cada esquina (`esquina i x`, `esquina i y`, `esquina i v`, D-083). | ACI 22.6.5.2, 22.6.5.3 y 8.4.4.2; NSR-10 C.11.11.2.1 y C.11.11.7 |
| Transferencia de momento por flexión (barras x o y) | Por caso mayorado: γf·\|Msc\| frente a φMn de la malla inferior dentro de bslab = c + 1.5h a cada lado, sin pasar de los bordes de la zapata: a cada lado, el menor entre 1.5h y la distancia de la cara al borde (D-102; si recorta, el valor `bslab sin recortar` da c + 3h); en la combinada, más el band. No se suma al momento de la zapata. | ACI 8.4.2.2 (13.3.3.1); NSR-10 C.11.11.7.1 y C.13.5.3.2 (D-087) |
| Transferencia de momento: parte negativa (barras x o y) | La misma γf·\|Msc\| frente a la malla superior en bslab o, sin ella, al concreto simple si el nivel lo permite. En la zapata aislada siempre CUMPLE: lo que la zapata no resiste lo debe tomar la viga de cimentación (valor `para la viga`, sin razón demanda/capacidad) y queda en `foundation_beam_moments` y en la memoria (D-087). En la combinada la resisten las barras superiores en bslab (top y band superior) o el concreto simple; si no alcanzan, NO CUMPLE (D-120). | Ídem (D-087, D-120) |
| Fuera de la franja central malla … | Zapata rectangular: As fuera de la franja frente a (1 − γs)·As. No se revisa si fuera de la franja no cabe ninguna barra (D-142). | ACI 13.3.3.3(b); NSR-10 C.15.4.4.2 (D-087) |
| Acero mínimo por punzonamiento (barras x o y) | Solo ACI, cuando vuv > φ0.17√f'c: As,min de 8.6.1.2 (con el bslab recortado por los bordes, D-102) frente a las barras de la malla inferior dentro de bslab. | ACI 8.6.1.2 |
| Desarrollo malla … (barras x o y) | Longitud de desarrollo (recta o con gancho) frente a la disponible desde la cara de la columna hasta el extremo de la barra. La superior, solo con momento negativo. | ACI 25.4.2 y 25.4.3; NSR-10 C.12.2 y C.12.5 |
| Pasadores: área mínima | Área de los pasadores frente a 0.005 por el área de la columna. | ACI 16.3.4.1; NSR-10 C.15.8.2.1 |
| Pasadores: anclaje a compresión | ldc frente al espacio hasta la malla inferior. | ACI 25.4.9; NSR-10 C.12.3 |
| Aplastamiento en la zapata | Por caso mayorado: Pu frente a φ·0.85f'c·A1·√(A2/A1) ≤ 2 (A2 del tronco de pirámide 1:2). | ACI 22.8.3.2; NSR-10 C.10.14.1 |
| Pasadores: compresión sobre el aplastamiento | Si Pu > φBn: área de los pasadores frente a (Pu − φBn)/(φ·fy). | ACI 16.3.3.4; NSR-10 C.15.8.1.2(a) |

Si la resultante cae fuera de la base o N no es de compresión, ambas verificaciones del caso son FAIL ("Sin
equilibrio con el suelo"). Sin casos de servicio, la presión admisible sale INCOMPLETE.
