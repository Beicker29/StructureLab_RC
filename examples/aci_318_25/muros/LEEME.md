# Muros de contención, perfil aci-318-25

Muros de contención según ACI 318-25 (D-173): la pantalla del voladizo es una losa en una dirección (13.3.6.1), con el
Vc propio de 13.3.6.1.1 y la sección crítica en la unión con la zapata (13.3.6.3). Los empujes siguen a Das
(*Principles of Foundation Engineering*, 2016, y *Principles of Geotechnical Engineering*, 2014). Los campos de entrada y
de salida están en [docs/formatos/muros.md](../../../docs/formatos/muros.md).

Los ejemplos van por tipología, cada una con su `LEEME.md` (ejemplos y comandos), los de iterar en su carpeta y su copia
congelada en `pruebas/` (D-098); los muros de gravedad irán igual en `gravedad/`:

| Carpeta | Contenido |
| --- | --- |
| [`voladizo/`](voladizo/LEEME.md) | Muro de contención en voladizo (D-173). En construcción: la fase A (verificación) avanza por etapas. |

## Cómo correrlos

Todos los ejemplos para iterar de este elemento:

```console
structurelab-rc run examples/aci_318_25/muros
```

La copia congelada de las pruebas:

```console
structurelab-rc run examples/aci_318_25/muros/voladizo/pruebas
```
