# Copia congelada para las pruebas

Copia de los ejemplos de la carpeta de arriba que leen las pruebas, las huellas (`tests/fingerprints.json`) y la CI
(D-098). No se usa para iterar: para probar parámetros se cambian los archivos de la carpeta de arriba. Cambia solo con
un cambio de cálculo o de formato registrado en `docs/decisions.md`, con su huella actualizada.

Mientras la fase A del muro está en construcción (D-173), cada etapa que agrega verificaciones cambia esta huella; el
cambio queda registrado en la D-173. Para correrla:

```console
structurelab-rc run examples/nsr_10/muros/voladizo/pruebas
```
