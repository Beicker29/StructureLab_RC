# Excel de ETABS: cabezales

Tablas compartidas por los dos perfiles (D-138), **para iterar**. Las pruebas leen la copia congelada de `pruebas/` de
cada carpeta (D-098). Las plantillas están en [aci_318_25/cabezales](../../aci_318_25/cabezales/LEEME.md) y
[nsr_10/cabezales](../../nsr_10/cabezales/LEEME.md). Los campos están en
[docs/formatos/cabezales.md](../../../docs/formatos/cabezales.md).

| Archivo | Contenido |
| --- | --- |
| `columna/Joint Reactions - Servicio.xlsx`, `- Ultimas.xlsx` | Tabla "Joint Reactions" con las combinaciones de servicio y mayoradas de 91 apoyos: las cargas llegan de la columna. |
| `columna/Joint Location.xlsx` | Tabla "Point Object Connectivity" con la ubicación de las columnas (`etabs_files.locations`): el ejemplo de columna ubica su cabezal en la planta de localización. |
| `columna/Combinaciones.xlsx` | Excel de combinaciones (D-137): las 11 de las zapatas. |
| `pilotes/Joint Reactions - Servicio.xlsx`, `- Ultimas.xlsx` | Tabla "Element Forces - Columns" de los 88 elementos que modelan los pilotes (estaciones 0 y 0.002 m): las cargas llegan de cada pilote. Los dos libros traen las 16 combinaciones; el Excel de combinaciones decide de cuál se lee cada una. |
| `pilotes/Joint Location.xlsx` | Tabla "Point Object Connectivity" con la ubicación de las columnas (`etabs_files.locations`). Hoy es la misma de `columna/`: no trae las columnas del modelo de pilotes, por eso el ejemplo de pilotes no la declara. |
| `pilotes/Combinaciones.xlsx` | Excel de combinaciones de las 16 combinaciones. **Factores D y L y marca de sismo supuestos por el nombre; revisar.** |
