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
exista, sismo. El programa nunca cambia de teoría. Referencia: B. M. Das, *Principles of Foundation Engineering*, 8.ª
ed., 2016.

### Variables

| Variable | Significado |
| --- | --- |
| A | Esquina inferior del extremo del talón (cara inferior de la zapata). |
| B | Punto de la superficie del relleno sobre A. AB es el trasdós virtual vertical, de altura H'. |
| C | Corona de la pantalla, en la cara contra el relleno. |
| α | Inclinación del relleno respecto a la horizontal. |
| φ', γ | Ángulo de fricción interna efectivo y peso unitario del relleno. |
| β (`beta_coulomb`) | Ángulo del plano de empuje respecto a la horizontal, medido abajo, del lado del muro (fig. 12.12). 90° es vertical; β < 90° significa que el relleno se apoya sobre el plano. |
| θ de Chu (`theta_chu`) | Inclinación respecto a la vertical (§12.4). Es otra variable; no se comparte con β. |
| η | Ec. 13.1: η = 45° + α/2 − φ'/2 − ½·asin(sin α / sin φ'). |
| θ_v | Inclinación de AC respecto a la vertical: atan(Δx_AC/Δy_AC). |
| δ' (`delta_prima`) | Fricción suelo–concreto declarada; solo en contacto con concreto. |
| δ' (`delta_mob`) | Inclinación de P_a en planos dentro del suelo: α en un plano vertical (estado de Rankine del talud infinito) y φ' en el plano de rotura AC. |

Ka de Coulomb (ec. 12.26):

```text
Ka = sin²(β + φ') / { sin²β · sin(β − δ') · [1 + √( sin(φ' + δ')·sin(φ' − α) / (sin(β − δ')·sin(α + β)) )]² }
```

P_a forma con la horizontal el ángulo 90° − β + δ': P_h = P_a·cos(90° − β + δ') y P_v = P_a·sin(90° − β + δ').

### Los cuatro casos

| Caso | Plano de empuje | δ' | Fuerzas de la estabilidad | Pantalla |
| --- | --- | --- | --- | --- |
| 1. Voladizo con Rankine (Das §13.3, fig. 13.4a) | AB vertical; con α ≠ 0, Rankine con relleno inclinado (§12.4–12.5), θ = 0. P_a = ½·Ka·γ·H'², a H'/3, inclinado α | — | P_a, W_s (todo el relleno sobre el talón) y W_c | Rankine sobre su cara |
| 2. Gravedad con Rankine (fig. 13.4b) | AB vertical por el extremo del talón, como el caso 1 | — | P_a, W_s (el suelo entre la cara del muro y AB) y W_c; η, solo como información | — |
| 3. Gravedad con Coulomb (fig. 13.4c) | La cara real del muro contra el relleno, con β según la convención. P_a = ½·Ka·γ·H², a H/3 | Declarado | P_a y W_c (sin suelo sobre el muro) | — |
| 4a. Voladizo con Coulomb, talón largo (θ_v ≥ η) | AB, β = 90° | α | P_a, W_s y W_c; se reduce exactamente a Rankine (caso 1) | Coulomb sobre su cara, δ' declarado |
| 4b. Voladizo con Coulomb, talón corto (θ_v < η) | AC, β_AC = 90° − θ_v; muro de gravedad equivalente con trasdós AC (la rutina del caso 3). P_a = ½·Ka·γ·H², H = altura vertical de AC, a H/3 | φ' | P_a, W_cuña (el suelo entre la pantalla, la cara superior del talón y AC) y W_c completo | Coulomb sobre su cara, δ' declarado |

El caso 4 es una extensión aprobada por el usuario; no está en Das. En el 4b, AC atraviesa una parte pequeña del concreto
del talón cerca de A y se toma W_c completo, como en la fig. 13.4a. Con β = 90° y δ' = α, la ec. 12.26 da
Ka = cos α·(cos α − √(cos²α − cos²φ'))/(cos α + √(cos²α − cos²φ')), el de Rankine.

Los casos 2 y 3 son de muros de gravedad: se documentan aquí para fijar la regla, y se implementan cuando se agregue ese
tipo de muro.

### Verificaciones no válidas

El programa no sustituye la teoría declarada: cuando la fórmula sale de su rango de validez, la verificación se reporta
como no válida con el motivo.

| Condición | Mensaje |
| --- | --- |
| Rankine en voladizo con talón corto (θ_v < η) | «talón corto: supuesto de Rankine no válido (Das §13.3)» |
| Coulomb con c' > 0 | La ec. 12.26 es para c' = 0. |
| α > φ' | No hay solución con ninguna teoría. |
| Caso 4 con sismo | No implementado: falta el η sísmico (pendiente). |
| Rankine o declarado con c' > 0 | «relleno cohesivo (c' > 0) no implementado» (pendiente). |
| Ko con relleno inclinado | Las ec. 13.5 y 13.7 son para α = 0. |

Ko actúa sobre AB, horizontal (δ' = 0), como el caso 1. El coeficiente declarado también actúa sobre AB, inclinado α, y
lleva la misma revisión de talón corto que Rankine, porque el plano es el mismo. Las verificaciones no válidas quedan
BLOCKED, con el motivo.

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
