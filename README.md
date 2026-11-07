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
structurelab-rc validate examples/nsr_10/beam_t.json
structurelab-rc verify examples/nsr_10/beam_t.json
structurelab-rc import-etabs "examples/etabs/Element Forces - Beams.xlsx" examples/etabs/plantilla_nsr10.json --output results/etabs.json
structurelab-rc report results/etabs.json --output results/etabs
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/etabs/zapatas/plantilla_zapatas_nsr10.json --output results/zapatas.json
```

`report` verifica el proyecto y escribe en la carpeta de salida `resultado.json` (todo el detalle, en kN, kN·m, mm
y MPa), `memoria.txt` y `memoria.pdf`. La memoria resume cada miembro con la estación crítica de cada
verificación y detalla lo que no cumple; `--full` agrega todas las estaciones. El PDF requiere el extra `pdf`
(`pip install structurelab-rc[pdf]`).

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

Los materiales llevan `fc`, `fy`, `fyt` (estribos) y `concrete` (`normalweight`; el liviano aún no se
verifica). La sección lleva `cover`, el recubrimiento libre a los estribos. Cada estación declara
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
materiales, el suelo (`allowable_pressure_kPa`, `min_contact_fraction` y los pesos unitarios en kN/m³), el factor
de carga muerta de cada combinación mayorada (`dead_load_factors`) y los tipos de zapata. Cada tipo lista sus nudos
por Unique Name y declara solo dimensiones primarias (lx, ly, h, columna, relleno y pedestal) y las mallas
inferior y superior; el área, las inercias, los módulos, el núcleo central y los pesos se calculan. La reacción
de ETABS se convierte en la acción sobre la zapata: P = FZ, Vx = −FX, Vy = −FY, Mx = −MX y My = −MY. Las
verificaciones de zapatas aún no existen y el resultado es `BLOCKED`. La plantilla de ejemplo usa datos supuestos.

## Ejemplos y resultados

- `examples/<perfil>/*.json`: entradas válidas y documentadas, versionadas en Git.
  `examples/etabs/` guarda los ejemplos de importación desde ETABS.
- `results/`: salida generada, ignorada por Git. Nunca se edita a mano.

## Más información

- [Arquitectura](docs/architecture.md)
- [Decisiones y consultas abiertas](docs/decisions.md)
- [Cómo contribuir](CONTRIBUTING.md)
