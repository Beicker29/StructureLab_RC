# Zapatas, perfil nsr-10

Zapatas aisladas y combinadas según NSR-10 Título C (v3, en curso). Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_centrica.json` | Ejemplo de zapata aislada céntrica: Z1 de planta cuadrada centrada bajo una columna cuadrada con pedestal. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |
| `diseno_tipologias.json` | Diseño por tipologías (D-069): 6 columnas, 6 zapatas tipo, f'c de 21, 24.5 y 28 MPa con sus precios. |
| `plantilla_diseno_zapatas_etabs.json` | Diseño por tipologías desde los Excel compartidos de `examples/etabs/zapatas/`: cada Unique Name es una columna de 500 × 800 mm (cx × cy) con la zapata centrada; 6 tipologías y f'c de 21, 24.5 y 28 MPa. **Datos supuestos.** El diseño de los 73 apoyos tarda varios minutos. |
| `plantilla_combinadas_etabs.json` | Zapatas combinadas desde los mismos Excel (D-084): ZC-A toma de ETABS las cargas de servicio y las mayoradas de sus dos nudos y ZC-B solo las de servicio, con las mayoradas escritas en la plantilla. **Datos supuestos.** |
| `plantilla_zapatas_etabs.json` | Verificación desde los mismos Excel con tres tipos de zapata; cubre 57 de los 73 apoyos. **Dimensiones, columnas, mallas, suelo, relleno y sobrecargas supuestos.** Las combinaciones con sismo van marcadas `"seismic": true` en `load_factors`. |
| `zapata_combinada.json` | Ejemplo de zapata combinada: ZC1 rectangular de 7.0 × 2.6 m bajo dos columnas (C1 de 500 × 500 mm cerca del borde −X y C2 de 550 × 550 mm desplazada 150 mm en Y), con cargas de servicio y mayoradas, sismo en X y refuerzo transversal (band) bajo cada columna. La torsión de la viga larga queda bajo φTth (D-088). Datos ilustrativos (D-080 a D-083). |

Estado actual: se verifican la presión admisible y el contacto con el suelo (V3C) y toda la parte estructural
(V3D): flexión con las mallas, As,min, separación, franja central, altura mínima, cortante en una dirección,
punzonamiento, desarrollo de las barras, aplastamiento y pasadores. Zapatas combinadas (V3J, solo verificación): la
revisión geotécnica, la viga en la dirección larga y las franjas transversales con el código de vigas, el punzonamiento
por columna, el desarrollo, el aplastamiento y los pasadores.

## Cómo correrlos

```console
structurelab-rc verify examples/nsr_10/zapatas/zapata_centrica.json
structurelab-rc report examples/nsr_10/zapatas/zapata_centrica.json --output results/nsr_10/zapatas/zapata_centrica
structurelab-rc report examples/nsr_10/zapatas/zapata_combinada.json --output results/nsr_10/zapatas/zapata_combinada
```

Diseño por tipologías:

```console
structurelab-rc design-footings examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc report results/nsr_10/zapatas/diseno_tipologias/proyecto.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc typology-curve examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias_curva
```

Desde los Excel de ETABS (verificación y diseño):

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/plantilla_zapatas_etabs.json --output results/nsr_10/zapatas/etabs.json
structurelab-rc report results/nsr_10/zapatas/etabs.json --output results/nsr_10/zapatas/etabs
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/plantilla_combinadas_etabs.json --output results/nsr_10/zapatas/combinadas_etabs.json
structurelab-rc report results/nsr_10/zapatas/combinadas_etabs.json --output results/nsr_10/zapatas/combinadas_etabs
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/plantilla_diseno_zapatas_etabs.json --output results/nsr_10/zapatas/diseno_etabs.json
structurelab-rc design-footings results/nsr_10/zapatas/diseno_etabs.json --output results/nsr_10/zapatas/diseno_etabs
```

El diseño usa por defecto el método `milp` (D-075), que requiere `pip install structurelab-rc[opt]`; `--method dp`
usa solo la DP.

## Propio de este perfil

- `profile`: `nsr-10`; `seismic.level`: `DMI`, `DMO` o `DES`.
- Presión admisible: numeral C.15.2.2. El contacto mínimo es un criterio del proyecto (D-052).
- Deslizamiento y volcamiento: NSR-10 remite al Título H; los datos del suelo y los factores de seguridad son del usuario (D-070). En estos ejemplos son **datos supuestos** (μ = 0.45, c_a = 0, Kp = 3.0, c = 0, f_p = 0.5; FS 1.5/1.1 al deslizamiento y 2.0/1.5 al volcamiento; qa aumentada 1.33 con sismo, D-079) y las combinaciones con E van marcadas `seismic`.
