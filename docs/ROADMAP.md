# Hoja de ruta de StructureLab_RC

Herramienta de oficina para elementos de concreto reforzado con los perfiles `aci-318-25` y `nsr-10`. Solo lista lo
pendiente; lo hecho está en [decisions.md](decisions.md) y en el historial de Git. Cada fase se cierra con plan
aprobado, oráculo, pruebas y huella antes de abrir la siguiente.

**Orden vigente (2026-11-10):** v3 fases 1 a 5, luego v1 fases 2 a 5, luego v2. El diseño, el despiece y el dibujo se
construyen primero en zapatas (v3 fases 3 y 4) con piezas neutras que después reutilizan las vigas (v1 fases 4 y 5).

**Pendiente sin fase:** correr de nuevo el diseño por tipologías desde ETABS con D-079 (N = 6 y curva costo–N); diferido
por el usuario.

## v3: zapatas (en curso)

Hecho: zapata aislada (verificación, diseño por tipologías, estabilidad, concreto simple) y zapata combinada de dos
columnas (verificación, entrada desde ETABS), D-052 a D-087.

### Fase 1: zapatas combinadas completas

1. Zapata combinada en dos direcciones (ACI 13.3.4, capítulo 8): declarar el comportamiento e implementar sus
   verificaciones (mínimo 0.0018·Ag en cada dirección, separación 2h y 450 mm, sin torsión de viga, Av,min ni piel, y un
   criterio de reparto entre franjas de columna y centrales). Hoy se revisa en una dirección y se avisa si B ≥ ℓn
   (D-091).

### Fase 2: geotecnia, estabilidad y concreto simple

1. Suelo bajo nivel freático: subpresión en la base, pesos sumergidos y pasiva con γ' (D-092). Antes de implementarlo,
   consultar cómo se declara, qué revisiones afecta y con qué presión se compara qa. El pedestal no aporta pasiva por
   decisión del usuario.
2. Excepción de viviendas de una o dos familias para el concreto simple en cimentaciones con sismo alto (D-072).

### Fase 3: diseño (alcance de la Fase 4 de vigas)

Optimizador sobre el catálogo; entrega las mejores soluciones ordenadas por costo, cada una aprobada por la verificación
existente. Sin fórmulas propias; si nada cumple, `FAIL` con el motivo y los límites no se amplían (como D-069).

- **3A Piezas reutilizables** (neutras, en `design/`, para la viga larga ahora y para las vigas después):
  - barras longitudinales a partir de la envolvente de As requerido por estación (`domain/flexure_strength`), con
    separaciones y número de capas del perfil;
  - puntos de corte con ld y las extensiones (d, 12db, punto de inflexión) que el perfil calcula;
  - estribos por zona a partir del cortante (Vs requerido, Av,min y separación máxima del perfil);
  - refuerzo superficial cuando h > 900 mm.
- **3B Zapata combinada:** largo, ancho y posición respecto a las columnas (resultante de servicio centrada o
  declarada), espesor, barras de la viga larga con 3A, franjas transversales (`band`), malla, pasadores y refuerzo
  superficial.
- **3C Integración con las tipologías:** pares de columnas con zapata combinada en el diseño desde ETABS (declarados en
  la plantilla o por cercanía, a consultar) y la planta de cada tipo.

### Fase 4: despiece y dibujo (alcance de la Fase 5 de vigas)

- **4A Despiece** (`detailing/`, neutro, sin fórmulas normativas):
  - forma de cada barra (recta, gancho de 90° o 180°, L, U, estribo cerrado) con el diámetro de doblado y la
    extensión del gancho que da el perfil, y su longitud de corte;
  - empalmes por traslapo ubicados cuando la barra supera la longitud comercial;
  - marcas, cartilla (marca, diámetro, cantidad, forma, dimensiones, longitud y peso) y cantidades (acero por diámetro y
    concreto);
  - aplicado a mallas, pasadores, viga larga (cortes, estribos, piel) y franjas.
  - El costo del diseño por tipologías pasa a usar estas cantidades (una sola fuente de pesos); puede mover resultados
    del diseño, se revisa al implementarlo.
- **4B Dibujo** (`drawing/`, neutro):
  - modelo de dibujo neutro `<nombre>_drawing.json` (capas, líneas, polilíneas, círculos, textos, cotas y tablas en
    mm);
  - vistas: planta con mallas y marcas, cortes en X y en Y; en la combinada, alzado de la viga larga con cortes y
    estribos; cartilla como tabla; planta de localización de las tipologías con las coordenadas de ETABS;
  - salidas DXF (extra `cad`, ezdxf) y SVG de vista previa.
  - Huella sobre la cartilla y `<nombre>_drawing.json`; nunca sobre el DXF ni el PDF.
- **Reutilización en vigas:** formas, longitudes de corte, empalmes, marcas, cartilla, cantidades, modelo de dibujo,
  salidas DXF/SVG, sección transversal y alzado de viga (el de la viga larga). Las vigas añadirán los requisitos
  sísmicos (v1 Fase 3) y las secciones T.
- **Consultas al empezar:** longitud comercial de las barras y clase de empalme, redondeo de longitudes, convención de
  marcas, ganchos en los bordes de la zapata, capas y escala del DXF, columnas de la cartilla.

### Fase 5: tipos de cimentación nuevos, uno por vez (D-052, D-055)

Cada tipo entra con verificación, diseño, despiece y dibujo sobre las fases 3 y 4.

1. Medianera con viga de amarre (pausada, con 7 preguntas abiertas).
2. Zapatas combinadas de otras formas o con más de dos columnas.
3. Zapata combinada en T invertida (viga de cimentación sobre una zarpa más ancha) y zapata corrida (strip footing)
   bajo una fila de columnas o un muro: la viga y las aletas de la zarpa, con la presión del suelo, revisadas con el
   código de vigas y de losas en una dirección (ACI 13.3.2, NSR-10 C.15).
4. Zapatas escalonadas, rotadas y con pedestal de sección distinta a la columna.
5. Losas de cimentación.
6. Pilotes y dados.
7. Muros.

## v1: vigas (pendientes)

Hecho: andamiaje, modelo y mecánica, verificación por estación (flexión, cortante, torsión, separación por fisuración),
importación de ETABS y memorias (fases 0 a 2, D-001 a D-051).

### Fase 2: verificación pendiente

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

### Fase 3: requisitos sísmicos

Según el nivel declarado: Ve con momentos probables, zonas de confinamiento, límites de cuantía y geometría, empalmes
prohibidos y miembros que no hacen parte del sistema. Aceptación: un ejemplo por nivel y perfil.

### Fase 4: diseño

Barras longitudinales, puntos de corte y estribos por zona con las piezas de la v3 Fase 3A, más los requisitos sísmicos
de la Fase 3 y las secciones T; mejores soluciones ordenadas, cada una verificada con las fases 2 y 3.

### Fase 5: despiece y dibujo

Sobre la v3 Fase 4: alzado y secciones de la viga, estribos por zona, empalmes ubicados fuera de las zonas prohibidas,
cartilla y cantidades; DXF y SVG.

## v2: columnas, losas y muros

1. Columnas: P-M biaxial y confinamiento (el diagrama de interacción usará Pn = Pu/φ, D-024); factor ψr de estribos o
   espirales en el desarrollo (D-071).
2. Losas y muros, sobre el mismo `ReinforcementLayout`.
3. Interfaz web y API.

## Referencias

- Páginas restantes de la fe de erratas del ACI 318-25 (C-016), cuando estén disponibles.
