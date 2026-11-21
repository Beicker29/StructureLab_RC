# Cartilla DL-NET (`.dli`, D-133)

`report` y `run` escriben `<caso>.dli` junto a la memoria, el DXF y `cartilla.csv` cuando el proyecto tiene `detailing`.
Es la cartilla del despiece en el formato de DL-NET (software de despiece de PazdelRío), que lo abre directamente para
el pedido de acero figurado. Hay un elemento DL-NET por elemento del proyecto (nombre = su `id`) y una línea por marca
de la cartilla.

El exportador (`src/structurelab_rc/io/dlnet.py`) traduce la cartilla (`detailing/schedule.py`): el mismo modelo de
despiece de las zapatas, que usarán las vigas y los demás elementos. No tiene reglas de diseño propias.

## Plantilla

El archivo se arma sobre una plantilla: un `.dli` real guardado por DL-NET, del que se copian el encabezado, las
librerías de barras y mallas y la cola. La plantilla lleva la licencia de DL-NET del usuario, así que **no se versiona**:

- por defecto, `references/dlnet/plantilla.dli` en la carpeta del proyecto o en una superior (`references/` está en
  `.gitignore`);
- o la ruta de la variable de entorno `STRUCTURELAB_DLNET_TEMPLATE`.

Sin plantilla, `run` lo avisa (`<caso>.dli no se genero: falta la plantilla DL-NET …`) y escribe lo demás. Las pruebas
que usan los archivos reales (`tests/fixtures/dlnet/n_12.dli` y `PRUEBA_StructureLab.dli`, también fuera de Git) se
saltan si no están; las demás usan una plantilla sintética.

## Formato

Deducido por ingeniería inversa de archivos guardados por DL-NET 2026 (el formato anterior, un ZIP cifrado, no se lee).

- **Registros:** `[puntero float64 LE][n uint16 LE][texto n bytes latin-1][cola 2 bytes]`.
  - `puntero = offset del registro + 12 + n + 1`: la posición, en base 1, del registro siguiente.
  - El último registro es `FINALDEARCHIVORANDOM`, sin cola, y su puntero repite el del anterior.
  - La cola de 2 bytes parece residuo de búfer (`NA`, `DE`, `RC`, `\x00\x00`…). Se conserva al leer y reescribir; en
    lo que se genera, los contadores llevan `NA` y los textos `\x00\x00`.
  - Lo que siga a `FINALDEARCHIVORANDOM` se ignora: DL-NET deja ahí el residuo del archivo anterior cuando guarda encima
    de uno más largo.
- **Orden:**
  1. encabezado (licencia, preferencias, contadores);
  2. librería de barras, entre los contadores `" 21 + 1"` y `" 26 + 0"`: una fila por barra con sus alias entre
     comillas, el primero es el nombre de DL-NET (`"5/8''"   "SR-No5"   "5"   "5/8"   "#5" …`);
  3. librería de mallas;
  4. **bloque de elementos:** `" N"` y, por elemento, su nombre, `" k"` y sus k líneas;
  5. **cola:** los grupos (`" G"` y, por grupo, nombre, marca y la pertenencia de los elementos), luego anotaciones,
     página y `FINALDEARCHIVORANDOM`.
- **Grupos:** la pertenencia lleva, por elemento, las veces que se construye: `" 1  1 "` con dos elementos de una
  unidad, `" 3 "` con uno de tres (`ESTRIBOS.dli`), vacía con ninguno. Confirmado por el usuario (D-159). Al generar, cada
  elemento es un tipo, con la cartilla de una unidad, y entra en cada grupo de la plantilla con sus N unidades.

## Líneas

Longitudes en metros, sin cero inicial ni ceros sobrantes (`0.50` → `.5`, `6.00` → `6`). La barra va con su nombre de
DL-NET, leído de la librería de la plantilla por su alias del catálogo (`#5` → `"5/8''"`). Las dimensiones son las de la
cartilla (D-147): la longitud total es el tramo horizontal más la longitud de cada gancho (L con 90°, U con 180°), a
1 cm, y DL-NET reconstruye el tramo como Ltotal − 2L o Ltotal − 2U; L y U, a 50 mm, con las fórmulas de
[zapatas](zapatas.md) (despiece).

| Forma de la cartilla | Línea DL-NET | Estado |
| --- | --- | --- |
| `recta` | `2  "5/8''"  2.2` | Verificada (`PRUEBA_StructureLab.dli`, guardado por DL-NET) |
| `L` (un gancho de 90°) | `3  "3/4''"  6.4   L.3` | Verificada (ídem) |
| `L-L` (gancho de 90° en los dos extremos) | `1  "1-1/8''"  5.8   L.5   L.5` | Verificada (`n_12.dli`) |
| `U-U` (gancho de 180°; también `U` y `L-U`) | `1  "5/8''"  5.8   U.2   U.2` | Verificada por el usuario (D-147): `U` es el gancho de 180° |
| `E`, estribo cerrado b × h, ganchos de 135° | `1  E  "3/8''"  .3*.5   G.15   F0/45` | Verificada por el usuario (`ESTRIBOS.dli`): b × h exteriores a 1 cm; `F0/45` es la figura de ganchos de 135° (`F0/90` es otra figura y no se escribe). G es la g de la cartilla y DL-NET calcula L = 2·(b + h) + 2·g, la misma longitud de la cartilla (D-160) |
| Figura G | `6  G  "3/4''"  .5   G.2/.2   F360/0` | No implementada |

Confirmado por el usuario (D-147): la longitud es la de corte, `U` es el gancho de 180° y la geometría de L y U es la de
DL-NET (tramo = Ltotal − 2L o Ltotal − 2U). También confirmado (D-133, 2026-11-21): los
`.dli` generados abren sin errores, b × h del estribo son sus dimensiones exteriores (a 1 cm, dos decimales, como la cartilla
del DXF) y la figura del estribo de 135° escribe `F0/45`. El número de la pertenencia de cada grupo es la cantidad de unidades del elemento (D-159). Una forma o un gancho que DL-NET no representa (figura G, gancho de 135° en una barra,
estribo sin ganchos de 135°, una barra fuera de la librería) es un error con la marca, nunca una salida silenciosa.
