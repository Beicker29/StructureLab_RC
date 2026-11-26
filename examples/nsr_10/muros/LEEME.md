# Muros de contención, perfil nsr-10

Muros de contención según NSR-10 Título C (D-173): la pantalla del voladizo se diseña por flexión según C.10, con el
refuerzo horizontal mínimo de C.14.3.3 (C.14.1.2). Los empujes siguen a Das (*Principles of Foundation Engineering*,
2016, y *Principles of Geotechnical Engineering*, 2014). Los campos de entrada y de salida están en
[docs/formatos/muros.md](../../../docs/formatos/muros.md).

Los ejemplos van por tipología, cada una con su `LEEME.md` (ejemplos y comandos), los de iterar en su carpeta y su copia
congelada en `pruebas/` (D-098); los muros de gravedad irán igual en `gravedad/`:

| Carpeta | Contenido |
| --- | --- |
| [`voladizo/`](voladizo/LEEME.md) | Muro de contención en voladizo (D-173). En construcción: la fase A (verificación) avanza por etapas. |

## Cómo correrlos

Todos los ejemplos para iterar de este elemento:

```console
structurelab-rc run examples/nsr_10/muros
```

La copia congelada de las pruebas:

```console
structurelab-rc run examples/nsr_10/muros/voladizo/pruebas
```
