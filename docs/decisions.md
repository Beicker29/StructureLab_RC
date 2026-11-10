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

> El momento negativo sin malla superior ya no queda BLOCKED: ver D-072.

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

### D-063: cortante en una dirección y punzonamiento de zapatas (V3D.2)

- **Fecha:** 2026-11-07
- **Implementación, con la regla DRY (D-060):**
  - `domain/footing/loads.py` reúne la carga neta de cada caso mayorado y su integración a un lado de un plano; la usan la flexión (plano en la cara) y el cortante en una dirección (plano a d de la cara, con la d de las barras de esa dirección, ACI 13.2.7.2 y NSR-10 C.15.5.2).
  - Vc en una dirección: NSR-10 usa la misma función de vigas (`codes/nsr_10/shear.concrete_shear`, D-030) con Vu y Mu de la sección y ρw de la malla; ACI tiene su propia ecuación de zapatas (13.2.6.2(a), 0.17λ√f'c·b·d). El límite √f'c ≤ 8.3 MPa se toma de `limited_sqrt_fc`, ahora pública en los dos perfiles.
  - `mechanics/perimeter.py` calcula el perímetro crítico a d/2 recortado con la base (lados fuera: αs = 30 o 20, D-059), su centroide y Jc a partir de los lados que quedan; para la columna interior coincide con ACI R8.4.4.2.3. d es el promedio de las dos capas de la malla inferior (ACI 22.6.2.1).
  - `domain/shear_strength.py` evalúa el cortante en dos direcciones para cualquier elemento: vu = Vu/(b0·d) + γv·Msc·c/Jc en los dos ejes, máximo en los extremos de los lados, frente a φvc del perfil (ACI Tabla 22.6.5.2 con λs = 1 por 13.2.6.2(b); NSR-10 C.11.11.2.1). Vu y Msc son la fuerza y el momento, respecto al centroide de los lados, de la carga neta fuera del área crítica. γf = 1/(1 + (2/3)√(b1/b2)) con b1 y b2 del área crítica.
  - ACI 8.6.1.2: cuando vuv > φ0.17√f'c, se exige As,min = 5vuv·bslab·b0/(φαs·fy) con las barras de la malla inferior dentro de bslab = c + 3h, en cada dirección.
  - La presión de los casos mayorados se calcula una sola vez por zapata y la comparten flexión y cortante.
- **Oráculo:** `tests/oracles/derive_footing_shear.py`, sin importar el paquete: integración exacta y Jc por cuadratura numérica; 6 casos por perfil (interior, con momento, borde, esquina, columna alargada con β = 3 y zapata delgada).

### D-064: cortante del ejemplo 15-3 de Wight (C-013)

- **Fecha:** 2026-11-07
- **Diferencias reportadas:** punzonamiento dentro de ±1 % (Vu = 712.4 frente a 712 kips, b0 = 200 in, vu = 111.3 frente a 111 psi, φvc = 176.3 frente a 177 psi). Una dirección: Vu = 163.4 y 169.35 kips frente a 166 (−1.6 % y +2.02 %) y φVc = 407.4 y 394.9 kips frente a 392 (+3.9 % y +0.7 %). Causas: la d de cada capa frente a la d promedio (D-062); el ACI en SI usa 0.17√f'c (MPa) y Wight 2√f'c (psi) = 0.166√f'c (+2.4 %; D-015 no convierte constantes); y Wight imprime 166 kips aunque su cálculo da 166.37.
- **Decisión del usuario:** el ejemplo se compara en `tests/oracles/<perfil>/wight_footing.json` con ±1 % en el punzonamiento, ±2.5 % en Vu de una dirección y ±4 % en φVc de una dirección. El valor impreso del libro no se modifica.

### D-065: desarrollo, aplastamiento y pasadores de zapatas (V3D.3)

- **Fecha:** 2026-11-07
- **Decisión del usuario (recomendaciones aprobadas):**
  1. ld con la ecuación detallada (ACI 25.4.2.4, NSR-10 C.12.2.3) y Ktr = 0; cb es el menor entre la distancia del centro de la barra a la superficie más cercana y la mitad de la separación.
  2. Sin reducciones opcionales en la v3: ni As requerido/As suministrado (ACI 25.4.10.1, NSR-10 C.12.2.5) ni los factores de gancho por recubrimiento o confinamiento (ACI ψcc = ψr = 1.0, permitido por 25.4.3.2; NSR-10 sin C.12.5.3). Quedan pendientes en la hoja de ruta.
  3. Longitud disponible: la menor distancia de una cara de la columna al borde, menos el recubrimiento del extremo; malla superior solo con momento negativo en esa dirección y ψt = 1.3 si hay más de 300 mm de concreto debajo.
  4. La compresión que excede φBn la toman los pasadores: As ≥ (Pu − φBn)/(φ·fy) con φ = 0.65.
  5. Los pasadores llegan a la malla inferior: espacio para ldc = h − recubrimiento − db1 − db2; el gancho no cuenta a compresión.
- **Implementación (DRY):** las longitudes de desarrollo están en `codes/<perfil>/development.py` y el aplastamiento en `codes/<perfil>/bearing.py`, reutilizables por vigas y columnas; `domain/development.py` elige la ecuación (recta, gancho o compresión) y arma el Check; `domain/footing/connection.py` solo calcula longitudes disponibles, A2 y los pasadores. A2 es la base del tronco de pirámide 1:2 bajo la columna contenido en la zapata: (cx + 2k)(cy + 2k), con k el menor entre 2h y las distancias de la columna a los bordes. El refuerzo se toma sin recubrimiento epóxico (ψe = 1); la entrada aún no lo declara.
- **Oráculo:** `tests/oracles/derive_footing_connection.py`, sin importar el paquete; 6 casos por perfil.

### D-066: constante de la ecuación de ganchos del ACI 318-25 (C-014)

- **Fecha:** 2026-11-07
- **Problema:** el PDF de `references/` imprime en 25.4.3.1(a) ldh = fy·ψe·ψs·ψcc·ψr/(21λ√f'c)·db, que en SI da 3.8db (96 mm para una barra #8), cinco veces menos que el ACI 318-19 y que la NSR-10 C.12.5.2. El comentario R25.4.3.1 dice que la expresión restaura la del ACI 318-14 con modificaciones menores; en SI, esa ecuación es (0.24ψe·fy/(λ√f'c))·db = fy/(4.17λ√f'c)·db.
- **Decisión del usuario:** se usa ldh = fy·ψe·ψs·ψcc·ψr/(4.2λ√f'c)·db (constante `_HOOK_CONSTANT` en `codes/aci_318_25/development.py`). Con ella, una barra #8 da 480 mm (NSR-10: 484 mm).

### D-067: revisión de la fe de erratas del ACI 318-25 (SI), parte disponible (C-015)

- **Fecha:** 2026-11-07
- **Fuente:** fe de erratas del ACI Committee 318 al 14 de mayo de 2026, 6 imágenes en `references/Fe de erratas aci 318-25/` (sin versionar).
- **Revisado:** la tabla de conversiones faltantes (2.2, R7.6.3.1, R8.3.1.1, 8.3.1.2, 8.6.2.1, R8.6.2.1, 8.6.2.3, 8.7.6.3, 8.7.7.1.2, 9.6.1.2, 9.8.1.2, 10.7.5.2.1, 17.6.1.2, R17.7.3.1, R18.7.5.2, 18.8.3.2, R22.2.2.4.3, R22.4.2.1, 22.9.4.2, R23.4.3, 24.2.3.5, R24.3.1, R24.3.2.1, 25.4.6.1(b), R25.6.2.1, 25.7.1.8.3(c), R25.7.2.3, 25.7.3.1(a)) y las correcciones de 8.7.4.1.3, 9.6.3.1, R11.8.4.1, R17.1.9, 17.6.5.5.1, R17.7.2.1.2, 18.10.3.3, 18.10.6.2, 18.10.6.4, R18.10.6.5, 18.12.7.6, 18.12.12.1, 19.2.3.1, R25.9.4.4.6 y 27.4.6.2.
- **Efecto en lo implementado:** ninguno.
  - 9.6.1.2 (80 000 psi → 550 MPa): el As,min de vigas ya limita fy a 550 MPa (D-019).
  - 9.6.3.1: solo quita una unidad sobrante del texto de la tabla; el Av,min (Tabla 9.6.3.4) no cambia.
  - 19.2.3.1: el módulo de rotura es fr = 0.62λ√f'c (el PDF imprime 0.062). No se usa todavía; aplicará en la subfase 2D (fisuración y deflexiones).
  - Las demás son de capítulos no implementados (losas en dos direcciones, anclajes, sísmico, muros, evaluación de estructuras existentes) o del comentario.

### D-068: memoria de cálculo con el formato de StructureLab_HFS (V3E)

- **Fecha:** 2026-11-07
- **Decisión del usuario:** la memoria de cálculo sigue el formato y estilo de StructureLab_HFS, adaptado a este repositorio. Reemplaza el formato de memoria de D-050 (las salidas `resultado.json`, `memoria.txt` y `memoria.pdf` se mantienen).
- **Implementación (DRY):**
  - `reporting/document.py` construye, solo a partir de `resultado.json`, una memoria por elemento como bloques neutros (título, resumen, capítulos, tablas, pares, notas y alertas); `reporting/text.py` y `reporting/pdf.py` dibujan los mismos bloques. `reporting/glossary.py` da el capítulo, los símbolos y el nombre en palabras de cada verificación y de cada valor. Vigas y zapatas comparten la verificación gobernante, el detalle de cada revisión, la tabla de requisitos y los índices DCR.
  - Un archivo por proyecto con la memoria de cada elemento, como el `multi_member` de StructureLab_HFS. Arriba, `RESULTADO: <estado> (<CUMPLE…>)` y el DCR máximo; después, la revisión de mayor DCR de cada capítulo.
  - Capítulos fijos de viga: materiales, geometría y armado por estación, solicitaciones, requerimientos técnicos, servicio (falta implementación), flexión, cortante, torsión, índices DCR, notas y limitaciones. De zapata: materiales, geometría, suelo y armado, solicitaciones de servicio y mayoradas, revisión geotécnica, requerimientos técnicos, flexión, cortante en una dirección, punzonamiento, desarrollo, aplastamiento y pasadores, índices DCR, notas y limitaciones. Lo que no corresponde dice "No aplica"; lo que no está programado, "Falta implementación".
  - `resultado.json` trae lo que la memoria imprime: las propiedades del perfil que usa el cálculo (β1, εcu, 0.85, Es, εty, λ), las solicitaciones y el armado de cada estación, los casos de carga y las mallas de cada zapata, y el caso de cada verificación de zapata.
  - Texto con Unicode (φ, ², ·, —), en lugar de la regla Latin-1 de D-050. El PDF usa una fuente TrueType del sistema (Segoe UI, Arial o DejaVu); sin ninguna, escribe equivalentes en ASCII. Las 65 zapatas de ETABS generan su PDF en unos 4 s.
  - La huella de todos los ejemplos cambió por el formato nuevo (cambio intencional); el cálculo no cambió.

### D-069: diseño de zapatas por tipologías (V3F)

- **Fecha:** 2026-11-07
- **Decisión del usuario:**
  1. El diseño busca un número dado de tipologías iguales (dimensiones y mallas) que cubran todas las columnas; el f'c es una variable de diseño entre los valores comerciales 21, 24.5, 28, 31.5, 35, 42 y 48 MPa, con un solo f'c para todas las zapatas del proyecto.
  2. Formas en planta disponibles: cuadrada (por defecto), voladizos iguales y relación lx/ly fija.
  3. Las soluciones se ordenan por costo: precio del concreto por m³ para cada f'c permitido y del acero por kg (excavación y formaleta fuera).
  4. Con ETABS, un número dado de zapatas tipo para todas las columnas: la plantilla trae el bloque design y las secciones de las columnas; la asignación la hace el diseño.
  5. Si nada cumple dentro de los límites, el resultado es FAIL con el motivo; los límites no se amplían.
  6. Dentro de una tipología, cada columna se verifica con su propia sección, sus cargas y sus pasadores, que se diseñan por columna.
- **Implementación (DRY):** el diseño no tiene fórmulas propias. `design/footing/typology.py` propone zapatas (planta, espesor, mallas a partir del As requerido de `domain/flexure_strength`, pasadores con el aplastamiento de `codes`) y las aprueba con `domain/footing/checks.footing_checks`; después de la primera planta viable explora dos más y se queda con la más barata, y elige los pasadores de menor área que aprueban área, anclaje y exceso de aplastamiento. `design/footing/grouping.py` parte la lista ordenada en N tramos continuos por programación dinámica (óptima para ese orden); `design/footing/typologies.py` diseña cada columna, las ordena por costo, agrupa y prueba cada f'c. El proyecto diseñado es un proyecto de verificación normal (`proyecto.json`), que `report` verifica y documenta.
- **Rendimiento:** el As requerido se memoiza (una columna pasó de más de una hora a 0.6 s); un algoritmo genético se descartó porque necesitaría miles de verificaciones donde la búsqueda usa unas pocas y no garantiza el óptimo. Los diseños individuales, las coberturas y los diseños de tramo se reparten entre procesos (`design-footings --workers N`, por defecto los núcleos del equipo); el resultado es idéntico con cualquier número de procesos (ETABS, 65 columnas: 8 min con 32 hilos; referencia vigente desde la medición E0 del 2026-11-09, [docs/mediciones/E0.md](mediciones/E0.md): 73 columnas, 16 hilos, 35 min con NSR-10 y 39 min con ACI 318-25). Una partición perezosa con cota inferior del concreto se probó y se descartó: con la cota a ~30 % del costo real tuvo que diseñar el 75 % de los tramos.

### D-070: deslizamiento y volcamiento de zapatas

- **Fecha:** 2026-11-08
- **Problema:** ACI 318-25 13.2.6.1 exige dimensionar las zapatas contra el volcamiento y el deslizamiento en la interfaz
  suelo–zapata "de acuerdo con el código general de construcción", sin método ni factores; NSR-10 remite al Título H,
  que no está en `references/`.
- **Decisión del usuario:**
  1. Los factores de seguridad los declara el usuario en `soil`: deslizamiento y volcamiento, cada uno con un valor para
     casos sin sismo y otro para casos con sismo.
  2. Cada caso de carga puede marcarse `seismic: true` (en ETABS, por combinación en `load_factors`); sin marca, el caso
     se revisa con los factores sin sismo.
  3. Se revisan los casos de servicio tal como llegan, con sus factores de carga muerta y viva (como V3C); las
     combinaciones favorables las define el usuario.
  4. Deslizamiento: resistencia = μ·N + c_a·A_contacto + f_p·P_p, con μ y c_a declarados, A_contacto el área en contacto
     de Bellos y Bakas y P_p el empuje pasivo afectado por el factor f_p (por defecto 0.5), porque la fricción y la
     pasiva no se movilizan por completo a la vez. La pasiva usa Kp declarado por el usuario, actúa solo sobre el
     espesor h de la zapata con la sobrecarga del relleno encima (de Kp·γ·D₁ a Kp·γ·(D₁ + h), γ del relleno, D₁ la
     altura del relleno) e incluye la cohesión declarada (2c·√Kp). Con cortante en los dos ejes se revisan la dirección
     de la resultante, con P_p(θ) = P_p,x·|cos θ| + P_p,y·|sin θ|, y cada eje por separado; gobierna el menor factor.
  5. Volcamiento: alrededor de cada borde, factor = momento resistente / momento volcador = (L/2)/|e| en cada eje, con
     la resultante en la base (momento de la columna más el cortante por h + pedestal); la pasiva no se cuenta.
  6. Los datos nuevos son obligatorios; los ejemplos y plantillas se actualizan (las huellas cambian).
  7. El diseño por tipologías (D-069) incluye ambas revisiones en su búsqueda.

### D-071: reducciones del desarrollo y refuerzo con recubrimiento epóxico

- **Fecha:** 2026-11-08
- **Referencias:** ACI 318-25 25.4.2.5 (Tabla), 25.4.3.2 (Tabla), 25.4.9.3 y 25.4.10; NSR-10 C.12.2.1, C.12.2.4(b),
  C.12.2.5, C.12.3.3, C.12.5.2 y C.12.5.3 (leídos del PDF escaneado).
- **Decisión del usuario (recomendaciones aprobadas):**
  1. `materials.coating` obligatorio: `uncoated`, `galvanized`, `epoxy` o `zinc_epoxy` (los dos últimos con el mismo ψe).
     Tracción: ψe = 1.5 con recubrimiento libre < 3db o separación libre < 6db, 1.2 en otro caso, ψt·ψe ≤ 1.7; ganchos:
     ψe = 1.2; compresión: sin ψe.
  2. As requerido de una malla = el mayor entre el As de flexión de los casos mayorados y el As,min (el factor no aplica
     al refuerzo de retracción y temperatura, R25.4.10.1).
  3. El factor As requerido/As suministrado se aplica solo con nivel sísmico `DMI` (NSR-10) o `none`/`ordinary` (ACI);
     con niveles mayores no se aplica y la memoria dice por qué. NSR-10 C.12.2.5 remite a "C.21.2.1.6", que no existe en
     NSR-10 (C.21.2.1 es el alcance de los pórticos DMI); ACI 25.4.10.2(e) excluye el sistema sísmico en categorías C a F.
     El resultado sigue limitado por los mínimos (300 mm a tracción).
  4. En NSR-10 el factor también se aplica a los ganchos (C.12.5.3(d)); en ACI no (25.4.10.2(d)).
  5. Los pasadores a compresión no usan el factor: su área mínima es prescriptiva.
  6. ψcc = 0.7 en ganchos de barras hasta la No. 36 con recubrimiento lateral libre ≥ 65 mm (barra extrema de la fila a la
     cara lateral) y, en ganchos de 90°, recubrimiento sobre la extensión ≥ 50 mm (recubrimiento del extremo).
  7. ψr = 1.0 (zapatas sin estribos); se incorporará con vigas y columnas.
- **Implementación (DRY):** los factores son funciones públicas de `codes/<perfil>/development.py`
  (`tension_coating_factor`, `hook_coating_factor`, `hook_cover_factor`, `excess_factor_permitted`); `domain/development.py`
  describe la barra con `BarAnchorage`, elige ecuación y factores y arma el Check, para cualquier elemento; `domain/basis.py`
  lleva el nivel sísmico hasta la verificación. El As requerido de las mallas sale de `required_mat_area`, la misma función
  de la franja central. El modelo de zapata no distingue gancho de 90° y de 180°: se usa la condición del de 90°, que exige
  además el recubrimiento sobre la extensión.
- **Oráculo:** `tests/oracles/derive_footing_connection.py` con 8 casos nuevos por perfil (epóxico, tope de 1.7, refuerzo
  en exceso con nivel bajo y alto, mínimo de 300 mm, ganchos con ψcc y recubrimiento corto). El caso existente de ganchos
  cambia porque ahora le corresponde ψcc = 0.7.

### D-072: momento negativo de zapatas como concreto simple y lista de f'c del diseño

- **Fecha:** 2026-11-08
- **Referencias:** ACI 318-25 14.1.3, 14.3.2.1, 14.4.3.2.1, 14.5.1.6, 14.5.1.7, 14.5.2.1 y Tabla 21.2.1(f); NSR-10
  C.9.3.5, C.22.4.5, C.22.4.7, C.22.5.1, C.22.7.4, C.22.7.5 y C.22.10.1 (leídos del PDF escaneado).
- **Decisión del usuario (recomendaciones aprobadas):**
  1. El momento negativo en una cara sin malla superior se revisa como concreto simple: φMn = 0.60·0.42λ√f'c·Sm ≥ Mu,
     Sm = b·(h − 50)²/6 (concreto vaciado contra el suelo) con b el ancho completo; reemplaza el BLOCKED de D-059. El
     cortante sigue revisándose como concreto reforzado.
  2. Se permite con NSR-10 DMI y DMO (C.22.10.1 lo prohíbe con DES) y con ACI none, ordinary e intermediate (14.1.3 lo
     restringe en categorías D a F; special se toma como tales). Si no se permite, FAIL "requiere malla superior".
  3. La excepción de viviendas de una o dos familias de hasta tres pisos no se implementa (pendiente).
  4. El diseño por tipologías prueba primero sin malla superior y la agrega solo si hace falta.
  5. No se agrega la verificación de espesor mínimo de 200 mm: la altura mínima del concreto reforzado ya la supera.
  6. El diseño evalúa una lista explícita de f'c (`design.fc_options`), comerciales y con precio en `concrete_per_m3`;
     la tabla de precios puede traer más resistencias.
- **Implementación (DRY):** `codes/<perfil>/plain.py` (φ, 0.42λ√f'c, reducción de 50 mm, niveles permitidos) y
  `domain/plain_strength.py` (sección rectangular), reutilizables en muros y pedestales; `domain/footing/flexure.py` solo
  arma la verificación "Flexion concreto simple".
- **Ejemplo de ETABS (pedido del usuario):** la plantilla de diseño toma cada Unique Name de los Excel como columna de
  500 × 800 mm (cx × cy) con la zapata centrada. Los Excel de ETABS se actualizaron (73 apoyos en 4 niveles); la plantilla
  de verificación quedó con los 57 apoyos que siguen existiendo.
- **Oráculo:** `tests/oracles/derive_footing_flexure.py` con nivel sísmico por caso y tres casos de concreto simple.

### D-073: los mismos ejemplos para los dos perfiles

- **Fecha:** 2026-11-08
- **Decisión del usuario:** los ejemplos de ACI 318-25 y de NSR-10 son el mismo caso con los mismos datos, para poder
  comparar resultados; solo cambian el perfil y el nivel sísmico equivalente (`ordinary` ↔ DMI, `intermediate` ↔ DMO,
  `special` ↔ DES). Las plantillas de ETABS (`plantilla_*_etabs.json`) van en la carpeta de su perfil y leen los Excel
  compartidos de `examples/etabs/<elemento>/`, que solo guarda los Excel. Se conservan los ejemplos pequeños de
  `diseno_tipologias.json` (rápidos, en la huella) y el diseño desde los Excel (73 apoyos, varios minutos).
- **Cambios:** el diseño por tipologías de NSR-10 pasa a 6 tipologías como el de ACI; las vigas de ACI pasan a
  `intermediate`, equivalente a DMO; se crean las plantillas de ETABS de ACI, gemelas de las de NSR-10. Reemplaza la
  ubicación de las plantillas de D-058.

### D-074: tipologías repetidas y reasignación en el diseño por tipologías (E1)

- **Fecha:** 2026-11-09
- **Contexto:** la medición E0 ([docs/mediciones/E0.md](mediciones/E0.md)) encontró en NSR-10 una solución de N = 6
  con dos tipologías idénticas (Z4 = Z5) y, en los dos perfiles, columnas que otra tipología elegida cubre más barato
  (2.2 % del costo en NSR-10, 7.9 a 8.3 % en ACI 318-25).
- **Decisión del usuario:**
  1. Se permiten tipologías repetidas, pero se marcan. Iguales: coinciden f'c, lx, ly, h, malla inferior y malla
     superior (los pasadores son de cada columna). No hay FAIL ni se descarta el f'c: se elige el f'c más barato.
     La primera propuesta (FAIL en modo `dp`, descartar el f'c) se cambió por esta.
  2. `tipologias.json` trae `distinct_count`, `duplicates` (grupos de tipologías idénticas: nombres y `at_limit`, los
     límites de diseño `plan_max` o `h_max` en que está la tipología, cuando el paso siguiente los supera) y, por cada
     f'c evaluado, su costo y su `distinct_count`. La memoria muestra una advertencia visible cuando hay repetidas.
     Las repetidas, junto con el ahorro marginal de la curva costo–N, servirán como indicador de saturación de N.
  3. Reasignación que conserva las N: en orden de id, cada columna pasa a la tipología elegida más barata que la
     cubre si baja el costo y su grupo de origen conserva al menos una columna; se repite hasta que nada cambie. Las
     tipologías no se rediseñan. Va antes de comparar los f'c. Salida: `cost_before_reassignment` y `reassigned`
     (`column`, `from`, `to`, `saving`).
  4. En E2, la verificación `C_MILP ≤ C_DP` se exige solo cuando la DP no tiene repetidas; si las tiene, se reportan
     los dos costos con su `distinct_count` y una nota. En la curva costo–N los puntos con repetidas se marcan.
- **Seguridad:** la reasignación solo mueve una columna a una tipología que la cubre según `covers()` (todas las
  verificaciones de la columna con sus pasadores), y el proyecto diseñado se reverifica completo con `report`.
- **Resultado (E1, 2026-11-09, proyecto de ETABS, 73 columnas, N = 6, 16 procesos):** huella de los ejemplos idéntica
  (6 columnas y N = 6: nada que reasignar). La reasignación cuesta 1.3 a 1.9 s por f'c (365 coberturas).

  | Perfil | E0: f'c, costo | E1: f'c, costo antes → después | Reasignadas | Distintas | `report` |
  | --- | --- | --- | --- | --- | --- |
  | NSR-10 | 21 MPa, 644 701 163 (5 distintas) | 24.5 MPa, 649 544 544 → 624 266 644 (−3.2 % frente a E0) | 15 | 6 | PASS |
  | ACI 318-25 | 21 MPa, 811 203 293 | 21 MPa, 811 203 293 → 746 988 349 (−7.9 %) | 43 | 6 | PASS |

  En NSR-10 la reasignación cambia el f'c elegido: 21 MPa baja a 630 730 196 (exactamente lo estimado en E0) y
  sigue con 5 distintas; 24.5 MPa queda más barato, sin repetidas. En ACI 318-25 el ahorro coincide con la estimación
  de E0 que conserva las 6 tipologías. En los dos queda una sola columna reasignable, bloqueada porque es la única de
  su grupo.

### D-075: segundo solucionador del diseño por tipologías: MILP sobre el catálogo de la DP (E2)

- **Fecha:** 2026-11-09
- **Decisión del usuario:** E2 con la matriz completa de cobertura (E0: ≈1 % del tiempo), tal como está en
  [plan-tipologias](planes/plan-tipologias.md); el modo `dp` conserva la huella de E1.
- **Implementación:**
  1. La tabla de tramos ya no depende de N: se diseñan todos los tramos de la lista ordenada (n(n+1)/2). La DP da el
     mismo resultado: los tramos que se agregan no entran en ninguna partición en N tramos.
  2. El costo de una tipología en una columna (`typology.column_cost`: concreto, mallas y pasadores) es el costo por
     par; el de un grupo es la suma del de sus columnas, y la DP lo reutiliza. La huella no cambió.
  3. `design/footing/assignment.py`: MILP con highspy (extra opcional `opt`, `highspy==1.15.1`): cada columna una
     tipología, cada tipología elegida con al menos una columna, exactamente N, solo pares que `covers()` aprueba.
     Brecha 0, un hilo, semilla fija; costos en pesos enteros y acero en gramos enteros; desempate en tres pasos (costo;
     con ese costo fijo, acero; con los dos fijos, el orden del catálogo).
  4. Flujo con `design.method = "milp"` o `--method milp`, por f'c: DP con la reasignación de D-074 → catálogo (diseños
     individuales y de tramo, sin repetidas) → matriz completa con `covers()` en el pool → MILP con arranque desde la
     DP si no tiene repetidas. Se exige `C_MILP ≤ C_DP` en pesos enteros cuando la DP no tiene repetidas; si no se
     cumple, el f'c se rechaza (error interno). Si el MILP no tiene solución (no hay N tipologías distintas en el
     catálogo), queda la DP con sus repetidas marcadas y una nota. Se elige el f'c de menor costo del método pedido.
  5. Límite de tiempo por f'c `design.milp_time_limit_s`, 120 s por defecto, compartido por los tres pasos; si se
     agota, queda la mejor solución y el estado `time_limit` (sin certificar).
  6. Sin highspy, pedir `milp` es FAIL con "instale structurelab-rc[opt]"; nunca una DP silenciosa. La CI instala el
     extra `opt`.
- **Seguridad:** el MILP solo elige entre pares aprobados por `covers()`, y el proyecto diseñado se reverifica completo.
- **Resultado (E2, 2026-11-09, proyecto de ETABS, 73 columnas, N = 6, 16 procesos):** huella de los ejemplos idéntica
  con `dp` y con `milp`. Óptimo certificado en todos los f'c; `report` PASS.

  | Perfil | E1 (DP): f'c, costo | E2 (MILP): f'c, costo | Por f'c: DP → MILP | MILP por f'c |
  | --- | --- | --- | --- | --- |
  | NSR-10 | 24.5 MPa, 624 266 644 | 21 MPa, 605 443 055 (−3.0 %) | 21: 630.73 M (5 distintas) → 605.44 M; 24.5: 624.27 → 609.74 M; 28: 629.54 → 622.55 M | 57–76 candidatos; 18–23 s |
  | ACI 318-25 | 21 MPa, 746 988 349 | 21 MPa, 712 419 298 (−4.6 %) | 21: 746.99 → 712.42 M; 24.5: 770.44 → 736.76 M; 28: 801.51 → 766.61 M | 36–37 candidatos; 13–14 s |

  `C_MILP ≤ C_DP` se exigió y se cumplió en los cinco f'c cuya DP no tiene repetidas; en NSR-10 21 MPa la DP tiene
  repetidas y la nota lo dice. El MILP agrega 13 a 23 s por f'c (matriz de cobertura; el solucionador tarda ≈1 s) y la
  tabla completa de tramos 15 rediseños más; el diseño tardó 2338 s (NSR-10) y 2539 s (ACI 318-25).
- **Método por defecto:** `milp`, por decisión del usuario al cumplirse la aceptación de E2. `dp` sigue disponible con
  `--method dp`. La prueba del wheel en la CI instala `[pdf,opt]`.

### D-076: espesor y mallas de menor costo en `design_group` (E3a)

- **Fecha:** 2026-11-09
- **Problema:** `design_group` tomaba el menor espesor con solución de cada planta, no el de menor costo (E0: en ACI
  318-25 una zapata más gruesa sin malla superior resultó más barata), y en cada espesor devolvía la primera
  combinación de mallas que pasaba, con una sola malla superior candidata. Es un defecto frente a D-069 (la tipología
  más económica).
- **Decisión del usuario e implementación** (`design/footing/typology.py`; las verificaciones no cambian):
  1. Mallas: las verificaciones de la malla inferior y de la superior son separables (las de la superior, o del
     concreto simple sin ella, dependen solo de ella; la altura efectiva de la inferior, el cortante, el punzonamiento
     y el anclaje de los pasadores no dependen de la superior). Se busca la inferior de menor costo con sus pasadores
     (su anclaje depende de los diámetros de la inferior), de menor a mayor peso y hasta que su acero más los
     pasadores mínimos no pueda ganar; con ella, la superior más liviana que pasa entre todas las candidatas (ninguna
     primero si el perfil permite concreto simple, D-072). El par se confirma con una verificación completa; si no
     pasara, se enumeran todas las combinaciones.
  2. Espesor: desde el menor con solución (bisección), se recorren los mayores hasta `h_max` y se elige el de menor
     costo. Un espesor que no cumple el suelo se salta y el barrido sigue.
  3. Poda exacta: se deja de subir cuando la cota inferior alcanza el mejor costo: concreto más la malla inferior
     mínima con `min_reinforcement_ratio` del perfil (la misma del chequeo de As,min), las longitudes de `_mat_mass` y
     la menor masa por área de las barras candidatas; sin pasadores ni malla superior. La cota crece con h.
  4. La búsqueda de plantas (la primera viable y dos más) no cambia y **sigue siendo heurística**.
- **Control:** enumerador independiente en las pruebas (no reutiliza `_at_height`): todos los espesores, incluidos los
  menores que el de la bisección, y todas las combinaciones de mallas candidatas, en casos sin momento negativo, con
  momento negativo en DES (malla superior obligatoria) y en DMO (concreto simple permitido). El resultado es el mínimo
  y nunca se usa el respaldo conjunto. La poda no cambia el resultado frente al barrido completo.
- **Multiplicador de tiempo** (diseños individuales del proyecto de ETABS, 73 columnas × 3 f'c, 16 procesos): 0.99 a
  1.10 en el tiempo de las tareas (1.03 a 1.17 en tiempo de pared). Ningún diseño individual sube de costo; mejoran 1
  (NSR-10, 28 MPa) o 2 (ACI 318-25) de 73 columnas, con −0.06 a −0.08 % del costo de los individuales, siempre con
  una zapata más gruesa. Huella de los ejemplos idéntica.
- **Diagnóstico (2026-11-09):** 18 tramos reales de la tabla de la DP (ETABS NSR-10, f'c 24.5, 3 por rango de longitud),
  con la búsqueda de E2 y la de E3a. Ningún tramo se dispara (el más lento, 40 s), pero todos cuestan unas 3 veces más
  (CPU de la tabla por f'c: 3.6 h con E2 y 13.8 h con E3a): el barrido de espesores subía unos 12 espesores sobre el
  mejor porque la cota (concreto y malla inferior mínima) era holgada. La hipótesis de la malla superior no se confirmó
  (unas 2 verificaciones por espesor). Los costos de los 18 tramos fueron idénticos a los de E2. El final con 2 de 16
  procesos se debía al reparto: los últimos lotes juntaban los tramos más largos.
- **Ajustes aprobados por el usuario:**
  1. La cota suma los pasadores mínimos de cada columna y, si la malla superior es obligatoria (momento negativo sin
     concreto simple permitido), su acero mínimo en las direcciones con momento negativo; todo está en cualquier
     solución, así que sigue siendo exacta. Con ella la tabla quedó en 1.43 veces E2 (NSR-10), pero ETABS ACI 318-25
     tardó 5 759 s (E2: 2 539 s) con el mismo costo.
  2. Los tramos más largos se reparten primero (el resultado no cambia).
  3. El barrido de espesores se aplica solo donde decide el resultado: los diseños individuales y el refinamiento de
     cada grupo elegido por la DP o el MILP (`_refine`: rediseño con barrido sobre exactamente sus columnas, que se
     reemplaza solo si baja de costo). La tabla de tramos usa la búsqueda rápida (`design_group(..., sweep=False)`:
     el menor espesor con solución, con las mallas de menor costo).
  4. La consola del CLI reemplaza los caracteres que no tiene (el "≤" de la nota del MILP interrumpía el comando en
     cp1252 con la salida redirigida, aunque los resultados ya estaban escritos).
- **Resultado (ETABS, 73 columnas, N = 6, `milp`, 16 procesos):**

  | Perfil | E2: costo, tiempo | E3a cerrada: costo, tiempo |
  | --- | --- | --- |
  | NSR-10 | 21 MPa, 605 443 055; 2 338 s | 21 MPa, 605 443 055; 1 560 s (−33 %) |
  | ACI 318-25 | 21 MPa, 712 419 298; 2 539 s | 21 MPa, 712 419 298; 1 717 s (−32 %) |

  Mismas tipologías que con el barrido en toda la tabla; óptimo certificado; `report` PASS. Huella de los ejemplos
  idéntica. En estos proyectos E3a no baja el costo (sus mejoras de −0.06 a −0.08 % en 1 o 2 diseños individuales no
  cambian las tipologías finales); la búsqueda de plantas sigue siendo heurística.
- **Pruebas:** la poda no pierde el óptimo y la cota no supera el costo de una solución real (sin negativo, DES y DMO);
  el refinamiento nunca sube el costo; la tabla usa la búsqueda rápida y el refinamiento el barrido; la consola cp1252
  no interrumpe el CLI.

### D-077: diseño por tipologías iterativo sin tabla de tramos: `milp_iter` (E3b)

- **Fecha:** 2026-11-10
- **Problema:** con `milp`, el 92 % del tiempo se va en diseñar los 2402 tramos de la tabla de la DP (E0), aunque el
  MILP solo usa unos pocos.
- **Decisión del usuario:** método `design.method = "milp_iter"` (`--method milp_iter`), con `design.iter_max` (10 por
  defecto) y `design.iter_time_limit_s` (600 s por f'c por defecto). Al cumplirse la aceptación, el usuario decidió que
  `milp_iter` sea el método por defecto (2026-11-10); `milp` y `dp` siguen disponibles con `--method`.
- **Implementación** (`design/footing/typologies.py`, `_iterative` y `_proposals`; las verificaciones no cambian):
  1. Catálogo inicial: los diseños individuales y un diseño de todas las columnas (con él siempre hay N tipologías que
     cubren todo: esa y N − 1 individuales). Cobertura con `covers()` solo de los candidatos nuevos.
  2. En cada iteración, MILP desde la solución anterior (el catálogo solo crece: el costo nunca sube) y rediseños de lo
     propuesto: cada grupo de dos o más columnas sobre exactamente sus columnas, con el barrido de espesores (D-076), y,
     con la búsqueda rápida, el reparto de cada par de grupos: la unión de sus columnas, ordenada por el costo de su
     diseño individual, cortada en dos en cada posición.
  3. Para cuando el costo no baja, cuando los rediseños no agregan candidatos, a las `iter_max` iteraciones o al pasar
     `iter_time_limit_s`. Los grupos finales se refinan con el barrido (la misma función que `milp`).
  4. La matriz de costos por par y el armado de los grupos se comparten con `milp` (`_pair_costs`, `_chosen`).
  5. La medición `--profile` (E0) registra con `milp_iter` cada lote por el tipo de sus tareas (`single`, `design`, `covers`, `refine`) y agrega las iteraciones por f'c; antes deducía las etapas por el orden de los lotes de la tabla de tramos y fallaba con `milp_iter` (corregido el 2026-11-10).
- **Intentos medidos antes del reparto de pares:** solo rediseñar los grupos propuestos se detenía en la primera
  iteración (el rediseño repetía la tipología) y NSR-10 quedaba +0.28 %; los subgrupos de cada grupo y el reparto de
  pares consecutivos no bastaron: la tipología que faltaba juntaba columnas de dos grupos no consecutivos.
- **Resultado (ETABS, 73 columnas, N = 6, 16 procesos):**

  | Perfil | `milp`: costo, tiempo | `milp_iter`: costo, tiempo | Por f'c: `milp` → `milp_iter` |
  | --- | --- | --- | --- |
  | NSR-10 | 21 MPa, 605 443 055; 1 560 s | 21 MPa, 605 443 055; 510 s (−67 %) | 21: igual; 24.5: 609.74 → 608.84 M; 28: 622.55 → 621.86 M |
  | ACI 318-25 | 21 MPa, 712 419 298; 1 717 s | 21 MPa, 712 419 298; 533 s (−69 %) | 21, 24.5 y 28: iguales |

  Dos o tres iteraciones por f'c; óptimo certificado del MILP en cada una; `report` PASS. `milp_iter` puede mejorar a
  `milp` porque sus grupos no tienen que ser tramos continuos de la lista ordenada. Huella de los ejemplos idéntica
  con los dos métodos (también con `milp_iter` por defecto).
- **Pruebas:** costo de las iteraciones no creciente y mismo costo que `milp` con 1, 2 y 3 tipologías; mismo resultado
  con 1 y 2 procesos (el tiempo de cada iteración no entra en la comparación); límite de iteraciones; el proyecto
  diseñado pasa la verificación completa.

### D-078: curva costo–N del diseño por tipologías

- **Fecha:** 2026-11-10
- **Decisión del usuario:** comando `typology-curve` con N por defecto de 1 a 12 (o hasta el número de columnas) y
  `--n` para elegir otros; lo que no depende de N se conserva entre valores de N; la gráfica en SVG y en la memoria.
- **Implementación:** `typology_curve` (`design/footing/typologies.py`) diseña con cada N reutilizando por f'c el
  catálogo y su cobertura (`milp_iter`, que siguen creciendo: un punto puede salir igual o más barato que el diseño
  suelto con ese N) o la tabla de tramos (`milp` y `dp`: cada punto igual al diseño suelto). Cada punto lleva el f'c,
  el costo, el ahorro frente al N anterior, si el costo sube, la certificación del MILP del f'c elegido, las tipologías
  distintas y las repetidas (con `at_limit`). `reporting/curve.py` arma `curva.json`, `curva.csv`, `curva.svg` y los
  bloques de la memoria (`memoria_curva.txt` y `.pdf`); los renderizadores tienen el bloque `image` (el PDF incrusta
  el SVG). La saturación no tiene umbral automático: repetidas y ahorro marginal pequeño se muestran para el ingeniero.
- **Resultado (ETABS, 73 columnas, N = 1 a 12, `milp_iter`, 16 procesos):** NSR-10 en 1 355 s y ACI 318-25 en
  1 434 s; óptimo certificado en todos los puntos, sin repetidas y sin subidas; N = 6 coincide con el diseño suelto.

  | N | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | NSR-10 (M) | 912.9 | 702.0 | 647.1 | 622.0 | 612.1 | 605.4 | 599.0 | 592.6 | 589.3 | 586.2 | 583.4 | 581.4 |
  | ahorro (%) | – | 23.1 | 7.8 | 3.9 | 1.6 | 1.1 | 1.1 | 1.1 | 0.6 | 0.5 | 0.5 | 0.3 |
  | ACI 318-25 (M) | 1 077.1 | 827.1 | 760.9 | 734.7 | 723.2 | 712.4 | 706.3 | 702.5 | 698.9 | 696.0 | 693.6 | 692.1 |
  | ahorro (%) | – | 23.2 | 8.0 | 3.4 | 1.6 | 1.5 | 0.9 | 0.5 | 0.5 | 0.4 | 0.3 | 0.2 |

  El ahorro marginal cae bajo 2 % desde N = 5 en los dos perfiles; el f'c elegido es 21 MPa en todos los puntos salvo
  NSR-10 con N = 3 (24.5 MPa).
- **Pruebas:** cada punto igual (`milp`) o igual o menor (`milp_iter`) que el diseño suelto; mismo resultado con 1 y 2
  procesos; ahorro y costo que sube; CSV, SVG y memoria; el CLI escribe los archivos y rechaza N mayor que las columnas.

### D-079: aumento de la presión admisible en combinaciones con sismo

- **Fecha:** 2026-11-10
- **Problema:** con sismo, la capacidad portante del suelo puede aumentarse por un factor que fija el estudio de suelos;
  la verificación comparaba siempre con qa.
- **Decisión del usuario:** dato opcional `soil.seismic_bearing_factor` (1.0 por defecto, sin aumento; no menor que 1.0).
  Se usa la marca `seismic` que ya llevan los casos de carga y las combinaciones de ETABS (D-070); no se dividen los
  Excel. En los ejemplos y plantillas, 1.33 como dato supuesto.
- **Implementación:** `Soil.bearing_capacity(seismic)` da qa o qa × factor; la verificación de presión admisible de cada
  caso de servicio la usa y, con sismo y factor distinto de 1, muestra qa, el factor y la nota. El contacto, el
  deslizamiento y el volcamiento no cambian. El diseño por tipologías lo toma de la misma verificación, y la cota de
  planta usa la capacidad de cada caso.
- **Oráculo:** `derive_footing_service.py` con el factor 1.33 y dos casos con sismo (306.5 kPa cumple con 332.5 kPa;
  441.9 kPa no cumple); la prueba compara además la capacidad.
- **Efecto en los ejemplos:** la capacidad de los casos con sismo de `zapata_aislada` pasa de 250 a 332.5 kPa sin
  cambiar estados; los `diseno_tipologias` dan las mismas tipologías y el mismo costo. La curva costo–N agrega el ahorro
  acumulado frente al primer N en la tabla de la memoria, el JSON y el CSV (pedido del usuario).

## Consultas abiertas

### C-016: páginas restantes de la fe de erratas del ACI 318-25 (SI)

- **Pendiente:** la fe de erratas tiene 17 páginas; en `references/Fe de erratas aci 318-25/` hay 6 imágenes. La descripción del documento menciona correcciones en "cálculos de resistencia a cortante" que no aparecen en ellas, y tampoco aparece 25.4.3.1 (D-066). Revisar las páginas restantes cuando estén disponibles.
