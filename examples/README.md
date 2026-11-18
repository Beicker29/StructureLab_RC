# Ejemplos

Entradas válidas y documentadas, versionadas en Git. Cada carpeta tiene un `LEEME.md` con sus ejemplos y lo propio
del perfil; los campos de entrada y de salida están, una sola vez, en [docs/formatos/](../docs/formatos/).

Nombres (D-098): `<tipo>.json` con las cargas declaradas en el JSON y `<tipo>_etabs.json` con las cargas tomadas de los
Excel de ETABS (plantilla de importación).

Dos copias de cada ejemplo (D-098):

- **Para iterar**: los archivos de cada carpeta y los Excel de `examples/etabs/<elemento>/`. Se pueden cambiar
  libremente para probar parámetros: ninguna prueba los lee.
- **Para las pruebas**: `pruebas/` dentro de cada carpeta, una copia congelada que leen las pruebas, las huellas y la CI.
  Sus plantillas leen los Excel de `examples/etabs/<elemento>/pruebas/`. Solo cambia con un cambio de cálculo o de
  formato registrado, con su huella.

Los elementos con varias tipologías van en una carpeta por tipología (D-146), cada una con su `LEEME.md` (ejemplos y
comandos) y su `pruebas/`:

```text
examples/
├── aci_318_25/ y nsr_10/   los mismos ejemplos, con los mismos datos, en cada perfil
│   ├── cabezales/
│   │   ├── una_columna/       una columna: cargas de la columna o de los pilotes, tres pilotes, diseño, ETABS
│   │   └── varias_columnas/   dos y cuatro columnas
│   ├── zapatas/
│   │   ├── aislada/           céntrica, diseño por tipologías y curva costo–N, ETABS
│   │   ├── combinada/         combinada de dos columnas y su diseño, ETABS
│   │   └── t_invertida/       T invertida y su diseño, ETABS
│   └── vigas/                 rectangular, T, de gran altura, ETABS
└── etabs/                     Excel de ETABS compartidos por los dos perfiles (cabezales/, zapatas/, vigas/)
```

Cada ejemplo de ACI 318-25 tiene su gemelo en NSR-10 con los mismos datos; solo cambian el perfil y el nivel sísmico
equivalente (`ordinary` ↔ DMI, `intermediate` ↔ DMO, `special` ↔ DES), para poder comparar resultados (D-073).

Las salidas van a `results/`, con la misma estructura de carpetas y una carpeta con el nombre de cada ejemplo; la curva
costo–N del diseño por tipologías va en `<ejemplo>_curva`. `results/` es salida generada: Git solo guarda sus carpetas
vacías. `run` sobre una carpeta corre todos sus ejemplos y salta las `pruebas/`; para correr una copia congelada se pide
esa carpeta (los comandos están en cada `LEEME.md`).

| Carpeta | Instructivo |
| --- | --- |
| `aci_318_25/cabezales` | [LEEME.md](aci_318_25/cabezales/LEEME.md) |
| `aci_318_25/zapatas` | [LEEME.md](aci_318_25/zapatas/LEEME.md) |
| `aci_318_25/vigas` | [LEEME.md](aci_318_25/vigas/LEEME.md) |
| `nsr_10/cabezales` | [LEEME.md](nsr_10/cabezales/LEEME.md) |
| `nsr_10/zapatas` | [LEEME.md](nsr_10/zapatas/LEEME.md) |
| `nsr_10/vigas` | [LEEME.md](nsr_10/vigas/LEEME.md) |
| `etabs/cabezales` | [LEEME.md](etabs/cabezales/LEEME.md) (Excel compartidos) |
| `etabs/zapatas` | [LEEME.md](etabs/zapatas/LEEME.md) (Excel compartidos) |
| `etabs/vigas` | [LEEME.md](etabs/vigas/LEEME.md) (Excel compartido) |
