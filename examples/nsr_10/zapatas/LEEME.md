# Zapatas, perfil nsr-10

Zapatas aisladas según NSR-10 Título C (v3, en curso). Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `diseno_tipologias.json` | Diseño por tipologías (D-069): 6 columnas, 2 zapatas tipo, f'c entre 21 y 28 MPa con sus precios. |
| `zapata_aislada.json` | Ejemplo de zapatas aisladas: Z1 centrada bajo columna cuadrada con pedestal y Z2 rectangular con la columna desplazada 400 mm en X. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |

Estado actual: se verifican la presión admisible y el contacto con el suelo (V3C) y toda la parte estructural
(V3D): flexión con las mallas, As,min, separación, franja central, altura mínima, cortante en una dirección,
punzonamiento, desarrollo de las barras, aplastamiento y pasadores.

## Cómo correrlos

```console
structurelab-rc verify examples/nsr_10/zapatas/zapata_aislada.json
structurelab-rc report examples/nsr_10/zapatas/zapata_aislada.json --output results/nsr_10/zapatas/zapata_aislada
```

Diseño por tipologías:

```console
structurelab-rc design-footings examples/nsr_10/zapatas/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc report results/nsr_10/zapatas/diseno_tipologias/proyecto.json --output results/nsr_10/zapatas/diseno_tipologias/reporte
```

## Propio de este perfil

- `profile`: `nsr-10`; `seismic.level`: `DMI`, `DMO` o `DES`.
- Presión admisible: numeral C.15.2.2. El contacto mínimo es un criterio del proyecto (D-052).
- Deslizamiento y volcamiento: NSR-10 remite al Título H; los datos del suelo y los factores de seguridad son del usuario (D-070). En estos ejemplos son **datos supuestos** (μ = 0.45, c_a = 0, Kp = 3.0, c = 0, f_p = 0.5; FS 1.5/1.1 al deslizamiento y 2.0/1.5 al volcamiento) y las combinaciones con E van marcadas `seismic`.
