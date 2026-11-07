# Vigas, perfil aci-318-25

Verificación de vigas según ACI CODE-318-25. Los campos de entrada y de salida están en
[docs/formatos/vigas.md](../../../docs/formatos/vigas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `viga_rectangular.json` | Viga rectangular: en el apoyo (z = 0) hay torsión de equilibrio (Tu ≥ φTth), con estribos cerrados #4 y dos barras #6 de torsión a media altura (role = torsion, no cuentan como As); en el centro de luz solo flexión y cortante. |
| `viga_t.json` | Viga T con el ala en la cara superior (salientes de 350 mm a cada lado): en el apoyo (z = 0) hay torsión (Tu ≥ φTth, umbral calculado con las alas efectivas), con estribos cerrados #4 y dos barras #8 de torsión, porque Aℓ,min crece con el ala; en el centro de luz solo flexión y cortante. |

## Cómo correrlos

```console
structurelab-rc verify examples/aci_318_25/vigas/viga_t.json
structurelab-rc report examples/aci_318_25/vigas/viga_t.json --output results/aci_318_25/vigas/viga_t
```

## Propio de este perfil

- `profile`: `aci-318-25`; `seismic.level`: `none`, `ordinary`, `intermediate` o `special`.
- Los numerales de cada verificación (`clause`) son los de ACI CODE-318-25.
- Solo en este perfil se verifica la interacción de los cortantes V2 y V3 (ACI 318-25).
