# Reglas de trabajo de StructureLab_RC

## Alcance

- El repositorio verifica, diseña, despieza y dibuja elementos de concreto reforzado.
  La v1 cubre solo vigas. Los demás elementos se incorporan en el orden de la
  [hoja de ruta](docs/ROADMAP.md), uno por vez.
- Dos perfiles normativos: `aci-318-25` (ACI CODE-318-25) y `nsr-10` (NSR-10 Título C).
  Cada proyecto declara un solo perfil y todo su cálculo sale de él. Nunca se mezclan.
- Fuente normativa: los PDF locales en `references/` (ignorada por Git; no versionar PDF).
  Ecuaciones en unidades SI. Si un PDF trae solo unidades inglesas, consultar antes de
  convertir constantes.
- Decisiones y consultas abiertas: [docs/decisions.md](docs/decisions.md).
- Antes de trabajar, registrar rama/SHA y cambios locales. No borrar trabajo del usuario
  ni archivos no versionados desconocidos; no cambiar permisos.
- Sin commit ni push salvo autorización. Mensajes de commit descriptivos.

## Arquitectura

Una fuente de verdad por concepto ([arquitectura](docs/architecture.md)).

- Fórmulas y constantes en `codes/<perfil>/<tema>.py`: funciones puras con el nombre de
  su ecuación o numeral. Sin lectura de archivos, sin imports de otras capas del paquete
  y sin imports del otro perfil.
- Ambos perfiles exponen los mismos módulos y nombres públicos. Una prueba de
  conformidad lo verifica.
- Elección de cláusula y armado de cada `Check` en `domain/<elemento>/`. `engine.py`
  solo orquesta. Las interfaces (CLI, futura web) llaman a `engine`/`execution`; nunca
  calculan capacidades.
- `mechanics/` es neutro: equilibrio, compatibilidad, fibras, Icr. No conoce φ ni numerales.
- `model/ReinforcementLayout` es el contrato central: lo produce `design/`, lo evalúa
  `domain/` y lo consumen `detailing/` y `drawing/`.
- `detailing/` y `drawing/` son neutros: usan límites ya calculados por el perfil
  (ld, ganchos, separaciones) y no contienen fórmulas normativas.
- Sin respaldo cruzado: lo no implementado en un perfil devuelve `BLOCKED`
  ("no implementado en NSR-10"); nunca se usa la fórmula del otro perfil.
- No fusionar ecuaciones por parecido algebraico. NSR-10 deriva de ACI 318-08: aunque
  una ecuación coincida, cada perfil la define con su numeral.
- El nivel sísmico es un hecho declarado por el usuario en el vocabulario de su perfil
  (`DMI`/`DMO`/`DES`; `none`/`ordinary`/`intermediate`/`special`), con una justificación
  textual que sale en la memoria. La app no lo deriva; solo valida que exista en el perfil.
- Las fuerzas llegan mayoradas (JSON o ETABS). No se generan combinaciones en la v1.
- Unidades: entrada en mm, MPa, kN y kN·m; interno en N, mm y MPa. La conversión ocurre
  solo al cargar (`model/`) y al presentar (`reporting/`, con `kN()` y `kNm()`).
- Tablas (barras, ganchos, materiales) en `src/structurelab_rc/data/` como CSV o TOML,
  cargadas por `setup.load_engine()`. Nada de Excel versionado.
- No añadir clases, servicios, registros o dependencias sin necesidad demostrada.
- Eliminar el código sustituido en la misma tarea; sin fachadas sin consumidores.

## Estados y exactitud normativa

- Estados: `PASS`, `FAIL`, `INCOMPLETE`, `BLOCKED`. Una sola agregación, en
  `domain/status.py`: `FAIL` prevalece sobre `INCOMPLETE`, este sobre `BLOCKED` y este
  sobre `PASS`.
- `PASS` solo para el alcance declarado, con todas las obligaciones cumplidas.
- No suponer valores por ausencia de datos: `INCOMPLETE` con error estructurado.
- Para cambiar una regla, identificar numeral, ecuación, condiciones y unidades;
  distinguir norma y comentario.
- Una decisión que la norma no resuelve inequívocamente se consulta al usuario (problema,
  referencia, alternativas, consecuencias, recomendación) y se registra en `docs/decisions.md`.
- `float` en el cálculo; redondeo solo para presentación. Los factores φ se leen del
  resultado, nunca como literal en la memoria.

## Ejemplos, resultados y verificación

- `examples/<perfil>/*.json` versionados, entradas válidas y documentadas.
  `results/` es salida generada e ignorada.
- La huella de los ejemplos se calcula sobre el JSON de resultado, la memoria en texto,
  la cartilla y `<nombre>_drawing.json`, sin fecha. Nunca sobre el DXF ni el PDF.
- Cambios de cálculo requieren casos en el oráculo independiente
  (`tests/oracles/<perfil>/`, no importa el paquete).
- No modificar valores de referencia para hacer pasar un cambio.
- Antes de cerrar: `pytest`, `ruff check`, `mypy`, `lint-imports` y la huella.
- Cerrar cada tarea con: cambios, pruebas reales (comando y resultado), diferencias
  numéricas, riesgos y pendientes.
