# Cabezales, perfil nsr-10

Cabezales sobre pilotes según NSR-10 Título C (D-138). Los campos de entrada y de salida están en
[docs/formatos/cabezales.md](../../../docs/formatos/cabezales.md). NSR-10 no fija empotramiento, borde ni tolerancia mínima: esas revisiones no aplican y la tolerancia declarada se usa igual.

| Ejemplo | Qué muestra |
| --- | --- |
| `cabezal_columna.json` | Cuatro pilotes de 400 mm bajo una columna de 500 × 500 con las fuerzas de la columna; la mala ubicación aumenta las reacciones (ΔR). Datos ilustrativos. |
| `cabezal_pilotes.json` | El mismo cabezal con la acción de cada pilote sobre el cabezal, sin el peso (`reactions_include_weight: false`). Datos ilustrativos. |
| `cabezal_tres_pilotes.json` | Tres pilotes de 400 mm en triángulo (lado 1200 mm) con las dos esquinas superiores recortadas (`clipped_corners`, D-141) y la columna en el centroide del grupo; fuerzas de la columna. Datos ilustrativos. |
| `diseno_cabezal_columna.json` | Diseño (D-141) con las fuerzas de la columna: CP1 con las cargas de `cabezal_columna` y CP2 con las de `cabezal_tres_pilotes`; el diseño elige pilotes (L = 1200 mm, E = 500 mm), espesor, mallas, pasadores y f'c de menor costo. Precios ilustrativos. |
| `diseno_cabezal_pilotes.json` | Diseño (D-141) con la acción de cada pilote de `cabezal_pilotes`: arreglo declarado; se diseña solo el cabezal. Precios ilustrativos. |
| `cabezal_dos_columnas.json` | Dos columnas de 500 × 500 a 1400 mm entre ejes sobre seis pilotes de 400 mm en malla 3 × 2 (D-143), con las fuerzas de cada columna: secciones entre columnas, franja de cada columna y punzonamiento por columna. Datos ilustrativos. |
| `cabezal_columna_etabs.json` | Desde `etabs/cabezales/columna/`: las reacciones del nudo 1600 de ETABS como fuerzas de la columna, y su ubicación en la planta de localización (`Joint Location.xlsx`). **Geometría, pilote, suelo y armado supuestos.** |
| `cabezal_pilotes_etabs.json` | Desde `etabs/cabezales/pilotes/`: los pilotes 1799 y 1725 de ETABS, en la estación 0.002 m (la cabeza); la columna del cabezal se declara con `column_unique_name` (277, supuesto). **Geometría, pilote, suelo y armado supuestos; se supone que las reacciones no incluyen el peso del cabezal.** |
| `diseno_cabezal_columna_etabs.json` | Diseño (D-141) desde `etabs/cabezales/columna/`: las reacciones del nudo 1600 como fuerzas de la columna; el diseño elige pilotes de 500 mm (L = 1500 mm, E = 750 mm) y el cabezal, ubicado con `Joint Location.xlsx`. **Pilote, suelo y precios supuestos.** |
| `diseno_cabezal_pilotes_etabs.json` | Diseño (D-141) desde `etabs/cabezales/pilotes/`: los pilotes 1799 y 1725 en la estación 0.002 m, arreglo declarado y borde de 900 mm; se diseña solo el cabezal. **Pilote, suelo y precios supuestos; se supone que las reacciones no incluyen el peso del cabezal.** |
