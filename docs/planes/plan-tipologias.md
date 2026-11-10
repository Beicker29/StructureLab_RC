# Plan: tipologías de zapatas con DP y MILP

Plan de trabajo por etapas para mejorar el diseño de zapatas por tipologías (V3F, D-069). Cada etapa se ejecuta en
una sesión aparte, se cierra con su criterio de aceptación y actualiza la tabla de estado. Este plan no reemplaza a
`AGENTS.md`: todas sus reglas siguen vigentes.

## Estado

| Etapa | Estado | Decisión o evidencia |
|---|---|---|
| E0. Medición | Cerrada (2026-11-09) | [`docs/mediciones/E0.md`](../mediciones/E0.md): 92 % del tiempo en rediseños de tramo; matriz completa ≈ 1 % del tiempo; NSR-10 con 1 repetida; reasignables 2.2 % (NSR-10) y 7.9–8.3 % (ACI) |
| E1. DP: repetidas marcadas y reasignación | Cerrada (2026-11-09) | D-074: huella idéntica; ETABS −3.2 % (NSR-10, f'c 21 → 24.5) y −7.9 % (ACI); `report` PASS |
| E2. Generador compartido y MILP | Cerrada (2026-11-09) | D-075: huella idéntica; ETABS −3.0 % (NSR-10) y −4.6 % (ACI) frente a E1, óptimo certificado; `milp` por defecto |
| E3a. Espesor y mallas de menor costo en `design_group` | Cerrada (2026-11-09) | D-076: mismo costo en los dos proyectos de ETABS; tiempo −33 % (NSR-10) y −32 % (ACI) frente a E2; barrido solo en individuales y grupos elegidos; huella idéntica |
| E3b. Velocidad: rediseñar solo lo que proponga el MILP | Pendiente (según E2 y E3a) | — |
| Curva costo–N | Fase siguiente | — |

Ninguna etapa empieza si la anterior no está cerrada y su resultado registrado. Las decisiones de continuar o no
las toma el usuario con los datos de la etapa previa.

## Contexto: lo que existe hoy

- `design/footing/typology.py`: `design_group` diseña la tipología más económica para un grupo de columnas (planta
  creciente, espesor por bisección, mallas más livianas, pasadores por columna). `covers(ctx, typology, column)`
  devuelve los pasadores con que una tipología aprueba todas las verificaciones de una columna, o `None`.
  `priced` calcula costo, concreto y acero. `_soil_ok` revisa presión, contacto y equilibrio, que dependen solo de
  la planta y el espesor.
- `design/footing/grouping.py`: `partition` parte una lista ordenada en N tramos continuos por programación
  dinámica (DP), óptima para ese orden.
- `design/footing/typologies.py`: `_for_fc` diseña cada columna, las ordena por costo, calcula el costo de los
  tramos (tipología de la columna más exigente si cubre a todas; si no, rediseño del tramo) y parte; `_design`
  prueba cada f'c. Las tareas se reparten entre procesos con `--workers`, con resultado idéntico.
- Referencia de rendimiento (D-069, medición E0): proyecto de ETABS con 73 columnas, 16 hilos: 35 min con NSR-10 y
  39 min con ACI 318-25. El 92 % del tiempo se va en los rediseños de tramo.

## Objetivo

Que el costo de las N tipologías sea confiable, porque más adelante se construirá la curva costo total frente a N
para decidir cuántas tipologías conviene tener. En la zona plana de esa curva el ahorro entre N consecutivos es
pequeño, así que el error del algoritmo debe ser menor que ese ahorro.

## Definiciones y reglas que no cambian

- **N tipologías; las repetidas se permiten y se marcan** (D-074). El resultado tiene exactamente N grupos de
  columnas. Si dos o más grupos tienen la misma tipología, no hay FAIL ni se descarta el f'c: la salida trae
  `distinct_count` y `duplicates`, y la memoria muestra una advertencia.
- **Tipologías iguales:** coinciden f'c, lx, ly, h, malla inferior y malla superior. Los pasadores no cuentan:
  son de cada columna.
- **La seguridad no depende del algoritmo.** Ningún solucionador decide si una zapata cumple: todos usan `covers()`
  y `footing_checks`, y el proyecto diseñado se reverifica completo con `verify` y `report`. Esa reverificación es
  obligatoria en todos los métodos.
- **Determinismo.** El mismo JSON da el mismo resultado con cualquier número de procesos y en ejecuciones
  repetidas. La huella de los ejemplos existentes no cambia salvo donde la etapa lo diga explícitamente.
- **Sin dependencias nuevas en el núcleo.** El MILP usa `highspy` como extra opcional (`opt`). Pedir `milp` sin
  tenerlo instalado es un error claro, nunca una DP silenciosa.
- **Excavación y formaleta fuera del costo** (D-069). Este plan no cambia la función de costo.
- **Sin estimar tiempos de implementación** antes de tener los datos de E0.

## E0. Medición (sin cambiar resultados)

**Objetivo:** saber con datos dónde se va el tiempo hoy, cuánto costaría la matriz completa de cobertura y si la
DP actual pierde dinero, antes de escribir el MILP.

**Preguntas que debe responder:**

1. ¿En qué se van los 8 minutos del proyecto de 65 columnas?
2. ¿Cuánto tarda en promedio una llamada a `covers()`?
3. ¿Cuánto tardaría la matriz completa de cobertura?
4. ¿La solución actual tiene tipologías repetidas?
5. ¿El orden por costo está perdiendo dinero?

**Casos:** el proyecto real de ETABS (`examples/<perfil>/zapatas/plantilla_diseno_zapatas_etabs.json` con los Excel
de `examples/etabs/zapatas/`) y `diseno_tipologias.json` de ambos perfiles.

**Qué medir:**

| Medida | Dónde |
|---|---|
| Número y tiempo de las tareas `single` (diseños individuales) | `_for_fc` |
| Número y tiempo de las tareas `covers` | `_for_fc` |
| Número y tiempo de las tareas `design` (rediseños de tramo) | `_for_fc` |
| Tramos cubiertos por la tipología de su columna más exigente frente a tramos rediseñados | `_for_fc` |
| Dentro de `covers()`: tiempo de la revisión de suelo frente a las verificaciones completas, y opciones de pasadores probadas | `typology.py` |
| Tiempo de `partition()` | `grouping.py` |

Todo por cada f'c, con SHA, máquina, sistema operativo y número de procesos. En paralelo, cada tarea devuelve su
propio tiempo junto con su resultado (no solo el tiempo total).

**Análisis, sin aplicar ningún cambio al resultado:**

- **Estimación de la matriz completa.** Armar la lista de candidatos que usaría el MILP: las tipologías
  individuales y las de los tramos, sin repetidas. Tomar una muestra fija de unos 500 pares columna–candidato, con
  semilla, medir el tiempo de `covers()` y la fracción que descarta `_soil_ok`, y extrapolar:
  candidatos × columnas × tiempo por par ÷ procesos.
- **Repetidas.** Contar las tipologías repetidas en la solución actual de cada N que se corra.
- **Columnas reasignables.** Para las N tipologías elegidas, contar las columnas que podrían pasar a otra tipología
  elegida más barata que también las cubre, y cuánto bajaría el costo. Solo se cuenta.

**Entregables:**

- Código de medición como comando aparte o como opción `--profile` de `design-footings`, con pruebas mínimas.
- `docs/mediciones/E0.md`, versionado, con las cinco respuestas, las tablas de números y la configuración usada.
- La huella de los ejemplos queda idéntica.

**Reglas de decisión propuestas** (el usuario fija los umbrales finales):

| Resultado | Siguiente paso |
|---|---|
| Matriz completa estimada ≤ 2 veces el tiempo actual | E2 con matriz completa |
| Mucho mayor | E2 con candidatos reducidos: individuales, solución DP y vecinas |
| Cero repetidas y cero columnas reasignables | Probablemente el MILP aporta poco: cerrar en E1 y registrar la decisión |
| Hay repetidas o columnas reasignables | Se justifica E2 |

## E1. DP: repetidas marcadas y reasignación

**Objetivo:** que la DP marque las tipologías repetidas y no deje dinero obvio sobre la mesa.

1. **Detección de repetidas** según la definición de arriba, sin FAIL ni descarte de f'c (D-074): se elige el f'c
   más barato como hoy. `tipologias.json` trae `distinct_count` y `duplicates` (grupos de tipologías idénticas, cada uno
   con sus nombres y `at_limit`, los límites de diseño `plan_max` o `h_max` en que está la tipología, p. ej.
   `[{"typologies": ["Z4", "Z5"], "at_limit": []}]`) y, por cada f'c evaluado, su costo y su `distinct_count`. La memoria muestra una advertencia
   visible cuando hay repetidas.
2. **Reasignación que conserva las N.** Para cada columna, en orden fijo por id, buscar entre las N tipologías
   elegidas la más barata que la cubre. Mover la columna solo si baja el costo y su tipología de origen conserva al
   menos una columna. Repetir hasta que nada cambie (termina porque el costo baja en cada movimiento). Las
   tipologías no se rediseñan en esta etapa. La salida trae `cost_before_reassignment` y `reassigned`
   (`column`, `from`, `to`, `saving`).
3. Registrar D-074 en `docs/decisions.md` y documentar los campos en `docs/formatos/zapatas.md`.

**Aceptación:**

- Huella idéntica en los ejemplos sin repetidas ni reasignaciones; los cambios se listan y justifican.
- Pruebas: el costo nunca sube con la reasignación, siempre quedan N grupos con columnas, mismo resultado con
  cualquier número de procesos, repetidas marcadas en la salida y en la memoria.

## E2. Generador compartido y MILP

**Objetivo:** un segundo solucionador que elimine la restricción de tramos continuos de la DP y certifique el
óptimo dentro del catálogo de candidatos.

**1. Refactor de `_for_fc`**, sin cambiar la huella del modo `dp`:

- Generador de candidatos: tipologías sin repetidas, con la tabla de tramos independiente de N (deja lista la
  curva de la fase siguiente).
- Costo por par `c_ij`: costo de la tipología j en la columna i, con sus pasadores y pedestal. Hoy `_cost` calcula
  por grupo; se separa por columna, y la DP lo reutiliza.
- Dos solucionadores separados: `grouping.py` (DP) y `assignment.py` (MILP, nuevo).

**2. Modelo:**

```
min  Σ_i Σ_j c_ij · x_ij
s.a. Σ_j x_ij = 1          ∀ i   cada columna, una tipología
     x_ij ≤ y_j            ∀ i,j solo tipologías elegidas
     Σ_i x_ij ≥ y_j        ∀ j   cada tipología elegida tiene al menos una columna
     Σ_j y_j = N                 exactamente N
     x_ij = 0 si j no cubre a i
     x, y binarias
```

**3. Flujo con `--method milp`:** DP → catálogo (candidatos de la DP, sin repetidas) → matriz de cobertura → MILP
arrancando desde la solución DP con `setSolution()`. Si la DP tiene repetidas, su solución no es factible en el
modelo (exige N tipologías distintas) y no sirve de arranque.

**4. Configuración para que sea fiable:**

- Brecha relativa 0, un hilo y semilla fija.
- Costos redondeados a pesos enteros.
- Desempate en dos etapas: primero el costo mínimo; luego, con ese costo fijo, el menor peso de acero y después
  un orden fijo de candidatos.
- `C_MILP ≤ C_DP` se exige como verificación solo cuando la DP no tiene repetidas (D-074): entonces se cumple si la
  solución DP está en el catálogo, ambos modelos tienen las mismas restricciones y el mismo costo por par, y se
  conserva la mejor solución factible; si no se cumple, es un error y el resultado se rechaza. Si la DP tiene
  repetidas, se reportan los dos costos con su `distinct_count` y una nota (la DP usa menos tipologías distintas).

**5. Estados:**

| Estado del solver | Resultado |
|---|---|
| Óptimo con brecha 0 | "Óptimo certificado en el catálogo" |
| Límite de tiempo con solución | "Sin certificar"; nunca peor que la DP gracias al arranque (si la DP no tiene repetidas) |
| Infactible | No hay N tipologías distintas en el catálogo que cubran todas las columnas: se reporta el motivo y queda la solución DP con sus repetidas marcadas |

**6. Interfaz y salida:** `--method dp|milp` en la CLI y `design.method` en el JSON (por defecto `dp` hasta que el
usuario decida otra cosa con los datos). Límite de tiempo configurable. La salida incluye método, costo DP, costo
MILP, estado y tiempos. Registrar D-075 y actualizar `docs/formatos/zapatas.md` y los `LEEME`.

**Aceptación:**

- Modo `dp` con la misma huella que al cerrar E1.
- `C_MILP ≤ C_DP` en todos los ejemplos cuya DP no tiene repetidas; en los demás, los dos costos con su
  `distinct_count` y la nota.
- Coincidencia exacta con fuerza bruta (oráculo independiente) en casos de 6 a 8 columnas.
- Mismo resultado en ejecuciones repetidas y con cualquier número de procesos.
- Error claro si falta `highspy`; CI instalando el extra `opt`.

## E3a. Espesor de menor costo en `design_group` (después de E2, por separado)

**Problema (E0):** `design_group` toma el menor espesor con solución de cada planta (bisección), no el de menor costo.
En ACI 318-25 una zapata más gruesa sin malla superior resultó más barata que la elegida con malla superior (Z3 frente a
Z2 en [E0](../mediciones/E0.md)). Es un defecto frente a lo que declara D-069 (la tipología más económica).

**Cambio** (aprobado el 2026-11-09, D-076). La verificación no cambia: cada propuesta sigue aprobándose con
`footing_checks`.

1. **Mallas por espesor.** Hoy `_at_height` devuelve la primera combinación que pasa en orden de malla inferior y prueba
   una sola malla superior. Si las verificaciones de la malla inferior y de la superior son separables (confirmarlo en
   el código y probarlo contra la enumeración), se halla la más liviana que pasa de cada una (la superior entre todas
   las candidatas, o ninguna si el perfil lo permite con el nivel sísmico, D-072) y el par se confirma con una
   verificación completa.
2. **Espesor.** Desde el menor espesor con solución (bisección), recorrer los espesores mayores hasta `h_max` y elegir
   el de menor costo. Una falla de suelo no detiene el barrido: ese espesor se salta y se sigue.
3. **Poda exacta.** Se deja de subir cuando la cota inferior de un espesor alcanza el mejor costo: concreto más la malla
   inferior mínima, con la misma función de acero mínimo del perfil (incluida la cuantía por tramos de NSR-10), las
   mismas longitudes que `_mat_mass` y la menor relación masa/área de las barras candidatas. Pasadores y malla superior
   quedan fuera de la cota.
4. La búsqueda de plantas (la primera viable y dos más) no cambia y sigue siendo heurística.

**Pruebas:** enumerador independiente (no reutiliza la lógica de `_at_height`) que recorre todos los espesores, incluidos
los menores que el resultado de la bisección, y todas las combinaciones de mallas candidatas, en casos de una columna
con la planta fija: el resultado debe ser el mínimo. La poda nunca descarta el óptimo. Mismo resultado con cualquier
número de procesos.

**Aceptación:** va sola, después de E2, para medir su ganancia por separado. Antes de correr ETABS completo se mide el
multiplicador de tiempo con los diseños individuales y se reporta. Cambia la huella (cambio de cálculo intencional,
listado y justificado). Costo y tiempo antes y después en los dos proyectos de ETABS con `milp`; `report` PASS.

## E3b. Velocidad (según E2 y E3a)

**Objetivo:** bajar el tiempo, que hoy se va casi todo en los rediseños de tramo (E0: 92 %).

**Ya hecho en E3a (D-076):** los grupos elegidos se refinan con el barrido de espesores sobre exactamente sus columnas, y
la tabla usa la búsqueda rápida.

**Idea:** partir de los diseños individuales y rediseñar con `design_group` solo los grupos que proponga el MILP, sobre
exactamente esas columnas; agregar esos rediseños al catálogo, calcular la cobertura solo de los candidatos nuevos y
resolver de nuevo desde la solución anterior, hasta que el costo no baje o se alcance el límite de iteraciones o de
tiempo. El costo nunca sube entre iteraciones, porque solo se agregan candidatos.

**Aceptación:** iguala o mejora el costo de la DP completa en los dos proyectos de ETABS, con menos tiempo. La salida
reporta costo y tiempo de cada iteración; el presupuesto de tiempo es configurable.

## Fase siguiente: curva costo–N

Después de E3b. Con la tabla independiente de N (E2) y las N exactas y distintas (E1), correr la asignación para N = 1…k. Cada
punto lleva su f'c, su estado (certificado o no), su `distinct_count`, una marca si tiene tipologías repetidas y una
advertencia si su costo sube respecto al anterior.

**Indicador de saturación de N:** las repetidas (cuántas y si están en un límite de diseño, `at_limit`), junto con el
ahorro marginal entre N consecutivos, indican cuándo aumentar N ya no aporta: si al subir N aparecen repetidas y el
ahorro marginal es pequeño, N está saturado. Una repetida en `plan_max` o `h_max` indica además que el límite, no la
demanda, fija la tipología.

## Cómo usar este plan

- Una etapa por sesión. Al empezar: leer `AGENTS.md` y este plan, registrar rama y SHA, presentar un plan corto de
  la etapa y esperar aprobación.
- Al cerrar: actualizar la tabla de estado, registrar la decisión o la evidencia, y cerrar con cambios, pruebas
  reales, diferencias numéricas, riesgos y pendientes, como pide `AGENTS.md`.
- Si algo de este plan contradice el código o una decisión registrada, detenerse y consultar al usuario antes de
  seguir.
