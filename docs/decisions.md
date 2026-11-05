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
- **Decisión del usuario:** para As,min cuenta todo el acero a tracción en el estado nominal, y d es su centroide. En la viga T de ejemplo a momento positivo, As = 1928 mm² y As,min = 362 mm².

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

## Consultas abiertas

Ninguna.
