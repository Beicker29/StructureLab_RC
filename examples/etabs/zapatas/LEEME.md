# Excel de ETABS: zapatas

Estos Excel son **para iterar** (los leen las plantillas de la carpeta de cada perfil). Las pruebas leen la copia
congelada de [`pruebas/`](pruebas/LEEME.md) (D-098).

Tablas compartidas por los dos perfiles. Las plantillas que las leen están en la carpeta de cada perfil, con los mismos
datos: [aci_318_25/zapatas](../../aci_318_25/zapatas/LEEME.md) y [nsr_10/zapatas](../../nsr_10/zapatas/LEEME.md)
(D-073). Las columnas que se leen, la conversión de signos y los campos de la plantilla están en
[docs/formatos/etabs.md](../../../docs/formatos/etabs.md).

| Archivo | Contenido |
| --- | --- |
| `Joint Reactions - Servicio.xlsx` | Tabla "Joint Reactions" de ETABS con las combinaciones de servicio (73 apoyos en 4 niveles de cimentación). |
| `Joint Reactions - Ultimas.xlsx` | Tabla "Joint Reactions" con las combinaciones mayoradas de los mismos apoyos. |
| `Joint Location.xlsx` | Tabla "Point Object Connectivity" con las coordenadas de los nudos del modelo (1412 puntos, X e Y en m): la planta de localización (`etabs_files.locations`, D-130). |
