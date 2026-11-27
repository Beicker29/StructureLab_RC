# Formato de muros de contención

Muro de contención en voladizo (D-173). En construcción: la fase A (verificación del muro declarado) avanza por etapas;
hoy están la entrada y su validación. Las verificaciones, la salida y la memoria se documentan al implementarse.

## Convenciones

- Entrada en mm, kN/m³ (pesos unitarios), kPa (presión admisible) y grados (ángulos); internamente N, mm, MPa y radianes.
- Sección transversal por metro de muro: la pantalla de espesor constante se apoya en la base; la base sale hacia el
  relleno (talón) y hacia el frente (puntera).
- Relleno granular (c' = 0) y horizontal, con su cara superior a `backfill_height` sobre la cara superior de la base.
- El peso del suelo sobre la puntera no estabiliza (puede erosionarse o retirarse), como en el manual ACI MNL-17(21).

## Teoría de presión lateral (D-173, decisión 9)

La teoría (Rankine o Coulomb) se declara por muro y se usa en todos sus cálculos: estabilidad, pantalla y, cuando
exista, sismo. El programa nunca cambia de teoría. **El plano de empuje lo define el talón, no el tipo de muro:** la
misma regla vale para gravedad, semigravedad y voladizo. Referencia: B. M. Das, *Principles of Foundation Engineering*,
8.ª ed., 2016.

### Variables

| Variable | Significado |
| --- | --- |
| A | Extremo del talón, en la cara inferior de la base. |
| B | Punto de la superficie del relleno sobre A. AB es el trasdós virtual vertical, de altura H'. |
| C | Corona de la cara del muro en contacto con el relleno: la pantalla en el voladizo; la cara trasera en gravedad. |
| α | Inclinación del relleno respecto a la horizontal. |
| φ', γ | Ángulo de fricción interna efectivo y peso unitario del relleno. |
| θ_v | Inclinación de AC respecto a la vertical: atan(Δx_AC/Δy_AC). |
| η | Ec. 13.1: η = 45° + α/2 − φ'/2 − ½·asin(sin α / sin φ'). Talón largo: θ_v ≥ η; talón corto: θ_v < η. |
| β (`beta_coulomb`) | Ángulo del plano de empuje respecto a la horizontal, medido abajo, del lado del muro (fig. 12.12). |
| θ de Chu (`theta_chu`) | Inclinación respecto a la vertical, positiva como en la fig. 12.8. No se comparte con β. |
| δ' | Fricción suelo–concreto declarada; solo en contacto con concreto. |

### Rankine

| Talón | Plano | Qué se hace | Pesos |
| --- | --- | --- | --- |
| Largo | AB vertical | Ka de Rankine (con α); P_a inclinado α, a H'/3 | El suelo entre el muro y AB, y el concreto |
| Corto | AC | Rankine generalizado de Chu (§12.4, ec. 12.13 a 12.17) con θ = +θ_v; P_a inclinado β'_a (ec. 12.15) respecto a la normal a AC (θ_v + β'_a respecto a la horizontal); H = altura vertical de AC, a H/3 | La cuña entre AC y el muro, y el concreto |

Con θ_v ≤ η, β'_a ≤ φ': el campo de Rankine es admisible sobre AC y la pantalla no lo obstruye. Chu en AC más la cuña
equivale exactamente a Rankine en AB más el suelo sobre el talón, así que Rankine es continuo en θ_v = η y el ejemplo 2
del manual ACI (talón corto según Das) se reproduce por la ruta normal. Para que la equivalencia sea exacta:

- la cuña de concreto del talón entre AC y AB (por debajo de la cara superior del talón), que P_a ya cuenta como suelo,
  se descuenta del peso del lado del muro, con su centroide;
- el suelo sobre el talón lleva siempre el factor del relleno: la parte que P_a contiene (el triángulo ABC) se corrige
  con (`fill_factor` − `earth_factor`) en su centroide.

### Coulomb

Ka con la ec. 12.26:

```text
Ka = sin²(β + φ') / { sin²β · sin(β − δ) · [1 + √( sin(φ' + δ)·sin(φ' − α) / (sin(β − δ)·sin(α + β)) )]² }
```

P_a = ½·Ka·γ·H², a H/3, forma con la horizontal el ángulo 90° − β + δ.

| Talón | Plano | β | δ | Pesos |
| --- | --- | --- | --- | --- |
| Sin talón | La cara real del muro | El de la cara | δ' declarado | Solo el concreto |
| Corto (θ_v < η) | AC, dentro del suelo | 90° − θ_v | φ' (rotura suelo contra suelo) | La cuña entre la cara, la cara superior del talón y AC (menos la cuña de concreto del talón entre AC y AB), y el concreto |
| Largo (θ_v ≥ η) | AB vertical | 90° | α | El suelo entre el muro y AB, y el concreto; se reduce exactamente a Rankine |

Sin talón es Das fig. 13.4c; corto y largo son una extensión aprobada, no están en Das. En θ_v = η el paso de AC a AB es
continuo; entre sin talón y corto hay un salto (δ' a φ'), que se revisa con los muros de gravedad (el voladizo de la fase
A exige talón).

### Pesos y pantalla

El suelo del lado del relleno respecto al plano de empuje ya está en P_a y no se suma; el del lado del muro se suma como
peso, con el concreto. La pantalla del voladizo lleva la teoría declarada sobre su cara (con Coulomb, δ').

### Verificaciones no válidas

El programa no sustituye la teoría declarada: cuando la fórmula sale de su rango de validez, la verificación queda
BLOCKED con el motivo.

| Condición | Mensaje |
| --- | --- |
| Coulomb con c' > 0 | La ec. 12.26 es para c' = 0. |
| α > φ' | No hay solución con ninguna teoría. |
| Ko con relleno inclinado | Las ec. 13.5 y 13.7 son para α = 0. |
| Rankine o declarado con c' > 0 | «relleno cohesivo (c' > 0) no implementado» (pendiente). |
| Coulomb con talón y sismo | No implementado: falta el η sísmico (pendiente). |

Ko actúa sobre AB, horizontal. El coeficiente declarado actúa siempre sobre AB, inclinado α.

## Verificaciones

Se verifican el empuje, la estabilidad y las presiones (casos de servicio), la pantalla y la base (casos mayorados). El
agrietamiento toma la mayor separación entre fs calculado con el mayor momento de servicio (sección fisurada elástica,
n = Es/Ec con Ec = 4700√f'c) y fs = 2/3·fy, los dos permitidos (D-174); sin casos de servicio, 2/3·fy. Si la fórmula del empuje no vale, solo queda el empuje BLOCKED.

### Estabilidad y presiones (casos de servicio)

| Verificación | Qué se revisa |
| --- | --- |
| Presión admisible del suelo | q_max (Bellos y Bakas, sin tracción) ≤ qa |
| Contacto con el suelo | Fracción de la base en contacto ≥ `min_contact_fraction` |
| Deslizamiento | FS·P_h ≤ μ·N + Pp (la pasiva solo si se declara) |
| Volcamiento | FS·Mo ≤ Mr, alrededor del borde de la puntera (sin pasiva) |

### Pantalla (casos mayorados, por franja de 1 m)

Sección crítica en la unión con la base. Vu = factor del empuje·P_h y Mu = Vu·H/3, con P_h el empuje sobre la cara de la
pantalla y H la altura del relleno sobre la base; la carga axial se desprecia.

| Verificación | ACI 318-25 | NSR-10 |
| --- | --- | --- |
| Flexión pantalla (φMn ≥ Mu) | 13.3.6.1 y 7.5.1.1(a) | C.14.1.2 y C.10 |
| Deformación neta de tracción | 7.3.3.1 (controlada por tracción) | C.10.3.5 (εt ≥ 0.004) |
| Acero mínimo (0.0018·Ag) | 7.6.1.1 | C.10.5.4 y C.7.12.2.1 |
| Separación máxima (3h y 450 mm) | 7.7.2.3 | C.10.5.4 |
| Separación por agrietamiento | 24.3.2 | C.10.6.4 |
| Cortante sin refuerzo de cortante (Vn = Vc, φVc ≥ Vu, √f'c ≤ 8.3 MPa); Vc, el mayor de los dos procedimientos del perfil | 22.5.1.1, 22.5.1.5, 22.5.3.1, mayor de 13.3.6.1.1 y Tabla 22.5.5.1 (fila (c)), 13.3.6.3 y 7.6.3.1 | C.11.1.1, C.11.1.2, mayor de C.11.2.1.1 y C.11.2.2.1, C.11.4.6.1(a) y C.11.4.7.1 |
| Dimensiones de la sección por cortante (Vu ≤ φ(Vc + 0.66√f'c·bw·d)) | 22.5.1.2 | C.11.4.7.9 |
| Refuerzo horizontal: la mitad de la cuantía en cada cara | 24.4.3.2 (0.0018), separación 24.4.3.3 | C.14.3.3 (0.0020 o 0.0025), separación C.14.3.5 |
| Verticales de la cara exterior: la mitad de la retracción | 24.4.3.2, separación 24.4.3.3 | C.7.12.2.1, separación C.7.12.2.2 |

### Base (casos mayorados, por franja de 1 m)

La base es una zapata en una dirección. Las cargas de cada caso mayorado son las de la estabilidad con sus factores, y la
presión del suelo es la de Bellos y Bakas con la resultante mayorada.

- Talón: carga neta = su concreto + el suelo que cuenta como peso + la componente vertical del empuje − la presión. Momento
  y cortante en la cara de la pantalla (la junta se abre); barras superiores (`base.top`).
- Puntera: la presión − su concreto (el suelo sobre ella no cuenta). Momento en la cara exterior de la pantalla y cortante a d
  de ella; barras inferiores (`base.bottom`).
- Un momento de signo contrario (tracción en la otra cara) queda BLOCKED: no está en la fase A.

| Verificación | ACI 318-25 | NSR-10 |
| --- | --- | --- |
| Flexión talón y puntera (φMn ≥ Mu) | 13.3.2.1, 7.5.1.1(a) y 13.2.7.1 | C.15.4.1 y C.15.4.2 |
| Deformación neta de tracción | 13.3.2.1 y 7.3.3.1 | C.10.3.5 |
| Cortante talón (en la cara), Vc de las zapatas | 13.3.2.1, 7.5.1.1(b) y 13.2.6.2(a); R13.3.6.3 | C.15.5.1 y C.11.2 |
| Cortante puntera (a d de la cara), Vc de las zapatas | 13.2.6.2(a) y 13.2.7.2 | C.15.5.1, C.15.5.2 y C.11.2 |
| Dimensiones de la sección por cortante | 22.5.1.2 | C.11.4.7.9 |
| Acero mínimo (0.0018·Ag) y separación máxima (3h y 450 mm) | 13.3.2.1, 7.6.1.1 y 7.7.2.3 | C.10.5.4 y C.7.12.2.1 |
| Separación por agrietamiento (fs de servicio) | 7.7.2.2 y 24.3.2 | C.10.6.4 |
| Longitudinal: retracción sobre la sección de la base, barras en cada cara | 24.4.3.2 y 24.4.3.3 | C.7.12.2.1 y C.7.12.2.2 |
| Altura sobre las barras inferiores ≥ 150 mm | 13.3.1.2 | C.15.7 |
| Desarrollo de las barras de la pantalla en la base (disponible: espesor − recubrimiento) | 25.4.3 o 25.4.2 | C.12.5 o C.12.2 |
| Desarrollo de las barras superiores del talón y las inferiores de la puntera (el lado más corto de la cara de la pantalla − recubrimiento) | 25.4.2 o 25.4.3 | C.12.2 o C.12.5 |

## Entrada

Un proyecto con muros declara `retaining_soil` y `retaining_walls`; usa `concrete` y `reinforcement_steel` del proyecto. El
peso unitario del concreto va en `concrete.unit_weight_kNm3`, como en zapatas y cabezales (D-139). Los campos propios del
muro no llevan la unidad en el nombre (decisión del usuario); la unidad está en estas tablas. Los comunes con las zapatas
conservan sus nombres (`allowable_pressure_kPa`).

### Suelo del muro (`retaining_soil`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `unit_weight_backfill` | kN/m³ | Peso unitario del relleno. |
| `friction_angle` | ° | Ángulo de fricción interna efectivo del relleno φ'. |
| `cohesion` | kPa | Cohesión c' del relleno. Obligatoria con Coulomb, que solo la admite nula (con c' > 0 la verificación queda BLOCKED); con las demás teorías, c' > 0 queda «relleno cohesivo no implementado». Sin ella, relleno granular. |
| `passive_coefficient` | - | Opcional: Kp de la pasiva frente a la puntera, sobre el espesor de la base; sin él la pasiva no cuenta. |
| `unit_weight_front` | kN/m³ | Peso unitario del suelo del frente; solo con `passive_coefficient`. |
| `friction_coefficient` | - | Coeficiente de fricción μ entre la base y el suelo. |
| `allowable_pressure_kPa` | kPa | Presión admisible del suelo. |
| `min_contact_fraction` | - | Fracción mínima de la base en contacto (1: la resultante en el tercio medio). |
| `sliding_safety_factor` | - | Factor de seguridad mínimo al deslizamiento. |
| `overturning_safety_factor` | - | Factor de seguridad mínimo al volcamiento. |

### Muro (`retaining_walls[]`)

| Campo | Unidad | Descripción |
| --- | --- | --- |
| `id` | texto | Identificador, único en el proyecto. |
| `quantity` | - | Veces que se construye (D-159). |
| `stem_height` | mm | Altura de la pantalla sobre la cara superior de la base. |
| `stem_thickness` | mm | Espesor constante de la pantalla. |
| `toe`, `heel` | mm | Puntera y talón: salientes de la base desde las caras exterior y del relleno de la pantalla (mayores que 0 en la fase A). |
| `base_thickness` | mm | Espesor de la base. |
| `backfill_height` | mm | Altura del relleno sobre la cara superior de la base (≤ `stem_height`). |
| `stem_cover`, `base_cover` | mm | Recubrimientos libres de la pantalla y de la base. |
| `earth_pressure.state` | texto | `active` (Ka) o `at_rest` (Ko). |
| `earth_pressure.method` | texto | Para Ka: `rankine` o `coulomb` (ec. 12.26); para Ko: `jaky` (ec. 13.5) o `mayne_kulhawy` (ec. 13.7, con `ocr`); `declared` para los dos, con `coefficient`. Ver los casos de arriba. |
| `earth_pressure.coefficient` | - | El coeficiente declarado; solo con `declared`. Actúa sobre AB como Rankine. |
| `earth_pressure.ocr` | - | Relación de sobreconsolidación (≥ 1); solo con `mayne_kulhawy`. |
| `earth_pressure.wall_friction_angle` | ° | δ' declarado, fricción suelo–concreto; solo con `coulomb`, y solo en las caras de concreto. |
| `stem.back` | barras | Verticales de la cara del relleno (las de flexión), con el extremo de su pie en la base. |
| `stem.front` | barras | Verticales de la cara exterior. |
| `stem.horizontal` | barras | Horizontales de cada cara. |
| `base.top` | barras | Transversales superiores (flexión del talón). |
| `base.bottom` | barras | Transversales inferiores (flexión de la puntera). |
| `base.longitudinal` | barras | Paralelas al muro en cada cara. |
| `cases[]` | lista | Casos de carga: `case`, `kind` (`service` o `factored`) y los factores de su combinación (D-173): `dead_factor` (peso del concreto), `fill_factor` (peso del relleno sobre el talón) y `earth_factor` (empuje). |

Cada grupo de barras es `{"designation", "spacing" (mm), "end"}`, como en las zapatas.

La validación revisa que las barras estén en el catálogo, que su separación deje espacio libre y que el refuerzo de las
dos caras y los recubrimientos quepan en el espesor de la pantalla y en el de la base.

## Salida

`resultado.json` trae `retaining_soil` (el suelo en unidades de presentación) y `retaining_walls`, una entrada por muro
(D-173, etapa 5). Todo va por franja de 1 m de muro: fuerzas en kN y momentos en kN·m por metro.

| Campo | Contenido |
| --- | --- |
| `id`, `quantity`, `status` | El muro, las veces que se construye y su estado agregado. |
| `geometry [mm]` | Las dimensiones declaradas y las calculadas: `base_width` (puntera + pantalla + talón) y `retained_height` (base + relleno). |
| `earth_pressure` | La teoría declarada: `state`, `method`, `coefficient`, `ocr` y `wall_friction_angle [deg]`. |
| `thrust.estabilidad`, `thrust.pantalla` | El empuje sin factores: `plano` (cara, AC o AB), `talon` (sin talón, corto o largo), `K [-]`, `Pa [kN]`, `Ph [kN]`, `Pv [kN]`, su punto `x [mm]` e `y [mm]` (desde el borde de la puntera y la cara inferior de la base), `altura del plano [mm]`, `delta [deg]`, `eta [deg]`, `theta_v [deg]`, `W suelo [kN]` y `invalida` (el motivo si la fórmula no vale). |
| `reinforcement` | El refuerzo declarado de la pantalla y de la base. |
| `cases` | Los casos con sus factores. |
| `checks` | Las verificaciones, cada una con su `case` (None si vale para todo el muro). |

La memoria del muro tiene los capítulos de materiales; geometría, suelo y armado; empuje del relleno y casos de carga
(la tabla de los empujes de la estabilidad y de la pantalla); revisión geotécnica (con la tabla de la resultante, las
presiones y los factores de seguridad de cada caso de servicio); requisitos técnicos; flexión; cortante en una
dirección; desarrollo; índices DCR, y notas y limitaciones.
