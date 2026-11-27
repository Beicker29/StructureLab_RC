# Hoja de ruta de StructureLab_RC

Solo lista lo que falta por implementar, en el orden en que se va a trabajar. Lo implementado está en el
[README](../README.md#estado) (resumen), en [docs/formatos/](formatos/) (detalle por elemento) y en
[decisions.md](decisions.md) (el porqué, decisión por decisión). Cada fase se cierra con plan aprobado, oráculo,
pruebas y huella antes de abrir la siguiente.

**Orden vigente (prioridad del usuario, 2026-11-12):** cimentaciones (tipos nuevos y su diseño, despiece y dibujo),
luego vigas, luego columnas, losas y muros. El diseño, el despiece y el dibujo se construyen en cimentaciones con piezas
neutras que después reutilizan las vigas.

## Siguiente

El usuario elige entre:

1. Muro de contención en voladizo, fase A (en curso, ver [Muros de contención](#muros-de-contención-d-173)).
2. Cerrar lo pendiente de cabezales (ver [Cabezales](#cabezales-sobre-pilotes)).
3. El siguiente tipo de cimentación (ver [Tipos nuevos](#tipos-nuevos-uno-por-vez-d-052-d-055)).

## Validaciones del usuario

1. Tipos de combinadas (D-157): revisar con un proyecto real el criterio de familia (separación a 1 mm, mismas secciones,
   linderos y `combined_design`) y la rejilla de posiciones de la base.
2. `.dli` en DL-NET con elementos tipo y estribos (D-159, D-160, D-161): abrir el del diseño por tipologías desde ETABS
   y revisar que el total de cada grupo multiplique por N (`10  5  24  9  14  5  3`) y que la longitud y el peso de cada
   estribo coincidan con la cartilla (L = 2·(b + h) + 2·g; en el de una rama, L = h + 2·g).
3. DXF de cabezales (D-166): abrirlo en AutoCAD y revisar los pilotes, sus cotas, el cuadro de pilotes y que los campos
   L de los alzados (MULTILEADER) se actualicen al estirar una barra.
4. Combinadas no rectangulares (D-164, D-167, D-169, D-170): abrir en DL-NET y en AutoCAD el `.dli` y el DXF de
   `zapata_combinada_trapecio`, `_planta_l`, `_planta_t`, `_planta_i`, `_trapecio_estribos`, `zapata_t_invertida_trapecio`
   y los diseños de `diseno_combinada_formas` y `diseno_t_invertida_formas`: las marcas de las barras y los estribos de
   longitud variable (una por medida), la piel inclinada, las cotas de la planta y su ubicación en la planta de
   localización.
5. Rapidez del diseño por tipologías (D-171): correr en el PC personal `structurelab-rc run
   examples/nsr_10/zapatas/tipologias/diseno_tipologias_etabs.json --profile` y comparar `medicion.json` con los tiempos
   de este PC.
6. Alertas de tipologías atípicas (D-172): con un proyecto real, revisar si los umbrales de `typology_alerts` señalan
   las tipologías que el ingeniero considera atípicas (`tipologias_estadistica.csv`, `alertas_columnas.csv` y la sección
   final de la memoria) y ajustarlos en la plantilla.

## Cimentaciones

### Cabezales sobre pilotes

1. Diseño de cabezales de varias columnas.
2. Cobertura de oráculo: estados límite CRSI 4 a 6 con varias columnas, valor del perímetro común, importación con
   `column_station` y desarrollo con varias columnas (pendiente de la auditoría de D-145).

### Tipos nuevos, uno por vez (D-052, D-055)

Cada tipo entra primero con su verificación (y su entrada desde ETABS si aplica); después, su diseño, despiece y dibujo.

1. Medianera con viga de amarre (pausada; las preguntas abiertas se reformulan al empezar).
2. Zapata corrida bajo un muro (los criterios se revisan al empezar).
3. Zapatas escalonadas, rotadas y con pedestal de sección distinta a la columna.
4. Losas de cimentación.

### Zapata combinada en dos direcciones

1. Comportamiento en dos direcciones (ACI 13.3.4, capítulo 8): declararlo e implementar sus verificaciones (mínimo
   0.0018·Ag en cada dirección, separación 2h y 450 mm, sin torsión de viga, Av,min ni piel, y un criterio de reparto
   entre franjas de columna y centrales). Hoy se revisa en una dirección y se avisa si B ≥ ℓn (D-091).

### Nivel freático

1. Suelo bajo nivel freático: subpresión en la base, pesos sumergidos y pasiva con γ' (D-092). Antes de implementarlo,
   consultar cómo se declara, qué revisiones afecta y con qué presión se compara qa. El pedestal no aporta pasiva por
   decisión del usuario.

## Muros de contención (D-173)

Categoría propia, como zapatas o vigas (`examples/<perfil>/muros/<tipología>/`, `docs/formatos/muros.md`). Referencia de
los ejemplos: ACI MNL-17(21), capítulo 12 (en unidades inglesas, pasados a SI); empujes según B. M. Das, *Principles of
Geotechnical Engineering* SI, 8.ª ed., 2014, capítulo 13, sin simplificaciones.

### Voladizo

1. Fase A (cerrada el 2026-11-27, revisión del usuario pendiente), verificación del muro declarado (ejemplo 2 del
   manual): empuje activo o en reposo (Ka o Ko, calculado con
   Rankine o Coulomb a partir de los datos declarados, o declarado), estabilidad al volcamiento y al deslizamiento con
   la pasiva declarada, presiones bajo la base, pantalla como losa en una dirección (flexión, cortante, mínimos,
   separaciones y retracción), talón con carga neta y factor del relleno declarado, puntera y desarrollo de los
   pasadores. Cada caso declara sus factores de carga.
2. Fase A2: sobrecarga, relleno inclinado, muro sin puntera o sin talón y llave de cortante (ejemplos 3 a 6 del manual).
3. Fase B: diseño de menor costo, cada solución verificada.
4. Fase C: despiece (cartilla por metro y por la longitud del muro, corte de barras en la pantalla).
5. Fase D: dibujo (corte transversal en DXF y SVG).

### Pendientes del voladizo (después de las fases A a D)

1. Sismo:
   - empuje sísmico del relleno por Mononobe–Okabe (Das §13.13);
   - fuerza sísmica de la masa de la pantalla (y de la zapata y el relleno que se mueven con el muro);
   - cómo combinar el empuje de Mononobe–Okabe con la inercia de la masa de la pantalla (simultáneos o con un factor de
     combinación), según NSR-10 Título H y la referencia que se adopte. Consultar antes de implementar.
2. Nivel freático en el relleno y bajo la base (subpresión y pesos sumergidos).
3. Carga axial en la pantalla (hoy se desprecia, del lado de la seguridad).
4. Relleno cohesivo (c' > 0, con la grieta de tracción); la primera fase exige relleno granular.

### Sótano

1. Muro de sótano apoyado en la losa o el entrepiso superior y en la cimentación (ejemplo 1 del manual), con su
   verificación, diseño, despiece y dibujo. Los criterios se revisan al empezar.

### Gravedad

1. Muro de gravedad con Rankine sobre el trasdós virtual o con Coulomb sobre su cara (casos 2 y 3 de la decisión 9 de
   D-173, Das 2016 §13.3, fig. 13.4b y c), con su verificación, diseño, despiece y dibujo. Sus ejemplos van en
   `examples/<perfil>/muros/gravedad/`, con los de iterar afuera y la copia congelada en `pruebas/`, como el voladizo.

## Vigas

### Verificación pendiente

1. Servicio: espesor mínimo y deflexiones; requieren cargas de servicio en la entrada (D-017, D-039). En ACI,
   fr = 0.62λ√f'c según la fe de erratas de 19.2.3.1 (D-067).
2. Torsión: reducción a φTcr en torsión de compatibilidad (ACI 22.7.3.2, NSR-10 C.11.5.2.2), Aℓ en la zona comprimida
   por flexión (ACI 9.5.4.5, NSR-10 C.11.5.3.9) y secciones huecas (ACI 22.7.7.1(b), NSR-10 C.11.5.3.1(b)); prolongación
   (bt + d) del refuerzo de torsión (ACI 9.7.5.3 y 9.7.6.3.2, NSR-10 C.11.5.6.3), desarrollo de Aℓ en los extremos (ACI
   9.7.5.4, NSR-10 C.11.5.4.3) y gancho de 135° de los estribos cerrados (ACI 25.7.1.6, NSR-10 C.11.5.4.2). Aplican a
   las vigas y a la viga larga de la zapata combinada (D-088); necesitan datos por tramo que la entrada por estaciones
   no trae.
3. Vigas de gran altura (D-089): desarrollo en los apoyos simples (ACI 9.9.4.5 y 9.9.4.6, NSR-10 C.12.10.6) y pandeo
   lateral (NSR-10 C.10.7.2). El puntal-tensor queda fuera del alcance por decisión del usuario.
4. Separación mínima del refuerzo (D-102): la separación libre entre las barras de cada capa (ACI 25.2.1, NSR-10
   C.7.6.1 y C.3.3.2(c), con `materials.max_aggregate` obligatorio) y la separación vertical libre entre capas de al
   menos 25 mm (ACI 25.2.2, NSR-10 C.7.6.2). En zapatas ya se revisa; en vigas el subcapítulo 6.2.2 de la memoria queda
   vacío hasta entonces.

### Requisitos sísmicos

Según el nivel declarado: Ve con momentos probables, zonas de confinamiento, límites de cuantía y geometría, empalmes
prohibidos y miembros que no hacen parte del sistema. Hoops (estribos de confinamiento, ganchos sísmicos en los dos
extremos) y crossties (ganchos suplementarios: gancho sísmico en un extremo y de al menos 90° en el otro) como piezas
propias, con el vocabulario del ACI 318-25 (D-161); el gancho de cada uno mide la g del estribo (D-160). Aceptación: un
ejemplo por nivel y perfil.

### Diseño

1. Piezas neutras que faltan en `design/` (ya están las barras para un As requerido, D-107, y los estribos cerrados,
   D-110): barras en varias capas a partir de la envolvente de As requerido por estación; puntos de corte con ld y las
   extensiones (d, 12db, punto de inflexión) que el perfil calcula; estribos por zona.
2. Diseño de vigas con esas piezas, los requisitos sísmicos y las secciones T; mejores soluciones ordenadas, cada una
   verificada.

### Despiece y dibujo

Sobre el despiece y el dibujo de las cimentaciones (formas, longitudes de corte, empalmes, marcas, cartilla, cantidades,
modelo de dibujo, DXF y SVG): alzado y secciones de la viga, estribos por zona, empalmes fuera de las zonas prohibidas y
secciones T. Las vigas declaran `quantity` y su tipo, y usan `detailing/units.py` para la cartilla de una unidad y de las
N unidades (D-159); sus estribos, la convención de D-160.

## Columnas, losas y muros

1. Columnas: P-M biaxial y confinamiento (el diagrama de interacción usará Pn = Pu/φ, D-024); factor ψr de estribos o
   espirales en el desarrollo (D-071). Su refuerzo transversal son ties (y hoops y crossties en zonas sísmicas), no
   stirrups (ACI 318-25 cap. 2, D-161).
2. Losas y muros, sobre el mismo `ReinforcementLayout`.
3. Interfaz web y API.

## Diferido

- Algoritmo genético: para la geometría de la zapata combinada y la T (con el refuerzo determinista actual y la cota de
  costo del concreto) y como mejora de la calidad del óptimo del diseño por tipologías, no del tiempo.
- Rendimiento (D-124): vectorizar el cálculo de las barras con NumPy si hace falta otro salto; flexión uniaxial en
  zapatas con M2 = 0 (cambia resultados en secciones asimétricas, requiere decisión).

## Referencias

- Páginas restantes de la fe de erratas del ACI 318-25 (C-016), cuando estén disponibles.
