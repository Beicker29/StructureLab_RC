# Hoja de ruta de StructureLab_RC

Herramienta de oficina. La v1 cubre vigas con los perfiles `aci-318-25` y `nsr-10`.
Cada fase se cierra con pruebas, huella y decisiones registradas antes de abrir la siguiente.

**Orden vigente (2026-11-10):** cerradas las subfases 2A, 2B, 2C, 2E y 2F y la v3 hasta V3J, los pendientes siguen el
plan de etapas de la sección final, empezando por V3K (zapatas combinadas desde los Excel de ETABS).

## v1: vigas

### Fase 0: andamiaje
Estructura de carpetas, `pyproject.toml`, CI, `.gitignore`, `errors.py`, `domain/status.py`,
`setup.load_engine()`, catálogo de barras empaquetado y CLI mínima.
Aceptación: el wheel instalado fuera del repositorio arranca y carga el catálogo.

### Fase 1: modelo y mecánica
`model/` (Project, Member, Section, Demands, ReinforcementLayout, SeismicFacts),
`Check` en `domain/`, carga de JSON con conversión de unidades, `mechanics/` (compatibilidad de deformaciones
en sección rectangular y T), registro de perfiles y prueba de conformidad.
Aceptación: los ejemplos cargan y validan; los resultados de mecánica coinciden con el oráculo.

### Fase 2: verificación de vigas
Por estación y en ambos perfiles. Se entrega en subfases, cada una con su oráculo y la CI en verde:

- **2A Flexión:** φMn, φ según εt, εt mínima y As,min.
- **2B Cortante:** Vc, Vs, Av,min, separación máxima y límite de sección. Si la torsión no es despreciable
  (Tu ≥ φTth), el cortante queda `BLOCKED` hasta 2C (D-032).
- **2C Torsión:** umbral con alas, sección, At, Aℓ, distribución e interacción con el cortante. Cada capa
  declara su función; las barras de Aℓ no cuentan como As de flexión (D-027, D-034 a D-037).
- **2D Servicio:** control de fisuración y espesor mínimo (en ACI, fr = 0.62λ√f'c según la fe de erratas de 19.2.3.1, D-067). La separación por fisuración (ACI 24.3.2, NSR-10 C.10.6.4) ya se revisa (D-081); el resto, pendiente: se hará después de 2E y 2F (D-039);
  las deflexiones también quedan pendientes (D-017).
- **2E ETABS:** importación de fuerzas mayoradas desde el archivo exportado.
- **2F Memorias:** resultados en JSON, memoria en texto y PDF; huella (D-050, D-051).

Aceptación: ejemplos de referencia (Wight, ACI MNL-17) dentro de tolerancia; huella estable.

**Pendientes:**
- Deflexiones. Requieren cargas de servicio, que la entrada aún no trae (D-017).
- Reducciones permitidas en torsión: Tu a φTcr en torsión de compatibilidad (ACI 22.7.3.2, NSR-10 C.11.5.2.2)
  y Aℓ en la zona comprimida por flexión (ACI 9.5.4.5, NSR-10 C.11.5.3.9).
- Secciones huecas a torsión (ACI 22.7.7.1(b), NSR-10 C.11.5.3.1(b)); la v1 verifica secciones macizas.

### Fase 3: requisitos sísmicos de vigas
Según el nivel declarado: Ve con momentos probables, zonas de confinamiento, límites de
cuantía y geometría, empalmes prohibidos, miembros que no hacen parte del sistema.
Aceptación: un ejemplo por nivel y perfil.

### Fase 4: diseño de vigas
Optimizador sobre el catálogo: barras longitudinales, puntos de corte y estribos por zona.
Entrega las mejores soluciones ordenadas, cada una verificada con la Fase 2 y la Fase 3.

### Fase 5: despiece y dibujo
Marcas, longitudes de corte, doblado, empalmes ubicados, cartilla y cantidades.
Modelo de dibujo neutro, DXF y SVG de vista previa.

## v2 (pendiente)
Columnas (P-M biaxial y confinamiento; el diagrama de interacción usará Pn = Pu/φ, D-024), luego losas y muros, sobre el mismo
`ReinforcementLayout`. Interfaz web y API cuando la v1 esté cerrada.

## v3: zapatas (en curso)
Diseño de zapatas en ambos perfiles. La presión del suelo bajo la zapata rígida se calcula con la
solución analítica de Bellos y Bakas (2017), `references/bellos2017.pdf`. Alcance y criterios en D-052.
Se entrega en subfases, cada una con su oráculo y la CI en verde:

- **V3A Presión del suelo (hecha):** regiones A a E de Bellos e integración exacta de la presión sobre polígonos (D-053).
- **V3B Modelo y entrada (hecha):** zapata con columna y su desplazamiento, datos del suelo, mallas inferior y
  superior, propiedades derivadas, casos de servicio y mayorados desde dos Excel de ETABS (D-054, D-055).
- **V3C Verificación geotécnica (hecha, D-056):** con los casos de servicio, pmax ≤ qa, región, fracción de contacto mínima y
  equilibrio.
- **V3D Verificación estructural** (V3D.1 flexión, As,min, separación, franja y altura: hecha, D-061; V3D.2 cortante y
  punzonamiento: hecha, D-063; V3D.3 desarrollo, aplastamiento y pasadores: hecha, D-065): con la presión mayorada, flexión en las caras de la columna (mallas inferior y
  superior), As,min y separación, cortante en una dirección, punzonamiento con γv·Msc, distribución γs, altura
  mínima, desarrollo de las barras, aplastamiento y pasadores.
- **V3E Memoria y huella (hecha, D-068):** memoria de cálculo por elemento con el formato de StructureLab_HFS, para
  vigas y zapatas, en texto y PDF; huella de zapatas.
- **V3F Diseño por tipologías (hecha, D-069):** N zapatas tipo para todas las columnas, f'c comercial, planta, espesor,
  mallas y pasadores al menor costo; cada solución verificada con V3C y V3D.
- **V3G Estabilidad (hecha, D-070):** deslizamiento (fricción, adherencia sobre el área en contacto y pasiva afectada
  por su factor, en la dirección de la resultante y en cada eje) y volcamiento alrededor de cada borde, con los casos de
  servicio y los factores de seguridad declarados, sísmicos en los casos marcados; incluidos en el diseño por tipologías.
- **V3H Desarrollo (hecha, D-071):** ψe por el recubrimiento de las barras (`materials.coating`), ψcc en ganchos y el
  factor As requerido/As suministrado donde el perfil lo permite con el nivel sísmico; en `domain/development.py`,
  común a vigas y columnas.
- **V3I Concreto simple (hecha, D-072):** momento negativo sin malla superior resistido por el concreto simple donde el
  nivel sísmico lo permite; el diseño prueba primero sin malla superior; lista explícita de f'c a evaluar.
- **V3J Zapatas combinadas (hecha, D-080 a D-083):** solo verificación, dos columnas, rectangular, presión de Bellos.
  V3J.1 modelo, entrada y revisión geotécnica; V3J.2 viga en la dirección larga con el código de vigas; V3J.3 franjas
  transversales, punzonamiento, desarrollo, aplastamiento y pasadores; V3J.4 memoria, ejemplos y documentación.

## Plan de los pendientes (2026-11-10)

Una etapa por vez; cada punto con su plan, oráculo, pruebas y huella antes del siguiente.

**Etapa 1. Zapatas en uso: entrada y resultados de ETABS**
1. **V3K Zapatas combinadas desde los Excel de ETABS (hecha, D-084):** plantilla con las dos columnas de cada zapata por el Unique
   Name de su nodo; por zapata, las cargas de servicio y las mayoradas salen de los Excel (`etabs`) o de la plantilla
   (`json`), así sirve solo el Excel de servicio, solo el de últimas o ambos.
2. Correr de nuevo el diseño por tipologías desde ETABS con D-079 (N = 6 y curva costo–N), diferido.
3. Limpiar las salidas viejas de `results/` (hecho: `results/etabs/` y las corridas e3a/e3b).

**Etapa 2. Zapatas combinadas completas** (D-080 a D-083)
1. Franja transversal de una columna donde la presión del suelo es nula (hoy BLOCKED).
2. Punzonamiento de dos columnas cuyos perímetros críticos se traslapan: perímetro común (hoy cada una por separado).
3. Vy y columnas desplazadas en Y: carga directa en las franjas (Mx + H·Vy) y torsión en la viga larga (consultar el
   tratamiento de la torsión en cimentaciones).
4. Vigas de gran altura (ACI 318-25 9.9, NSR-10 C.11.7: luz libre ≤ 4h o cargas concentradas a menos de 2h del apoyo),
   en vigas y en la viga larga.

**Etapa 3. Geotecnia y estabilidad**
1. Empuje pasivo sobre el pedestal y suelo bajo nivel freático (D-070).
2. Diseño por tipologías con apoyos en distintos niveles de cimentación (hoy todas las zapatas usan el mismo relleno y el
   mismo pedestal del bloque `design`; los Excel de ejemplo tienen 4 niveles).

**Etapa 4. Desarrollo y concreto simple**
1. Factores por estribos o espirales en el desarrollo (ψr, D-071), junto con las columnas.
2. Excepción de viviendas de una o dos familias para el concreto simple en cimentaciones con sismo alto (D-072).

**Etapa 5. Tipos de cimentación nuevos, uno por vez** (D-052, D-055)
1. Medianera con viga de amarre (pausada, con 7 preguntas abiertas).
2. Zapatas combinadas de otras formas o con más de dos columnas.
3. Zapatas escalonadas, rotadas y con pedestal de sección distinta a la columna.
4. Losas de cimentación.
5. Pilotes y dados.
6. Muros.

**Etapa 6. Lo que falta de vigas (v1)**
1. 2D Servicio: espesor mínimo y deflexiones (requieren cargas de servicio en la entrada, D-017).
2. Torsión: reducción de compatibilidad, Aℓ en la zona comprimida y secciones huecas.
3. Fase 3 (sísmica), Fase 4 (diseño) y Fase 5 (despiece y dibujo).

**Etapa 7. v2 y revisión de referencias**
1. Columnas, luego losas y muros; interfaz web y API.
2. Páginas restantes de la fe de erratas del ACI 318-25 (C-016), cuando estén disponibles.
