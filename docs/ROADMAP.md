# Hoja de ruta de StructureLab_RC

Herramienta de oficina. La v1 cubre vigas con los perfiles `aci-318-25` y `nsr-10`.
Cada fase se cierra con pruebas, huella y decisiones registradas antes de abrir la siguiente.

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
- **2C Torsión:** umbral, sección, At, Al e interacción con el cortante. Cada capa del armado declara su
  función; las barras de Al no cuentan como As de flexión (D-027).
- **2D Servicio:** control de fisuración y espesor mínimo. Las deflexiones quedan pendientes (D-017).
- **2E ETABS:** importación de fuerzas mayoradas desde el archivo exportado.
- **2F Memorias:** resultados en JSON, memoria en texto y PDF; huella.

Aceptación: ejemplos de referencia (Wight, ACI MNL-17) dentro de tolerancia; huella estable.

**Pendientes:**
- Deflexiones. Requieren cargas de servicio, que la entrada aún no trae (D-017).
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

## v2
Columnas (P-M biaxial y confinamiento; el diagrama de interacción usará Pn = Pu/φ, D-024), luego losas, zapatas y muros, sobre el mismo
`ReinforcementLayout`. Interfaz web y API cuando la v1 esté cerrada.
