# StructureLab_RC

Herramienta de oficina para verificar, diseñar, despiezar y dibujar elementos de concreto reforzado con dos perfiles
normativos, `aci-318-25` (ACI CODE-318-25) y `nsr-10` (NSR-10 Título C). Cada proyecto declara un solo perfil y todo su
cálculo sale de él.

- **Entrada:** un JSON por proyecto, con las fuerzas ya mayoradas (y las de servicio en cimentaciones), o una plantilla
  que las toma de los Excel exportados de ETABS. La herramienta no genera combinaciones.
- **Resultado:** cada verificación sale como `PASS`, `FAIL`, `INCOMPLETE` (faltan datos; nada se supone) o `BLOCKED`
  (falta implementación), con su demanda, su capacidad y el numeral de la norma.
- **Diseño:** propone soluciones de menor costo y las aprueba con la misma verificación; no tiene fórmulas propias.
- **Salidas:** `resultado.json` con todo el detalle, la memoria de cálculo en texto y PDF (una por elemento, con el
  resultado y el DCR máximo arriba, cada valor con su nombre, su símbolo y la referencia literal de la norma) y, si el
  proyecto lo pide, la cartilla de despiece, el `.dli` de DL-NET y los planos en DXF y SVG.

## Estado

Lo implementado hoy, en los dos perfiles; lo que falta está en la [hoja de ruta](docs/ROADMAP.md) y el porqué de cada
criterio, en [decisions.md](docs/decisions.md). Todas las salidas incluyen `resultado.json` y la memoria en texto y PDF.

| Elemento | Verificación | Diseño | Despiece y dibujo | Desde ETABS | Formato |
| --- | --- | --- | --- | --- | --- |
| Vigas (macizas, rectangulares y T) | Flexión biaxial, cortante en dos direcciones, torsión y separación por fisuración, por estación; sin servicio ni requisitos sísmicos | Pendiente | Pendiente | Sí | [vigas](docs/formatos/vigas.md) |
| Zapata aislada | Presión, contacto, estabilidad, flexión (con concreto simple), cortante, punzonamiento, desarrollo, pasadores y aplastamiento | Por tipologías (DP y MILP) y curva costo–N | Sí: cartilla, `.dli` de DL-NET, DXF, SVG y planta de localización | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| Zapata combinada de dos columnas, rectangular | Viga larga, franjas de columna, placa, punzonamiento y geotecnia | Sí, con estribos | Sí | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| T invertida de dos columnas | Viga con capas declaradas, aletas y geotecnia | Sí | Sí | Sí, verificación y diseño | [zapatas](docs/formatos/zapatas.md) |
| Cabezal sobre pilotes | Una o varias columnas: geotecnia de los pilotes, flexión por secciones, franjas de columna, cortante, punzonamiento (guía CRSI, P1 a P4 y grupos), conexión; esquinas recortadas con una columna; hasta 16 pilotes | Una columna: número y arreglo de pilotes, o solo el cabezal con los pilotes declarados | Sí | Sí, verificación y diseño | [cabezales](docs/formatos/cabezales.md) |
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

## Uso

Un comando corre un ejemplo de punta a punta, o todos los de una carpeta: reconoce si es una verificación, un diseño o
una plantilla de ETABS y deja sus salidas en `results/`, con la misma estructura de `examples/`.

```console
structurelab-rc run <ejemplo.json o carpeta>
```

`structurelab-rc --help` lista los comandos (también los de cada paso por separado: importar de ETABS, verificar,
diseñar, generar la memoria) y `structurelab-rc <comando> --help` sus argumentos. Los comandos para correr cada ejemplo
están en el `LEEME.md` de su carpeta.

## Ejemplos

En [examples/](examples/README.md), por perfil, elemento y tipología, con los mismos ejemplos y datos en los dos
perfiles. Cada carpeta tiene un `LEEME.md` con sus ejemplos y sus comandos, y una copia congelada en `pruebas/`, la que
leen las pruebas y las huellas (D-098). Los Excel de ETABS compartidos están en `examples/etabs/`. `results/` es salida
generada y no se versiona.

## Documentación

- [Formatos de entrada y salida por elemento](docs/formatos/): vigas, zapatas, cabezales, plantillas de ETABS y DL-NET.
- [Hoja de ruta](docs/ROADMAP.md): lo que falta por implementar.
- [Decisiones y consultas abiertas](docs/decisions.md): el porqué de cada criterio.
- [Arquitectura](docs/architecture.md) y [cómo contribuir](CONTRIBUTING.md).
