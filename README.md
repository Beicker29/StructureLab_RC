# StructureLab_RC

Herramienta de oficina para verificar, diseñar, despiezar y dibujar elementos de concreto
reforzado con dos perfiles normativos, `aci-318-25` (ACI CODE-318-25) y `nsr-10` (NSR-10 Título C). Cada proyecto
declara un solo perfil.

## Estado

Lo implementado hoy, en los dos perfiles; lo que falta está en la [hoja de ruta](docs/ROADMAP.md) y el porqué de cada
criterio, en [decisions.md](docs/decisions.md). Todas las salidas incluyen `resultado.json` y la memoria en texto y PDF.

| Elemento | Verificación | Diseño | Despiece y dibujo | Desde ETABS | Formato |
| --- | --- | --- | --- | --- | --- |
| Vigas (macizas, rectangulares y T) | Flexión biaxial, cortante en dos direcciones, torsión y separación por fisuración, por estación; sin servicio ni requisitos sísmicos | Pendiente | Pendiente | Sí | [vigas](docs/formatos/vigas.md) |
| Zapata aislada | Presión, contacto, estabilidad, flexión (con concreto simple), cortante, punzonamiento, desarrollo, pasadores y aplastamiento | Por tipologías (DP y MILP) y curva costo–N | Sí: cartilla, `.dli` de DL-NET, DXF, SVG y planta de localización | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| Zapata combinada de dos columnas, rectangular | Viga larga, franjas de columna, placa, punzonamiento y geotecnia | Sí, con estribos | Sí | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| T invertida de dos columnas | Viga con capas declaradas, aletas y geotecnia | Sí | Sí | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| Cabezal sobre pilotes | Una o varias columnas: geotecnia de los pilotes, flexión por secciones, franjas de columna, cortante, punzonamiento (guía CRSI, P1 a P4 y grupos), conexión; esquinas recortadas con una columna | Una columna: número y arreglo de pilotes, o solo el cabezal con los pilotes declarados | Sí | Sí, verificación y diseño | [cabezales](docs/formatos/cabezales.md) |
| Columnas, losas y muros | Pendiente | Pendiente | Pendiente | — | — |

## Instalación

Requiere Python 3.12 o superior.

```console
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux y macOS
pip install -e ".[dev]"
```

Extras opcionales: `pdf` (fpdf2) y `cad` (ezdxf).

## Uso de la CLI

Los comandos van por bloques: los comunes a todos los elementos y los propios de cabezales, zapatas y vigas. `structurelab-rc
<comando> --help` muestra los argumentos de cada uno.

### Comunes

Un solo comando por ejemplo (D-096): `run` reconoce el ejemplo por su contenido (proyecto de verificación, diseño de
zapatas, de la combinada o de cabezales, curva costo-N o plantilla de ETABS, que lee sus Excel de `etabs_files`) y deja
en `results/<perfil>/<elemento>/<ejemplo>/` el `resultado.json`, las memorias `memoria.txt` y `memoria.pdf`, las figuras
y, si el proyecto lo pide, la cartilla, el `.dli` y el DXF. Con una carpeta, corre todos sus ejemplos.

```console
structurelab-rc --version
structurelab-rc run examples/nsr_10/cabezales/cabezal_dos_columnas.json
structurelab-rc run examples
structurelab-rc report examples/nsr_10/zapatas/zapata_centrica.json --output results/nsr_10/zapatas/zapata_centrica
structurelab-rc validate examples/nsr_10/vigas/viga_t.json
structurelab-rc catalog
```

`report` verifica el proyecto y escribe en la carpeta de salida `resultado.json` (todo el detalle, en kN, kN·m, mm
y MPa), `memoria.txt` y `memoria.pdf`. Hay una memoria de cálculo por elemento (viga, zapata o cabezal), todas en el mismo
archivo, con el formato de StructureLab_HFS: el resultado y el DCR máximo arriba, capítulos fijos (materiales,
geometría, solicitaciones, requerimientos técnicos, cada revisión con su ubicación gobernante, índices DCR y notas y
limitaciones), cada valor con su nombre en palabras, su símbolo y la referencia literal de la norma. Lo que no
corresponde dice «No aplica» y lo que no está programado, «Falta implementación». `--full` agrega la tabla de todas
las ubicaciones de cada verificación. El PDF requiere el extra `pdf` (`pip install structurelab-rc[pdf]`) y usa una
fuente TrueType del sistema para los símbolos.

`validate` comprueba que un proyecto en JSON sea coherente con su perfil normativo y con el
catálogo, e informa `PASS`, `INCOMPLETE` (faltan datos) o `FAIL` (entrada inválida, con código
de salida 1). No verifica la resistencia del elemento.

`catalog` lista la designación, el diámetro nominal (mm), el área (mm²) y la masa (kg/m) de
las barras del catálogo.

El proyecto declara su perfil y un nivel sísmico que exista en ese perfil, con una
justificación: `none`, `ordinary`, `intermediate` o `special` en `aci-318-25`, y `DMI`, `DMO` o
`DES` en `nsr-10`. Los valores normativos, como εcu y β1, salen del perfil y no se declaran.

### Ejemplos de las carpetas `pruebas/`

Cada carpeta de ejemplos tiene una copia congelada en `pruebas/`, la que leen las pruebas y las huellas (D-098). `run`
sobre `examples` o sobre la carpeta de un elemento la salta; para correrla se pide esa carpeta. Cada ejemplo deja su
salida en `results/<perfil>/<elemento>/pruebas/<ejemplo>/` y al final se imprime un resumen (0: cumple; 1: no cumple o
error). En orden, por bloque y por perfil:

```console
# Cabezales
structurelab-rc run examples/aci_318_25/cabezales/pruebas
structurelab-rc run examples/nsr_10/cabezales/pruebas

# Zapatas (aislada, combinada, T invertida, diseño y curva costo-N)
structurelab-rc run examples/aci_318_25/zapatas/pruebas
structurelab-rc run examples/nsr_10/zapatas/pruebas

# Vigas
structurelab-rc run examples/aci_318_25/vigas/pruebas
structurelab-rc run examples/nsr_10/vigas/pruebas
```

Un ejemplo suelto se corre con su ruta, por ejemplo `structurelab-rc run examples/nsr_10/cabezales/pruebas/cabezal_dos_columnas.json`.
En zapatas, `diseno_tipologias_etabs.json` (73 columnas) y `curva_tipologias.json` (el diseño para cada N) tardan
minutos; `--workers N` fija los procesos en paralelo (por defecto, los núcleos del equipo). Las carpetas
`examples/etabs/<elemento>/pruebas/` solo traen los Excel que leen esas plantillas; no se corren solas.

### Cabezales

Cada ejemplo de `examples/<perfil>/cabezales/` con `run` (aquí con NSR-10; con ACI 318-25, `aci_318_25`):

```console
# Verificación con las cargas declaradas
structurelab-rc run examples/nsr_10/cabezales/cabezal_columna.json
structurelab-rc run examples/nsr_10/cabezales/cabezal_pilotes.json
structurelab-rc run examples/nsr_10/cabezales/cabezal_tres_pilotes.json
structurelab-rc run examples/nsr_10/cabezales/cabezal_dos_columnas.json
structurelab-rc run examples/nsr_10/cabezales/cabezal_cuatro_columnas.json

# Verificación desde ETABS (plantillas)
structurelab-rc run examples/nsr_10/cabezales/cabezal_columna_etabs.json
structurelab-rc run examples/nsr_10/cabezales/cabezal_pilotes_etabs.json

# Diseño (con las cargas declaradas y desde ETABS)
structurelab-rc run examples/nsr_10/cabezales/diseno_cabezal_columna.json
structurelab-rc run examples/nsr_10/cabezales/diseno_cabezal_pilotes.json
structurelab-rc run examples/nsr_10/cabezales/diseno_cabezal_columna_etabs.json
structurelab-rc run examples/nsr_10/cabezales/diseno_cabezal_pilotes_etabs.json
```

Los mismos pasos por separado:

```console
structurelab-rc import-etabs-footings "examples/etabs/cabezales/columna/Joint Reactions - Servicio.xlsx" "examples/etabs/cabezales/columna/Joint Reactions - Ultimas.xlsx" examples/nsr_10/cabezales/cabezal_columna_etabs.json --output results/nsr_10/cabezales/etabs.json
structurelab-rc report results/nsr_10/cabezales/etabs.json --output results/nsr_10/cabezales/etabs
structurelab-rc design-pile-caps examples/nsr_10/cabezales/diseno_cabezal_columna.json --output results/nsr_10/cabezales/diseno_cabezal_columna
```

Los cabezales sobre pilotes (`pile_caps`, D-138) son de una o varias columnas (D-143) y se verifican con las cargas de
las columnas o de cada pilote, declaradas o desde ETABS ("Joint Reactions", o "Element Forces - Columns" en la estación
declarada) con `import-etabs-footings` o `run` sobre su plantilla; ver [docs/formatos/cabezales.md](docs/formatos/cabezales.md).

`design-pile-caps` diseña cabezales sobre pilotes (D-141): con las cargas de la columna elige el número y el arreglo de
los pilotes (familias generadas con la separación y el borde declarados, incluido el triángulo de tres con esquinas
recortadas) y el cabezal; con las de los pilotes, solo el cabezal. Elige espesor, mallas, pasadores y f'c de menor costo
(concreto, acero y pilotes), aprobado por la verificación de cabezales. Escribe `proyecto.json` y `resumen.json`
([docs/formatos/cabezales.md](docs/formatos/cabezales.md)).

### Zapatas

Cada ejemplo de `examples/<perfil>/zapatas/` con `run` (aquí con NSR-10; con ACI 318-25, `aci_318_25`):

```console
# Verificación con las cargas declaradas
structurelab-rc run examples/nsr_10/zapatas/zapata_centrica.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada.json

# Verificación desde ETABS (plantillas); la combinada tiene una plantilla por par de columnas
structurelab-rc run examples/nsr_10/zapatas/zapata_centrica_etabs.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_A.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_BK.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_FH.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_cgl.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_j.json
structurelab-rc run examples/nsr_10/zapatas/zapata_combinada_etabs_m.json
structurelab-rc run examples/nsr_10/zapatas/zapata_t_invertida_etabs.json

# Diseño por tipologías, de la combinada y de la T invertida (con las cargas declaradas y desde ETABS)
structurelab-rc run examples/nsr_10/zapatas/diseno_tipologias.json
structurelab-rc run examples/nsr_10/zapatas/diseno_tipologias_etabs.json
structurelab-rc run examples/nsr_10/zapatas/diseno_combinada.json
structurelab-rc run examples/nsr_10/zapatas/diseno_combinada_etabs.json
structurelab-rc run examples/nsr_10/zapatas/diseno_t_invertida.json
structurelab-rc run examples/nsr_10/zapatas/diseno_t_invertida_etabs.json

# Curva costo-N
structurelab-rc run examples/nsr_10/zapatas/curva_tipologias.json
```

```console
structurelab-rc run examples/aci_318_25/zapatas/zapata_combinada_etabs.json
structurelab-rc run examples/nsr_10/zapatas/pruebas/zapata_combinada_etabs.json
```

Los mismos pasos por separado:

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/zapata_centrica_etabs.json --output results/nsr_10/zapatas/etabs.json
structurelab-rc report results/nsr_10/zapatas/etabs.json --output results/nsr_10/zapatas/etabs
structurelab-rc design-footings examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc typology-curve examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias_curva
structurelab-rc design-combined examples/nsr_10/zapatas/diseno_combinada.json --output results/nsr_10/zapatas/diseno_combinada
```

`import-etabs-footings` genera un proyecto de zapatas o de cabezales a partir de dos tablas "Joint Reactions" de
ETABS, una con las combinaciones de servicio y otra con las mayoradas, y de una plantilla con el perfil, los
materiales, el suelo (`allowable_pressure_kPa`, `min_contact_fraction`, los pesos unitarios en kN/m³ y los datos de
deslizamiento y volcamiento, D-070), un Excel de combinaciones con las que entran, su tipo, sus factores de carga muerta
y viva y si incluyen sismo (D-137), y los tipos de zapata, con sus sobrecargas
superimpuestas en kN/m². Cada tipo lista sus nudos
por Unique Name y declara solo dimensiones primarias (lx, ly, h, columna, relleno y pedestal) y las mallas
inferior y superior; el área, las inercias, los módulos, el núcleo central y los pesos se calculan. La reacción
de ETABS se convierte en la acción sobre la zapata: P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY. Con los
casos de servicio se verifican la presión admisible, el contacto mínimo y la estabilidad; con los mayorados, la revisión
estructural ([docs/formatos/zapatas.md](docs/formatos/zapatas.md)). La plantilla de ejemplo usa datos supuestos.

`design-footings` diseña zapatas por tipologías (D-069): a partir de columnas con sus casos de carga y un bloque
`design` (número de tipologías, f'c comerciales con su precio por m³, precio del acero por kg, forma en planta y
límites), encuentra las N zapatas tipo (f'c, dimensiones, mallas y pasadores por columna) de menor costo que cubren todas
las columnas. Escribe `proyecto.json`, un proyecto de verificación normal que `report` verifica y documenta, y
`tipologias.json` con el resumen. Con ETABS, `import-etabs-footings` y una plantilla que trae el bloque `design` generan
el proyecto de diseño. Por defecto (`design.method = "milp"`) una asignación óptima sobre el catálogo de la DP completa
el diseño (D-075); requiere el extra `opt` (`pip install structurelab-rc[opt]`). `--method dp` usa solo la DP.

`typology-curve` repite el diseño por tipologías para cada N y escribe la curva costo–N (JSON, CSV, SVG y memoria, D-078).

`design-combined` diseña una zapata combinada rectangular de dos columnas (D-107): ubica la base en la resultante de las
cargas de servicio D+L (con un voladizo máximo opcional en cada extremo, para columnas de lindero) y elige largo, ancho,
espesor, f'c y refuerzo (barras de la viga larga continuas, band de cada columna, mallas, piel y pasadores) de menor
costo, aprobado por la verificación de la combinada. Escribe `proyecto.json` y `resumen.json`.

#### Supuestos de las zapatas

- La presión del suelo es lineal y sin tracción bajo la zapata rígida (Bellos y Bakas, 2017).
- El empuje pasivo del deslizamiento actúa solo sobre el espesor de la zapata; el pedestal no aporta pasiva (D-092).
- No hay nivel freático: la presión, el contacto, la estabilidad y la revisión estructural se calculan sin subpresión
  ni pesos sumergidos. Su implementación está pendiente en la [hoja de ruta](docs/ROADMAP.md) (D-092).

### Vigas

Cada ejemplo de `examples/<perfil>/vigas/` con `run` (aquí con NSR-10; con ACI 318-25, `aci_318_25`):

```console
structurelab-rc run examples/nsr_10/vigas/viga_rectangular.json
structurelab-rc run examples/nsr_10/vigas/viga_t.json
structurelab-rc run examples/nsr_10/vigas/viga_alta.json
structurelab-rc run examples/nsr_10/vigas/viga_rectangular_etabs.json
```

Los mismos pasos por separado:

```console
structurelab-rc verify examples/nsr_10/vigas/viga_t.json
structurelab-rc import-etabs "examples/etabs/vigas/Element Forces - Beams.xlsx" examples/nsr_10/vigas/viga_rectangular_etabs.json --output results/nsr_10/vigas/etabs.json
structurelab-rc report results/nsr_10/vigas/etabs.json --output results/nsr_10/vigas/etabs
```

`verify` valida el proyecto y verifica cada estación a flexión biaxial (φMn ≥ |Mu| en la dirección de
(M3, M2), con la sección completa), εt mínima en tres estados (M3, M2 y biaxial) y As,min en los dos ejes;
y a cortante en las dos direcciones (V2 y V3: resistencia, límite de la sección, Av,min y separación),
con la interacción V2-V3 en ACI.
Si la torsión no es despreciable (Tu ≥ φTth), el cortante se reemplaza por la verificación combinada de
torsión: límite de la sección, refuerzo transversal, mínimo, Aℓ, separación y distribución de barras.
Muestra demanda, capacidad, estado y numeral, y sale con 1 si algo falla.

Cada miembro declara su tipo (`beam`, `column`, `footing`, `wall` o `slab`); entre los miembros solo se verifican
vigas (las zapatas y los cabezales tienen su propio bloque). Cada estación lleva `Pu_kN` (compresión positiva, también cuando es 0), `Mu_kNm`,
`M2_kNm`, `Vu_kN`, `V3_kN` y `Tu_kNm`. Una viga T con momento negativo
declara `statically_determinate`.

Los materiales llevan `fc`, `fy`, `fyt` (estribos), `concrete` (`normalweight`; el liviano aún no se
verifica) y `coating`, el recubrimiento de las barras (`uncoated`, `galvanized`, `epoxy` o `zinc_epoxy`, D-071). La sección lleva `cover`, el recubrimiento libre a los estribos. Cada estación declara
`stirrups` (`designation`, `legs`, `spacing`, `closed`), o `null` si no tiene refuerzo a cortante. Cada
capa declara `depth`, `role` (`flexure`, o `torsion` para las barras de Aℓ, que no cuentan como As) y
`bars`, en orden de x creciente: solo designaciones, como `["#8", "#6", "#8"]`, que se reparten entre las
esquinas del estribo; barras con posición, como `{"designation": "#8", "x": 62}`; o barras iguales por
separación, como `{"designation": "#4", "spacing": 200, "from": -300, "to": 600}`, útil para la malla
del ala. Las secciones con ala declaran `hf`, `overhang_x_neg` y `overhang_x_pos` (0 en el lado sin ala).

Ejes (los de ETABS): Y = eje 2 hacia arriba, X = eje 3 y Z = eje 1, a lo largo del miembro. La estación se
ubica con `z` y las barras con `x`, desde la cara del alma del lado −3. `Mu_kNm` (M3) positivo comprime la
cara superior y `M2_kNm` positivo comprime la cara +3; cada estación lleva también `V3_kN`.

`import-etabs` genera el proyecto JSON a partir de la tabla "Element Forces - Beams" exportada de ETABS
a Excel y de una plantilla con lo que ETABS no trae: perfil, nivel sísmico, materiales, secciones y armado
por tramos (`segments`, en mm desde la estación 0 de ETABS). Cada viga se identifica por su Unique Name;
se importan todas las combinaciones, o las listadas en `combinations`, y las filas Max y Min de una
envolvente se tratan como dos estados de carga. La tabla debe venir en m, kN y kN-m. El proyecto generado
se verifica después con `verify`.

## Ejemplos y resultados

- `examples/<perfil>/<elemento>/*.json` (`vigas`, `zapatas`, `cabezales`): entradas válidas y documentadas, versionadas en Git. Los dos
  perfiles tienen los mismos ejemplos con los mismos datos (solo cambian el perfil y el nivel sísmico equivalente), para
  poder comparar resultados; `<tipo>.json` trae las cargas declaradas y `<tipo>_etabs.json` es la plantilla que las toma
  de los Excel compartidos de `examples/etabs/<elemento>/` (D-073, D-098). Los archivos de cada carpeta son para iterar;
  las pruebas, las huellas y la CI leen solo la copia congelada de `pruebas/` (D-098). Cada carpeta tiene un `LEEME.md`
  con sus ejemplos y lo propio del perfil; los campos de entrada y de salida están en
  [docs/formatos/](docs/formatos/) y el índice en [examples/README.md](examples/README.md).
- `results/`: salida generada, ignorada por Git (D-121). Nunca se edita a mano; se regenera con `structurelab-rc run`.

## Más información

- [Hoja de ruta (lo que falta)](docs/ROADMAP.md)
- [Formatos de entrada y salida por elemento](docs/formatos/)
- [Arquitectura](docs/architecture.md)
- [Decisiones y consultas abiertas](docs/decisions.md)
- [Cómo contribuir](CONTRIBUTING.md)
