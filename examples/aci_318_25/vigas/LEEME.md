# Vigas, perfil aci-318-25

Verificación de vigas según ACI CODE-318-25. Los campos de entrada y de salida están en
[docs/formatos/vigas.md](../../../docs/formatos/vigas.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `viga_rectangular.json` | Viga rectangular: en el apoyo (z = 0) hay torsión de equilibrio (Tu ≥ φTth), con estribos cerrados #4 y dos barras #6 de torsión a media altura (role = torsion, no cuentan como As); en el centro de luz solo flexión y cortante. |
| `plantilla_vigas_etabs.json` | Plantilla de importación de ETABS (vigas B34 y B37) para el Excel compartido `examples/etabs/vigas/Element Forces - Beams.xlsx`: perfil, nivel sísmico, materiales, secciones y armado por tramos. |
| `viga_alta.json` | Viga de transferencia de gran altura (`deep_beam: true`) con la geometría del ACI MNL-17(21), volumen 2, ejemplo de puntal-tensor 1, en SI: 600 × 2300 mm, 12 #9 en dos capas y malla #5 c/200 mm en cada cara; se verifican el límite de sección y el refuerzo distribuido, y la memoria avisa que la flexión y el cortante son seccionales (D-089). |
| `viga_t.json` | Viga T con el ala en la cara superior (salientes de 350 mm a cada lado): en el apoyo (z = 0) hay torsión (Tu ≥ φTth, umbral calculado con las alas efectivas), con estribos cerrados #4 y dos barras #8 de torsión, porque Aℓ,min crece con el ala; en el centro de luz solo flexión y cortante. |

## Cómo correrlos

Un solo comando por ejemplo (D-096). Cada uno deja en `results/aci_318_25/vigas/<ejemplo>/` el `resultado.json` y las
memorias `memoria.txt` y `memoria.pdf`. La plantilla de ETABS lee su Excel de `etabs_files` (ruta relativa a la
plantilla), se importa sola y deja además el `proyecto.json` importado.

```console
structurelab-rc run examples/aci_318_25/vigas/plantilla_vigas_etabs.json
structurelab-rc run examples/aci_318_25/vigas/viga_alta.json
structurelab-rc run examples/aci_318_25/vigas/viga_rectangular.json
structurelab-rc run examples/aci_318_25/vigas/viga_t.json
```

Todos los ejemplos de esta carpeta, o los de todo el repositorio (cada uno en su carpeta de salida):

```console
structurelab-rc run examples/aci_318_25/vigas
structurelab-rc run examples
```

Los comandos de cada paso (`import-etabs`, `verify`, `report`) siguen disponibles.

## Propio de este perfil

- `profile`: `aci-318-25`; `seismic.level`: `none`, `ordinary`, `intermediate` o `special`.
- Los numerales de cada verificación (`clause`) son los de ACI CODE-318-25.
- Solo en este perfil se verifica la interacción de los cortantes V2 y V3 (ACI 318-25).
