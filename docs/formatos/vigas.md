# Formato de vigas

Referencia de la entrada y la salida de la verificación de vigas, común a los dos perfiles. Los ejemplos están en `examples/<perfil>/vigas/`.

## Convenciones

- Unidades de entrada: mm y MPa; fuerzas mayoradas en kN y kN·m. La aplicación no genera combinaciones.
- Ejes de ETABS: X = eje 3 (horizontal), Y = eje 2 (hacia arriba), Z = eje 1 (a lo largo del miembro).
- `Pu_kN` es positiva en compresión. `Mu_kNm` (M3) positivo comprime la cara superior; `M2_kNm` positivo comprime
  la cara +3 (x = bw).

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
| `materials.max_aggregate` | mm | Tamaño máximo nominal del agregado grueso, opcional. En vigas aún no se usa: la separación mínima de las barras se revisa por ahora en zapatas (D-102). |
| `members` | lista | Vigas del proyecto. |

### Miembro (`members[]`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `id` | texto | Identificador único. |
| `type` | texto | Tipo de miembro; esta carpeta usa `beam`. |
| `statically_determinate` | sí/no | Si la viga es isostática; solo se exige para As,min con el ala a tracción. |
| `deep_beam` | sí/no | Viga de gran altura declarada por el usuario (ACI 9.9.1.1, NSR-10 C.11.7.1); opcional, por defecto no (D-089). |
| `length` | mm | Longitud del miembro. |
| `section.bw` | mm | Ancho del alma. |
| `section.h` | mm | Altura total. |
| `section.cover` | mm | Recubrimiento libre a los estribos. |
| `section.hf` | mm | Espesor del ala, solo en vigas T o L. |
| `section.overhang_x_neg`, `section.overhang_x_pos` | mm | Salientes del ala hacia −3 y +3 (0 si no hay); solo con `hf`. |
| `stations` | lista | Secciones verificadas a lo largo de la viga. |

El programa calcula el área bruta, el ancho del ala y las alas efectivas a torsión; no se declaran.

### Estación (`stations[]`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `z` | mm | Posición a lo largo del miembro, desde el extremo inicial. |
| `case` | texto | Nombre del estado de carga (opcional, informativo). |
| `layout.layers[].depth` | mm | Profundidad del centro de la capa, desde la fibra superior. |
| `layout.layers[].role` | texto | `flexure` (As de flexión), `torsion` (Aℓ; no cuenta como As) o `skin` (refuerzo superficial en las caras laterales, D-083; no cuenta como As). |
| `layout.layers[].bars` | lista | Tres formas: solo designaciones (`["#6", "#6"]`, repartidas entre las esquinas del estribo); barras con posición (`{"designation": "#6", "x": 60}`, x desde la cara −3 del alma); o barras por separación (`{"designation": "#4", "spacing": 200, "from": -300, "to": 600}`, para la malla del ala). |
| `layout.stirrups.designation` | texto | Barra del estribo, del catálogo (`structurelab-rc catalog`). |
| `layout.stirrups.legs` | - | Número de ramas verticales (≥ 2). |
| `layout.stirrups.spacing` | mm | Separación a lo largo del miembro. |
| `layout.stirrups.closed` | sí/no | Estribo cerrado; la torsión lo exige. `stirrups: null` declara que no hay estribos. |
| `demands.Pu_kN` | kN | Carga axial mayorada, positiva en compresión. Con Pu ≥ 0.10 f'c·Ag el miembro sale del alcance de viga. |
| `demands.Mu_kNm` | kN·m | Momento M3 (eje fuerte). |
| `demands.M2_kNm` | kN·m | Momento M2 (eje débil). |
| `demands.Vu_kN` | kN | Cortante V2 (vertical). |
| `demands.V3_kN` | kN | Cortante V3 (horizontal). |
| `demands.Tu_kNm` | kN·m | Torsión. |

## Salida

`report` escribe tres archivos en la carpeta de salida:

| Archivo | Contenido |
| --- | --- |
| `resultado.json` | Todo el detalle en unidades de presentación (kN, kN·m, kPa, mm, MPa), redondeado a 6 cifras significativas. Es la fuente de la memoria. |
| `memoria.txt` | Memoria de cálculo de cada elemento, una tras otra (D-068): resultado y DCR máximo, capítulos fijos con cada revisión en su ubicación gobernante, índices DCR y notas y limitaciones. |
| `memoria.pdf` | Los mismos bloques en PDF, cada elemento desde una página nueva; requiere el extra `pdf` (`pip install structurelab-rc[pdf]`). |

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

## Verificaciones de vigas

| Verificación | Qué compara |
| --- | --- |
| Flexión: resistencia | φMn biaxial con Pn = Pu frente a Mu y M2; valores `phi`, `Mn3`, `Mn2`, `theta` (orientación del eje neutro), `c`, `et`. |
| Flexión: deformación neta de tracción (M3, M2, biaxial) | εt mínima del perfil frente a la εt de cada estado. |
| Flexión: acero mínimo (M3, M2) | As,min frente al acero a tracción del lado en tracción (más allá de la mitad de la altura), con d ≥ 0.8h; si As < As,min, basta 4/3 del As requerido por el momento de la estación (ACI 9.6.1.3, NSR-10 C.10.5.3; valores `As,min` y `As analisis`). |
| Flexión: refuerzo superficial | Solo con h > 900 mm (ACI 9.7.2.3, NSR-10 C.10.6.7): en cada cara lateral, la mayor separación entre la capa en tracción, las barras `skin` o `torsion` (D-090) y el límite h/2 frente al control de agrietamiento con cc a la cara lateral; sin barras de piel en una cara, FAIL. |
| Flexión: separación por fisuración | Separación entre barras vecinas de la capa más cercana a la cara en tracción frente a 380·(280/fs) − 2.5·cc ≤ 300·(280/fs), fs = 2/3·fy (ACI 24.3.2, NSR-10 C.10.6.4); con una sola barra, el ancho de esa cara. Valores `cc` y `barras`. |
| Cortante: resistencia, dimensiones de la sección, refuerzo mínimo, separación máxima | Vc + Vs, límite de la sección, Av,min y separaciones en la dirección V2. |
| Cortante V3: ... | Las mismas verificaciones en la dirección V3; d ≥ 0.8bw. |
| Cortante: interacción V2-V3 | Solo ACI 318-25: interacción de los cortantes en dos direcciones. |
| Torsión: umbral | Si Tu < φTth la torsión se desprecia (valores `Tu` y `phi Tth`). |
| Torsión: dimensiones, refuerzo transversal y longitudinal, mínimos y distribución | Verificación combinada con el cortante cuando la torsión no es despreciable; Aℓ provisto suma las capas `torsion` y `skin` (D-027, D-090). |
| Viga alta: límite de sección | Solo con `deep_beam`: Vu frente a φ·0.83√f'c·bw·d (ACI 9.9.2.1, NSR-10 C.11.7.3; valores `phi`, `d`). |
| Viga alta: refuerzo distribuido transversal | Ramas·Ab/s de los estribos frente a 0.0025·bw (ACI 9.9.3.1(a), NSR-10 C.11.7.4.1). |
| Viga alta: refuerzo distribuido longitudinal | La capa intermedia que gobierna frente a 0.0025·bw por su altura tributaria (ACI 9.9.3.1(b), NSR-10 C.11.7.4.2; valor `capa`). |
| Viga alta: separación del refuerzo distribuido | La separación de los estribos y el mayor salto vertical entre capas frente a la menor entre d/5 y 300 mm (valores `s estribos`, `sd vertical`). |
| Viga alta: cortinas | Solo ACI 318-25 con bw > 200 mm: separación de las ramas a lo ancho frente a 600 mm (9.9.4.4). |
