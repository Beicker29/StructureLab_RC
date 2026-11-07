# Decisiones y consultas abiertas

## Plantilla

```markdown
### D-000: título

- **Fecha:** AAAA-MM-DD
- **Problema:** qué hay que resolver.
- **Referencia:** numeral, ecuación o documento.
- **Alternativas:** opciones consideradas.
- **Consecuencias:** qué implica la opción elegida.
- **Decisión:** qué se resolvió y quién lo confirmó.
```

## Decisiones

### D-001: un perfil por proyecto

- **Fecha:** 2026-11-02
- **Decisión:** cada proyecto declara `aci-318-25` o `nsr-10`, y todo su cálculo sale de ese perfil. Los perfiles nunca se mezclan.

### D-002: nivel sísmico declarado por el usuario

- **Fecha:** 2026-11-02
- **Decisión:** el usuario declara el nivel en el vocabulario de su perfil, con una justificación textual que sale en la memoria. La app no lo deriva; solo valida que exista en el perfil.

### D-003: fuerzas mayoradas de entrada en la v1

- **Fecha:** 2026-11-02
- **Decisión:** las fuerzas llegan mayoradas desde JSON o ETABS. La v1 no genera combinaciones.

### D-004: sin respaldo cruzado entre perfiles

- **Fecha:** 2026-11-02
- **Decisión:** lo no implementado en un perfil devuelve `BLOCKED`. Nunca se usa la fórmula del otro perfil.

### D-005: la v1 cubre solo vigas

- **Fecha:** 2026-11-02
- **Decisión:** los demás elementos se incorporan después, en el orden de la [hoja de ruta](ROADMAP.md).

### D-006: precedencia de estados y agregación vacía

- **Fecha:** 2026-11-02
- **Decisión:** `FAIL` prevalece sobre `INCOMPLETE`, este sobre `BLOCKED` y este sobre `PASS`. `aggregate([])` devuelve `INCOMPLETE`, porque sin verificaciones no hay obligaciones cumplidas.

### D-007: valores de `data/rebar.csv`

- **Fecha:** 2026-11-02
- **Problema:** el catálogo de barras necesita valores confirmados antes de usarse en cálculo.
- **Referencia:** valores nominales propuestos a partir de ASTM A615/A615M y A706/A706M; el cotejo con NSR-10 y NTC 2289 lo hizo el usuario.
- **Consecuencias:** el área nominal de la #4 (129 mm²) difiere 1.8 % de la geométrica (126.7 mm²). Se conserva el valor nominal.
- **Decisión:** se aceptan los valores del archivo. Confirmado por el usuario.

### D-008: `Check` vive en `domain/`

- **Fecha:** 2026-11-02
- **Problema:** la hoja de ruta ponía `Check` en `model/`, pero `Check` necesita `Status`, que vive en `domain/status.py`, y `model` no puede importar `domain`.
- **Alternativas:** mover `Check` a `domain/`, o mover `Status` a `model/`. La segunda contradice que la agregación esté en `domain/status.py`, salvo que se separe el enum de la función.
- **Consecuencias:** `model` queda libre de estados y el contrato de capas no cambia. `AGENTS.md` ya ubica el armado de `Check` en `domain/`.
- **Decisión:** `Check` se define en `domain/`. Confirmado por el usuario.

### D-009: fuentes del oráculo de flexión

- **Fecha:** 2026-11-02
- **Problema:** `mechanics` necesita referencias que no salgan del propio código.
- **Referencia:** ACI MNL-17(21), vol. 1, cap. 7, ejemplos 2, 3 y 5 (basado en ACI 318-19).
- **Alternativas:** usar solo el manual, que no cubre la T con bloque en el alma ni el acero a compresión, o completarlo con derivaciones.
- **Consecuencias:** el manual valida la mecánica, no ACI 318-25 ni NSR-10. No hay caso del manual para el momento nominal Mn: lo validan solo los casos derivados.
- **Decisión:** usar el manual donde cubre y casos derivados con solución cerrada donde no, marcados como tales. Confirmado por el usuario.

### D-010: β1 entre 55 y 56 MPa en NSR-10

- **Fecha:** 2026-11-02
- **Problema:** a 55 MPa, ACI da 0.65 y el texto de NSR-10 da 0.657. El comentario CR10.2.7 de NSR-10 habla de 0.65 para más de 55 MPa.
- **Referencia:** ACI CODE-318-25, Tabla 22.2.2.4.3; NSR-10 C.10.2.7.3 y CR10.2.7.
- **Alternativas:** seguir el texto del reglamento o el comentario.
- **Consecuencias:** los perfiles difieren hasta 1.1 %, solo en ese tramo.
- **Decisión:** seguir el texto del reglamento; el comentario no es norma. Confirmado por el usuario.

### D-011: unidades y tolerancia del oráculo del manual

- **Fecha:** 2026-11-02
- **Problema:** el manual está en unidades inglesas y redondea en pasos intermedios.
- **Alternativas:** convertir constantes normativas o solo los datos de los ejemplos.
- **Consecuencias:** el mayor desvío frente al manual es 0.74 %. Una tolerancia de 1 % no distinguiría errores menores.
- **Decisión:** convertir solo datos y resultados de los ejemplos (25.4 mm/in, 6.894757e-3 MPa/psi), con β1 = 0.80 del manual, y comparar con ±1 % sobre el valor impreso. Confirmado por el usuario.

### D-012: concreto desplazado y raíz del equilibrio

- **Fecha:** 2026-11-02
- **Problema:** una capa de acero dentro del bloque de compresión desplaza concreto. Al descontarlo, la fuerza salta cuando el bloque alcanza la capa, y puede haber más de una raíz de equilibrio.
- **Referencia:** las normas exigen equilibrio y compatibilidad (ACI 22.2.1, NSR-10 C.10.2.1), sin tratar este detalle numérico.
- **Alternativas:** no descontar el concreto desplazado, lo que sobrestima la compresión, o descontarlo.
- **Consecuencias:** solo cambia el resultado con acero a compresión dentro del bloque.
- **Decisión:** descontarlo y tomar la menor raíz. Confirmado por el usuario.

### D-013: límites de la validación de entrada

- **Fecha:** 2026-11-02
- **Problema:** hay que decidir qué capa valida contra la norma y qué pasa fuera de sus rangos.
- **Alternativas:** validar en `model`, que no puede importar `codes`, o en `domain`.
- **Consecuencias:** por debajo de 17 MPa ningún perfil define β1 y la entrada se rechaza, en lugar de suponer un valor. Una demanda ausente da `INCOMPLETE`.
- **Decisión:** `model` valida la forma y `domain` la coherencia con el perfil. El usuario declara el perfil y el nivel; εcu, β1, 0.85 y Es salen del perfil. Confirmado por el usuario.

### D-014: referencias de NSR-10 para la Fase 2

- **Fecha:** 2026-11-04
- **Problema:** la Fase 2 pide ejemplos de referencia en ambos perfiles, y no hay una fuente con ejemplos resueltos de NSR-10.
- **Referencia:** Wight, *Reinforced Concrete: Mechanics and Design*, 9.ª ed. (`references/`). Se basa en ACI CODE-318-25 y trae la mayoría de sus ejemplos en unidades inglesas.
- **Alternativas:** conseguir una fuente publicada de NSR-10, usar casos derivados a mano, o tomar los resultados de Wight.
- **Consecuencias:** Wight no aplica NSR-10. Donde NSR-10 difiere de ACI 318-25 (por ejemplo φ, β1 entre 55 y 56 MPa o Vc), sus resultados no tienen por qué coincidir con el perfil.
- **Decisión:** tomar los resultados de Wight como referencia del perfil `nsr-10`. Si un resultado no coincide, se reporta al usuario con la cláusula, el valor del libro y el valor del perfil, antes de modificar código o casos para hacerlo coincidir. Confirmado por el usuario.

### D-015: unidades y tolerancia de los ejemplos de Wight

- **Fecha:** 2026-11-04
- **Problema:** la mayoría de los ejemplos de Wight están en unidades inglesas.
- **Referencia:** D-011 y D-014.
- **Decisión:** igual que D-011: convertir solo datos y resultados de cada ejemplo (25.4 mm/in, 6.894757e-3 MPa/psi), sin convertir constantes normativas, y comparar con ±1 % sobre el valor impreso. Confirmado por el usuario.

### D-016: la Fase 2 se entrega en subfases

- **Fecha:** 2026-11-04
- **Decisión:** dividir la Fase 2 en 2A (flexión), 2B (cortante), 2C (torsión), 2D (servicio), 2E (ETABS) y 2F (memorias y huella). Cada subfase se cierra con su oráculo y la CI en verde. La huella empieza en 2F, sobre el JSON de resultados y la memoria en texto. Confirmado por el usuario.

### D-017: deflexiones pendientes

- **Fecha:** 2026-11-04
- **Problema:** las deflexiones requieren momentos de servicio, y la entrada solo trae fuerzas mayoradas.
- **Alternativas:** ampliar la entrada con momentos de servicio, o dejar las deflexiones para después.
- **Decisión:** dejarlas pendientes y anotarlas en la hoja de ruta. 2D cubre solo control de fisuración y espesor mínimo. Confirmado por el usuario.

### D-018: el archivo de ETABS llega en Excel

- **Fecha:** 2026-11-04
- **Decisión:** la importación de 2E lee el archivo de ETABS en formato Excel, porque es el formato en que el usuario siempre lo tiene. Confirmado por el usuario.

### D-019: tope de fy en As,min de ACI

- **Fecha:** 2026-11-04
- **Problema:** el PDF de ACI CODE-318-25, que está en SI, limita fy en 9.6.1.2 a "80,000 psi".
- **Alternativas:** convertir a 551.6 MPa, o usar 550 MPa, el valor que el mismo documento usa en SI en sus demás límites.
- **Decisión:** 550 MPa. Confirmado por el usuario.

### D-020: deformación de fluencia εty

- **Fecha:** 2026-11-04
- **Referencia:** ACI 21.2.2.1; NSR-10 C.10.3.3.
- **Decisión:** εty = fy/Es en ambos perfiles, que es la regla general. No se usa el valor 0.002 que ambas normas permiten para acero de 420 MPa. Confirmado por el usuario.

### D-021: viga isostática con el ala a tracción

- **Fecha:** 2026-11-04
- **Referencia:** ACI 9.6.1.2; NSR-10 C.10.5.2.
- **Decisión:** el miembro declara de forma opcional si es isostático. Solo se exige en vigas T con momento negativo; si falta en ese caso, As,min queda `INCOMPLETE`. Confirmado por el usuario.

### D-022: excepción del tercio adicional de As,min

- **Fecha:** 2026-11-04
- **Referencia:** ACI 9.6.1.3; NSR-10 C.10.5.3.
- **Decisión:** no se implementa por ahora y queda pendiente en la hoja de ruta. Si As < As,min, la verificación devuelve `BLOCKED` ("no implementado"), porque la excepción podría levantar el incumplimiento. Confirmado por el usuario.

### D-023: lectura del Excel de ETABS

- **Fecha:** 2026-11-04
- **Decisión:** leer el `.xlsx` con la biblioteca estándar (`zipfile` y `xml`), sin añadir dependencias. Se versiona `examples/etabs/Element Forces - Beams.xlsx` como ejemplo real de entrada, y `AGENTS.md` aclara que la regla "Nada de Excel versionado" aplica a las tablas de `data/`. Confirmado por el usuario.

### D-024: carga axial en la flexión de vigas

- **Fecha:** 2026-11-04
- **Problema:** cómo incluir la carga axial mayorada en la resistencia a flexión de una viga.
- **Referencia:** ACI 9.5.1.1, 9.5.2.1, 21.2.2 y 22.2.1.1; NSR-10 C.10.3.1 y C.10.3.5.
- **Alternativas:** Pn = Pu/φ, iterando φ, o Pn = Pu.
- **Consecuencias:** con tracción axial, Pn = Pu sobrestima Mn frente a Pu/φ (cerca de 2 % en el ejemplo revisado); con compresión, lo subestima un poco.
- **Decisión del usuario:** en vigas, el equilibrio usa Pn = Pu, porque se busca el momento resistente del miembro sometido a la carga P. No se itera φ. Se aplica en ambos perfiles. Pu siempre es dato (si falta, `INCOMPLETE`); compresión positiva en el JSON (ETABS se invierte al importar); los momentos se toman respecto al centroide de la sección bruta, donde ETABS aplica P. Si Pu ≥ 0.10 f'c·Ag, la estación queda `BLOCKED`, porque el miembro no puede tratarse como viga. Cada miembro declara su tipo (`beam`, `column`, `footing`, `wall` o `slab`); los tipos distintos de viga quedan `BLOCKED` hasta que se implementen.
- **Para columnas (v2):** el diagrama de interacción usará Pn = Pu/φ, por indicación del usuario.

### D-025: refuerzo de tracción para As,min

- **Fecha:** 2026-11-04
- **Problema:** con el eje neutro muy alto (vigas T a momento positivo), las barras cercanas a la cara comprimida quedan a tracción y bajarían la d usada en As,min.
- **Referencia:** ACI 9.6.1.2; NSR-10 C.10.5.1. Ambas usan d, la distancia al centroide del refuerzo de tracción.
- **Alternativas:** contar solo las capas a tracción de la mitad traccionada, o todo el acero a tracción.
- **Decisión del usuario:** para As,min cuenta todo el acero a tracción en el estado nominal, y d es su centroide, pero no menor que 0.8h (D-043). En la viga T de ejemplo a momento positivo, As = 1928 mm², el centroide queda a 361.5 mm y d = 0.8h = 400 mm, así que As,min = 400 mm².

### D-026: As,min frente a los ejemplos de Wight

- **Fecha:** 2026-11-04
- **Problema:** cuando rige la expresión 1.4·bw·d/fy, As,min difiere de +1.1 % a +1.8 % de Wight (ejemplos 4-1, 4-3 vigas 1 y 3, 4-4, 4-6 y 5-3).
- **Causa:** Wight usa 200 psi (1.379 MPa) y la versión SI de ambas normas usa 1.4 MPa, más el redondeo del libro.
- **Decisión del usuario:** la diferencia es aceptable. El oráculo de Wight compara As,min con 2 % y el resto de magnitudes con 1 % (D-015).

### D-027: el refuerzo longitudinal de torsión no es As de flexión

- **Fecha:** 2026-11-04
- **Problema:** en 2C aparecerán barras longitudinales de torsión (Al), que no deben confundirse con el refuerzo de flexión.
- **Referencia:** ACI 9.5.4.3 (el refuerzo de torsión se suma al requerido por Vu, Mu y Pu) y 9.5.4.5 (reducción de Al en la zona comprimida por flexión). El numeral equivalente de NSR-10 se verificará en 2C.
- **Decisión del usuario:** las barras de Al no cuentan como As en ninguna verificación de flexión (φMn, εt y As,min). Se implementa en 2C: cada capa del armado declarará su función (flexión o torsión) y la flexión solo usará las capas de flexión.

### D-028: tipo de concreto y factor λ

- **Fecha:** 2026-11-05
- **Referencia:** ACI 19.2.4; NSR-10 C.8.6.1.
- **Decisión:** los materiales declaran de forma obligatoria el tipo de concreto (`normalweight` o `lightweight`). En la v1 solo se verifica concreto de peso normal (λ = 1); con concreto liviano, el cortante queda `BLOCKED`, sin suponer λ. Confirmado por el usuario.

### D-029: Vc en ACI con Av ≥ Av,min

- **Fecha:** 2026-11-05
- **Referencia:** ACI Tabla 22.5.5.1, filas (a) y (b), que la norma permite usar indistintamente.
- **Decisión:** se toma la mayor de las dos expresiones y se informa Vc. Con Av < Av,min se usa la fila (c), con el efecto de tamaño λs. Además, sin tracción axial neta, Vc no se toma menor que 0.083λ√f'c·bw·d, como permite 22.5.5.1.1. Confirmado por el usuario.

### D-030: Vc en NSR-10

- **Fecha:** 2026-11-05
- **Referencia:** NSR-10 C.11.2.1 (método simple) y C.11.2.2 (método detallado, con ρw, Vu·d/Mu y carga axial).
- **Decisión del usuario:** se calculan ambos métodos y se toma el mayor. Con tracción axial, el método simple da Vc = 0 (C.11.2.1.3) y rige el detallado (C.11-8); así no hace falta juzgar si la tracción es "significativa".

### D-031: coeficiente de ACI 9.6.3.1

- **Fecha:** 2026-11-05
- **Problema:** el PDF en SI escribe la condición como "Vu > φλ√f'c·bw·d", sin coeficiente, que es la forma de la versión en psi.
- **Alternativas:** usar 1.0 literal, o 0.083, el equivalente en SI que el mismo documento usa en 22.5.5.1.1 y en el umbral de torsión.
- **Decisión:** Av,min se exige si Vu > φ·0.083λ√f'c·bw·d. Confirmado por el usuario.

### D-032: alcance del cortante en 2B

- **Fecha:** 2026-11-05
- **Decisión:**
  - El umbral de torsión (ACI 9.5.4.1 y Tabla 22.7.4.1(a); NSR-10 C.11.5.1) se adelanta a 2B. Si Tu ≥ φTth, el cortante de la estación queda `BLOCKED` hasta 2C. El umbral se calcula con la sección del alma (bw·h), que nunca da un valor mayor que el de la norma con alas.
  - La excepción de Av,min para viga integral con losa solo se aplica a vigas T, porque su ala da el espesor de la losa.
  - La sección crítica la elige el usuario con sus estaciones (ACI 9.4.3.2, NSR-10 C.11.1.3); la aplicación no la reubica.
  - d y ρw salen del acero a tracción del estado nominal a flexión (D-025).
  - fyt se limita a 420 MPa (ACI Tabla 20.2.2.4(a) para estribos de barra; NSR-10 C.11.4.2).
  - El recubrimiento libre a los estribos (`cover`) es dato de la sección; ACI lo usa para la separación de ramas a lo ancho y 2C para la torsión.

  Confirmado por el usuario.

### D-033: Vc y Av,min frente a los ejemplos de cortante de Wight

- **Fecha:** 2026-11-05
- **Problema:** Vc difiere de +1.7 % a +2.4 % de Wight, la separación requerida por resistencia de +1.0 % a +3.7 % y la separación máxima por Av,min −4.8 % (6-1M) y −1.7 % (6-1).
- **Causa:** el libro usa 2√f'c en psi (0.166√f'c en MPa) o 1/6 para Vc, y 1/3 MPa o 50 psi para Av,min; la versión SI de ambas normas usa 0.17 y 0.35.
- **Decisión del usuario:** la diferencia es aceptable. El oráculo de cortante de Wight compara Vc y la separación por resistencia con 4 %, la separación por Av,min con 5 % y el resto con 1 % (D-015).

### D-034: entrada para torsión

- **Fecha:** 2026-11-05
- **Decisión:**
  - Cada capa del armado declara su función (`role`: `flexure` o `torsion`). La flexión solo usa las capas de flexión, y Aℓ solo las de torsión (D-027).
  - Cada estribo declara si es cerrado (`closed`). La torsión exige estribos cerrados (ACI 9.7.6.3.1, NSR-10 C.11.5.4.1); si no lo son, la verificación transversal da `FAIL`.
  - θ = 45° en ambos perfiles (ACI 22.7.6.1.2, NSR-10 C.11.5.3.6).
  - Las reducciones permitidas (Tu a φTcr en torsión de compatibilidad, y Aℓ en la zona comprimida) y las secciones huecas quedan pendientes en la hoja de ruta.

  Confirmado por el usuario.

### D-035: barras de esquina y área de Aℓ

- **Fecha:** 2026-11-05
- **Problema:** ACI 9.7.5.1 y NSR-10 C.11.5.6.2 piden al menos una barra longitudinal en cada esquina de los estribos, y con D-027 esas barras suelen ser de flexión.
- **Alternativas:** (A) cumplir las esquinas con cualquier barra longitudinal y contar para Aℓ solo las barras de torsión; (B) acreditar a Aℓ el sobrante de As en las esquinas; (C) exigir barras de torsión en las esquinas, lo que es físicamente imposible.
- **Decisión del usuario:** opción A. La distribución se verifica con todas las capas: al menos dos barras en las capas extremas, separación ≤ 300 mm en esas capas y entre capas consecutivas. El diámetro mínimo se exige a las barras de torsión.

### D-036: alas en torsión

- **Fecha:** 2026-11-05
- **Referencia:** ACI 9.2.4.4; NSR-10 C.11.5.1.1 y C.13.2.4.
- **Decisión:**
  - Las secciones con ala declaraban `flange_sides` (1 para viga L, 2 para viga T); desde D-045 declaran los salientes a cada lado.
  - Acp y pcp se calculan con el saliente efectivo por lado, el menor entre el saliente real, h − hf y 4hf. Las alas se ignoran si reducen Acp²/pcp.
  - Así se calculan el umbral de torsión, que reemplaza el umbral solo con el alma de D-032, y Aℓ,min.
  - Aoh y ph salen solo del alma, porque los estribos cerrados están en ella.

  Confirmado por el usuario.

### D-037: combinación de cortante y torsión en los estribos

- **Fecha:** 2026-11-05
- **Referencia:** ACI 9.5.4.3 y 22.7.6.1; NSR-10 C.11.5.3.8 y CR11.5.3.8.
- **Decisión:**
  - Si Tu ≥ φTth, la resistencia a cortante, Av,min y la separación de 2B se reemplazan por sus versiones combinadas.
  - Se exige Av/s + 2At/s ≤ n·Ab/s, y At/s ≤ Ab/s, porque solo las ramas exteriores resisten torsión.
  - La separación es la menor entre la de cortante y la de torsión (ph/8 y 300 mm).
  - Aℓ requerido usa la formulación de cada perfil: ACI 22.7.6.1(b) y NSR-10 (C.11-22), que coinciden con θ = 45°.
  - Aℓ,min usa el At/s requerido, como Wight.

  Confirmado por el usuario.

### D-038: Aℓ,min frente al ejemplo 7-2 de Wight

- **Fecha:** 2026-11-05
- **Problema:** Aℓ,min sale 0.526 in² frente a 0.51 in² del libro (+3.2 %).
- **Causa:** el libro usa 5√f'c (psi), que equivale a 0.415√f'c en MPa; ambas normas en SI usan 0.42√f'c, y la resta de At/s·ph amplía la diferencia relativa.
- **Decisión del usuario:** la diferencia es aceptable. El oráculo de torsión de Wight compara Aℓ,min con 4 %.

### D-039: orden de las subfases

- **Fecha:** 2026-11-05
- **Decisión del usuario:** después de 2C siguen 2E (ETABS) y 2F (memorias y huella). La subfase 2D (servicio) queda pendiente.

### D-040: formato de las barras de cada capa

- **Fecha:** 2026-11-06
- **Problema:** una capa debe admitir diámetros distintos y posiciones libres, y el eje débil necesita la posición horizontal de cada barra.
- **Decisión:**
  - Cada capa lista sus barras de izquierda a derecha en `bars`, con dos formas.
  - Forma corta: solo las designaciones, repartidas de forma uniforme entre las esquinas interiores del estribo, a recubrimiento + estribo + db/2 de cada cara. Una barra sola va centrada.
  - Forma explícita: cada barra con su `z`, la distancia de la cara izquierda del alma a su centro.
  - Una capa usa una sola forma. Desaparecen `designation` y `count`.
  - `depth` es la profundidad de los centros de la capa.
  - La validación exige barras dentro del estribo y en orden.
  - La distribución de Aℓ (D-035) usa ahora las posiciones reales. Una barra ocupa la esquina si su centro está a no más de un diámetro de la posición de esquina.

  Confirmado por el usuario.

### D-041: eje débil (M2 y V3)

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - Se verifican también M2 y V3.
  - La flexión se resuelve con un análisis biaxial por fibras: el polígono real de la sección, con sus alas, y el bloque equivalente con el eje neutro inclinado (c perpendicular al eje neutro, ACI 22.2.2.4.2 y NSR-10 C.10.2.7.2). Se verifica a carga axial constante (Pn = Pu, D-024), en la dirección del momento demandado. El mismo motor servirá para columnas.
  - El cortante V3 usa ancho h, d hasta el acero a tracción del estado girado y las ramas horizontales del estribo (2 si es cerrado, 1 si es abierto). En ACI se aplica la interacción de 22.5.1.10 y 22.5.1.11; NSR-10 verifica cada dirección por separado.
  - Con torsión, las ramas horizontales cumplen Av3/s + 2At/s ≤ (ramas horizontales)·Ab/s.
  - Las estaciones llevan `M2_kNm` y `V3_kN`, obligatorios como Pu (0 si no hay).
  - Se implementa en 2E.2, después de la importación desde ETABS (2E.1).

### D-042: importación desde ETABS

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - Comando `import-etabs`: genera el JSON del proyecto a partir del Excel de ETABS y de una plantilla con perfil, nivel sísmico, materiales, secciones y tramos de armado.
  - Cada viga se identifica por su Unique Name.
  - Se usan todas las filas de tipo "Combination", con la opción de dar una lista; otros tipos de caso se rechazan.
  - Las filas "Max" y "Min" de las combinaciones con envolvente se tratan como dos estados de carga, como en el diseño de ETABS.
  - Las unidades se leen de la fila de unidades de la tabla, y se exigen m, kN y kN-m.
  - P se invierte para que la compresión sea positiva, y m se convierte a mm.
  - Toda estación debe quedar dentro de un tramo de armado de la plantilla; si no, la importación da error.

### D-043: d no menor que 0.8h

- **Fecha:** 2026-11-06
- **Problema:** con tracción axial y momento pequeño, casi toda la sección queda a tracción. Con D-025, d es el centroide de las barras superiores e inferiores juntas: en el ejemplo de ETABS, 192 mm en lugar de 440 mm. Eso reducía a la mitad el límite de separación d/2, y también Vc y el límite de la sección.
- **Referencia:** ACI 22.5 y NSR-10 C.11 definen d hasta el centroide del refuerzo a tracción, sin tratar secciones casi toda a tracción. ACI 22.5.2.1(a) permite d = 0.8h en columnas rectangulares.
- **Alternativas:** d de las barras de la mitad opuesta a la cara comprimida; mantener D-025; o d no menor que 0.8h.
- **Decisión del usuario:** en As,min, en el cortante y en la torsión, d es el centroide del acero a tracción del estado a flexión, pero no menor que 0.8h, en secciones rectangulares, T y L y en ambos perfiles. ρw usa esa misma d. El acero que cuenta sigue siendo todo el acero a tracción (D-025).

### D-044: ejes y signos de ETABS

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - Se usan los ejes locales de ETABS: Y = eje 2 (vertical, hacia arriba), X = eje 3 (horizontal) y Z = eje 1 (eje del miembro), con Z = Y × X por la regla de la mano derecha de 2 a 3.
  - La posición de una estación a lo largo del miembro es `z`. La posición horizontal de una barra es `x`, medida sobre el eje 3 desde la cara del alma del lado −3; `depth` sigue midiéndose desde la cara superior.
  - M3 (`Mu_kNm`) positivo comprime la cara +2 (superior), comprobado con los datos del usuario. M2 (`M2_kNm`) positivo comprime la cara +3 (x = bw), comprobado por el usuario en ETABS.
  - Vu es V2 y `V3_kN` es el cortante horizontal. M2 y V3 son obligatorios como Pu (0 si no hay).
  - La importación pasa M2 y V3 con el signo de ETABS; solo P cambia de signo.

### D-045: salientes del ala y barras en el ala

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - Una sección con ala declara `hf`, `overhang_x_neg` (saliente hacia −3) y `overhang_x_pos` (hacia +3), con 0 en el lado sin ala; reemplazan a `bf` y `flange_sides` (D-036).
  - La torsión aplica el saliente efectivo, el menor entre el real, h − hf y 4hf, a cada lado por separado.
  - Una barra de flexión puede quedar fuera del alma si está a la altura del ala (depth ≤ hf) y dentro de ella, con el recubrimiento en sus bordes. Las barras de torsión van dentro de los estribos.
  - Nueva forma de capa por separación, para la malla del ala: `{"designation": "#4", "spacing": 200, "from": x0, "to": x1}`.
  - Las barras del ala con `role: flexure` cuentan como As.

### D-046: flexión y cortante en los dos ejes

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - La resistencia a flexión se verifica siempre con un motor biaxial por fibras: el polígono real de la sección, con sus alas, y las barras en su posición, con Pn = Pu (D-024), en la dirección de (Mu3, Mu2).
  - La εt mínima se verifica en tres estados: M3 solo, M2 solo y el biaxial.
  - As,min se verifica en los dos ejes. En el eje débil el ancho es h y d es el del estado girado, no menor que 0.8 veces el ancho total en esa dirección (bw, o bw más los salientes).
  - El cortante se verifica en las dos direcciones: V2 con ancho bw y ramas verticales, y V3 con ancho h y ramas horizontales. En ACI se aplica la interacción de 22.5.1.10 y 22.5.1.11; NSR-10 verifica cada dirección por separado.
  - La separación del eje débil se compara con su propia d. En ACI, la separación vertical entre ramas horizontales se compara con esa d.
  - Con torsión, las ramas horizontales cumplen Av3/s + 2At/s ≤ (ramas horizontales)·Ab/s.

### D-047: d del cortante V3

- **Fecha:** 2026-11-06
- **Problema:** con la regla de As,min del eje débil (d ≥ 0.8 veces el ancho total), una viga T con salientes grandes tendría una d del cortante V3 mucho mayor que la real, porque los estribos solo están en el alma. Eso aumentaría Vs, del lado inseguro.
- **Decisión:** en el cortante V3, d es el centroide del acero a tracción del estado de M2 solo, no menor que 0.8bw (el alma). As,min del eje débil mantiene 0.8 veces el ancho total (D-046), que solo aumenta el acero exigido. Confirmado por el usuario.

### D-048: separación de estribos en el eje débil

- **Fecha:** 2026-11-06
- **Problema:** con d del eje débil cercana a 0.8bw, el límite d/2 es de unos 120 mm en una viga de 300 mm de ancho. Aplicarlo siempre haría fallar casi cualquier viga aunque V3 sea 0.
- **Referencia:** ACI 9.7.6.2.2 y NSR-10 C.11.4.5 limitan la separación del refuerzo a cortante.
- **Decisión:** la separación y el Av,min del eje débil se verifican solo si V3 exige refuerzo, es decir, si |V3| supera el umbral de Av,min de esa dirección. Confirmado por el usuario.

### D-049: orientación del eje neutro cuando hay varias soluciones

- **Fecha:** 2026-11-06
- **Problema:** con M2 casi nulo, varias orientaciones del eje neutro, separadas menos de 0.3°, dan la misma dirección de momento. Ocurre por los saltos de fuerza cuando el bloque alcanza o deja una barra. La resistencia es la misma, pero εt del estado biaxial cambia un poco: en el ejemplo de ETABS, 0.01529 o 0.01560.
- **Decisión:** la búsqueda parte de la orientación estimada (θ = 90° − dirección del momento) y toma la solución que encuentra al avanzar desde ella, en pasos de 5° y con refinamiento por regula falsi. Si no encuentra un cambio de signo, recorre media vuelta. Así la búsqueda es 19 veces más rápida (94 s → 5 s en las 638 estaciones de ETABS) y elige la solución más cercana en los casos casi uniaxiales.

### D-050: memorias y resultados

- **Fecha:** 2026-11-06
- **Decisión del usuario:**
  - El comando `report` escribe en la carpeta de salida `resultado.json` (todo el detalle), `memoria.txt` y `memoria.pdf`.
  - El JSON y la memoria usan unidades de presentación (kN, kN·m, mm, MPa) y redondean a 6 cifras significativas; el cálculo interno no se redondea.
  - La memoria tiene datos y supuestos (con el nivel sísmico y su justificación), un resumen por miembro con la estación crítica de cada verificación, el detalle de todo lo que no cumple y el detalle de las estaciones críticas; `--full` agrega todas las estaciones.
  - La memoria se construye solo desde el resultado, así que φ, las capacidades y los numerales no se escriben como literales.
  - El PDF requiere el extra `pdf` (fpdf2); si no está, se generan los otros dos archivos con un aviso. Sus fuentes básicas solo admiten Latin-1, así que los caracteres fuera de ese rango se escriben con equivalentes en ASCII.

### D-051: huella de los ejemplos

- **Fecha:** 2026-11-06
- **Decisión del usuario:** la huella es el SHA-256 de `resultado.json` y `memoria.txt`, sin fecha, para los ejemplos de `examples/<perfil>/` y para el proyecto importado de ETABS. Se guarda en `tests/fingerprints.json` y la compara `tests/test_fingerprints.py`. Solo se actualiza (`STRUCTURELAB_UPDATE_FINGERPRINTS=1 pytest tests/test_fingerprints.py`) después de reportar un cambio de cálculo intencional.

### D-052: alcance y criterios de la v3 (zapatas)

- **Fecha:** 2026-11-07
- **Referencias:** ACI 318-25 cap. 13 (13.2.6, 13.2.7, 13.3) y NSR-10 C.15; presión del suelo según Bellos y Bakas (2017), `references/bellos2017.pdf`.
- **Decisión del usuario:**
  1. Alcance: zapata aislada rectangular de espesor constante sobre suelo, con una columna rectangular (las circulares o poligonales como cuadradas de igual área, ACI 13.2.7.3 y NSR-10 C.15.3), que puede ir desplazada del centro. Quedan pendientes las zapatas combinadas, medianeras con viga de amarre, losas de cimentación, pilotes, zapatas escalonadas y muros.
  2. Las cargas de servicio llegan en un Excel de ETABS distinto del de cargas mayoradas. Las de servicio se usan para la presión admisible y el contacto (ACI 13.3.1.1, NSR-10 C.15.2.2); las mayoradas, para el diseño estructural. No se generan combinaciones.
  3. En resistencia, la presión neta sale de las cargas de la columna: el peso de la zapata y del relleno se cancela con la reacción uniforme que produce. En servicio se suman; el usuario declara el peso unitario del concreto y del relleno y la altura del relleno, sin valores por defecto.
  4. Las fuerzas se declaran en la base de la columna y se trasladan al centroide de la base: M_base = M + V·(h + altura del pedestal) + P·desplazamiento de la columna. Convención global de ETABS: Z hacia arriba, ex = My/P y ey = −Mx/P.
  5. El contacto se verifica solo con las cargas de servicio: se reportan la región de Bellos y la fracción de contacto, y la verificación es FAIL si no hay equilibrio (la resultante sale de la base) o si la fracción de contacto es menor que el mínimo declarado por el usuario, que es un dato obligatorio. Gobierna la condición más exigente.
  6. El punzonamiento incluye la fracción γv·Msc del momento en los dos ejes (ACI 8.4.4.2 y 22.6, NSR-10 C.11.11.7); Msc es el momento de la columna menos el de la presión dentro del perímetro crítico.
  7. La presión para resistencia también sigue la distribución de Bellos con las cargas mayoradas, con levantamiento si lo hay (ACI R13.2.6.3, NSR-10 CR15.2), no la presión uniforme P/A.
  8. La malla superior se incluye desde la v3.

### D-053: implementación de la presión del suelo

- **Fecha:** 2026-11-07
- **Decisión:** `mechanics/soil_pressure.py` aplica las Ecs. 8 y 13 a 31 de Bellos y Bakas (2017) y describe la presión como el plano p0 + gx·x + gy·y recortado en cero, con origen en el centroide de la base. Usa 1/xn y 1/yn en lugar de los interceptos, que son infinitos cuando el eje neutro es paralelo a un lado. En la región B, la Ec. 28 se resuelve con Newton (1 a 4 iteraciones) en lugar de la iteración directa del artículo, que cerca del borde con la región C no llega a 10⁻⁶ en 500 pasos. `mechanics/polygon.py` reúne el recorte y las integrales exactas que usan la sección y la presión del suelo.
- **Verificación:** las fórmulas de las cinco regiones coinciden con un equilibrio resuelto por Newton, independiente del paquete, con error relativo de 10⁻¹¹ (`tests/oracles/derive_soil_pressure.py`), y con los casos frontera 1 a 5 del artículo.
- **Erratas del artículo, reportadas al usuario:**
  - En la Ec. 25 aparece (1/2 − |ex|/ly); por simetría con la Ec. 21 es (1/2 − |ex|/lx), y así se implementa.
  - La Tabla 1 no se usa como oráculo: en la combinación B, ey = −0.003 m no corresponde a las presiones de las esquinas, que implican |ey| ≈ 0.022 m (probablemente 0.023).

### D-054: peso propio en la presión mayorada y casos sin equilibrio (C-010)

- **Fecha:** 2026-11-07
- **Problema:** con la malla superior (D-052, punto 8), el momento negativo lo produce el peso de la zapata y del relleno sobre la zona sin contacto. Ese peso entra en la presión mayorada con el factor de carga muerta de cada combinación, que la aplicación no genera.
- **Decisión del usuario:**
  - La plantilla declara, para cada combinación mayorada, su factor de carga muerta; es un dato obligatorio. La presión mayorada sale de las cargas de la columna más el peso factorado de la zapata y del relleno. Con contacto total, el resultado en la malla inferior es el mismo que con la presión neta (D-052, punto 3), porque el peso uniforme se cancela.
  - Un caso mayorado cuya resultante sale de la base, o cuya carga total no es de compresión, es FAIL ("la resultante mayorada sale de la base").

### D-055: entrada de zapatas e importación de ETABS

- **Fecha:** 2026-11-07
- **Decisión del usuario:**
  1. La presión admisible se declara en kPa y los pesos unitarios en kN/m³; se convierten a MPa y N/mm³ al cargar.
  2. Las filas Max y Min de una combinación con envolvente son estados de carga distintos, como en vigas (D-042).
  3. lx va a lo largo de X global y ly a lo largo de Y global; las zapatas rotadas quedan pendientes.
  4. La plantilla agrupa los nudos en tipos de zapata: cada tipo lista sus Unique Name y declara dimensiones, columna, relleno, pedestal y mallas. El importador crea una zapata por nudo, con id `<tipo>-<Label de ETABS>`.
  5. Las propiedades que se derivan de las dimensiones (área, inercias, módulos de sección, núcleo central, volúmenes y pesos) se calculan y se reportan; nunca se declaran.
- **Implementación:**
  - Las tablas "Joint Reactions" dan la fuerza del apoyo sobre la estructura; la acción sobre la zapata es la opuesta: P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY, en la base de la columna.
  - El pedestal tiene la sección de la columna y el relleno ocupa el área de la base menos la de la columna en toda su altura.
  - Cada malla declara qué dirección va más cerca de la cara (`first`), porque eso define la d de cada dirección.
  - Mientras no existan V3C y V3D, cada zapata devuelve una verificación `BLOCKED`.

### D-056: verificación geotécnica de zapatas (V3C)

- **Fecha:** 2026-11-07
- **Referencias:** ACI 318-25 13.3.1.1 y NSR-10 C.15.2.2 (área de la base con cargas sin mayorar y presión admisible); Bellos y Bakas (2017) para la presión.
- **Implementación de D-052 (puntos 2 a 5):**
  - Por cada caso de servicio, la resultante en el centroide de la base suma la columna y los pesos sin mayorar: Mx_base = Mx − P·oy − H·Vy y My_base = My + P·ox + H·Vx, con H = h + altura del pedestal. El pedestal pesa en el eje de la columna y desplaza el relleno de esa área. ex = My_base/N y ey = −Mx_base/N.
  - "Presion admisible del suelo": pmax ≤ qa. Como los pesos de la zapata y del relleno están incluidos, pmax es la presión bruta y qa se compara como presión admisible bruta.
  - "Contacto con el suelo": la fracción de la base en contacto debe ser al menos el mínimo declarado. La razón que se reporta es el mínimo sobre la fracción, de modo que cumple con razón ≤ 1. La nota indica la región de Bellos.
  - Sin equilibrio (N ≤ 0 o resultante fuera de la base), las dos verificaciones del caso son FAIL.
  - Sin casos de servicio, la verificación es INCOMPLETE. Los casos mayorados no se usan para el contacto.
- **Oráculo:** `tests/oracles/derive_footing_service.py` calcula el momento como suma de r × F de cada fuerza, sin importar el paquete; 8 casos por perfil.

### D-057: sobrecargas superimpuestas y factores de carga por combinación

- **Fecha:** 2026-11-07
- **Decisión del usuario:** cada zapata declara una sobrecarga superimpuesta muerta y otra viva, en kN/m², sobre el relleno. qa es una presión admisible bruta (confirma D-056).
- **Consecuencia:** la carga viva no está en todas las combinaciones (SERVICIO 2 es D+EX+EZ) y su factor cambia entre las mayoradas (1.6, 1.0 o 0). Por eso cada caso, de servicio o mayorado, declara `dead_factor` y `live_factor`. En la plantilla de ETABS, `load_factors` da `{"dead", "live"}` para cada combinación de las dos tablas, y reemplaza a `dead_load_factors` (D-054).
- **Implementación:** las sobrecargas actúan sobre el área de la base menos la de la columna, como el relleno. dead_factor multiplica los pesos propios y la sobrecarga muerta; live_factor, la sobrecarga viva. En servicio los factores son los de la combinación (por ejemplo 1 y 1 en D+L, 1 y 0 en D+E).

### D-058: estructura de ejemplos y resultados

- **Fecha:** 2026-11-07
- **Decisión del usuario:**
  - `examples/` y `results/` se organizan por perfil (`aci_318_25`, `nsr_10`) y dentro de cada uno por tipo de elemento (`vigas`, `zapatas`); ETABS va aparte, en `etabs/<elemento>/`.
  - Los campos de entrada y de salida se documentan una sola vez por elemento, en `docs/formatos/` (`vigas.md`, `zapatas.md`, `etabs.md`), porque el formato no depende del perfil. Cada carpeta de ejemplos tiene un `LEEME.md` corto con sus ejemplos, cómo correrlos y lo propio del perfil; `examples/README.md` es el índice.
  - Los archivos de ejemplo se nombran en español, como las carpetas: `viga_rectangular.json`, `viga_t.json`, `zapata_aislada.json`. Los valores del JSON (por ejemplo `"type": "beam"`) siguen en inglés, como el código.
- **Implementación:** Git guarda solo el esqueleto de `results/` (`.gitkeep`). La plantilla de vigas de ETABS se renombró a `plantilla_vigas_nsr10.json`. La huella conserva los mismos hashes de las vigas con las rutas nuevas.

### D-059: criterios de la verificación estructural de zapatas (V3D)

- **Fecha:** 2026-11-07
- **Referencias:** ACI 318-25 13.2.6, 13.2.7, 13.3, 8.6.1, 8.7.2.2, 22.6, 8.4.4.2, 22.8, 25.4; NSR-10 C.15.4 a C.15.8, C.10.5.4, C.7.12, C.11.11, C.10.14, C.12.
- **Hallazgo:** la Tabla 22.6.5.2 del ACI 318-25 escribe (b) y (c) como (0.17 + 0.33/β) y (0.17 + 0.083αs·d/b0), distintas de la NSR-10 (C.11.11.2.1), que conserva 0.17(1 + 2/β) y 0.083(αs·d/b0 + 2). Cada perfil usa su ecuación.
- **Decisión del usuario:**
  1. El acero mínimo adicional de ACI 8.6.1.2 (si vuv > φ0.17√f'c·λs·λ) aplica a las zapatas, con λs = 1 (13.2.6.2(b)). La NSR-10 no tiene ese requisito.
  2. As,min = 0.0018Ag lo cumple la malla inferior completa. La malla superior lo cumple solo si hay momento negativo.
  3. Un momento negativo en una zapata sin malla superior se resistiría como concreto simple (ACI cap. 14, NSR-10 C.22), que no está implementado: la verificación sale BLOCKED. El diseño en concreto simple queda pendiente en la hoja de ruta.
  4. La dirección corta de una zapata rectangular admite una separación propia en la franja central de ancho igual al lado corto (ACI 13.3.3.3, NSR-10 C.15.4.4.2); se verifica que el acero de la franja sea al menos γs·As requerido.
  5. Punzonamiento: el perímetro crítico a d/2 se recorta con la base. Con los cuatro lados dentro, αs = 40; con un lado fuera, αs = 30; con dos lados fuera, αs = 20 (ACI 22.6.5.3 y R22.6.5.3; NSR-10 C.11.11.2.1). b0 cuenta solo los lados dentro de la base.
  6. Aplastamiento: en la v3 se verifica solo la cara de la zapata (A2 del tronco de pirámide 1:2). El lado de la columna se verificará con las columnas.
  7. Pasadores (C-011, aprobado): en la v3, `column.dowels` (designación y cantidad) es obligatorio y su ausencia da INCOMPLETE. Se verifican el área ≥ 0.005Ag de la columna (ACI 16.3.4.1, NSR-10 C.15.8.2.1), el anclaje a compresión ldc dentro del espesor de la zapata (ACI 25.4.9, NSR-10 C.12.3) y que los pasadores tomen la compresión que excede el aplastamiento de la cara de la zapata (ACI 16.3.3.4, NSR-10 C.15.8.1.2(a)). El aplastamiento del lado de la columna, el empalme con sus barras y la tracción a través de la interfaz quedan para las columnas.
  8. Cada malla declara si sus barras terminan rectas o con gancho estándar; se verifica ld o ldh desde la cara de la columna.

### D-060: flexión común a todos los elementos

- **Fecha:** 2026-11-07
- **Decisión del usuario:** el código se mantiene DRY: el momento resistente nominal de una zapata se calcula igual que el de una viga, con el mismo código.
- **Implementación:** `domain/flexure_strength.py` reúne lo que no es propio de un elemento: modelos de material del perfil, φ según εt, la resistencia de una sección rectangular sobre el motor de `mechanics`, el As requerido para un Mu (por bisección) y la verificación de εt mínima. `domain/beam/flexure.py` lo usa y se eliminó su copia. En `codes/<perfil>`, `beam_min_net_tensile_strain` pasó a `min_net_tensile_strain`, porque vale igual para vigas, losas y zapatas (ACI 9.3.3.1, 7.3.3.1 y 8.3.3.1; NSR-10 C.10.3.5); cada elemento cita su numeral. La huella de las vigas no cambió.

### D-061: implementación de la flexión de zapatas (V3D.1)

- **Fecha:** 2026-11-07
- **Implementación:**
  - Carga neta por caso mayorado: presión de Bellos con la resultante factorada (D-054, D-057) menos las cargas uniformes sobre el voladizo, fd·(γc·h + γf·hf + qD) + fl·qL.
  - Momento en las cuatro caras de la columna con todo el ancho (ACI 13.2.6.6, NSR-10 C.15.4.1): positivo tracciona la malla inferior y negativo la superior. La resistencia es la de la sección rectangular del ancho total con la capa de esa dirección y su propia d (la segunda capa de la malla tiene d menor).
  - Barras: n = ⌊(ancho − 2·recubrimiento − db)/s⌋ + 1, centradas en el ancho útil. Con band_spacing, la franja central (lado corto, centrada en la columna) lleva su separación y fuera rige spacing desde la última barra de la franja. Sin band_spacing, la franja cuenta las barras uniformes que caen en ella.
  - εt, As,min, separación máxima, franja γs y altura mínima se verifican una vez por zapata. As,min de la malla superior y su franja, solo si algún caso produce momento negativo en esa dirección. La franja exige γs·As, con As el mayor entre el requerido por el momento y As,min.
  - Altura mínima: ACI 13.3.1.2 mide la d del refuerzo inferior (se toma la de la segunda capa); NSR-10 C.15.7 mide la altura sobre el refuerzo inferior (desde la cara superior de la malla).
- **Oráculo:** `tests/oracles/derive_footing_flexure.py`, sin importar el paquete: momentos por integración exacta sobre el voladizo y resistencia con el bloque de Whitney; 5 casos por perfil.

### D-062: ejemplo 15-3 de Wight y cuantía mínima de NSR-10 por tramos (C-012)

- **Fecha:** 2026-11-07
- **Diferencias reportadas:** Mu = 891.3 kip·ft frente a 891 (0.03 %) y As,min ACI = 8.94 in² (igual). φMn = 1357.7 (barras x, d = 32.5 in) y 1315.1 kip·ft (barras y, d = 31.5 in) frente a 1340 de Wight, que usa d promedio = 32 in: +1.3 % y −1.9 %.
- **Decisión del usuario:**
  1. Se mantiene la d de cada capa y φMn se compara con Wight con ±2 % (`tests/oracles/<perfil>/wight_footing.json`); Mu, As,min y el número de barras, con ±1 % (D-015).
  2. NSR-10 C.7.12.2.1 se lee por tramos de fy: 0.0020 con fy ≤ 350 MPa (grados 280 y 350), 0.0018 con 350 < fy ≤ 420 MPa (grado 420) y 0.0018·420/fy con fy > 420 MPa, no menor que 0.0014. Así el Grado 60 convertido (413.7 MPa) usa 0.0018.

## Consultas abiertas

Ninguna.
