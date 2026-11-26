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
