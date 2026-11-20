# Zapatas, perfil nsr-10

Zapatas aisladas, combinadas y en T invertida según NSR-10 Título C. Los campos de entrada y de salida están en
[docs/formatos/zapatas.md](../../../docs/formatos/zapatas.md).

Los ejemplos van por tipología, cada una con su `LEEME.md` (ejemplos y comandos) y su copia congelada en `pruebas/`:

| Carpeta | Contenido |
| --- | --- |
| [`aislada/`](aislada/LEEME.md) | Zapatas aisladas: verificación y diseño de zapatas céntricas, una por columna, con las cargas declaradas y desde ETABS. |
| [`tipologias/`](tipologias/LEEME.md) | Diseño por tipologías (D-069), con zapatas combinadas para los pares declarados (D-153), y curva costo-N (D-078) (D-155). |
| [`combinada/`](combinada/LEEME.md) | Zapatas combinadas rectangulares de dos columnas: verificación (D-080 a D-083) y diseño (D-107), con las cargas declaradas y desde ETABS. |
| [`t_invertida/`](t_invertida/LEEME.md) | Zapatas combinadas en T invertida de dos columnas: verificación (D-093, D-106) y diseño (D-113), desde ETABS y con las cargas declaradas. |

## Cómo correrlos

Todos los ejemplos para iterar de este elemento (salta las carpetas `pruebas/`):

```console
structurelab-rc run examples/nsr_10/zapatas
```

Las copias congeladas de las pruebas, en orden:

```console
structurelab-rc run examples/nsr_10/zapatas/aislada/pruebas
structurelab-rc run examples/nsr_10/zapatas/tipologias/pruebas
structurelab-rc run examples/nsr_10/zapatas/combinada/pruebas
structurelab-rc run examples/nsr_10/zapatas/t_invertida/pruebas
```

Los mismos pasos que hace `run`, por separado (importar de ETABS, verificar y diseñar):

```console
structurelab-rc import-etabs-footings "examples/etabs/zapatas/Joint Reactions - Servicio.xlsx" "examples/etabs/zapatas/Joint Reactions - Ultimas.xlsx" examples/nsr_10/zapatas/aislada/zapata_centrica_etabs.json --output results/nsr_10/zapatas/etabs.json
structurelab-rc report results/nsr_10/zapatas/etabs.json --output results/nsr_10/zapatas/etabs
structurelab-rc design-footings examples/nsr_10/zapatas/tipologias/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias
structurelab-rc typology-curve examples/nsr_10/zapatas/tipologias/diseno_tipologias.json --output results/nsr_10/zapatas/diseno_tipologias_curva
structurelab-rc design-combined examples/nsr_10/zapatas/combinada/diseno_combinada.json --output results/nsr_10/zapatas/diseno_combinada
```

## Propio de este perfil

- `profile`: `nsr-10`; `seismic.level`: `DMI`, `DMO` o `DES`.
- Presión admisible: numeral C.15.2.2. El contacto mínimo es un criterio del proyecto (D-052).
- Deslizamiento y volcamiento: NSR-10 remite al Título H; los datos del suelo y los factores de seguridad son del usuario (D-070). En estos ejemplos son **datos supuestos** (μ = 0.45, c_a = 0, Kp = 3.0, c = 0, f_p = 0.5; FS 1.5/1.1 al deslizamiento y 2.0/1.5 al volcamiento; qa aumentada 1.33 con sismo, D-079) y las combinaciones con E van marcadas `seismic`.
