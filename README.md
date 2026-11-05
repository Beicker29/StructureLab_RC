# StructureLab_RC

Herramienta de oficina para verificar, diseñar, despiezar y dibujar elementos de concreto
reforzado. La v1 cubrirá vigas con dos perfiles normativos, `aci-318-25` (ACI CODE-318-25)
y `nsr-10` (NSR-10 Título C). Cada proyecto declara un solo perfil.

**Estado:** Fase 2A, flexión de vigas. Verifica la resistencia a flexión, la deformación neta de
tracción y el acero mínimo por estación; cortante, torsión, servicio y memorias vienen en las
siguientes subfases ([hoja de ruta](docs/ROADMAP.md)).

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
```

`catalog` lista la designación, el diámetro nominal (mm), el área (mm²) y la masa (kg/m) de
las barras del catálogo.

`validate` comprueba que un proyecto en JSON sea coherente con su perfil normativo y con el
catálogo, e informa `PASS`, `INCOMPLETE` (faltan datos) o `FAIL` (entrada inválida, con código
de salida 1). No verifica la resistencia de la viga.

`verify` valida el proyecto y verifica cada estación a flexión: φMn ≥ |Mu|, la deformación neta de
tracción mínima y As,min. Muestra demanda, capacidad, estado y numeral, y sale con 1 si algo falla.

El proyecto declara su perfil y un nivel sísmico que exista en ese perfil, con una
justificación: `none`, `ordinary`, `intermediate` o `special` en `aci-318-25`, y `DMI`, `DMO` o
`DES` en `nsr-10`. Los valores normativos, como εcu y β1, salen del perfil y no se declaran.

Cada miembro declara su tipo (`beam`, `column`, `footing`, `wall` o `slab`); por ahora solo se
verifican vigas. Cada estación lleva `Pu_kN` (compresión positiva, también cuando es 0), `Mu_kNm`
(positivo con la fibra superior comprimida), `Vu_kN` y `Tu_kNm`. Una viga T con momento negativo
declara `statically_determinate`.

## Ejemplos y resultados

- `examples/<perfil>/*.json`: entradas válidas y documentadas, versionadas en Git.
  `examples/etabs/` guarda los ejemplos de importación desde ETABS.
- `results/`: salida generada, ignorada por Git. Nunca se edita a mano.

## Más información

- [Arquitectura](docs/architecture.md)
- [Decisiones y consultas abiertas](docs/decisions.md)
- [Cómo contribuir](CONTRIBUTING.md)
