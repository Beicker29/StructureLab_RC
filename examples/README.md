# Ejemplos

Entradas válidas y documentadas, versionadas en Git. Cada carpeta tiene un `LEEME.md` con sus ejemplos y lo propio
del perfil; los campos de entrada y de salida están, una sola vez, en [docs/formatos/](../docs/formatos/).

```text
examples/
├── aci_318_25/
│   ├── vigas/       viga_rectangular.json, viga_t.json
│   └── zapatas/     zapata_aislada.json
├── nsr_10/
│   ├── vigas/       viga_rectangular.json, viga_t.json
│   └── zapatas/     zapata_aislada.json
└── etabs/
    ├── vigas/       Excel de fuerzas en vigas y su plantilla
    └── zapatas/     Excel de reacciones (servicio y mayoradas) y su plantilla
```

Las salidas van a `results/`, con la misma estructura (`results/<perfil>/<elemento>/` y `results/etabs/<elemento>/`).
`results/` es salida generada: Git solo guarda sus carpetas vacías.

| Carpeta | Instructivo |
| --- | --- |
| `aci_318_25/vigas` | [LEEME.md](aci_318_25/vigas/LEEME.md) |
| `aci_318_25/zapatas` | [LEEME.md](aci_318_25/zapatas/LEEME.md) |
| `nsr_10/vigas` | [LEEME.md](nsr_10/vigas/LEEME.md) |
| `nsr_10/zapatas` | [LEEME.md](nsr_10/zapatas/LEEME.md) |
| `etabs/vigas` | [LEEME.md](etabs/vigas/LEEME.md) |
| `etabs/zapatas` | [LEEME.md](etabs/zapatas/LEEME.md) |
