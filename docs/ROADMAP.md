# Hoja de ruta de StructureLab_RC

Herramienta de oficina. La v1 cubre vigas con los perfiles `aci-318-25` y `nsr-10`.
Cada fase se cierra con pruebas, huella y decisiones registradas antes de abrir la siguiente.

**Orden vigente:** cerradas las subfases 2A, 2B, 2C, 2E y 2F, sigue la v3 (zapatas). Quedan pendientes
la subfase 2D, las Fases 3 a 5 de vigas, las mejoras de la memoria y la v2.

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
- **2D Servicio:** control de fisuración y espesor mínimo. Pendiente: se hará después de 2E y 2F (D-039);
  las deflexiones también quedan pendientes (D-017).
- **2E ETABS:** importación de fuerzas mayoradas desde el archivo exportado.
- **2F Memorias:** resultados en JSON, memoria en texto y PDF; huella (D-050, D-051).

Aceptación: ejemplos de referencia (Wight, ACI MNL-17) dentro de tolerancia; huella estable.

**Pendientes:**
- Deflexiones. Requieren cargas de servicio, que la entrada aún no trae (D-017).
- Reducciones permitidas en torsión: Tu a φTcr en torsión de compatibilidad (ACI 22.7.3.2, NSR-10 C.11.5.2.2)
  y Aℓ en la zona comprimida por flexión (ACI 9.5.4.5, NSR-10 C.11.5.3.9).
- Secciones huecas a torsión (ACI 22.7.7.1(b), NSR-10 C.11.5.3.1(b)); la v1 verifica secciones macizas.
- Excepción de As,min cuando As supera en un tercio al requerido (ACI 9.6.1.3, NSR-10 C.10.5.3). Mientras no exista, la verificación devuelve `BLOCKED` si As < As,min (D-022).

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
- **V3D Verificación estructural** (V3D.1 flexión, As,min, separación, franja y altura: hecha, D-061; siguen V3D.2
  cortante y punzonamiento y V3D.3 desarrollo, aplastamiento y pasadores): con la presión mayorada, flexión en las caras de la columna (mallas inferior y
  superior), As,min y separación, cortante en una dirección, punzonamiento con γv·Msc, distribución γs, altura
  mínima, desarrollo de las barras, aplastamiento y pasadores.
- **V3E Memoria y huella:** memoria, resultados y huella de zapatas.
- **V3F Diseño:** dimensiones en planta, altura y barras del catálogo; soluciones ordenadas y verificadas con V3C y V3D.

Pendientes de la v3: diseño en concreto simple (momento negativo sin malla superior, D-059), zapatas combinadas, medianeras con viga de amarre, losas de cimentación, pilotes, zapatas
escalonadas, zapatas rotadas, pedestal de sección distinta a la columna y muros (D-052, D-055).
