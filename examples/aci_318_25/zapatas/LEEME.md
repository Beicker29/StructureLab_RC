# Zapatas, perfil aci-318-25

Zapatas aisladas según ACI CODE-318-25 (v3, en curso). Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `diseno_tipologias.json` | Diseño por tipologías (D-069): 6 columnas, 6 zapatas tipo, f'c de 21, 24.5 y 28 MPa con sus precios. |
| `plantilla_diseno_zapatas_etabs.json` | Diseño por tipologías desde los Excel compartidos de `examples/etabs/zapatas/`: cada Unique Name es una columna de 500 × 800 mm (cx × cy) con la zapata centrada; 6 tipologías y f'c de 21, 24.5 y 28 MPa. **Datos supuestos.** El diseño de los 73 apoyos tarda varios minutos. |
| `plantilla_zapatas_etabs.json` | Verificación desde los mismos Excel con tres tipos de zapata; cubre 57 de los 73 apoyos. **Dimensiones, columnas, mallas, suelo, relleno y sobrecargas supuestos.** Las combinaciones con sismo van marcadas `"seismic": true` en `load_factors`. |
| `zapata_aislada.json` | Ejemplo de zapatas aisladas: Z1 centrada bajo columna cuadrada con pedestal y Z2 rectangular con la columna desplazada 400 mm en X. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |

Estado actual: se verifican la presión admisible y el contacto con el suelo (V3C) y toda la parte estructural
(V3D): flexión con las mallas, As,min, separación, franja central, altura mínima, cortante en una dirección,
punzonamiento, desarrollo de las barras, aplastamiento y pasadores.

## Cómo correrlos

```console
structurelab-rc verify examples/aci_318_25/zapatas/zapata_aislada.json
structurelab-rc report examples/aci_318_25/zapatas/zapata_aislada.json --output results/aci_318_25/zapatas/zapata_aislada
```

Diseño por tipologías:

```console
structurelab-rc design-footings examples/aci_318_25/zapatas/diseno_tipologias.json --output results/aci_318_25/zapatas/diseno_tipologias
structurelab-rc report results/aci_318_25/zapatas/diseno_tipologias/proyecto.json --output results/aci_318_25/zapatas/diseno_tipologias/reporte
```

Desde los Excel de ETABS (verificación y diseño):

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/aci_318_25/zapatas/plantilla_zapatas_etabs.json --output results/aci_318_25/zapatas/etabs.json
structurelab-rc report results/aci_318_25/zapatas/etabs.json --output results/aci_318_25/zapatas/etabs
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/aci_318_25/zapatas/plantilla_diseno_zapatas_etabs.json --output results/aci_318_25/zapatas/diseno_etabs.json
structurelab-rc design-footings results/aci_318_25/zapatas/diseno_etabs.json --output results/aci_318_25/zapatas/diseno_etabs
```

El diseño usa por defecto el método `milp` (D-075), que requiere `pip install structurelab-rc[opt]`; `--method dp`
usa solo la DP.

## Propio de este perfil

- `profile`: `aci-318-25`; `seismic.level`: `none`, `ordinary`, `intermediate` o `special`.
- Presión admisible: numeral 13.3.1.1. El contacto mínimo es un criterio del proyecto (D-052).
- Deslizamiento y volcamiento: 13.2.6.1 remite al código general; los datos del suelo y los factores de seguridad son del usuario (D-070). En estos ejemplos son **datos supuestos** (μ = 0.45, c_a = 0, Kp = 3.0, c = 0, f_p = 0.5; FS 1.5/1.1 al deslizamiento y 2.0/1.5 al volcamiento) y las combinaciones con E van marcadas `seismic`.
