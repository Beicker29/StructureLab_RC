# Ejemplos

Entradas válidas y documentadas, versionadas en Git. Cada carpeta tiene un `LEEME.md` con sus ejemplos y lo propio
del perfil; los campos de entrada y de salida están, una sola vez, en [docs/formatos/](../docs/formatos/).

Nombres (D-098): `<tipo>.json` con las cargas declaradas en el JSON y `<tipo>_etabs.json` con las cargas tomadas de los
Excel de ETABS (plantilla de importación).

Dos copias de cada ejemplo (D-098):

- **Para iterar**: los archivos de cada carpeta (`examples/<perfil>/<elemento>/*.json` y los Excel de
  `examples/etabs/<elemento>/`). Se pueden cambiar libremente para probar parámetros: ninguna prueba los lee.
- **Para las pruebas**: `pruebas/` dentro de cada carpeta, una copia congelada que leen las pruebas, las huellas y la CI.
  Sus plantillas leen los Excel de `examples/etabs/<elemento>/pruebas/`. Solo cambia con un cambio de cálculo o de
  formato registrado, con su huella.

```text
examples/
├── aci_318_25/
│   ├── vigas/       viga_rectangular.json, viga_t.json, viga_alta.json, viga_rectangular_etabs.json
│   │   └── pruebas/ copia congelada para las pruebas
│   └── zapatas/     zapata_centrica.json, zapata_combinada.json, diseno_tipologias.json, curva_tipologias.json,
│       │            zapata_centrica_etabs.json, zapata_combinada_etabs.json, zapata_t_invertida_etabs.json,
│       │            diseno_tipologias_etabs.json
│       └── pruebas/ copia congelada para las pruebas
├── nsr_10/          los mismos ejemplos, con los mismos datos, para NSR-10
│   ├── vigas/       (y pruebas/)
│   └── zapatas/     (y pruebas/)
└── etabs/           Excel de ETABS compartidos por los dos perfiles
    ├── vigas/       Element Forces - Beams.xlsx (y pruebas/)
    └── zapatas/     Joint Reactions - Servicio.xlsx, Joint Reactions - Ultimas.xlsx (y pruebas/)
```

`structurelab-rc run examples/nsr_10/zapatas` corre los ejemplos para iterar y salta `pruebas/`; para correr la copia
congelada se pide la carpeta: `structurelab-rc run examples/nsr_10/zapatas/pruebas`.

Cada ejemplo de ACI 318-25 tiene su gemelo en NSR-10 con los mismos datos; solo cambian el perfil y el nivel sísmico
equivalente (`ordinary` ↔ DMI, `intermediate` ↔ DMO, `special` ↔ DES), para poder comparar resultados (D-073).

Las salidas van a `results/`, con la misma estructura (`results/<perfil>/<elemento>/`) y una carpeta con el nombre
de cada ejemplo; la curva costo–N del diseño por tipologías va en `<ejemplo>_curva`.
`results/` es salida generada: Git solo guarda sus carpetas vacías.

| Carpeta | Instructivo |
| --- | --- |
| `aci_318_25/vigas` | [LEEME.md](aci_318_25/vigas/LEEME.md) |
| `aci_318_25/zapatas` | [LEEME.md](aci_318_25/zapatas/LEEME.md) |
| `nsr_10/vigas` | [LEEME.md](nsr_10/vigas/LEEME.md) |
| `nsr_10/zapatas` | [LEEME.md](nsr_10/zapatas/LEEME.md) |
| `etabs/vigas` | [LEEME.md](etabs/vigas/LEEME.md) (Excel compartido) |
| `etabs/zapatas` | [LEEME.md](etabs/zapatas/LEEME.md) (Excel compartidos) |
