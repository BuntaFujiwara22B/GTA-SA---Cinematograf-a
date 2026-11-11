# Prueba de captura de animaciones

1. Copia `animaciones_prueba.lua` a `C:\Users\Danilo\Desktop\respaldo\GTA San Andreas\moonloader`.
2. Abre `gta_sa.exe` y carga una partida. Deja cerrado el menu del mod.
3. Colocate en un terreno plano, abierto y bien iluminado, con ocho metros libres delante.
4. Pulsa **F8** una vez y deja el juego en primer plano. **F9** cancela.
5. La prueba solicita hasta **60 capturas** (10 animaciones por 6 poses). Cuenta con unos tres minutos, segun las cargas y el equipo.

Para comparar con la primera tanda que produjo capturas azules, usa modo ventana desde las opciones del juego o tu configuracion habitual, si esta disponible. Esta revision reafirma la camara en cada pose, espera 700 ms antes de capturar y 2000 ms despues de solicitar el guardado. Es una prueba para investigar el problema, no una correccion confirmada. Guarda la nueva tanda en otra carpeta para no mezclar sus 60 capturas con las anteriores.

No utiliza F10 ni modifica main.py ni los scripts existentes. No cambia la hora ni el clima. Al terminar elimina su NPC y restaura camara, HUD y radar; el HUD y radar quedan visibles. No guardar la partida durante la prueba.

## Resultados

Windows guarda las imagenes en su carpeta habitual de capturas, igual que en los capturadores anteriores. El script **no confirma que Windows haya guardado cada PNG**: comprueba que aparezcan. No hagas otras capturas durante la tanda.

En `moonloader` se guarda un archivo `animaciones_prueba_FECHA_HORA.csv` con categoria, indice original, animacion, biblioteca, fase, numero de solicitud y nombre propuesto. Se escribe y vacia a disco tras cada solicitud. Los nombres `nombre_destino` son para el futuro importador: **Windows todavia guarda sus nombres habituales**, no esos nombres.

La consola de MoonLoader (`moonloader.log`) registra los fallos de carga o reproduccion. Una animacion fallida se registra como ERROR; no se supone que todas hayan producido seis imagenes.

Se muestrean poses al 5, 23, 41, 59, 77 y 95 por ciento del ciclo, pausando la animacion mientras Windows captura. Esto es una secuencia de poses, **no un video ni una medicion de velocidad o duracion**. Se bloquea el desplazamiento horizontal del NPC para mantenerlo encuadrado. La prueba usa bucle para muestrear; no significa que la animacion original sea un bucle. Movimientos que dependan del desplazamiento, objetos o parejas necesitaran otro tratamiento en el catalogo completo.

## Si falla

- Sin mensaje al iniciar GTA: revisar `moonloader\moonloader.log`.
- Sin imagenes: probar manualmente Win + Impr Pant dentro del juego y revisar la carpeta de capturas de Windows.
- Solo una pose repetida o mal encuadrada: conservar imagenes y CSV para ajustar la prueba antes de ampliar a las 1263 animaciones.
- Para repetir desde una animacion concreta, cambiar `EMPEZAR_EN` (1 a 10), guardar y reiniciar el juego. Se crea un CSV nuevo por tanda.

El script todavia necesita una prueba real dentro de esta instalacion de GTA. No envia imagenes a Gemini ni consume cuota de API.

Referencia de opcodes: https://github.com/sannybuilder/library/blob/master/sa/sa.json (0605, 0614 y 0393).
