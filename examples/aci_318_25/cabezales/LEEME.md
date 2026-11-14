# Cabezales, perfil aci-318-25

Cabezales sobre pilotes según ACI CODE-318-25 (D-138). Los campos de entrada y de salida están en
[docs/formatos/cabezales.md](../../../docs/formatos/cabezales.md). Con ACI se revisan además el empotramiento ≥ 75 mm, el borde ≥ 100 mm y la tolerancia ≥ 75 mm (13.4.1.4 y 13.4.6.3).

| Ejemplo | Qué muestra |
| --- | --- |
| `cabezal_columna.json` | Cuatro pilotes de 400 mm bajo una columna de 500 × 500 con las fuerzas de la columna; la mala ubicación aumenta las reacciones (ΔR). Datos ilustrativos. |
| `cabezal_pilotes.json` | El mismo cabezal con la acción de cada pilote sobre el cabezal, sin el peso (`reactions_include_weight: false`). Datos ilustrativos. |
| `cabezal_columna_etabs.json` | Desde `etabs/cabezales/columna/`: las reacciones del nudo 1600 de ETABS como fuerzas de la columna, y su ubicación en la planta de localización (`Joint Location.xlsx`). **Geometría, pilote, suelo y armado supuestos.** |
| `cabezal_pilotes_etabs.json` | Desde `etabs/cabezales/pilotes/`: los pilotes 1799 y 1725 de ETABS, en la estación 0.002 m (la cabeza). **Geometría, pilote, suelo y armado supuestos; se supone que las reacciones no incluyen el peso del cabezal.** |
