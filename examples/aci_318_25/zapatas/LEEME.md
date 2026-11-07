# Zapatas, perfil aci-318-25

Zapatas aisladas según ACI CODE-318-25 (v3, en curso). Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `zapata_aislada.json` | Ejemplo de zapatas aisladas: Z1 centrada bajo columna cuadrada con pedestal y Z2 rectangular con la columna desplazada 400 mm en X. Fuerzas en la base de la columna, ejes globales. Datos ilustrativos. |

Estado actual: se verifican la presión admisible y el contacto con el suelo (V3C), la flexión con las mallas,
As,min, separación, franja central y altura mínima (V3D.1) y el cortante en una dirección y el punzonamiento
(V3D.2). Desarrollo, aplastamiento y pasadores llegan en V3D.3 y por ahora salen `BLOCKED`.

## Cómo correrlos

```console
structurelab-rc verify examples/aci_318_25/zapatas/zapata_aislada.json
structurelab-rc report examples/aci_318_25/zapatas/zapata_aislada.json --output results/aci_318_25/zapatas/zapata_aislada
```

## Propio de este perfil

- `profile`: `aci-318-25`; `seismic.level`: `none`, `ordinary`, `intermediate` o `special`.
- Presión admisible: numeral 13.3.1.1. El contacto mínimo es un criterio del proyecto (D-052).
