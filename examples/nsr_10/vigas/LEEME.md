# Vigas, perfil nsr-10

Verificación de vigas según NSR-10 Título C. Los campos de entrada y de salida están en
[docs/formatos/vigas.md](../../../docs/formatos/vigas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `viga_rectangular.json` | Viga rectangular: en el apoyo (z = 0) hay torsión de equilibrio (Tu ≥ φTth), con estribos cerrados #4 y dos barras #6 de torsión a media altura (role = torsion, no cuentan como As); en el centro de luz solo flexión y cortante. |
| `plantilla_vigas_etabs.json` | Plantilla de importación de ETABS (vigas B34 y B37) para el Excel compartido `examples/etabs/vigas/Element Forces - Beams.xlsx`: perfil, nivel sísmico, materiales, secciones y armado por tramos. |
| `viga_alta.json` | Viga de transferencia de gran altura (`deep_beam: true`) con la geometría del ACI MNL-17(21), volumen 2, ejemplo de puntal-tensor 1, en SI: 600 × 2300 mm, 12 #9 en dos capas y malla #5 c/200 mm en cada cara; se verifican el límite de sección y el refuerzo distribuido, y la memoria avisa que la flexión y el cortante son seccionales (D-089). |
| `viga_t.json` | Viga T con el ala en la cara superior (salientes de 350 mm a cada lado): en el apoyo (z = 0) hay torsión (Tu ≥ φTth, umbral calculado con las alas efectivas), con estribos cerrados #4 y dos barras #8 de torsión, porque Aℓ,min crece con el ala; en el centro de luz solo flexión y cortante. |

## Cómo correrlos

```console
structurelab-rc verify examples/nsr_10/vigas/viga_t.json
structurelab-rc report examples/nsr_10/vigas/viga_t.json --output results/nsr_10/vigas/viga_t
structurelab-rc report examples/nsr_10/vigas/viga_alta.json --output results/nsr_10/vigas/viga_alta
structurelab-rc import-etabs "examples/etabs/vigas/Element Forces - Beams.xlsx" examples/nsr_10/vigas/plantilla_vigas_etabs.json --output results/nsr_10/vigas/etabs.json
structurelab-rc report results/nsr_10/vigas/etabs.json --output results/nsr_10/vigas/etabs
```

## Propio de este perfil

- `profile`: `nsr-10`; `seismic.level`: `DMI`, `DMO` o `DES`.
- Los numerales de cada verificación (`clause`) son los de NSR-10 Título C.
- NSR-10 no tiene interacción de los cortantes V2 y V3: cada dirección se verifica por separado (D-046).
