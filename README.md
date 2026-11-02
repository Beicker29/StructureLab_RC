# StructureLab_RC

Herramienta de oficina para verificar, diseñar, despiezar y dibujar elementos de concreto
reforzado. La v1 cubrirá vigas con dos perfiles normativos, `aci-318-25` (ACI CODE-318-25)
y `nsr-10` (NSR-10 Título C). Cada proyecto declara un solo perfil.

**Estado:** Fase 0, andamiaje. Todavía no hay fórmulas normativas ni verificación de
elementos; ver la [hoja de ruta](docs/ROADMAP.md).

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
```

`catalog` lista la designación, el diámetro nominal (mm), el área (mm²) y la masa (kg/m) de
las barras del catálogo.

## Ejemplos y resultados

- `examples/<perfil>/*.json`: entradas válidas y documentadas, versionadas en Git.
  `examples/etabs/` guarda los ejemplos de importación desde ETABS.
- `results/`: salida generada, ignorada por Git. Nunca se edita a mano.

## Más información

- [Arquitectura](docs/architecture.md)
- [Decisiones y consultas abiertas](docs/decisions.md)
- [Cómo contribuir](CONTRIBUTING.md)
