# StructureLab_RC

Herramienta de oficina para verificar, diseñar, despiezar y dibujar elementos de concreto
reforzado. La v1 cubrirá vigas con dos perfiles normativos, `aci-318-25` (ACI CODE-318-25)
y `nsr-10` (NSR-10 Título C). Cada proyecto declara un solo perfil.

**Estado:** Fase 2, sin la subfase de servicio (2D). Verifica vigas macizas a flexión, cortante y torsión en los
dos ejes, importa fuerzas desde ETABS y genera memorias ([hoja de ruta](docs/ROADMAP.md)).

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

```console
structurelab-rc --version
structurelab-rc catalog
structurelab-rc validate examples/nsr_10/vigas/viga_t.json
structurelab-rc verify examples/nsr_10/vigas/viga_t.json
structurelab-rc report examples/nsr_10/zapatas/zapata_centrica.json --output results/nsr_10/zapatas/zapata_centrica
structurelab-rc import-etabs "examples/etabs/vigas/Element Forces - Beams.xlsx" examples/nsr_10/vigas/plantilla_vigas_etabs.json --output results/nsr_10/vigas/etabs.json
structurelab-rc report results/nsr_10/vigas/etabs.json --output results/nsr_10/vigas/etabs
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/plantilla_zapatas_etabs.json --output results/nsr_10/zapatas/etabs.json
structurelab-rc design-footings examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc typology-curve examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias_curva
```

`report` verifica el proyecto y escribe en la carpeta de salida `resultado.json` (todo el detalle, en kN, kN·m, mm
y MPa), `memoria.txt` y `memoria.pdf`. Hay una memoria de cálculo por elemento (viga o zapata), todas en el mismo
archivo, con el formato de StructureLab_HFS: el resultado y el DCR máximo arriba, capítulos fijos (materiales,
geometría, solicitaciones, requerimientos técnicos, cada revisión con su ubicación gobernante, índices DCR y notas y
limitaciones), cada valor con su nombre en palabras, su símbolo y la referencia literal de la norma. Lo que no
corresponde dice «No aplica» y lo que no está programado, «Falta implementación». `--full` agrega la tabla de todas
las ubicaciones de cada verificación. El PDF requiere el extra `pdf` (`pip install structurelab-rc[pdf]`) y usa una
fuente TrueType del sistema para los símbolos.

`catalog` lista la designación, el diámetro nominal (mm), el área (mm²) y la masa (kg/m) de
las barras del catálogo.

`validate` comprueba que un proyecto en JSON sea coherente con su perfil normativo y con el
catálogo, e informa `PASS`, `INCOMPLETE` (faltan datos) o `FAIL` (entrada inválida, con código
de salida 1). No verifica la resistencia de la viga.

`verify` valida el proyecto y verifica cada estación a flexión biaxial (φMn ≥ |Mu| en la dirección de
(M3, M2), con la sección completa), εt mínima en tres estados (M3, M2 y biaxial) y As,min en los dos ejes;
y a cortante en las dos direcciones (V2 y V3: resistencia, límite de la sección, Av,min y separación),
con la interacción V2-V3 en ACI.
Si la torsión no es despreciable (Tu ≥ φTth), el cortante se reemplaza por la verificación combinada de
torsión: límite de la sección, refuerzo transversal, mínimo, Aℓ, separación y distribución de barras.
Muestra demanda, capacidad, estado y numeral, y sale con 1 si algo falla.

El proyecto declara su perfil y un nivel sísmico que exista en ese perfil, con una
justificación: `none`, `ordinary`, `intermediate` o `special` en `aci-318-25`, y `DMI`, `DMO` o
`DES` en `nsr-10`. Los valores normativos, como εcu y β1, salen del perfil y no se declaran.

Cada miembro declara su tipo (`beam`, `column`, `footing`, `wall` o `slab`); por ahora solo se
verifican vigas. Cada estación lleva `Pu_kN` (compresión positiva, también cuando es 0), `Mu_kNm`,
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

`import-etabs-footings` genera un proyecto de zapatas (v3, en curso) a partir de dos tablas "Joint Reactions" de
ETABS, una con las combinaciones de servicio y otra con las mayoradas, y de una plantilla con el perfil, los
materiales, el suelo (`allowable_pressure_kPa`, `min_contact_fraction`, los pesos unitarios en kN/m³ y los datos de
deslizamiento y volcamiento, D-070), los factores de carga muerta y viva de cada combinación y si incluye sismo
(`load_factors`) y los tipos de zapata, con sus sobrecargas
superimpuestas en kN/m². Cada tipo lista sus nudos
por Unique Name y declara solo dimensiones primarias (lx, ly, h, columna, relleno y pedestal) y las mallas
inferior y superior; el área, las inercias, los módulos, el núcleo central y los pesos se calculan. La reacción
de ETABS se convierte en la acción sobre la zapata: P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY. Con los
casos de servicio se verifican la presión admisible (pmax ≤ qa, presión bruta con los pesos propios) y el
contacto mínimo (D-056); la verificación estructural aún no existe y queda `BLOCKED`. La plantilla de ejemplo usa datos supuestos.

`design-footings` diseña zapatas por tipologías (D-069): a partir de columnas con sus casos de carga y un bloque
`design` (número de tipologías, f'c comerciales con su precio por m³, precio del acero por kg, forma en planta y
límites), encuentra las N zapatas tipo (f'c, dimensiones, mallas y pasadores por columna) de menor costo que cubren todas
las columnas. Escribe `proyecto.json`, un proyecto de verificación normal que `report` verifica y documenta, y
`tipologias.json` con el resumen. Con ETABS, `import-etabs-footings` y una plantilla que trae el bloque `design` generan
el proyecto de diseño. Por defecto (`design.method = "milp"`) una asignación óptima sobre el catálogo de la DP completa
el diseño (D-075); requiere el extra `opt` (`pip install structurelab-rc[opt]`). `--method dp` usa solo la DP.

## Ejemplos y resultados

- `examples/<perfil>/<elemento>/*.json` (`vigas`, `zapatas`): entradas válidas y documentadas, versionadas en Git. Los dos
  perfiles tienen los mismos ejemplos con los mismos datos (solo cambian el perfil y el nivel sísmico equivalente), para
  poder comparar resultados; las plantillas de ETABS (`plantilla_*_etabs.json`) están en la carpeta de su perfil y leen
  los Excel compartidos de `examples/etabs/<elemento>/` (D-073). Cada carpeta tiene un `LEEME.md`
  con sus ejemplos y lo propio del perfil; los campos de entrada y de salida están en
  [docs/formatos/](docs/formatos/) y el índice en [examples/README.md](examples/README.md).
- `results/`: salida generada, ignorada por Git. Nunca se edita a mano.

## Más información

- [Arquitectura](docs/architecture.md)
- [Decisiones y consultas abiertas](docs/decisions.md)
- [Cómo contribuir](CONTRIBUTING.md)
