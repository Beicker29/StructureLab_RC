# Hoja de ruta de StructureLab_RC

Herramienta de oficina. La v1 cubre vigas con los perfiles `aci-318-25` y `nsr-10`.
Cada fase se cierra con pruebas, huella y decisiones registradas antes de abrir la siguiente.

## v1: vigas

### Fase 0: andamiaje
Estructura de carpetas, `pyproject.toml`, CI, `.gitignore`, `errors.py`, `domain/status.py`,
`setup.load_engine()`, catálogo de barras empaquetado y CLI mínima.
Aceptación: el wheel instalado fuera del repositorio arranca y carga el catálogo.

### Fase 1: modelo y mecánica
`model/` (Project, Member, Section, Demands, ReinforcementLayout, SeismicFacts, Check),
carga de JSON con conversión de unidades, `mechanics/` (compatibilidad de deformaciones
en sección rectangular y T), registro de perfiles y prueba de conformidad.
Aceptación: los ejemplos cargan y validan; los resultados de mecánica coinciden con el oráculo.

### Fase 2: verificación de vigas
Flexión, cortante, torsión y servicio en ambos perfiles, por estación. Importación de
fuerzas desde ETABS. Memoria en texto, JSON y PDF.
Aceptación: ejemplos de referencia (Wight, ACI MNL-17) dentro de tolerancia; huella estable.

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
Columnas (P-M biaxial y confinamiento), luego losas, zapatas y muros, sobre el mismo
`ReinforcementLayout`. Interfaz web y API cuando la v1 esté cerrada.
