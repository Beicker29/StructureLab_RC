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

## Consultas abiertas

Ninguna.
