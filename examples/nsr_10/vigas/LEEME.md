# Vigas, perfil nsr-10

Verificación de vigas según NSR-10 Título C. Los campos de entrada y de salida están en
[docs/formatos/vigas.md](../../../docs/formatos/vigas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `viga_rectangular.json` | Viga rectangular: en el apoyo (z = 0) hay torsión de equilibrio (Tu ≥ φTth), con estribos cerrados #4 y dos barras #6 de torsión a media altura (role = torsion, no cuentan como As); en el centro de luz solo flexión y cortante. |
| `plantilla_vigas_etabs.json` | Plantilla de importación de ETABS (vigas B34 y B37) para el Excel compartido `examples/etabs/vigas/Element Forces - Beams.xlsx`: perfil, nivel sísmico, materiales, secciones y armado por tramos. |
| `viga_t.json` | Viga T con el ala en la cara superior (salientes de 350 mm a cada lado): en el apoyo (z = 0) hay torsión (Tu ≥ φTth, umbral calculado con las alas efectivas), con estribos cerrados #4 y dos barras #8 de torsión, porque Aℓ,min crece con el ala; en el centro de luz solo flexión y cortante. |

## Cómo correrlos

```console
structurelab-rc verify examples/nsr_10/vigas/viga_t.json
structurelab-rc report examples/nsr_10/vigas/viga_t.json --output results/nsr_10/vigas/viga_t
structurelab-rc import-etabs "examples/etabs/vigas/Element Forces - Beams.xlsx" examples/nsr_10/vigas/plantilla_vigas_etabs.json --output results/nsr_10/vigas/etabs.json
structurelab-rc report results/nsr_10/vigas/etabs.json --output results/nsr_10/vigas/etabs
```

## Propio de este perfil

- `profile`: `nsr-10`; `seismic.level`: `DMI`, `DMO` o `DES`.
- Los numerales de cada verificación (`clause`) son los de NSR-10 Título C.
- NSR-10 no tiene interacción de los cortantes V2 y V3: cada dirección se verifica por separado (D-046).
