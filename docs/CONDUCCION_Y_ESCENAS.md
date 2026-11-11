# Escenas, conducción y música

Ejemplos para la pantalla inicial:

- «Una persona baila en una calle de San Fierro al atardecer».
- «Dos personas bailan en el campo».
- «Una persona camina hasta un auto, se sube y luego conduce a 30 km/h».

También se reconoce «quiero que un personaje camine, se suba a un vehículo y ande por la cuidad»: se interpreta como subir y conducir por la ciudad. El validador conserva la intención de conducción de Gemini en lugar de reducirla a solo entrar.

Ahora el análisis prepara personajes, vehículo, ubicación y clima ya seleccionados. La interfaz abre la cámara; después puedes elegir música o dejar «Sin música». Puedes cambiar las propuestas con los botones correspondientes. Las rutas del catálogo se pueden generar con un aviso de obstáculos aún sin comprobar; una colisión detectada sí bloquea la exportación, y una edición manual vuelve a requerir comprobación o la opción explícita de omitirla.

## Lugares y recorridos

El catálogo `assets/ubicaciones_escena.json` contiene **390 lugares**: 150 de ciudad, 120 de campo, 80 de desierto y 40 de playa. Se obtuvieron de nodos peatonales reales y se filtraron con las alturas del terreno. Las escenas de animación eligen un lugar al azar, respetando el entorno y la ciudad indicada. Puedes pedir otro lugar con el botón o marcarlo en el mapa.

Hay **90 recorridos de vehículo**, obtenidos de nodos conectados de carretera y contrastados con el mapa de alturas. El programa elige uno, permite cambiarlo en la lista o busca el más próximo al punto marcado. La línea azul muestra el recorrido. El inicio deja al personaje cerca de la puerta del conductor.

Estos filtros no detectan todos los objetos, paredes ni obstáculos de mods. La comprobación opcional de GTA revisa los tramos y varias líneas laterales del coche; tampoco sustituye una prueba real con el vehículo elegido.

Para regenerar el catálogo desde otra instalación:

```powershell
python -m tools.preparar_ubicaciones --paths "C:\ruta\a\GTA San Andreas\data\Paths"
```

## Subir y conducir

Se admite un conductor y un vehículo en esta secuencia. El resto de escenas mantiene el reparto de hasta cuatro personajes.

La tarea de entrada se inicia en `OBJ=0`. El objetivo `OBJ_1`, de tipo 2 y `SPHERE_TYPE=5`, espera a que el actor esté dentro del coche. Después hay una pausa de **un segundo** en `OBJ_2`. Al completarlo se activa `ACTION_V_1` con `OBJ=2`, usando una grabación CARREC, y se aplica el encuadre de vehículo elegido. La referencia actual es `templates/vehiculo_usuario.mms`, copiada del ejemplo `movimiento/carro.mms`.

Las cámaras de coche usan modo 7 y `CUM_VEH=1`. Se conservan los offsets del ejemplo: frontal `(2.96, 5.87999, 1.32)`, desde el asiento `(-0.0399999, -0.840001, 0.52)` con zoom 112, y elevada `(0, -0.440001, 12.68)`. Los campos `CARR_*` corresponden al final real de la grabación generada. Gemini recibe el archivo de ejemplo como contexto y el contrato que aplica el exportador.

Tras la prueba en GTA se retiró la toma elevada durante la conducción: ahora se ofrece vista interior o exterior fija al coche desde atrás, a 5.92 m y 2.04 m de altura relativa. La vista exterior es la opción predeterminada para conducir. La cámara elevada sigue disponible para escenas sin vehículo.

La barra regula una velocidad objetivo entre 10 y 90 km/h. Si no se pide una, se propone al azar un valor moderado. La grabación incluye aceleración y frenado, y no usa el movimiento de puntos que el mod fuerza a velocidad 999. Si el recorrido es corto, el coche se detiene al llegar; no repite la ruta.

La duración seleccionada corresponde al plano de conducción. El acercamiento, la entrada y la pausa previa de un segundo ocurren antes. Si el personaje no logra entrar, la conducción no empieza.

Los archivos `Carrec/CARREC<id>.rrr` son necesarios: copiar solo el texto del MMS no incluye la ruta. Se generan cuadros binarios de 32 bytes con tiempos, velocidad, orientación y posición. Estructura contrastada con el grabador local de Mission Maker y [CVehicleStateEachFrame](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/VehicleRecording.h).

El identificador nuevo se calcula a partir de los bytes completos de la grabación.
`ACTION_V_1.CARREC_SHA256` permite comprobar que el MMS y el recorrido pertenecen
a la misma exportación. Además se validan el primer instante, los tiempos y las
posiciones inicial y final. Una colisión de identificador o un recorrido distinto
ya presente en el destino bloquea la entrega y conserva los archivos existentes.
La comprobación también busca ese identificador en otras misiones de la misma
instalación de SAMM, porque el registro CARREC de GTA es global.

Guardar e instalar copian las dependencias antes del MMS; el selector de guardado
no escribe el MMS por adelantado. Los archivos se publican con escritura atómica,
se conservan respaldos de los reemplazados y se restaura el estado anterior si
falla la entrega. El guardado actualiza `mission_pack.ini` para que `Current`
seleccione el MMS de destino, conservando los demás datos de un paquete existente.
La instalación reconoce `gta_sa.exe` y `gta.exe`.

SAMM 1.87 cambia temporalmente el nombre `CARREC<n>.rrr` a `CARREC<n>` sin extensión
al iniciar el mod y lo restaura al cargar una misión (`Starter.txt:MAIN_CARREC_RESET`
y `EntityCreate.txt:USERMISS_CARREC_RESTORE` del código fuente local). El validador
admite ese nombre al leer una misión existente y normaliza la entrega a `.rrr`.
Si ambas formas existen con contenidos distintos, se rechazan.

Una revisión anterior de `movimiento/carro.mms` encontró `Carrec=260487` sin el archivo
correspondiente en su carpeta de juego. La copia del proyecto sí comenzaba en
`(1596.47, 224.175, 29.35)` y duraba 22 segundos. El paquete de reparación conserva
esa escena, sustituye la referencia por el ID de contenido `768639` y reduce la
pausa de 7000 a 1000 ms. La aplicación al juego conserva una copia `.bak` del MMS.
GTA debe reiniciarse para registrar el archivo nuevo si estaba ejecutándose;
las verificaciones automáticas no sustituyen la reproducción en el juego.

La escena posterior pedía `Carrec=402368` y la canción
`UMD_-_Trashiii_Z_fdc5fbe606.mp3`, pero faltaban ambos archivos en las subcarpetas
de la misión instalada. Sus copias sí estaban en la exportación del proyecto.
Se preparó un paquete validado con los recursos de esa misma escena; no se cambian
por una ruta o canción de una misión anterior. La reproducción y el audio de esa
reparación deben comprobarse dentro de GTA.

```powershell
python reparar_mision.py --mision 'RUTA\carro.mms' --conduccion --musica
python reparar_mision.py --mision 'RUTA\carro.mms' --conduccion --musica --aplicar
```

La primera orden prepara y valida el paquete en `.maintenance/reparacion_movimiento`.
La segunda entrega la grabación correcta, la canción ya seleccionada, el MMS y el
manifiesto de la misión, conservando un respaldo. Omite `--musica` cuando la escena
no tenga una canción seleccionada.

## Cámara frontal

La opción «Giro suave por delante» prepara un movimiento corto frente al actor, manteniendo el punto de interés sobre él. Usa la transición nativa modo 1 y una duración de hasta cuatro segundos; no es una órbita continua. Al conducir, la cámara pasa a quedar vinculada al coche después de la entrada.

Los campos y la secuencia se verifican automáticamente. Falta contrastar visualmente este movimiento, la velocidad percibida y las rutas nuevas dentro de GTA; no se ha afirmado una prueba de reproducción que no se haya realizado.

## Música y entrega

El cargador de SAMM comprueba que exista `Sounds/<GAME_MUSIC>` en la misión
seleccionada; si falta, omite la reproducción. En la escena revisada el MMS pedía
la canción feliz, mientras que `Sounds` conservaba solamente una pista de una
escena anterior. El generador ya usaba los campos correctos de audio; era necesario
entregar la canción elegida junto con la misión.

Se mantienen las categorías locales:

- Código fuente: `assets/music/mistica/` y `assets/music/feliz/`.
- Ejecutable: `%LOCALAPPDATA%/MMS-Director/music/mistica/` y `music/feliz/`.

Puedes usar MP3, WAV u OGG. La biblioteca local puede contener canciones añadidas
por el usuario; las canciones personales no se incluyen automáticamente en la
distribución. La exportación asigna nombres cortos ASCII y conserva los originales.
La música se configura una vez en `OBJ_0`, sin reiniciarse en cada diálogo:
`MUSIC_START=1` es el fundido de volumen de un segundo, `MUSIC_PROGRESS=0` comienza
al inicio, `MUSIC_SPEED=1` conserva la velocidad y `MUSIC_LOOP=1` permite repetirla.
`MUSIC_SHA256` identifica los bytes de la canción entregada. El guardado rechaza
archivos ausentes, vacíos o con una huella distinta a la indicada en el MMS.

En la página del archivo generado:

- **Guardar misión completa...** permite elegir el archivo del juego, por ejemplo
  `movimiento/carro.mms`, y entrega juntos el MMS, `Sounds`, `Carrec` y
  `mission_pack.ini`. El manifiesto selecciona el nombre de destino.
- **Guardar paquete completo** incluye MMS, `Sounds`, `Carrec` y `mission_pack.ini`.
- Cuando la escena tiene recorrido o música, el visor muestra una lista de
  recursos y **Copiar contenido** queda oculto. La entrega completa evita separar
  el MMS de sus dependencias. Para escenas sin recursos externos, el texto sigue
  disponible. Copiar o editar texto por fuera de la aplicación no transfiere
  archivos adicionales; guarda o instala el paquete completo para actualizarlo.
- **Instalar en GTA** crea una carpeta independiente dentro de `modloader/SAMM(Stable)`. Usa la ruta configurada o permite elegirla. No sobrescribe las misiones anteriores. Carga esa carpeta en Mission Maker; reinicia GTA si estaba abierto para que cargue las nuevas grabaciones.

Spotify se dejó fuera de la banda sonora porque su [política para desarrolladores](https://developer.spotify.com/policy) prohíbe sincronizar las grabaciones de su plataforma con vídeo. Se continúa con los archivos locales, como alternativa solicitada.

## Comprobaciones realizadas

En una revisión anterior se añadieron pruebas para rechazar un Carrec de otra
ubicación y para comprobar la copia de auxiliares antes de copiar el MMS. Aquella
versión de `movimiento/carro.mms` pedía `Carrec=224253`; esa reparación no cubría
pegar después un MMS nuevo sin su grabación correspondiente. La regresión actual
cubre dependencias ausentes, cuadros alterados, finales distintos, nombres sin
extensión, colisiones, destinos mezclados y reparación con respaldo.

Las pruebas incluyen la conservación de la intención «camine, se suba a un
vehículo y ande por la cuidad», propuestas de Gemini, exportación con los recursos
de la escena, audio global sin reinicios por diálogo y entrega completa con
respaldo. También se comprueban conflictos globales de CARREC y restauración ante
fallos de escritura. Los recuentos y resultados actuales deben consultarse en los
informes de evaluación y en la ejecución de la suite. Estas comprobaciones no
equivalen a reproducir las escenas nuevas dentro de GTA.

## Pasos rápidos para probar una misión

1. Pulsa **Guardar misión completa...**. Dentro de la carpeta de GTA, entra en
   `modloader/SAMM(Stable)`.
2. Crea una carpeta propia, por ejemplo `MiEscena`, entra en ella y guarda el
   archivo `.mms`. El programa entrega también el recorrido y la música necesarios.
3. Cierra GTA completamente, vuelve a abrirlo y carga `MiEscena` en Mission Maker.

Si prefieres **Instalar en GTA**, selecciona la carpeta principal que contiene
`gta_sa.exe` o `gta.exe`. Ese botón crea la carpeta de la misión dentro de SAMM y
copia todos sus recursos; no se selecciona la carpeta de destino manual del paso 1.
