# Tus bandas sonoras

Después de elegir una canción y generar la escena, usa **Guardar misión completa...**, **Guardar paquete completo** o **Instalar en GTA**. Estas opciones entregan juntos el MMS, la canción de `Sounds` y, cuando corresponde, el recorrido de `Carrec`.

Para actualizar la escena que ya usas en el juego, pulsa **Guardar misión completa...** y elige su archivo, por ejemplo `modloader/SAMM(Stable)/movimiento/carro.mms`. Se conservan respaldos de los archivos reemplazados y se actualiza `mission_pack.ini` para seleccionar el nombre de misión elegido. Si GTA estaba abierto, ciérralo y vuelve a iniciarlo antes de cargar la misión.

Coloca tus archivos MP3, WAV u OGG en:

- `mistica/`: música de ambiente místico, inquietante o Backrooms.
- `feliz/`: música alegre.

La biblioteca local puede contener tus canciones; actualmente este proyecto tiene pistas añadidas por el usuario. La distribución de la aplicación no incluye automáticamente esa música personal. Puedes añadir archivos mientras el programa está abierto y pulsar **Actualizar canciones** en la última pantalla de configuración. Elige categoría y una canción concreta, o deja que el programa elija una de esa categoría al generar.

Mission Maker busca la canción en `Sounds` dentro de la carpeta de la misión seleccionada. Un archivo de texto no transporta por sí solo esa canción ni el recorrido. Por eso, cuando hay música o conducción, la pantalla de resultado muestra los archivos necesarios y oculta **Copiar contenido**; la entrega se hace mediante las opciones de misión completa.

**Guardar paquete completo** crea un ZIP con MMS, `Sounds`, `Carrec` si corresponde y `mission_pack.ini`. Extrae todo junto en una carpeta propia dentro de `modloader/SAMM(Stable)`. **Instalar en GTA** crea esa carpeta de misión. La selección del juego debe corresponder a la carpeta que acabas de guardar o instalar.

La pista se configura para empezar al inicio, con un fundido de volumen de un segundo, y repetirse durante la escena. Estos campos corresponden al cargador `GameSet.txt` de SAMM 1.87. La canción no se reinicia en cada diálogo. Su nombre exportado incluye una huella y el MMS registra `MUSIC_SHA256` para comprobar el contenido exacto. Una canción vacía o una copia que no corresponda bloquea la entrega. Los originales se conservan.

El guardado valida el paquete antes de escribir, publica los recursos antes del MMS y restaura los archivos anteriores si falla la entrega. También comprueba conflictos de identificadores CARREC en otras misiones de SAMM, porque el registro de recorridos del juego es global. Estas comprobaciones de archivos no sustituyen escuchar y reproducir la escena en GTA.

Crear cinemática random genera una escena estática con una animación compatible, uno a cuatro personajes, una ubicación de las candidatas, ambiente y cámara aleatorios. Usa una categoría con archivos si existe; de lo contrario genera sin música. Consulta el analizador para decidir la reproducción de la animación, reutilizando su caché y límites de API. Si la API no responde, conserva el criterio local identificado como tal. No instala nada en GTA automáticamente.

Cada clip tiene modo de reproducción: una_vez (Loop=0, Freeze=0), mantener (Loop=0, Freeze=1) o bucle (Loop=1, Freeze=0). Levantar las manos se ejecuta una vez y conserva la última pose; un baile o aplauso puede repetirse. La IA recibe estas opciones junto con las descripciones disponibles, y puede elegir según la escena. No se toma el sufijo _loop como prueba suficiente. Una petición explícita de repetición tiene prioridad; un gesto desconocido no se repite automáticamente. La duración de la escena se conserva aunque el gesto termine antes.
