# Muro de contención en voladizo, perfil nsr-10

Muro de contención en voladizo (D-173, fase A): se verifican el empuje, la estabilidad, las presiones, la pantalla y la
base (talón, puntera, longitudinal y desarrollo). La memoria del muro llega en la etapa siguiente. Con la NSR-10 el
ejemplo da FAIL solo por el refuerzo horizontal de la pantalla (C.14.3.3: fy = 413.7 MPa < 420, cuantía 0.0025). Los
campos de entrada y de salida están en [docs/formatos/muros.md](../../../../docs/formatos/muros.md).

| Ejemplo | Qué muestra |
| --- | --- |
| `muro_voladizo.json` | El ejemplo 2 del manual ACI MNL-17(21), capítulo 12, pasado a SI: relleno horizontal de 15 ft sobre el terreno final y 3 ft bajo él, pantalla de 15 in, base de 24 in, puntera de 2 ft 6 in y talón de 5 ft 6 in; empuje activo de Rankine; un caso de servicio y uno mayorado (1.2D + 1.6H, con el relleno del talón a 1.6, como el manual). |

Estos archivos son **para iterar**: se pueden cambiar libremente para probar parámetros. Las pruebas, las huellas y la CI
leen solo la copia congelada de [`pruebas/`](pruebas/LEEME.md) (D-098).

## Cómo correrlo

Deja en `results/nsr_10/muros/voladizo/muro_voladizo/` el `resultado.json` y las memorias.

```console
structurelab-rc run examples/nsr_10/muros/voladizo/muro_voladizo.json
```
