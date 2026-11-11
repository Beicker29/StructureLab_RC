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
- **Resuelta por D-081 (2026-11-10):** la excepción se implementa en el acero mínimo de vigas (M3 y M2).

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
- **Revisada por D-081 (2026-11-10):** As,min cuenta solo el acero a tracción más allá de la mitad de la altura desde la cara comprimida; d sigue sin bajar de 0.8h.

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
  3. La excepción de viviendas de una o dos familias de hasta tres pisos no se implementa: en este repositorio no se
     aplican excepciones (decisión del usuario, 2026-11-11, D-092).
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
  distintas y las repetidas (con `at_limit`). `reporting/curve.py` arma `resultado.json`, `curva.csv`, `curva.svg` y los
  bloques de la memoria (`memoria.txt` y `.pdf`; hasta el 2026-11-11 `curva.json` y `memoria_curva.*`, renombrados para
  usar los nombres de las demás salidas); los renderizadores tienen el bloque `image` (el PDF incrusta
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

### D-080: zapatas combinadas (verificación) e imagen de presiones en planta

- **Fecha:** 2026-11-10
- **Referencias:** ACI 318-25 13.2.6.4, 13.3.2, 13.3.4 (y 13.2.6.2 para el cortante); NSR-10 C.15.10.1 a C.15.10.4 (leídos
  del PDF escaneado); Wight, ejemplo 15-6; ACI MNL-17(21), volumen 1, capítulo 11, ejemplo de cimentaciones 5 (compañero
  de ACI 318-19: lo que cambió en 318-25 se compara con cuidado).
- **Decisión del usuario:**
  1. Solo verificación (sin diseño por tipologías); dos columnas; solo rectangular (otras formas, pendientes).
  2. Zapata rígida con la presión lineal de Bellos y Bakas; todas las solicitaciones internas salen de esa presión.
  3. Refuerzo: malla inferior en las dos direcciones, malla superior en la dirección larga (opcional; sin ella, concreto
     simple según D-072) y refuerzo transversal adicional bajo cada columna (opcional).
  4. Viga en la dirección larga con las cargas y momentos de las columnas y la presión neta mayorada integrada a lo largo:
     flexión en las caras de las columnas y en el máximo entre ellas; cortante a d de cada cara.
  5. Franjas transversales de ancho columna + d/2 a cada lado (en la columna de borde, d/2 hacia el interior), en
     voladizo desde la cara de la columna, cargadas con la carga mayorada de la columna (Pu y Mx) repartida en el ancho B
     con la forma de la presión de Bellos en la posición de la columna; con presión uniforme en Y da Pu/B, como Wight y
     el manual (revisado en V3J.2: la opción b inicial, solo la presión bajo la franja, omitía los cortantes de la viga
     en los bordes de la franja y daba ≈55 % menos momento en el ejemplo del manual).
  6. Acero mínimo (revisado en V3J.2): en la dirección larga, el de vigas en los dos perfiles, ACI 9.6.1.2 con la
     exención 9.6.1.3 (13.3.2.1 remite las zapatas combinadas al capítulo 9) y NSR-10 C.10.5.1 con la exención C.10.5.3,
     como Wight y el manual; en las franjas transversales, 0.0018·Ag (ACI 7.6.1.1, NSR-10 C.10.5.4 y C.7.12.2.1). La
     separación máxima, la del perfil.
  6b. Cortante en una dirección de la viga larga sin estribos (el modelo no los tiene): Vu ≤ φVc a d de las caras, con
     ACI 13.2.6.2(a) y NSR-10 C.15.5 → C.11, como en las aisladas y como el manual; si no alcanza, FAIL.
  6c. Frente al manual se esperan diferencias: usa la presión bruta uniforme (con pesos propios) aunque su resultante
     está 0.2 ft fuera del centro; aquí la presión neta de Bellos. Se compara con explicación y tolerancia (D-064).
  6d. Separación máxima de las barras x de la viga larga (V3J.2): ACI, el menor de 3h y 450 mm (7.7.2.3) y del límite
     de fisuración de la Tabla 24.3.2 con fs = (2/3)·fy (24.3.2.1), por la remisión de 13.3.2.1 a los capítulos 7 y 9
     (más exigente que el manual, que no aplica 24.3: con 75 mm de recubrimiento da ≈190 mm); NSR-10, C.10.5.4 (3h y
     450 mm) y, por decisión del usuario (la combinada se revisa como viga), el control de agrietamiento de vigas
     C.10.6.4, ecuación (C.10-4), con fs = (2/3)·fy: la misma forma que 24.3.2.
  7. Se reutilizan la revisión geotécnica (con la resultante de las dos columnas), el punzonamiento por columna con el
     perímetro truncado y γv·Msc, el desarrollo, el aplastamiento y los pasadores.
  8. Oráculos: Wight 15-6 y el ejemplo 5 del manual, en SI con la tolerancia de D-064, más un oráculo independiente.
  9. Imagen en planta de la presión del suelo en cada esquina, para zapatas aisladas y combinadas: el caso de servicio
     que gobierna la presión admisible, con una tabla de las esquinas de todos los casos de servicio; las presiones las
     calcula la revisión geotécnica y la memoria solo las dibuja.
- **Subfases (todas hechas; D-081 a D-083):** V3J.1 modelo, entrada y revisión geotécnica; V3J.2 viga en la dirección larga; V3J.3 franjas
  transversales, punzonamiento, desarrollo, aplastamiento y pasadores; V3J.4 memoria, ejemplos y documentación. La
  imagen de presiones de las zapatas aisladas va primero, por separado.
- **V3J.1 (hecha):** `model/combined.py` (`CombinedFooting`, `CombinedColumn`; bloque `combined_footings` del proyecto);
  `combined_resultant` en `domain/footing/base.py`; la revisión geotécnica recibe la resultante ya calculada y una
  geometría común (`FootingBase`), así sirve igual para las dos zapatas (la aislada da el mismo resultado: huella
  idéntica). La verificación estructural de la combinada queda BLOCKED hasta V3J.3. Oráculo
  `derive_combined_service.py`: 6 casos por perfil (uniforme, excéntrica, borde con pedestal y momentos, sismo,
  deslizamiento y sin equilibrio); 3 de 3 mutaciones de la resultante detectadas.
- **V3J.2 (hecha):** `domain/footing/combined_beam.py`. Cuerpo libre a la izquierda de cada sección con la carga neta
  de Bellos integrada en todo el ancho, la fuerza de cada columna (`column_vertical`, compartida con la resultante) y su
  par My + (h + pedestal)·Vx en el plano de la base, para que V y M cierren en cero en los extremos. Momentos en las
  cuatro caras y donde V = 0; cortante a d de cada cara hacia su tramo. `effective_min_reinforcement` (9.6.1.3,
  C.10.5.3) y `combined_max_bar_spacing` en los dos perfiles. Las franjas, el punzonamiento, el desarrollo y los
  pasadores siguen BLOCKED; sin casos mayorados, INCOMPLETE. Oráculo `derive_combined_beam.py`: 8 casos por perfil
  (extremos por barrido y sección áurea, no por las raíces de V); 5 de 5 mutaciones detectadas, y encontró que el
  paquete saltaba el extremo cuando V = 0 caía en un punto del muestreo (corregido).
- **Referencias (decisión del usuario, V3J.2):** `tests/oracles/<perfil>/references_combined_beam.json`. Wight 15-6 con
  la presión neta de las columnas: Mu⁻ 2112 frente a 2100 kip·ft, φMn 2225 frente a 2220, Vu 307.5 frente a 307 (±1 %);
  φVc 294.7 (ACI, +2.3 %, 0.17√f'c en SI) y 298.2 (NSR-10, +3.5 %, gobierna C.11.2.2) frente a 288 (±3 % y ±4 %); As,min
  11.86 frente a 11.7 in² (±2 %); el cortante sin estribos es FAIL (Wight pone estribos). Wight toma el momento positivo
  de la columna interior en su eje (≈516 kip·ft); aquí en la cara, 13.2.7.1 (318 kip·ft). Del manual solo As,min (10.20
  frente a 10.0 in², ±2.5 %: el libro imprime 10.0 por 10.03) y el momento en la cara exterior de la columna de borde
  (2.1 frente a 2 kip·ft): sus diagramas no se reproducen con sus propios datos (con wu = 68.2 k/ft el máximo da 507
  kip·ft, no 576). Nuestros valores: 548 kip·ft entre columnas y 154 kip·ft en la cara interior de la exterior (159).
- **Pendiente (decisión del usuario, 2026-11-10):** incorporar Vy y las columnas desplazadas en Y en la verificación
  estructural. Hoy entran en la resultante y en la presión de Bellos (revisión geotécnica y carga neta), pero la viga
  larga no considera la torsión que producen, y en las franjas transversales (V3J.3) solo cuentan a través de la forma
  de la presión; el cortante Vy en la base de la columna no se lleva a las franjas.

### D-081: la dirección larga de la zapata combinada se revisa con el código de vigas

- **Fecha:** 2026-11-10
- **Referencias:** ACI 318-25 13.3.2.1, 9.6.1.2, 9.6.1.3, 7.6.3.1, 7.7.2.3, 13.2.6.2(a), Tabla 24.3.2 y 24.3.2.1;
  NSR-10 C.10.5.1, C.10.5.3, C.10.5.4, C.10.6.4 (ecuación C.10-4), C.11.4.6.1(a), C.15.5.
- **Decisión del usuario:** como la dirección larga se trata como viga, se reutiliza el código de vigas (sus
  verificaciones y requisitos normativos) en lugar de un código propio.
  1. La viga larga es un `Member` de tipo viga: sección B × h con el recubrimiento de la zapata, las barras inferiores y
     superiores x como capas con posición y los estribos opcionales (`stirrups` de la zapata combinada, como en vigas).
     Cada caso mayorado da estaciones en las secciones críticas: el mayor momento positivo y el mayor negativo, si los
     hay (caras de las columnas y puntos con V = 0, sin los ceros de V pegados a un borde libre, que son ruido), y las
     secciones a d de cada cara hacia su tramo. `station_checks` da la flexión con las dos capas, εt, As,min, la
     fisuración, el cortante, el eje débil (trivial: M2 = V3 = 0) y la interacción V2-V3.
  2. Cortante en modo cimentación: Vc de las cimentaciones superficiales (ACI 13.2.6.2(a); NSR-10 C.15.5 → C.11) y
     Av,min solo donde Vu > φVc en ACI (13.3.2.1 remite al capítulo 7: 7.6.3.1); NSR-10 no lo exige en zapatas
     (C.11.4.6.1(a)). Con estribos, Vs como en vigas.
  3. Excepción de 4/3 en el código de vigas (resuelve D-022): As provisto ≥ min(As,min, 4/3·As por análisis), con el As
     por análisis de la estación: el acero a tracción del estado nominal escalado hasta φMn = |Mu|. Si el provisto no
     alcanza el momento, FAIL.
  4. Control de fisuración en vigas y en la viga larga: la separación entre barras vecinas de la capa más cercana a la
     cara en tracción frente a 380·(280/fs) − 2.5·cc, no mayor que 300·(280/fs), con fs = (2/3)·fy y cc la menor
     distancia libre de la barra a esa cara (ACI Tabla 24.3.2; NSR-10 C.10.6.4). Con una sola barra en la capa, s es el
     ancho de la cara en tracción: lo dice NSR-10 C.10.6.4; en ACI, que no lo dice, la misma lectura (decisión del
     usuario). Se adelanta esta parte de la fase 2D.
  5. Propio de la zapata: sin barras superiores y M < 0, la flexión es de concreto simple (D-072); la separación de 3h
     y 450 mm (ACI 7.7.2.3, NSR-10 C.10.5.4) por capa.
  6. As,min y su excepción cuentan solo el acero a tracción del lado en tracción de la sección, más allá de la mitad de
     la altura desde la cara comprimida (ajusta D-025, en vigas y en la viga larga, los dos ejes; decisión del usuario):
     con c pequeño, las barras cercanas a la cara comprimida quedan a tracción pero no son refuerzo de tracción por
     flexión. Contarlas bajaba d (D-043) y dejaba el As,min del manual (ejemplo 5) en 9.26 in² frente a 10.0. El cortante
     sigue con D-043 (todo el acero a tracción, d ≥ 0.8h).
- **Consecuencias:** las reglas de vigas D-043 (d ≥ 0.8h) y D-025 (con el ajuste del punto 6) aplican a la viga
  larga. Sin barras superiores y M < 0, las barras inferiores quedan a tracción cerca de la cara comprimida y el
  cortante usa d = 0.8h. Los ejemplos de vigas solo ganan el check de fisuración (todos PASS; 638 por perfil en las
  plantillas de ETABS); ninguno tenía As < As,min. Oráculo `derive_combined_beam.py` rehecho con las reglas de vigas
  escritas aparte (compatibilidad de deformaciones con las dos capas); 9 casos por perfil; 5 de 5 mutaciones
  detectadas.

### D-082: franjas transversales, punzonamiento y conexión de la zapata combinada (V3J.3)

- **Fecha:** 2026-11-10
- **Referencias:** ACI 318-25 13.2.7.2, 9.4.3.2, 22.6, 8.4.4.2, 8.6.1.2, 22.8.3.2, 16.3, 25.4; NSR-10 C.15.5, C.11.1.3,
  C.11.11, C.10.14, C.15.8, C.12; Wight 15-6; ACI MNL-17(21) ejemplo 5.
- **Decisión del usuario:**
  1. Las franjas transversales se revisan con el código de vigas en modo cimentación, como la viga larga (D-081): As,min
     de vigas (como Wight: bw = columna + d), fisuración y cortante en las caras y a d de ellas. Esto reemplaza el
     0.0018·Ag de D-080 punto 6 para las franjas. La carga es la de D-080 punto 5; las barras, las y de la malla
     inferior que caen en la franja y el `band` de la columna, en una capa.
  2. El cortante en una dirección en el sentido transversal se incluye (por la misma vía de vigas), aunque ni Wight ni
     el manual lo revisan.
  3. Desarrollo de las barras x desde la sección de mayor momento de su signo hasta el extremo más cercano, como el
     manual; barras y de cada franja desde la cara de la columna hasta el borde. As requerido/As suministrado: el mayor
     entre el de análisis y el mínimo de vigas efectivo.
- **Reglas propias (no ambiguas en la norma):** en una estación en la cara de una columna, el cortante es el de la
  sección a d (ACI 9.4.3.2 y 13.2.7.2): sin esto, el código de vigas revisaba el cortante en la cara. Aplica a la viga
  larga y a las franjas. La malla y fuera de las franjas cumple el mínimo de losa (ACI 13.3.2.1 y 7.6.1.1, NSR-10
  C.10.5.4) y la separación de 3h y 450 mm. El tipo de extremo (rectas o con gancho estándar, que cambia ld por ldh en
  el desarrollo): las barras de la malla inferior y el `band` usan el `end` de la malla; las superiores declaran el
  suyo (`top.end`, decisión del usuario).
- **Reutilización:** `transferred_load` (carga que atraviesa la sección crítica: la acción de la columna como carga
  neta equivalente menos la carga neta dentro del área crítica), `punching_checks`, `bar_anchorage`, `bearing_area`,
  `bearing_checks` y `dowel_checks` salen de la zapata aislada sin cambiar sus resultados (huella idéntica); la acción
  de cada columna es F = `column_vertical` con ∫x·q = F·x + My + H·Vx y ∫y·q = F·y − Mx + H·Vy.
- **Oráculo:** `derive_combined_columns.py`, 5 casos por perfil (interiores con band, columna de borde, momentos y dos
  casos, ganchos con pasadores que toman el exceso de aplastamiento y sin pasadores, zapata delgada con A2/A1 < 4);
  resistencia de las franjas con un cálculo biaxial propio (con las barras asimétricas en la franja el eje neutro se
  inclina, D-046); 7 de 7 mutaciones detectadas.
- **Referencias:** Wight: Mu de la franja interior 405 kip·ft y As,min de las franjas 7.04 y 3.99 in² (±1 % y ±2 %).
  Manual: franjas 286.3 y 458.6 frente a 286 y 460 kip·ft; φvc 188.5 frente a 189.7 psi; φBn 1768 kip; pasadores
  2.0 in² y ldc 16.39 frente a 16.6 in (ACI, −1.25 %: fy/(4.2√f'c) en SI frente a fy/(50√f'c), D-015; ±2 %). El Vu de
  punzonamiento del manual (459.4 kips) no se compara: resta la presión bruta; aquí la neta (478.7 kips).
- **Consecuencia:** con el control de fisuración de vigas, las franjas con recubrimiento de 75 mm y la malla y en
  segunda capa piden separaciones de ≈120 mm; el armado transversal del manual (#7 @ 6 in) no cumpliría.
  Decisión del usuario: se conserva el control de fisuración en las franjas.

### D-083: refuerzo superficial y esfuerzos de punzonamiento por esquina

- **Fecha:** 2026-11-10
- **Referencias:** ACI 318-25 9.7.2.3 y 24.3.2; NSR-10 C.10.6.7 y C.10.6.4.
- **Decisión del usuario:** aplicar el refuerzo superficial y reportar en las memorias los esfuerzos de punzonamiento.
  1. Refuerzo superficial en el código de vigas, con un rol de capa nuevo, `skin`, que no cuenta como As (como la
     torsión, D-027). Con h mayor que 900 mm, en cada cara lateral debe haber barras de piel en la zona de h/2 desde la
     cara en tracción, y la mayor separación entre la capa en tracción, las barras de piel (de la más cercana a la más
     lejana) y el límite h/2 no excede el control de agrietamiento con fs = (2/3)·fy y cc la distancia libre de la barra
     de piel a la cara lateral. Sin barras de piel en una cara, FAIL. Lectura propia de "uniformemente distribuido en h/2"
     (la norma no fija cómo medirlo): cuenta también el tramo de la última barra al límite h/2.
  2. En la zapata combinada aplica a la viga larga, cuyas caras laterales son las caras largas de la zapata (campo
     `skin`: barra y separación vertical, al recubrimiento de la cara, desde la capa inferior hacia arriba sin llegar a
     la superior). No aplica a las franjas transversales: sus caras laterales quedan dentro del concreto.
  3. El punzonamiento reporta, además de vu, el esfuerzo en cada esquina del perímetro crítico (cortante directo más el
     del momento transferido en los dos ejes, con la carga neta de Bellos dentro del área crítica), Msc, Jc y el
     centroide del perímetro; gobierna la esquina de mayor esfuerzo. Valores `esquina i x`, `esquina i y`, `esquina i v`,
     ordenadas por y y luego por x. Aplica a las zapatas aisladas y a las combinadas.
- **Pendiente anotado:** vigas de gran altura (ACI 9.9, NSR-10 C.11.7).
- **V3J.4 (hecha):** resultado `combined_footings` y memoria propia (viga larga y franjas por separado, planta de
  presiones con las dos columnas y tabla de esfuerzos de punzonamiento por esquina, también en las zapatas aisladas);
  en modo cimentación las estaciones no llevan las verificaciones del eje débil (M2, V3 e interacción V2-V3), que no
  aplican; ejemplo `zapata_combinada.json` igual en los dos perfiles; propiedades derivadas de la base comunes
  (`RectangularBase`).

### D-084: zapatas combinadas desde los Excel de ETABS (V3K)

- **Fecha:** 2026-11-10
- **Decisión del usuario:**
  1. Cada columna de una zapata combinada se identifica por el Unique Name de su nudo de ETABS.
  2. Por zapata, `loads_source` dice si las cargas de servicio y las mayoradas salen de los Excel (`etabs`) o de la
     plantilla (`json`, en `columns[].loads`); así sirve solo el Excel de servicio, solo el de últimas o ambos.
  3. En la línea de comandos se conserva el orden `SERVICIO ULTIMAS PLANTILLA` y un `-` omite un Excel; si una zapata lo
     pide, la importación falla con un error claro.
- **Reglas:** la convención de signos y los factores por combinación son los de la zapata aislada (D-055); la plantilla
  puede traer zapatas aisladas, combinadas o ambas, sin repetir Unique Names. Un tipo de carga que viene de ETABS no
  puede traer casos escritos en la plantilla, ni uno que viene de la plantilla dejarlos vacíos. Con un solo Excel, las
  combinaciones del otro que estén en `load_factors` no se reclaman.
- **Ejemplo:** `plantilla_combinadas_etabs.json` en los dos perfiles con los mismos datos (ZC-A desde ETABS, ZC-B con las
  mayoradas escritas); entra en la huella. El diseño por tipologías sigue pidiendo los dos Excel.

### D-085: franja transversal sin presión en la línea de la columna (Etapa 2.1)

- **Fecha:** 2026-11-10
- **Problema:** la carga de la franja se reparte en el ancho con la forma de la presión de Bellos en la línea de la
  columna (D-080 punto 5); si la columna cae en la zona sin contacto, esa forma no existe y la franja quedaba BLOCKED. La
  norma y las referencias no tratan el caso.
- **Decisión del usuario (respaldo en dos pasos):** si en la línea de la columna hay presión, nada cambia; si es nula, la
  forma de la presión integrada en el ancho de la franja; si también es nula, la carga uniforme F/B, que equilibra el
  cortante de la viga larga (repartido en todo el ancho por la teoría de vigas). La nota de cada verificación de la
  franja dice qué forma se usó. La franja ya no queda BLOCKED.
- **Oráculo:** dos casos nuevos en `derive_combined_columns.py` (columna sin presión con la franja en contacto parcial,
  con Mx para que la forma en Y no sea uniforme, y columna con toda la franja sin contacto); la mutación que salta el paso
  intermedio se detecta. Sin momento en un lado de la franja, la capacidad biaxial no está definida y no se compara.

### D-086: punzonamiento con perímetros críticos traslapados (Etapa 2.2)

- **Fecha:** 2026-11-10
- **Referencias:** ACI 318-25 R13.2.7.2 y NSR-10 CR15.5.2 (comentario, no articulado): si los perímetros de cortante se
  traslapan, b0 es la porción de la menor envolvente de los perímetros individuales que resiste el cortante del grupo.
- **Decisión del usuario:**
  1. Envolvente: el menor rectángulo que contiene los dos perímetros, recortado con la base. Es el perímetro a d/2 de la
     caja que contiene las dos columnas; exacto con las columnas alineadas en Y y el mismo cy, un poco mayor que la
     envolvente convexa si no.
  2. Se agrega la revisión del grupo y se conservan las individuales (cumple solo si pasan todas).
- **Reglas:** hay traslapo si los perímetros sin recortar se cruzan en X y en Y. Carga: la suma de las acciones de las
  dos columnas menos la carga neta de Bellos dentro de la envolvente, con los momentos respecto a su centroide; β, el de
  la caja de las dos columnas; αs, por los lados fuera de la base; esfuerzo en cada esquina como en D-083. Nota del
  check: "Columnas C1 y C2 (perimetro comun)".
- **Oráculo:** caso `columnas-juntas` (350 mm entre caras, menos que d), donde el grupo gobierna; las mutaciones que
  omiten el grupo o una de las columnas en su carga se detectan.

### D-087: revisión de ACI 8.6.1.2 y 13.3.2 a 13.3.4; transferencia de momento por flexión

- **Fecha:** 2026-11-10
- **Revisión pedida por el usuario:** 8.6.1.2 estaba implementado; 13.3.2 (cimentaciones en una dirección, caps. 7 y 9)
  y 13.3.3.2 se cumplen; 13.3.4 (presión acorde al suelo, sin método directo) se cumple en lo aplicable. Hallazgos y
  decisiones:
  1. En la combinada, el refuerzo `band` dentro de bslab ahora cuenta en 8.6.1.2 (antes solo la malla, conservador).
  2. **Transferencia de momento por flexión** (ACI 8.4.2.2 por la remisión de 13.3.3.1 al cap. 8; NSR-10 C.11.11.7.1 →
     C.13.5.3, porque C.15.5.1 remite el cortante de zapatas a C.11.11): en cada dirección, γf·|Msc| (γf = 1 − γv, con
     el Msc del punzonamiento) frente a φMn de la malla inferior (más el band en la combinada) dentro de bslab = c + 1.5h a
     cada lado. Es una revisión de la capacidad de transferencia y de concentración de refuerzo: γf·Msc **no se suma** al
     momento de flexión de la zapata (decisión del usuario).
  3. **Parte negativa de γf·Msc** (decisión del usuario): la resiste la malla superior dentro de bslab (en la combinada,
     solo en X); si no la hay, el concreto simple en bslab si el nivel sísmico lo permite (D-072); si no alcanza, la debe
     tomar la viga de cimentación, que el programa no diseña. La verificación cumple con aviso, sin razón
     demanda/capacidad; el momento se reporta en `foundation_beam_moments` del resultado (caso, columna, dirección de la
     viga y M en kN·m), en una tabla "Momentos para la viga de cimentación" del capítulo de punzonamiento y en un aviso al
     comienzo de la memoria, para llevarlo fácilmente al diseño de la viga.
  4. Zapatas aisladas rectangulares: nueva verificación de que fuera de la franja central quede al menos (1 − γs)·As
     (ACI 13.3.3.3(b), NSR-10 C.15.4.4.2); antes solo se revisaba γs·As dentro de la franja.
  5. **8.6.1.2 en la combinada: decisión de criterio del usuario.** 13.3.2.1 remite las combinadas a los capítulos 7 y 9,
     que no lo piden; se conserva porque cubre el comportamiento en dos direcciones alrededor de cada columna. Queda en la
     nota de la verificación y en las convenciones de la memoria.
  6. Criterio de una o dos direcciones para la combinada (13.3.2 frente a 13.3.4): pendiente en la hoja de ruta; la norma
     no lo define.
- **Sin cambios en el punzonamiento:** vu, φvc, b0, αs, γv y Jc son los mismos (oráculo idéntico).
- **Oráculos:** transferencia (positiva y negativa) en `derive_footing_shear.py` y `derive_combined_columns.py`; fuera
  de la franja y `band_spacing` en `derive_footing_flexure.py`, con un caso de franja concentrada que no cumple fuera de
  ella; las mutaciones γv en lugar de γf y sin malla superior en la parte negativa se detectan.

### D-088: torsión de la viga larga por Vy y columnas desplazadas en Y (v3 Fase 1.1)

- **Fecha:** 2026-11-11
- **Referencias:** ACI 318-25 13.3.2.1 (combinadas con los capítulos 7 y 9), 9.5.4.1 (la torsión se desprecia si
  Tu < φTth) y 9.4.4.3 (Tu en la sección a d de la cara); NSR-10 C.15.10.1 (las zapatas que soportan más de una
  columna se diseñan para las cargas mayoradas con los requisitos del reglamento, entre ellos C.11.5), C.11.5.1 y
  C.11.5.2.4, verificados en la imagen del PDF (C-184 a C-195 y C-297).
- **Decisiones del usuario:**
  1. La torsión de la viga larga se calcula por equilibrio y se verifica con el código de torsión de vigas.
  2. Las franjas transversales se mantienen (forma de la presión, momentos desde los bordes libres); el par de la
     columna que la franja no equilibra lo lleva la viga larga como torsión; Vy como fuerza axial de la franja se
     desprecia. La columna desplazada en Y ya entraba en las franjas (caras en su `y`).
  3. Solo verificación, con código común: la torsión de vigas (`domain/beam/torsion.py`) y
     `shear_and_torsion_checks` de `domain/beam/station.py` sirven a las vigas y a la viga larga. Sin propuesta de
     refuerzo; el diseño queda para la v3 Fase 3.
- **Reglas:** T(x) = ∫y·q dA de la carga neta a la izquierda − Σ (F·y − Mx + (h + hp)·Vy) de las columnas a la
  izquierda; cierra en cero en los dos extremos por el equilibrio global. Tu se toma donde se toma el cortante (a d de
  la cara). Acp = B·h. En modo cimentación la rama de torsión no agrega el cortante del eje débil, y sin barras
  superiores con momento negativo también se revisa la torsión (antes solo el cortante).
- **Entrada:** `torsion_layers`, capas de Aℓ con el formato de las vigas y `role: "torsion"` (x desde la cara −Y,
  profundidad desde la superior), validadas como en las vigas (catálogo y barras dentro del estribo); sin ellas,
  Aℓ = 0. La memoria tiene el capítulo "Viga en la dirección larga: torsión" y la fila "Capas de torsión (Aℓ)".
- **Ejemplo:** C2 de `zapata_combinada.json` pasa a y = +150 mm: Tu máx. 171.3 kN·m < φTth 209.6 kN·m, las
  verificaciones no cambian. La ZC-A de la plantilla de ETABS: 438.1 < 587.3 kN·m.
- **Revisión de la torsión contra la norma (pedida por el usuario):** ACI 318-25 9.2.4.4, 9.4.4.3, 9.5.4, 9.6.4, 9.7.5,
  9.7.6.3, 22.5.5.1 y 22.7, y NSR-10 C.11.5.1 a C.11.5.6 (imágenes del PDF, C-184 a C-195). Correctos: umbral con Nu y
  alas, √f'c ≤ 8.3 MPa, fy y fyt ≤ 420 MPa, θ = 45°, A0 = 0.85Aoh, At/s y Aℓ (22.7.6.1(b) y C.11-22 coinciden con
  θ = 45°), solo ramas exteriores, estribos cerrados, (Av + 2At)min, Aℓ,min (las dos formas son equivalentes),
  límite de la sección con el Vc de 22.5 (o de cimentación), separación ph/8 y 300 mm, y Aℓ en el perímetro con
  barras en las esquinas. Decisiones del usuario:
  1. Diámetro mínimo de Aℓ de 9.5 mm en los dos perfiles: NSR-10 C.11.5.6.2 admite la barra No. 3 (3/8") o 10M; el
     "10 mm" de ACI 9.7.5.2 se toma como la barra No. 10 del ACI en SI (9.5 mm). Antes, 10 mm rechazaba la #3.
  2. Zapata combinada con estribos: el recubrimiento es al estribo; las mallas, las barras superiores y la piel quedan
     por dentro de él (antes d quedaba sobrestimado en un diámetro de estribo y Aoh ya suponía el recubrimiento al
     estribo). Sin estribos no cambia nada.
  3. Prolongación (bt + d), desarrollo de Aℓ en los extremos y gancho de 135° de los estribos: a la hoja de ruta (v1
     Fase 2) y a las limitaciones de las memorias de vigas y de zapatas combinadas.
  Se conserva el criterio conservador de D-027: Aℓ solo cuenta las capas `torsion` (9.5.4.3 y C.11.5.3.8 permiten
  sumarlo al acero de flexión). En el ACI, la fila de la Tabla 22.5.5.1 con torsión se elige comparando el refuerzo
  transversal total con (Av + 2At)min.
- **Oráculo:** `derive_combined_beam.py` calcula T(x) y la verificación combinada aparte; casos `torsion-con-estribos`
  (cumple At, Aℓ y sección) y `torsion-sin-superior` (concreto simple y torsión sin estribos), y `momentos-sismo`
  pasa a revisar torsión. Se detectan las mutaciones sin ∫y·q, con el signo de Mx cambiado y con Tu en la cara. Con
  estribos, el oráculo ubica las barras por dentro del estribo; la mutación que lo omite se detecta.

### D-089: vigas de gran altura (v3 Fase 1.2)

- **Fecha:** 2026-11-11
- **Referencias:** ACI 318-25 9.9 (texto del PDF) y NSR-10 C.11.7 (imagen del PDF, C-200 y C-201) y C.10.7.
- **Decisiones del usuario:**
  1. La condición de viga alta (ACI 9.9.1.1, NSR-10 C.11.7.1) la declara el usuario en el JSON: `deep_beam: true` en el
     miembro o en la zapata combinada (su viga larga), también en las plantillas de ETABS; por defecto `false`.
  2. No se implementa el puntal-tensor. Se verifican los criterios de vigas altas: límites de sección, de refuerzo y
     detallamiento del refuerzo.
  3. Opción B: la flexión y el cortante seccionales se mantienen; la memoria avisa al comienzo que no consideran la
     distribución no lineal de deformaciones (ACI 9.9.1.2, NSR-10 C.11.7.2) y que el análisis no lineal o el
     puntal-tensor quedan a cargo del analista.
- **Verificaciones** (`domain/beam/deep.py`, comunes a vigas y a la viga larga; fórmulas en `codes/<perfil>/deep_beam.py`),
  en cada estación de un miembro declarado alto:
  - límite de sección Vu ≤ φ·0.83√f'c·bw·d, con el φ y el d del cortante (ACI 9.9.2.1; NSR-10 C.11.7.3, √f'c ≤ 8.3 MPa
    por C.11.1.2);
  - refuerzo distribuido transversal: ramas·Ab/s ≥ 0.0025·bw (ACI 9.9.3.1(a); NSR-10 C.11.7.4.1);
  - refuerzo distribuido longitudinal: cada capa intermedia (todas menos la superior y la inferior, de cualquier
    función) frente a 0.0025·bw por su altura tributaria; sin capas intermedias no cumple (ACI 9.9.3.1(b); NSR-10
    C.11.7.4.2);
  - separación: la de los estribos y el mayor salto vertical entre capas frente a la menor entre d/5 y 300 mm (ACI
    9.9.4.3; NSR-10 C.11.7.4.1 y C.11.7.4.2);
  - cortinas (solo ACI 9.9.4.4, con bw > 200 mm): las ramas de los estribos, una cerca de cada cara, a no más de
    600 mm a lo ancho; NSR-10 C.11.7.4 pide el refuerzo en las dos caras sin ese límite;
  - As,min (ACI 9.9.3.2, NSR-10 C.10.7.3): la verificación de vigas que ya existe.
- **Sin verificar** (limitaciones de las memorias): la resistencia no lineal o por puntal-tensor, el desarrollo en los
  apoyos simples (ACI 9.9.4.5 y 9.9.4.6, NSR-10 C.12.10.6) y el pandeo lateral (NSR-10 C.10.7.2).
- **Referencia:** ACI MNL-17(21), volumen 2, ejemplo de puntal-tensor 1, paso 11 (p. 210), solo sus criterios de 9.9:
  Av/(bw·s) y Avh/(bw·s2) = 0.00287 (±1 %, el #5 del catálogo tiene 199 mm² frente a 0.31 in²), s = 9 in frente a d/5 y
  300 mm (el libro, 12 in) y la capacidad nominal 0.83√f'c·bw·d con d = 82.5 in (±0.2 %). **Diferencia del libro:**
  aplica φ = 0.85 en 9.9.2.1 (1064 kip); ACI 318 da φ = 0.75 para cortante (Tabla 21.2.1), que el paquete conserva
  (939 kip); la prueba compara la capacidad nominal. El libro usa además d = 83.5 in para d/5 y 82.5 in en 9.9.2.1.
- **Ejemplo:** `viga_alta.json` (los dos perfiles), la viga del manual en SI (600 × 2300 mm, 12 #9 en dos capas, malla #5
  c/200 mm en cada cara); cumple. La primera versión ponía tres capas de 4 #9 y la piel no cumplía ACI 9.7.2.3
  (D-083 cuenta solo las barras `skin`); se ajustó el ejemplo, no el código.
- **Oráculo:** `derive_deep_beam.py` (seis casos: cumple, límite de sección, distribuido escaso, cortinas, sin capas
  intermedias y no declarada); se detectan las mutaciones de la altura tributaria, la separación vertical y las capas
  extremas.

### D-090: el refuerzo de piel sirve como Aℓ de torsión y la torsión como piel

- **Fecha:** 2026-11-11
- **Decisión del usuario:** el refuerzo de piel puede usarse como refuerzo longitudinal de torsión y para cumplir el
  refuerzo superficial (ACI 318-25 9.7.2.3, NSR-10 C.10.6.7). El texto de 9.7.2.3 no lo dice expresamente (solo permite
  incluir la piel en la resistencia con un análisis de compatibilidad); queda como criterio del usuario.
- **Regla, común a vigas y viga larga** (`SIDE_ROLES` en `domain/beam/flexure.py`): Aℓ provisto suma las capas `torsion`
  y `skin`; el refuerzo superficial cuenta las barras `skin` y `torsion` dentro de h/2 desde la cara en tracción, con su
  recubrimiento lateral; el diámetro mínimo de Aℓ (9.5 mm, D-088) se exige a las dos. Las capas de flexión siguen sin
  contar como Aℓ (D-027). El refuerzo distribuido de las vigas altas ya contaba todas las capas intermedias (D-089).
- **Oráculo:** casos `piel-como-torsion` y `torsion-como-piel` en `derive_combined_beam.py`; las mutaciones que vuelven a
  separar los roles se detectan. Ningún ejemplo combinaba piel y torsión: sus verificaciones no cambian.

### D-091: zapata combinada en una o en dos direcciones

- **Fecha:** 2026-11-11
- **Problema:** ACI 318-25 13.3.2 (cimentaciones en una dirección, capítulos 7 y 9) y 13.3.4 (combinadas y losas de
  cimentación en dos direcciones, capítulo 8; sin método directo; presión acorde con el suelo) no dicen cuándo una
  zapata combinada trabaja en una u otra forma; NSR-10 C.15.10 remite a los requisitos apropiados del reglamento.
- **Decisión del usuario:**
  1. Se sigue revisando en una dirección (viga larga y franjas transversales, D-080 a D-083) y se avisa cuando la
     zapata es ancha: **B ≥ ℓn**, la luz libre entre las caras de las dos columnas a lo largo de X.
  2. La revisión en dos direcciones (declarar el comportamiento e implementar el capítulo 8: mínimo 0.0018·Ag,
     separación 2h, sin torsión de viga ni Av,min ni piel, reparto entre franjas de columna y centrales) queda pendiente
     en la hoja de ruta.
- **Implementación:** `two_way_warning` en `domain/footing/combined_beam.py`; el resultado trae `two_way_warning` (B, ℓn y
  B/ℓn, o null) y la memoria un aviso al comienzo y una limitación. El aviso no cambia el estado. El ejemplo ZC1
  (B = 2600, ℓn = 4475 mm) no avisa.

### D-092: empuje pasivo sobre el pedestal y nivel freático

- **Fecha:** 2026-11-11
- **Decisión del usuario:**
  1. El pedestal no aporta empuje pasivo: el pasivo del deslizamiento sigue actuando solo sobre el espesor h de la
     zapata (D-070). Queda fuera de la hoja de ruta.
  2. El nivel freático queda pendiente de implementar. Mientras tanto, la presión, el contacto, el deslizamiento, el
     volcamiento y la revisión estructural se calculan sin agua (sin subpresión ni pesos sumergidos). Al implementarlo
     se consultarán: cómo se declara (obligatorio con null por debajo de la base, u opcional), qué revisiones afecta
     (solo las geotécnicas o también la estructural, con el factor de carga de la subpresión) y si qa se compara con la
     presión efectiva.
- **Reportado en:** las limitaciones de las memorias de zapatas aisladas y combinadas, el README y la hoja de ruta
  (v3 Fase 2).
- **Fuera del alcance (decisión del usuario):**
  - las excepciones normativas, como la de viviendas de una o dos familias para el concreto simple en cimentaciones con
    sismo alto (D-072), no se aplican en este repositorio;
  - el diseño por tipologías con apoyos en distintos niveles de cimentación no se implementará; todas las zapatas del
    diseño usan el relleno y el pedestal del bloque `design`.

### D-093: zapata combinada en T invertida de dos columnas (v3 Fase 5.3a)

- **Fecha:** 2026-11-11
- **Decisiones del usuario:**
  1. Se declara con un bloque `beam: {"width": bw, "height": H}` en `combined_footings`: h es el espesor de la zarpa y H
     la altura total; la viga va centrada en Y, las columnas caben en su ancho, `band` no aplica y las barras superiores
     son obligatorias. Las cargas de las columnas salen del Excel de ETABS o se declaran (la plantilla acepta `beam`).
  2. Dirección larga con el código de vigas y la sección T volteada (profundidades desde la cara inferior, momento con
     el signo cambiado, el ala arriba). **Ala de viga aislada** (ACI 318-25 6.3.2.2, NSR-10 C.8.12.4, verificados en el
     PDF): bf = min(4bw, B) y solo si h ≥ 0.5bw; si no, solo el alma. La tabla de 6.3.2.1 (8h, sw/2, ℓn/8) es para vigas
     con losa y almas vecinas: no aplica.
  3. Las barras x inferiores cuentan dentro de bf; la viga es estáticamente determinada (sus fuerzas salen de la
     estática con la presión de Bellos), así que As,min con el ala a tracción usa min(bf, 2bw) (ACI 9.6.1.2, NSR-10
     C.10.5.2). Reparto del ala a tracción (ACI 24.3.4 con ℓn/10; NSR-10 C.10.6.6 con la luz entre centros / 10): si
     el ancho de reparto es menor que bf debe haber barras en las zonas exteriores.
  4. Aletas: voladizos por metro desde la cara de la viga; m(x) y v(x) con la presión de Bellos integrada en Y y la
     carga uniforme de la zarpa, el relleno y las sobrecargas; se barre X y gobierna el mayor (como las franjas de la
     combinada). Flexión y εt con la malla y, cortante en una dirección con el Vc de cimentación, mínimo de losa y
     separación de 3h y 450 mm, desarrollo de las barras y desde la cara de la viga; con momento negativo, concreto
     simple (D-072).
  5. Sin punzonamiento, franjas transversales ni transferencia γf·Msc: la carga de la columna la toma la viga.
     Aplastamiento con A2 dentro de la cara superior de la viga (lx × bw, altura H) y pasadores anclados en H.
- **Pesos:** la zarpa y el alma (carga lineal bw·(γc·(H − h) − γf·min(H − h, D1)) a lo largo de X); el relleno sobre la
  zarpa menos el alma y, sobre la viga, menos las columnas; el cortante horizontal actúa a H + pedestal.
- **Otros ajustes:** las barras superiores de la T van en el ancho de la viga; los estribos no recortan lateralmente
  las barras de la zarpa; el desarrollo de las barras x no se reduce por As requerido / As provisto (la sección no es
  rectangular) y el de las superiores usa la altura total para el factor de posición; la separación de las barras
  superiores la controla la fisuración de vigas.
- **Ejemplo:** `plantilla_t_invertida_etabs.json` (los dos perfiles): ZT-1 con los nudos 15 y 1659 del Excel, viga de
  1000 × 1700 mm sobre zarpa de 9.0 × 3.6 × 0.6 m; cumple (máxima razón 0.98, refuerzo superficial). Con alma de 800 o
  900 mm aparecía torsión por los casos con EY y mandaba Aℓ,min con el Acp de la T; se ajustó el ejemplo.
- **Oráculo:** `derive_inverted_t.py` (cumple, ala delgada, aleta escasa y momento positivo); se detectan las mutaciones
  del ala igual a B, sin el límite hf ≥ 0.5bw, sin el peso del alma, sin la regla isostática, aletas sin la carga
  uniforme y A2 sobre la base.

### D-094: dirección principal de las zapatas combinadas y en T invertida

- **Fecha:** 2026-11-11
- **Problema:** la zapata combinada (D-080) y la T invertida (D-093) se modelan como una viga a lo largo de X, con las
  cargas en ejes globales de ETABS y sin rotarlas. Una zapata cuyas columnas están alineadas en la Y global no se podía
  declarar: intercambiar X e Y en la plantilla dejaba las fuerzas mal asignadas, y rotarlas en los Excel ensucia el
  flujo de trabajo con ETABS.
- **Decisión del usuario:** cada zapata combinada o en T invertida declara su dirección principal, la de la viga,
  con `principal_direction`: `x` (por defecto, el comportamiento anterior) o `y`. El JSON se escribe en ejes globales,
  como está la zapata en planta: con `y`, `ly` es la dimensión paralela a la viga y las columnas van a distintas `y`.
  Los Excel de ETABS no se modifican. Los resultados y la memoria quedan en ejes de la viga, con una nota que explica
  el giro (recomendación aceptada por el usuario).
- **Implementación:**
  1. El cálculo trabaja en ejes de la viga (X a lo largo de ella). Con `y`, `model/combined.py` pasa la zapata a esos
     ejes al cargar el proyecto, donde ya se hacen las conversiones: giro de +90° alrededor de Z (X de la viga = +Y
     global, Y de la viga = −X global). Se intercambian lx y ly; las columnas pasan a x' = y, y' = −x, con cx' = cy y
     cy' = cx; las mallas x e y (y `first`) se intercambian; las cargas, como vectores: Vx' = Vy, Vy' = −Vx, Mx' = My,
     My' = −Mx (P no cambia). `top`, estribos, refuerzo superficial, capas de torsión, `band` y la viga de la T no
     tienen dirección propia. `domain/`, `mechanics/` y los perfiles no cambian.
  2. La plantilla de ETABS acepta el campo y pasa al proyecto la geometría y las fuerzas tal cual.
  3. Con `y`, `resultado.json` trae `principal_direction` en `geometry [mm]` y la memoria nombra las dimensiones
     ("Largo de la viga (ly declarado)") y advierte el giro; con `x` la salida no cambia.
- **Control:** la misma zapata con la viga en X y girada en planta con la viga en Y (escrita en ejes globales) da las
  mismas verificaciones, valor por valor, en la combinada y en la T invertida; la importación conserva geometría y
  fuerzas y el modelo las rota; caso `viga-en-y` en `derive_combined_service.py`, con su propia matriz de giro, escrito
  en ejes globales. Los ejemplos declaran `principal_direction: "x"` de forma explícita; la huella no cambia.

### D-095: momento positivo y negativo en las dos direcciones y diagramas de la zapata combinada

- **Fecha:** 2026-11-11
- **Problema:** la viga larga ya revisaba el momento positivo y el negativo, pero la memoria mostraba una sola flexión (la de
  mayor DCR); las franjas transversales solo tenían momento positivo, porque su carga era la fuerza de la columna
  repartida con la forma de la presión (D-080, D-085), sin los pesos; y no había diagramas de momento ni de cortante.
- **Decisiones del usuario:**
  1. Franja transversal con la carga neta real, como las aletas de la T invertida (D-093): q(y) = s·forma(y) − w·b, con w
     la carga uniforme mayorada (zapata, relleno y sobrecargas: la misma `net_load` del caso), b el ancho de la franja y
     s tal que ∫q dy = F de la columna. Con la forma uniforme es F/B, como antes; donde la presión baja o se anula, la
     carga uniforme manda y aparece el momento negativo. Se revisa además, en cada voladizo, la sección del mayor momento
     negativo (64 puntos entre la cara y el borde) si no está en la cara. Sin barras superiores transversales, el
     negativo es de concreto simple en el ancho de la franja (D-072); si el nivel sísmico no lo permite, es FAIL.
  2. Diagramas: la envolvente de todos los casos mayorados (máximo y mínimo en cada punto) con el caso de cada extremo.
- **Implementación:**
  - `combined_columns.strip_load` y `strip_cantilever` (franja), `flexure.plain_strip_check` (concreto simple con el ancho
    de la franja). Cada sección de la viga larga y de las franjas lleva en su nota el signo del momento físico ("momento
    positivo" o "momento negativo"); la memoria separa por él (y por "concreto simple" en el nombre) los capítulos
    "momento positivo" y "momento negativo" de la viga larga y de la dirección transversal; si un signo no aparece, lo
    dice.
  - `domain/footing/combined_diagrams.py`: envolventes con las funciones de las verificaciones (sin fórmulas nuevas):
    M(x) y V(x) de la viga larga (con el salto en el eje de cada columna), los voladizos de cada franja y, en la T
    invertida, las aletas por metro en la sección x que gobierna cada caso. El motor los calcula, `resultado.json` los
    trae en `combined_footings[].diagrams` y `figures.diagram_figures` los dibuja en
    `diagrama_<zapata>_longitudinal.svg` y `diagrama_<zapata>_transversal.svg`; la memoria (texto y PDF) los muestra en el
    capítulo "Diagramas de momento y cortante" con la tabla de los extremos.
  - Correcciones de paso: la verificación de concreto simple no permitido conserva la nota de la sección (antes quedaba
    sin ubicación) y, entre verificaciones sin razón, gobierna la de mayor demanda.
- **Control:** oráculo `derive_combined_columns.py` con la carga neta escrita aparte y el caso `negativo-transversal` (Mx
  grande: la presión se anula hacia −Y y aparece el negativo de concreto simple); los diagramas cierran en cero en los
  bordes libres y, en la cara de la columna, dan el momento de la sección revisada; en la sección que gobierna la
  flexión positiva de la viga larga, la envolvente vale lo mismo que la revisión (el pico cae en el eje de la columna,
  modelada como carga puntual, y no se revisa ahí: la norma revisa en las caras).
- **Diferencias en los ejemplos:** `zapata_combinada.json` (los dos perfiles): 370 verificaciones PASS antes y después;
  cambian 72 valores de las franjas transversales entre −3 % y +2 % (efecto de la carga neta con presión variable); no
  aparece momento negativo. Huellas actualizadas de `zapata_combinada.json` y de las plantillas de combinadas y T
  invertida (estas, con las plantillas y los Excel del commit).

## Consultas abiertas

### C-016: páginas restantes de la fe de erratas del ACI 318-25 (SI)

- **Pendiente:** la fe de erratas tiene 17 páginas; en `references/Fe de erratas aci 318-25/` hay 6 imágenes. La descripción del documento menciona correcciones en "cálculos de resistencia a cortante" que no aparecen en ellas, y tampoco aparece 25.4.3.1 (D-066). Revisar las páginas restantes cuando estén disponibles.
