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
| `soil` | objeto | Datos del suelo y de los pesos propios (abajo). Obligatorio con zapatas. |
| `footings` | lista | Zapatas del proyecto. |

### Suelo (`soil`); todos los campos son obligatorios

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `allowable_pressure_kPa` | kPa | Presión admisible **bruta** del suelo, qa. Se compara con la presión que incluye los pesos propios y las sobrecargas. |
| `min_contact_fraction` | - | Fracción mínima de la base que debe quedar en contacto con el suelo en los casos de servicio (0 a 1). |
| `unit_weight_concrete_kNm3` | kN/m³ | Peso unitario del concreto de la zapata y del pedestal. |
| `unit_weight_fill_kNm3` | kN/m³ | Peso unitario del relleno sobre la zapata. |

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
| `bottom` | objeto | Malla inferior (abajo). |
| `top` | objeto o `null` | Malla superior, o `null` si no hay. |
| `loads` | lista | Casos de carga (abajo). |

El relleno y las sobrecargas ocupan el área de la base menos la de la columna.

### Malla (`bottom`, `top`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `first` | texto | Dirección de las barras más cercanas a la cara de la zapata: `x` o `y`. Define la d de cada dirección. |
| `end` | texto | Cómo terminan las barras: `straight` (rectas) o `hook` (gancho estándar). Se usará para el desarrollo (V3D.3). |
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
| `P_kN`, `Vx_kN`, `Vy_kN` | kN | Fuerzas de la columna sobre la zapata. |
| `Mx_kNm`, `My_kNm` | kN·m | Momentos de la columna sobre la zapata. |

### Propiedades calculadas (no se declaran)

Área A, inercias Ix e Iy, módulos de sección Sx y Sy, núcleo central (lx/6, ly/6), pesos de la zapata, del pedestal
y del relleno, y fuerzas de las sobrecargas. Salen en `resultado.json`, en `footings[].properties`.

## Salida

`report` escribe tres archivos en la carpeta de salida:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | Todo el detalle en unidades de presentación (kN, kN·m, kPa, mm, MPa), redondeado a 6 cifras significativas. Es la fuente de la memoria. |
| `memoria.txt` | Memoria en texto: datos y supuestos, resumen, lo que no cumple y los casos críticos. |
| `memoria.pdf` | La misma memoria en PDF; requiere el extra `pdf` (`pip install structurelab-rc[pdf]`). |

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
propiedades calculadas, el número de casos y las verificaciones.

## Verificaciones de zapatas

Para cada caso de servicio, la resultante en el centroide de la base suma la columna, los pesos propios y las
sobrecargas con los factores del caso: N, Mx base = Mx − P·oy − H·Vy y My base = My + P·ox + H·Vx, con
H = h + altura del pedestal. Las excentricidades son ex = My base/N y ey = −Mx base/N.

| Verificación | Qué compara | Numeral |
| --- | --- | --- |
| Presión admisible del suelo | Presión máxima bruta frente a qa (kPa). La nota indica la región de contacto: C total, B pentagonal, D o E trapezoidal, A triangular. | ACI 13.3.1.1; NSR-10 C.15.2.2 |
| Contacto con el suelo | Fracción mínima exigida (`demand`) frente a la fracción de la base en contacto (`capacity`); cumple con razón ≤ 1. | D-052 |
| Zapata: equilibrio con cargas mayoradas | FAIL si un caso mayorado no tiene equilibrio con el suelo (D-054). | D-054 |
| Flexión malla inferior / superior (barras x o y) | Por caso mayorado: el mayor momento de la carga neta en las caras de la columna frente a φMn de la franja de ancho total. La superior solo aparece si hay momento negativo; sin malla superior sale `BLOCKED` (concreto simple, D-059). | ACI 13.2.6.6 y 13.2.7.1; NSR-10 C.15.4.1 y C.15.4.2 |
| Deformación neta de tracción malla … | εt de la malla frente a la mínima del perfil. | ACI 8.3.3.1; NSR-10 C.10.3.5 |
| Acero mínimo malla … | As frente a la cuantía mínima por el área bruta del ancho total. | ACI 8.6.1.1; NSR-10 C.10.5.4 y C.7.12.2.1 |
| Separación máxima malla … | Separación (y la de la franja) frente al máximo del perfil. | ACI 8.7.2.2; NSR-10 C.10.5.4 |
| Franja central malla … | Zapata rectangular: As en la franja frente a γs·As. | ACI 13.3.3.3; NSR-10 C.15.4.4.2 |
| Altura mínima de la zapata | 150 mm, medidos como pide cada perfil. | ACI 13.3.1.2; NSR-10 C.15.7 |
| Cortante en una dirección (barras x o y) | Por caso mayorado: Vu de la carga neta más allá de la sección a d de cada cara frente a φVc, con la d de esa dirección. | ACI 13.2.6.2(a) y 13.2.7.2; NSR-10 C.15.5 y C.11.2 |
| Punzonamiento | Por caso mayorado: esfuerzo máximo vu = Vu/(b0·d) + γv·Msc·c/Jc en los dos ejes, en el perímetro a d/2 (recortado con la base: αs = 40, 30 o 20), frente a φvc. Valores: Vu, b0, d, αs, γv y vuv. | ACI 22.6.5.2, 22.6.5.3 y 8.4.4.2; NSR-10 C.11.11.2.1 y C.11.11.7 |
| Acero mínimo por punzonamiento (barras x o y) | Solo ACI, cuando vuv > φ0.17√f'c: As,min de 8.6.1.2 frente a las barras de la malla inferior dentro de bslab. | ACI 8.6.1.2 |
| Zapata: verificaciones pendientes | Desarrollo, aplastamiento y pasadores (V3D.3); sale `BLOCKED`. | - |

Si la resultante cae fuera de la base o N no es de compresión, ambas verificaciones del caso son FAIL ("Sin
equilibrio con el suelo"). Sin casos de servicio, la presión admisible sale INCOMPLETE.
