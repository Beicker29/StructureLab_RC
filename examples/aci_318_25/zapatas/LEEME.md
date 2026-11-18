# Zapatas, perfil aci-318-25

Zapatas aisladas, combinadas y en T invertida según ACI CODE-318-25. Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

Los ejemplos van por tipología, cada una con su `LEEME.md` (ejemplos y comandos) y su copia congelada en `pruebas/`:

| Carpeta | Contenido |
| --- | --- |
| [`aislada/`](aislada/LEEME.md) | Zapatas aisladas: verificación con las cargas declaradas y desde ETABS, diseño por tipologías (D-069) y curva costo-N (D-078). |
| [`combinada/`](combinada/LEEME.md) | Zapatas combinadas rectangulares de dos columnas: verificación (D-080 a D-083) y diseño (D-107), con las cargas declaradas y desde ETABS. |
| [`t_invertida/`](t_invertida/LEEME.md) | Zapatas combinadas en T invertida de dos columnas: verificación (D-093, D-106) y diseño (D-113), desde ETABS y con las cargas declaradas. |

## Cómo correrlos

Todos los ejemplos para iterar de este elemento (salta las carpetas `pruebas/`):

```console
structurelab-rc run examples/aci_318_25/zapatas
```

Las copias congeladas de las pruebas, en orden:

```console
structurelab-rc run examples/aci_318_25/zapatas/aislada/pruebas
structurelab-rc run examples/aci_318_25/zapatas/combinada/pruebas
structurelab-rc run examples/aci_318_25/zapatas/t_invertida/pruebas
```

Los mismos pasos que hace `run`, por separado (importar de ETABS, verificar y diseñar):

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/aci_318_25/zapatas/aislada/zapata_centrica_etabs.json --output results/aci_318_25/zapatas/etabs.json
structurelab-rc report results/aci_318_25/zapatas/etabs.json --output results/aci_318_25/zapatas/etabs
structurelab-rc design-footings examples/aci_318_25/zapatas/aislada/diseno_tipologias.json --output results/aci_318_25/zapatas/diseno_tipologias
structurelab-rc typology-curve examples/aci_318_25/zapatas/aislada/diseno_tipologias.json --output results/aci_318_25/zapatas/diseno_tipologias_curva
structurelab-rc design-combined examples/aci_318_25/zapatas/combinada/diseno_combinada.json --output results/aci_318_25/zapatas/diseno_combinada
```

## Propio de este perfil

- `profile`: `aci-318-25`; `seismic.level`: `none`, `ordinary`, `intermediate` o `special`.
- Presión admisible: numeral 13.3.1.1. El contacto mínimo es un criterio del proyecto (D-052).
- Deslizamiento y volcamiento: 13.2.6.1 remite al código general; los datos del suelo y los factores de seguridad son del usuario (D-070). En estos ejemplos son **datos supuestos** (μ = 0.45, c_a = 0, Kp = 3.0, c = 0, f_p = 0.5; FS 1.5/1.1 al deslizamiento y 2.0/1.5 al volcamiento; qa aumentada 1.33 con sismo, D-079) y las combinaciones con E van marcadas `seismic`.
