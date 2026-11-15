# Formato de cabezales sobre pilotes (D-138)

Un cabezal de una columna sobre un grupo de pilotes declarados por coordenadas, en los dos perfiles. La v1 es solo
verificación. Unidades de entrada: mm, MPa, kN, kN·m, kN/m² y kN/m³.

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
`pedestal_height`, `surcharge_dead_kNm2`, `surcharge_live_kNm2`, `column` (con `dowels`), `bottom` y `top`. Además:

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `cover` | mm | Recubrimiento libre de las caras laterales y la superior. |
| `loads_from` | | Obligatorio: de dónde llegan las cargas, `column` (las de la columna, `loads`) o `piles` (las de cada pilote, `piles[].loads`; desde ETABS, el Unique Name de cada pilote y `etabs_station`). Lo demás debe ser coherente con él. |
| `bottom_cover` | mm | Recubrimiento libre de la cara inferior a la malla inferior, mayor que el empotramiento: la malla va sobre la cabeza de los pilotes. |
| `pile.shape` | | `circular` o `square`. |
| `pile.size` | mm | Diámetro o lado. El punzonamiento usa el cuadrado de igual área. |
| `pile.embedment` | mm | Empotramiento del pilote en el cabezal. |
| `piles[]` | | `id`, `x`, `y` (mm, respecto al centroide del cabezal) y, con cargas de los pilotes, `loads`. |
| `mislocation_mm` | mm | Tolerancia de mala ubicación de los pilotes, obligatoria. Con ACI 318-25, menor que 75 mm no cumple (13.4.1.4). |
| `loads` | | Cargas de la columna, como en la zapata aislada. |
| `reactions_include_weight` | | Obligatorio con cargas de los pilotes: si sus reacciones ya incluyen el peso del cabezal, el relleno y las sobrecargas. Si no, se suman repartidos por igual. |

Las cargas llegan de la columna (`loads`) o de todos los pilotes (`piles[].loads`), nunca de ambos. Las de un pilote son
su acción sobre el cabezal en la cabeza, en ejes globales: `P_kN` positiva en compresión del pilote, `Vx_kN`, `Vy_kN`
la fuerza horizontal y `Mx_kNm`, `My_kNm` el momento. Los pilotes repiten los mismos casos con los mismos factores.

## Cálculo

- **Reacciones con cargas de la columna:** el cabezal es rígido y los pilotes, articulados. La resultante (columna,
  pesos y sobrecargas) y su momento en el plano de la cabeza de los pilotes se reparten como R = N/n ± momentos del
  grupo. El cortante de la columna se reparte por igual. Si los pilotes están alineados, el momento normal a su eje
  queda INCOMPLETO.
- **Mala ubicación:** el brazo de cada pilote crece con la tolerancia del lado desfavorable, en la flexión y en el
  cortante. Con cargas de la columna, además, una excentricidad accidental igual a la tolerancia, en la dirección más
  desfavorable para cada pilote, cambia su reacción en ±ΔR, y con ACI la capacidad del pilote sube 10 % (13.4.1.4). Con
  cargas de los pilotes la tolerancia solo cambia los brazos.
- **Revisiones geotécnicas** con los casos de servicio, como las de las zapatas (las capacidades se multiplican por
  `seismic_capacity_factor` en los casos con sismo):
  - presión admisible de cada pilote a compresión (la mayor reacción con ΔR) y a tracción;
  - deslizamiento: la carga lateral de cada pilote frente a su capacidad lateral;
  - capacidad del grupo: la carga vertical total frente a η·n·Qa;
  - sin sismo (D+L), la excentricidad de la resultante de las reacciones respecto al centroide del grupo frente a la
    máxima declarada.
- **Flexión** en las caras de la columna con las reacciones concentradas en el centro de cada pilote, la acción de su
  cabeza y el peso hacia abajo. As mínimo con la interpretación de la guía CRSI (4.5):
  máx(As, mín(ηbd, 4/3·As), mín(ηbd, ρt·b·h)) en la malla inferior, con η = máx(0.25√f'c, 1.4)/fy; en la superior,
  solo máx(As, mín(ηbd, 4/3·As)), y la retracción ρt·b·h se revisa con las dos mallas sumadas (D-140). No se admite
  concreto simple (ACI 14.1.4, NSR-10 C.22.2.1).
- **Cortante** por secciones con la reacción interpolada entre dpile/2 afuera y dpile/2 adentro (ACI 13.4.6.7, NSR-10
  C.15.5.4): una dirección a d de las caras (ACI 22.5 con λs y, con pilotes a 4 diámetros o menos, el mayor entre ese y
  0.17λ√f'c·bw·d de 13.4.6.8(a); NSR-10 C.11.2) y dos direcciones a d/2 de la columna. Con
  pilotes dentro de d o d/2, los límites de la guía CRSI en la cara de la columna (estados límite 4 a 6, constantes
  pasadas a SI con 0.083). Además, el punzonamiento de cada pilote, aislado (P1) o de esquina (P3), el de dos pilotes
  vecinos cuya falla conjunta es más corta (P2: L < π(dp + d)/2, b0 = π(dp + d) + 2L, vc de la norma con
  β = (L + dp)/dp) y el cortante en una dirección en la esquina (P4: b = 2·((Ex + Ey)/√2 + dp/2 + d), d ≤ 330 mm solo
  en b, vc = 0.166λ√f'c), todos con las reacciones mayoradas.
- **Geometría:** d ≥ 300 mm (ACI 13.4.6.2; NSR-10 C.15.7, sobre el refuerzo inferior). En ACI también el empotramiento
  ≥ 75 mm y el borde ≥ 100 mm (13.4.6.3).
- **Desarrollo, pasadores y aplastamiento:** los de la zapata aislada.

## Plantilla de ETABS

Como la de zapatas ([etabs](etabs.md)), con `pile_caps` y `etabs_files` (`service`, `factored` y `combinations`). Todos
los cabezales de una plantilla toman las cargas de la misma fuente, la que declara `loads_from`:

| Campo | Descripción |
| --- | --- |
| `pile_caps[].column_unique_name` | Obligatorio: el Unique Name declarado de la columna del cabezal. Con cargas de la columna, de él se leen sus reacciones en "Joint Reactions" (P = FZ, Vx = −FX, Vy = −FY, Mx = −MX, My = −MY). Con `etabs_files.locations` se busca en esa tabla ("Joint Location", la ubicación de las columnas) para la planta de localización. |
| `pile_caps[].etabs_station` | Cargas de los pilotes: la estación (m, como la escribe ETABS) de "Element Forces - Columns" de la que se toman. Debe existir en la tabla para cada pilote. |
| `pile_caps[].piles[].etabs_unique_name` | Unique Name del elemento que modela el pilote. |
| `pile_caps[].piles[].angle` | Ángulo del eje local 2 respecto a X global, en grados (por omisión 0: eje 2 = X, eje 3 = Y). |
| `etabs_files.locations` | Opcional: la tabla "Point Object Connectivity" de ETABS (`Joint Location.xlsx`) con la ubicación de las columnas. Cada cabezal recibe la ubicación de su columna y sale en la planta de localización (D-130). |

De los pilotes se leen `P`, `V2`, `V3`, `M2` y `M3` (kN, kN-m) y se toma la acción opuesta sobre el cabezal:
P = −P, Vx = −V2·cos θ + V3·sen θ, Vy = −V2·sen θ − V3·cos θ, Mx = −M2·cos θ + M3·sen θ y My = −M2·sen θ − M3·cos θ.
Las filas Max y Min son dos casos.

## Salida

`pile_caps[]` en `resultado.json`: geometría, pilote y pilotes, pesos, armado, cargas, la reacción de cada pilote en
cada caso (`reactions`, con ΔR) y las verificaciones con su caso.
