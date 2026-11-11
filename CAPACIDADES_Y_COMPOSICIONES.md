El sistema consulta un registro común en `src/registro_capacidades.py`. Su copia legible está en
`assets/capacidades_compilador.json`: inventario de 1263 clips exportables, familias reconocidas,
composiciones, límites y dependencias pendientes. La presencia de un clip no demuestra que
estén preparados su objeto, soporte o combinación con otras tareas.

Gemini recibe ese registro, todo.txt, IDs y descripciones del catálogo y unas pocas capturas
reales recuperadas para cada petición. Groq recibe el registro resumido y las candidatas de
búsqueda, dentro de su límite de contexto. No se reenvían todas las fotos en cada consulta ni
se vuelve a entrenar un modelo. Las reglas locales también consultan las mismas capacidades.

Se reconoce fumar, incluidas sus conjugaciones y «furmar». La opción preferida es
`STAND:133:SMOKING:M_smk_drag`: en la captura f4 se observa una mano cerca de la boca.
Las poses M_smkstnd_loop y M_smk_loop no se eligen como sustituto automático de ese gesto.
Un ID pedido explícitamente conserva su prioridad. También se amplió la interpretación de
reír, beber, comer y hablar por teléfono; los gestos no crean automáticamente objetos o efectos.

La frase «una persona fuma en el techo de un auto de movimiento» se representa como
`accion=animacion_sobre_vehiculo`, `vehiculo_en_movimiento=true`, un actor y un clip. El MMS
contiene, por este orden lógico del cargador:

1. Vehicle_1 y ACTOR_1 creados en OBJ=0.
2. ACTION_A_1 Type=2, SPHERE_TYPE=6, SPHERE_ACTOR=1, SPHERE_VEH2=1 y T_X/Y/Z/A.
3. ACTION_A_2 Type=3, SPHERE_TYPE=0, TP=0, IFP=SMOKING y ANIM=M_smk_drag.
4. ACTION_V_1 con OBJ=0 y CARREC si se pide movimiento. Parado no incluye esta acción ni dependencia.

No se usa una tarea de entrar como conductor, una espera de entrada ni un reinicio Type=7
entre anclaje y animación. En la fuente de Mission Maker 1.87, EntityCreate carga ACTION_A
antes de ACTION_V. El handler de animación evita soltar el modo turret cuando no hay TP ni
reposición. La tarea de anclaje está en EntityCreate.txt, líneas 1940–1966 aproximadamente.

La composición sobre el techo es experimental y no se ha verificado visualmente en GTA.
Los offsets iniciales de seis sedanes están en `assets/soportes_vehiculos.json`; no son medidas
calibradas. Por eso el selector limita los modelos y el resumen indica que hay que comprobar
posición, pies y persistencia del anclaje. No se afirma que cualquier vehículo tenga un techo
utilizable. La cámara exterior sigue al coche y encuadra la altura del personaje.

El actor comienza en el techo: no se representa la acción de trepar o bajar. Se pueden ordenar
varios clips consecutivos conservando el anclaje. Fumar dentro del coche como conductor,
caminar fumando, efectos de humo y alinearse con una silla siguen teniendo dependencias
pendientes. El mensaje debe nombrar esa parte, no afirmar que fumar no existe en el mod.

La prueba real del proveedor se registra en `evaluaciones/resultado_escenas_ia.json`. La
revalidación de respuestas guardadas se marca como tal y conserva el resultado anterior.
Estas comprobaciones prueban el plan y el formato, no la ejecución física dentro de GTA.
Las pruebas locales incluyen exportación desde la interfaz, anclaje sin TP, clips, movimiento,
duración y archivos CARREC en el paquete. El corpus ampliado contiene 1305 peticiones.

Reinicia `python main.py` para usar los cambios. Los archivos de GTA no se modificaron. Para
probar la escena en movimiento, guarda o instala el paquete completo desde la interfaz; el
MMS necesita también su CARREC. La captura de revisión del resumen está en
`.maintenance/resumen_techo.png` y muestra las elecciones, no una simulación de la escena.
