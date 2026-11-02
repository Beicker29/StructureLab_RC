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

## Consultas abiertas

Ninguna.
