# Cabezales, perfil nsr-10

Cabezales sobre pilotes según NSR-10 Título C (D-138). Los campos de entrada y de salida están en
[docs/formatos/cabezales.md](../../../docs/formatos/cabezales.md). NSR-10 no fija empotramiento, borde ni tolerancia mínima: esas revisiones no aplican y la tolerancia declarada se usa igual.

| Ejemplo | Qué muestra |
| --- | --- |
| `cabezal_columna.json` | Cuatro pilotes de 400 mm bajo una columna de 500 × 500 con las fuerzas de la columna; la mala ubicación aumenta las reacciones (ΔR). Datos ilustrativos. |
| `cabezal_pilotes.json` | El mismo cabezal con la acción de cada pilote sobre el cabezal, sin el peso (`reactions_include_weight: false`). Datos ilustrativos. |
| `cabezal_columna_etabs.json` | Desde `etabs/cabezales/columna/`: las reacciones del nudo 1600 de ETABS como fuerzas de la columna, y su ubicación en la planta de localización (`Joint Location.xlsx`). **Geometría, pilote, suelo y armado supuestos.** |
| `cabezal_pilotes_etabs.json` | Desde `etabs/cabezales/pilotes/`: los pilotes 1799 y 1725 de ETABS, en la estación 0.002 m (la cabeza); la columna del cabezal se declara con `column_unique_name` (277, supuesto). **Geometría, pilote, suelo y armado supuestos; se supone que las reacciones no incluyen el peso del cabezal.** |
