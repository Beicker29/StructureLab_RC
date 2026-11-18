# Formato de cabezales sobre pilotes (D-138)

Un cabezal de una o varias columnas (D-143) sobre un grupo de pilotes declarados por coordenadas, en los dos perfiles: verificación y
diseño ([Diseño](#diseño-d-141)). Unidades de entrada: mm, MPa, kN, kN·m, kN/m² y kN/m³.

## Proyecto

`pile_caps` (lista) junto a `soil` (obligatorio), como en las zapatas: los pesos unitarios y los datos geotécnicos de
los pilotes. Un proyecto no mezcla zapatas y cabezales.

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `soil.unit_weight_fill_kNm3` | kN/m³ | Peso unitario del relleno (el del concreto va en `concrete.unit_weight_kNm3`, D-139). |
| `soil.pile_capacity_compression_kN` | kN | Capacidad admisible del pilote a compresión (cargas de servicio). |
| `soil.pile_capacity_tension_kN`, `pile_capacity_lateral_kN` | kN | Opcionales. Si un caso las necesita y faltan, su revisión queda INCOMPLETO. |
| `soil.seismic_capacity_factor` | – | Aumento de las capacidades en las combinaciones con sismo (≥ 1; 1.0 si no se declara). |
| `soil.group_efficiency` | – | Eficiencia del grupo de pilotes, entre 0 y 1. |
| `soil.max_eccentricity_mm` | mm | Excentricidad máxima de la resultante en las combinaciones de servicio sin sismo (D+L). |

`detailing` y `drawing` son los del proyecto (D-125, D-126): con ellos salen la cartilla, el `.dli`, las vistas y el DXF.

## Cabezal

Tiene los campos de la zapata aislada ([zapatas](zapatas.md)): `id`, `lx`, `ly`, `h`, `cover`, `fill_height`,
`pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2`, `bottom` y `top`; las columnas van en `columns` (D-143). Además:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `cover` | mm | Recubrimiento libre de las caras laterales y la superior. |
| `clipped_corners` | mm | Opcional (D-141): esquinas recortadas, cada una `{corner, along_x, along_y}` con `corner` = `+x+y`, `-x+y`, `-x-y` o `+x-y` y lo que el recorte quita de cada borde. El contorno es el rectángulo menos esos triángulos; la columna y los pilotes deben quedar dentro. |
| `columns[]` | | Una o varias columnas: `id`, `cx`, `cy`, `offset_x`, `offset_y` (mm, respecto al centroide del cabezal), `dowels` y `loads`. Dentro del contorno y sin traslaparse. `pedestal_height` vale para todas. |
| `loads_from` | | Obligatorio: de dónde llegan las cargas, `column` (las de cada columna, `columns[].loads`) o `piles` (las de cada pilote, `piles[].loads`; desde ETABS, el Unique Name de cada pilote y `etabs_station`). Lo demás debe ser coherente con él. |
| `bottom_cover` | mm | Recubrimiento libre de la cara inferior a la malla inferior, mayor que el empotramiento: la malla va sobre la cabeza de los pilotes. |
| `pile.shape` | | `circular` o `square`. |
| `pile.size` | mm | Diámetro o lado. El punzonamiento usa el cuadrado de igual área. |
| `pile.embedment` | mm | Empotramiento del pilote en el cabezal. |
| `piles[]` | | `id`, `x`, `y` (mm, respecto al centroide del cabezal) y, con cargas de los pilotes, `loads`. |
| `mislocation_mm` | mm | Tolerancia de mala ubicación de los pilotes, obligatoria. Con ACI 318-25, menor que 75 mm no cumple (13.4.1.4). |
| `columns[].loads` | | Con `loads_from: column`, las cargas de la columna, como en la zapata aislada; todas las columnas con los mismos casos y factores. Con `loads_from: piles`, opcionales y solo mayoradas (casos de los pilotes): dan la carga de la columna para el aplastamiento, los pasadores y las secciones que la necesitan; si faltan, esas revisiones quedan INCOMPLETO (con una sola columna, su carga sale del equilibrio, D-138). |
| `reactions_include_weight` | | Obligatorio con cargas de los pilotes: si sus reacciones ya incluyen el peso del cabezal, el relleno y las sobrecargas. Si no, se suman repartidos por igual. |

Las cargas llegan de las columnas (`columns[].loads`) o de todos los pilotes (`piles[].loads`), según `loads_from`. Las de un pilote son
su acción sobre el cabezal en la cabeza, en ejes globales: `P_kN` positiva en compresión del pilote, `Vx_kN`, `Vy_kN`
la fuerza horizontal y `Mx_kNm`, `My_kNm` el momento. Los pilotes repiten los mismos casos con los mismos factores.

## Cálculo

- **Reacciones con cargas de las columnas:** el cabezal es rígido y los pilotes, articulados. La resultante (columnas,
  pesos y sobrecargas) y su momento en el plano de la cabeza de los pilotes se reparten como R = N/n ± momentos del
  grupo. El cortante de las columnas se reparte por igual. Si los pilotes están alineados, el momento normal a su eje
  queda INCOMPLETO.
- **Mala ubicación:** el brazo de cada pilote crece con la tolerancia del lado desfavorable, en la flexión y en el
  cortante. Con cargas de las columnas, además, una excentricidad accidental igual a la tolerancia, en la dirección más
  desfavorable para cada pilote, cambia su reacción en ±ΔR, y con ACI la capacidad del pilote sube 10 % (13.4.1.4). Con
  cargas de los pilotes la tolerancia solo cambia los brazos.
- **Revisiones geotécnicas** con los casos de servicio, como las de las zapatas (las capacidades se multiplican por
  `seismic_capacity_factor` en los casos con sismo):
  - presión admisible de cada pilote a compresión (la mayor reacción con ΔR) y a tracción;
  - deslizamiento: la carga lateral de cada pilote frente a su capacidad lateral;
  - capacidad del grupo: la carga vertical total frente a η·n·Qa;
  - sin sismo (D+L), la excentricidad de la resultante de las reacciones respecto al centroide del grupo frente a la
    máxima declarada.
- **Flexión** en las caras de las columnas (con varias, también entre ellas; ver [Varias columnas](#varias-columnas-d-143-d-145)) con las reacciones concentradas en el centro de cada pilote, la acción de su
  cabeza y el peso hacia abajo. As mínimo con la interpretación de la guía CRSI (4.5):
  máx(As, mín(ηbd, 4/3·As), mín(ηbd, ρt·b·h)) en la malla inferior, con η = máx(0.25√f'c, 1.4)/fy; en la superior,
  solo máx(As, mín(ηbd, 4/3·As)), y la retracción ρt·b·h se revisa con las dos mallas sumadas (D-140). No se admite
  concreto simple (ACI 14.1.4, NSR-10 C.22.2.1).
- **Cortante** por secciones con la reacción interpolada entre dpile/2 afuera y dpile/2 adentro (ACI 13.4.6.7, NSR-10
  C.15.5.4): una dirección a d de las caras (ACI 22.5 con λs y, con pilotes a 4 diámetros o menos, el mayor entre ese y
  0.17λ√f'c·bw·d de 13.4.6.8(a); NSR-10 C.11.2) y dos direcciones a d/2 de cada columna. Con
  pilotes dentro de d o d/2, los límites de la guía CRSI en la cara de cada columna (estados límite 4 a 6, constantes
  pasadas a SI con 0.083). Además, el punzonamiento de cada pilote, aislado (P1) o de esquina (P3), el de dos pilotes
  vecinos cuya falla conjunta es más corta (P2: L < π(dp + d)/2, b0 = π(dp + d) + 2L, vc de la norma con
  β = (L + dp)/dp) y el cortante en una dirección en la esquina (P4: b = 2·((Ex + Ey)/√2 + dp/2 + d), d ≤ 330 mm solo
  en b, vc = 0.166λ√f'c), todos con las reacciones mayoradas. Los grupos de 3 o más pilotes conexos (cada uno a
  L < π(dp + d)/2 de otro) punzonan en conjunto con b0 = perímetro de la envolvente convexa de sus centros + π(dp + d),
  si es más corto que el de los pilotes aislados y no alcanza el perímetro crítico de ninguna columna; en cada caso se
  reporta el que gobierna (hasta 16 pilotes; con más, BLOQUEADO).
- **Geometría:** d ≥ 300 mm (ACI 13.4.6.2; NSR-10 C.15.7, sobre el refuerzo inferior). En ACI también el empotramiento
  ≥ 75 mm y el borde ≥ 100 mm (13.4.6.3).
- **Desarrollo, pasadores y aplastamiento:** los de la zapata aislada, por columna.

## Varias columnas (D-143, D-145)

- **Reacciones:** con las cargas de las columnas, la resultante de todas (con su pedestal y el relleno que desplazan) y
  de los pesos se reparte como con una columna; la mala ubicación usa la carga total.
- **Flexión:** en cada dirección, en las caras de cada columna y en secciones cada 50 mm fuera de las columnas, con el
  cuerpo libre del lado que tiene menos columnas (los dos si empatan): las reacciones de los pilotes con su brazo y su
  cabeza, las columnas de ese lado (su fuerza vertical, su momento y su cortante a h/2 + pedestal) y el peso. Así sale
  el momento negativo entre columnas. Sin la carga de una columna de ese lado (cargas de los pilotes), la sección no se
  calcula de ese lado; si no se puede de ninguno, "Flexion: secciones" queda INCOMPLETO.
- **Franja de cada columna (D-145):** con las columnas alineadas a lo largo de X (o de Y), en la otra dirección; si no
  están alineadas, en las dos. Su ancho es el lado de la columna más d/2 a cada lado (recortado con el cabezal). Se
  analiza por secciones dentro de su ancho, con el mismo cuerpo libre de la flexión a todo el ancho: las caras de las
  columnas que tocan la franja y secciones cada 50 mm fuera de ellas, del lado con menos columnas de la franja (los dos
  si empatan). Entran los pilotes con la fracción de 13.4.6.7 según la distancia de su centro al borde de la franja más
  la tolerancia, las columnas que tocan la franja con toda su carga y el peso sobre ella. Se revisan la sección de mayor
  momento positivo (malla inferior) y la de mayor negativo (superior): resistencia y εt con el código de vigas en modo
  cimentación y As mínimo del cabezal en el ancho de la franja; y el cortante a d de las caras de sus columnas con +ΔR y
  el Vc del cabezal. Las revisiones se llaman "Franja de la columna: …" y su nota dice la columna, la dirección de las
  barras y la sección. Con columnas alineadas da los voladizos desde las caras. La franja central γs no aplica con varias
  columnas.
- **Cortante y punzonamiento:** cortante en una dirección a d de las caras de cada columna (sin las secciones que caen en
  otra columna) y límites CRSI por columna, con el mismo criterio de cuerpo libre (D-145); punzonamiento de cada columna y, si los perímetros a d/2 de varias se
  traslapan, del perímetro común (la caja que las contiene), con el mismo criterio de cuerpo libre.
- **Desarrollo, pasadores y aplastamiento:** desarrollo desde la cara de cualquier columna más cercana al borde;
  pasadores y aplastamiento por columna, con su carga.
- **Esquinas recortadas:** con varias columnas se rechazan por ahora (las franjas no usan el contorno recortado, D-145).

## Esquinas recortadas (D-141)

Con `clipped_corners` el cálculo usa el contorno real: el área y el peso (en el centroide del contorno, que entra en el
reparto de las reacciones), el peso más allá de cada sección, el ancho de cada sección (la cuerda del contorno) con las
barras que la cruzan en la flexión de las caras y en el cortante, el perímetro de punzonamiento recortado con el
contorno, la distancia de los pilotes a los bordes y, en cada recorte, el cortante de esquina (P4) en la sección paralela
al recorte a dp/2 + d (d ≤ 330 mm) del pilote más cercano; P3 solo en las esquinas sin recortar. El despiece da barras de
largo variable (de borde a borde del contorno menos el recubrimiento, medido a lo largo de la barra) y el dibujo, el
contorno real. El As mínimo, la separación y la franja central se revisan con las mallas completas.

## Diseño (D-141)

Un proyecto de diseño trae `pile_cap_design` y `caps` en lugar de `pile_caps`; `concrete` va sin `fc` (lo elige el
diseño) y `soil`, `reinforcement_steel`, `detailing` y `drawing` son los del proyecto de verificación. `run` lo detecta
por `pile_cap_design`; también `structurelab-rc design-pile-caps <diseño.json> --output <carpeta>`. Escribe
`proyecto.json` (un proyecto de verificación con los cabezales diseñados, que `run` verifica a continuación con su
memoria, cartilla y DXF) y `resumen.json` (por f'c, los arreglos probados de cada cabezal con su costo o por qué no
tienen solución).

| Campo de `pile_cap_design` | Unidad | Descripción |
| --- | --- | --- |
| `fc_options` | MPa | Resistencias comerciales que se evalúan. Todos los cabezales del proyecto llevan el mismo f'c: gana el de menor costo total. |
| `prices` | | `concrete_per_m3` (por f'c, clave en MPa como texto), `steel_per_kg` y `pile_each` (cada pilote), en la moneda del usuario. |
| `pile` | | `shape`, `size` y `embedment`, como en el cabezal. |
| `pile_spacing` | mm | Separación mínima entre centros de pilotes, L (mayor que el tamaño del pilote). |
| `edge_distance` | mm | Distancia del centro de los pilotes al borde del cabezal, E (mayor que medio pilote). |
| `max_piles` | | Máximo de pilotes por cabezal (30 si no se declara). |
| `h_min`, `h_step`, `h_max` | mm | Espesores que se prueban. |
| `cover`, `bottom_cover`, `fill_height`, `pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2`, `mislocation_mm` | | Como en el cabezal. |
| `bars`, `spacing_step` | | Barras de las mallas y paso de su separación (mm). |
| `ends` | | Extremos de las barras: `bottom`, `top` y `dowels` (D-134). |
| `dowel_bars` | | Barras de los pasadores. |

| Campo de `caps[]` | Descripción |
| --- | --- |
| `id` | Identificador único. |
| `loads_from` | `column`: `loads` de la columna; el diseño elige el número y el arreglo de los pilotes y el cabezal. `piles`: `piles[]` con `id`, `x`, `y` (mm, desde el eje de la columna) y `loads`, y `reactions_include_weight`; el arreglo queda declarado y se diseña solo el cabezal. |
| `column` | `cx`, `cy` (mm). Con cargas de la columna va en el centroide del grupo. El diseño es de una columna (D-141): por eso `column` y no `columns`; el cabezal diseñado sale con `columns` de una columna, `C1`. Los cabezales de varias columnas se verifican (D-143) y su diseño queda para una fase siguiente. |
| `clipped_corners` | Solo con cargas de los pilotes: los recortes declarados (D-141). |

Arreglos que se prueban con cargas de la columna (familias generadas con L y E; las distancias irracionales se redondean
hacia arriba al milímetro): mallas nx × ny, el triángulo de tres pilotes con las dos esquinas superiores recortadas
paralelas a sus lados a E de ellos, mallas con un pilote en el centro de cada celda (a L·√2, cinco, ocho, trece…) y
filas desplazadas (a L·√3/2, de k y k − 1 o todas de k), cada una también girada 90°; no se prueban las de relación de
lados mayor que 2.5 con más de tres pilotes. El cabezal es el rectángulo que encierra los pilotes más E.

La búsqueda empieza en n0 = máx(2, ⌈máx P/(η·fs·Qa)⌉) pilotes con las cargas de servicio y sube hasta `max_piles`; se
para cuando el costo de los pilotes y del concreto mínimo ya no puede ganar. Para cada arreglo, los espesores desde
`h_min`: la malla inferior más liviana que cumple (con la franja central en la dirección corta de los rectangulares) con
sus pasadores, y la superior más liviana que completa el momento negativo y la retracción (D-140). Cada candidato lo
aprueba la verificación completa del cabezal; el costo es concreto, acero (la cartilla con `detailing`, D-127; si no,
barras rectas) y pilotes.

## Plantilla de ETABS

Como la de zapatas ([etabs](etabs.md)), con `pile_caps` y `etabs_files` (`service`, `factored` y `combinations`). Todos
los cabezales de una plantilla toman las cargas de la misma fuente, la que declara `loads_from`:

| Campo | Descripción |
| --- | --- |
| `pile_caps[].columns[]` | Las columnas como en el cabezal, sin `loads`, con `column_unique_name` (obligatorio) y `angle` (eje local 2 respecto a X, grados; 0 por omisión). |
| `pile_caps[].columns[].column_unique_name` | Obligatorio: el Unique Name declarado de cada columna. Con cargas de las columnas, de él se leen sus reacciones en "Joint Reactions" (P = FZ, Vx = −FX, Vy = −FY, Mx = −MX, My = −MY). Con `etabs_files.locations`, la primera columna se busca en esa tabla ("Joint Location", la ubicación de las columnas) para la planta de localización. |
| `pile_caps[].column_station` | Opcional, con cargas de los pilotes (D-143): la estación (m) de la base de las columnas en "Element Forces - Columns"; sus fuerzas mayoradas pasan a `columns[].loads` (P = −P; V y M, las de ETABS en la cara positiva, la del cabezal, sin cambiar el signo). Convención validada por el usuario (D-144). |
| `pile_caps[].etabs_station` | Cargas de los pilotes: la estación (m, como la escribe ETABS) de "Element Forces - Columns" de la que se toman. Debe existir en la tabla para cada pilote. |
| `pile_caps[].piles[].etabs_unique_name` | Unique Name del elemento que modela el pilote. |
| `pile_caps[].piles[].angle` | Ángulo del eje local 2 respecto a X global, en grados (por omisión 0: eje 2 = X, eje 3 = Y). |
| `etabs_files.locations` | Opcional: la tabla "Point Object Connectivity" de ETABS (`Joint Location.xlsx`) con la ubicación de las columnas. Cada cabezal recibe la ubicación de su columna y sale en la planta de localización (D-130). |

Ejes locales de ETABS (D-144): el eje 2 paralelo a X global y con su sentido, el 3 paralelo a Y y con su sentido, y el 1
= 2 × 3, hacia arriba; si un elemento tiene los ejes rotados, se declara su `angle`. V2 y V3 son los cortantes en la
dirección y el sentido de los ejes 2 y 3; M2 y M3, los momentos alrededor de ellos (regla de la mano derecha). ETABS
reporta las fuerzas internas sobre la cara positiva del corte (la del tramo de abajo): en la cabeza de un pilote, la acción
del cabezal sobre el pilote; en la base de una columna, la de la columna sobre el cabezal.

De los pilotes se leen `P`, `V2`, `V3`, `M2` y `M3` (kN, kN-m) y se toma la acción opuesta sobre el cabezal:
P = −P, Vx = −V2·cos θ + V3·sen θ, Vy = −V2·sen θ − V3·cos θ, Mx = −M2·cos θ + M3·sen θ y My = −M2·sen θ − M3·cos θ
(con θ = 0: Vx = −V2, Vy = −V3, Mx = −M2, My = −M3). De las columnas (`column_station`), la misma sin cambiar el signo
de V y M. Las filas Max y Min son dos casos.

### Plantilla de diseño de ETABS (D-141)

El proyecto de diseño con `etabs_files` y, en cada elemento de `caps`, `column_unique_name` (obligatorio, en el cabezal y
no en `columns`, porque el diseño es de una columna). Con
`loads_from: column` las cargas salen de las reacciones de esa columna en "Joint Reactions" y el cabezal no lleva
pilotes (los elige el diseño). Con `loads_from: piles` cada pilote lleva `etabs_unique_name` (y `angle`, si aplica) y el
cabezal `etabs_station`, como en la plantilla de verificación; sus coordenadas son desde el eje de la columna. Todos los
cabezales toman las cargas de la misma fuente. Con `etabs_files.locations`, la ubicación de la columna pasa al cabezal
diseñado (planta de localización, D-130). `run` importa (`diseno.json`), diseña (`proyecto.json`, `resumen.json`) y
verifica.

## Salida

`pile_caps[]` en `resultado.json`: geometría (con `columns`, sin sus cargas), pilote y pilotes, pesos, armado, cargas, la reacción de cada pilote en
cada caso (`reactions`, con ΔR) y las verificaciones con su caso.
