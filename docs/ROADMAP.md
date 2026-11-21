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

1. Cerrar lo pendiente de cabezales (ver [Cabezales](#cabezales-sobre-pilotes)).
2. Seguir con el diseño de zapatas (ver [Diseño de zapatas](#diseño-de-zapatas)): la integración de las combinadas con
   las tipologías ya está (D-153), también en tipos (D-157).
3. El siguiente tipo de cimentación (ver [Tipos nuevos](#tipos-nuevos-uno-por-vez-d-052-d-055)).

## Validaciones del usuario

Ya confirmado: el gancho `U` de 180° y la longitud total del `.dli` (D-147).

1. El `.dli` en DL-NET (constantes con `TODO D-133` en `io/dlnet.py`). Se prueba abriendo un `.dli` con estribos y con
   un grupo de tres o más tipos de barra:
   - el campo `F0/90` de la línea del estribo, copiado del ejemplo real sin conocer su significado;
   - que b × h del estribo sean sus dimensiones exteriores;
   - la marca de los grupos de más de dos elementos (deducida de `" 1  1 "` con dos).
2. Despiece: cómo medir el gancho de 135° de las barras y los estribos (hoy por el eje de la barra, D-147).
3. El DXF sobre la plantilla de los planos de despiece (D-150), en su CAD: unidades en metros, cotas, rótulos
   (`MULTILEADER`), bloque de la barra cortada y composición por elemento.
4. Tipos de combinadas (D-157): revisar con un proyecto real el criterio de familia (separación a 1 mm, mismas secciones,
   linderos y `combined_design`) y la rejilla de posiciones de la base.

## Cimentaciones

### Cabezales sobre pilotes

1. Diseño de cabezales de varias columnas.
2. Posición de la columna en la planta y en el DXF, y un dibujo más completo del cabezal.
3. Cobertura de oráculo: estados límite CRSI 4 a 6 con varias columnas, valor del perímetro común, importación con
   `column_station` y desarrollo con varias columnas (pendiente de la auditoría de D-145).
4. Fuera del alcance (D-152): más de 16 pilotes por cabezal, esquinas recortadas con varias columnas, puntal-tensor y
   requisitos sísmicos de los pilotes.

### Tipos nuevos, uno por vez (D-052, D-055)

Cada tipo entra primero con su verificación (y su entrada desde ETABS si aplica); después, su diseño, despiece y dibujo.

1. Medianera con viga de amarre (pausada; las preguntas abiertas se reformulan al empezar).
2. Zapatas combinadas de otras formas o con más de dos columnas.
3. Zapata corrida bajo un muro (los criterios se revisan al empezar) y T invertida o zapata corrida con más de dos
   columnas.
4. Zapatas escalonadas, rotadas y con pedestal de sección distinta a la columna.
5. Losas de cimentación.
6. Muros.

### Diseño de zapatas

1. Revisión de la interacción entre zapatas vecinas (hoy la planta de localización solo avisa si se traslapan, D-153).
   El ejemplo `zapata_centrica_etabs` tiene un traslapo de datos (Z3-566 y Z3-565) que el aviso muestra.
2. La curva costo–N y la medición de tiempos (`--profile`) con los pares de combinadas y sus tipos: hoy solo diseñan
   las tipologías aisladas (D-153, D-157).
3. Más rapidez en la búsqueda de cada combinada, que hoy fija el tiempo de los tipos (D-157): con tres pares, cerca de
   2 minutos con 32 procesos; cada búsqueda revisa todos los casos de todos sus pares.

### Zapata combinada en dos direcciones

1. Comportamiento en dos direcciones (ACI 13.3.4, capítulo 8): declararlo e implementar sus verificaciones (mínimo
   0.0018·Ag en cada dirección, separación 2h y 450 mm, sin torsión de viga, Av,min ni piel, y un criterio de reparto
   entre franjas de columna y centrales). Hoy se revisa en una dirección y se avisa si B ≥ ℓn (D-091).

### Nivel freático

1. Suelo bajo nivel freático: subpresión en la base, pesos sumergidos y pasiva con γ' (D-092). Antes de implementarlo,
   consultar cómo se declara, qué revisiones afecta y con qué presión se compara qa. El pedestal no aporta pasiva por
   decisión del usuario.

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
prohibidos y miembros que no hacen parte del sistema. Aceptación: un ejemplo por nivel y perfil.

### Diseño

1. Piezas neutras que faltan en `design/` (ya están las barras para un As requerido, D-107, y los estribos cerrados,
   D-110): barras en varias capas a partir de la envolvente de As requerido por estación; puntos de corte con ld y las
   extensiones (d, 12db, punto de inflexión) que el perfil calcula; estribos por zona.
2. Diseño de vigas con esas piezas, los requisitos sísmicos y las secciones T; mejores soluciones ordenadas, cada una
   verificada.

### Despiece y dibujo

Sobre el despiece y el dibujo de las cimentaciones (formas, longitudes de corte, empalmes, marcas, cartilla, cantidades,
modelo de dibujo, DXF y SVG): alzado y secciones de la viga, estribos por zona, empalmes fuera de las zonas prohibidas y
secciones T.

## Columnas, losas y muros

1. Columnas: P-M biaxial y confinamiento (el diagrama de interacción usará Pn = Pu/φ, D-024); factor ψr de estribos o
   espirales en el desarrollo (D-071).
2. Losas y muros, sobre el mismo `ReinforcementLayout`.
3. Interfaz web y API.

## Diferido

- Correr de nuevo el diseño por tipologías desde ETABS con D-079 (N = 6 y curva costo–N).
- Algoritmo genético: para la geometría de la zapata combinada y la T (con el refuerzo determinista actual y la cota de
  costo del concreto) y como mejora de la calidad del óptimo del diseño por tipologías, no del tiempo.
- Rendimiento (D-124): vectorizar el cálculo de las barras con NumPy si hace falta otro salto; flexión uniaxial en
  zapatas con M2 = 0 (cambia resultados en secciones asimétricas, requiere decisión).

## Referencias

- Páginas restantes de la fe de erratas del ACI 318-25 (C-016), cuando estén disponibles.
