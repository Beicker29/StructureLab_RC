# Ejemplos

Entradas válidas y documentadas, versionadas en Git. Cada carpeta tiene un `LEEME.md` con sus ejemplos y lo propio
del perfil; los campos de entrada y de salida están, una sola vez, en [docs/formatos/](../docs/formatos/).

```text
examples/
├── aci_318_25/
│   ├── vigas/       viga_rectangular.json, viga_t.json, plantilla_vigas_etabs.json
│   └── zapatas/     zapata_aislada.json, diseno_tipologias.json, plantilla_zapatas_etabs.json,
│                    plantilla_diseno_zapatas_etabs.json
├── nsr_10/          los mismos ejemplos, con los mismos datos, para NSR-10
│   ├── vigas/
│   └── zapatas/
└── etabs/           Excel de ETABS compartidos por los dos perfiles
    ├── vigas/       Element Forces - Beams.xlsx
    └── zapatas/     Joint Reactions - Servicio.xlsx, Joint Reactions - Ultimas.xlsx
```

Cada ejemplo de ACI 318-25 tiene su gemelo en NSR-10 con los mismos datos; solo cambian el perfil y el nivel sísmico
equivalente (`ordinary` ↔ DMI, `intermediate` ↔ DMO, `special` ↔ DES), para poder comparar resultados (D-073).

Las salidas van a `results/`, con la misma estructura (`results/<perfil>/<elemento>/`).
`results/` es salida generada: Git solo guarda sus carpetas vacías.

| Carpeta | Instructivo |
| --- | --- |
| `aci_318_25/vigas` | [LEEME.md](aci_318_25/vigas/LEEME.md) |
| `aci_318_25/zapatas` | [LEEME.md](aci_318_25/zapatas/LEEME.md) |
| `nsr_10/vigas` | [LEEME.md](nsr_10/vigas/LEEME.md) |
| `nsr_10/zapatas` | [LEEME.md](nsr_10/zapatas/LEEME.md) |
| `etabs/vigas` | [LEEME.md](etabs/vigas/LEEME.md) (Excel compartido) |
| `etabs/zapatas` | [LEEME.md](etabs/zapatas/LEEME.md) (Excel compartidos) |
