# Referencias cinematográficas

Se copiaron PRUEBA1.txt y prueba2.txt a referencias_mms como archivos .mms, sin modificar los originales. importar_referencias_mms.py genera catalogo.json con objetivos, cámaras, acciones, diálogos, entidades y dependencias externas.

El catálogo clasifica los bloques por modo cine, controles bloqueados y objetivos temporizados. Excluye los objetivos jugables detectados. Es una clasificación estructural que requiere revisión en el juego, no una validación visual automática.

La IA recibe un extracto acotado de estas referencias en cada planificación. Esto aporta contexto; no entrena ni modifica los pesos de Gemini. No se envían los archivos completos ni se copian sus historias.

El casino declara versión 1.87 y aporta ejemplos de TEXT y DIAL_TIME. Hotel rush declara versión 44.2: sus funciones no se consideran compatibles automáticamente con 1.87 y sus recorridos de cámara externos no se incluyen con estos textos.

En la interfaz se pueden editar hasta seis frases, una por línea. El exportador crea objetivos de diálogo consecutivos y distribuye entre ellos la duración seleccionada, manteniendo la caminata y el tipo de cámara. Rechaza frases que no tengan suficiente tiempo de lectura. Estos diálogos nuevos deben comprobarse en GTA.

El generador permite caminar con un actor o ejecutar un clip del catálogo con hasta cuatro actores. Los acompañantes quedan en un arco frente al principal, mirando hacia él. No se resuelven animaciones de pareja sincronizadas ni objetos requeridos. Cada integrante se elige y confirma en el carrusel; las miniaturas permiten volver a editarlo. El mapa de las escenas estáticas pide una única ubicación, sin destino; la orientación inicial es hacia el norte. Las caminatas conservan dos puntos y la comprobación opcional de recorrido en GTA.

El flujo es reparto, ubicación, clima, cámara y exportación. El clima muestra dos relojes, la fotografía y Confirmar; las fotos siguen siendo referencias cuando no existe una asociación verificada de hora y clima. Duración y diálogos se ajustan en la última pantalla.

Las capturas de tipo_camara se copiaron sin modificar a assets/camaras. templates/camaras_usuario.mms conserva el ejemplo 1.87 del usuario. Se utilizan OBJ_2 para tercera persona (modo 6, ligado al actor), OBJ_3 para elevada fija y OBJ_4 para costado fijo (ambos modo 3). Se ignoran los dos primeros planos; OBJ_5 no define una cámara nueva. Los planos fijos se trasladan y orientan a la ubicación elegida; no se convierten en seguimiento lateral. El encuadre final y las colisiones de cámara requieren prueba en GTA.

El zoom del mapa se calcula alrededor del cursor y el clic aplica la transformación inversa. Los marcadores se dibujan fuera de la capa ampliada y mantienen 28 píxeles en pantalla.

El planificador recibe el catálogo técnico completo de todo.txt, las descripciones visuales disponibles y los ejemplos cinematográficos. No se envían automáticamente todas las fotografías en cada consulta. Los nombres técnicos sin descripción siguen siendo inferencias, no evidencia visual confirmada.

Las referencias no habilitan por sí solas escenas completas de casino, vehículos ni montaje automático con cambios de plano. Cada nueva mecánica necesita implementación y validación dentro de Mission Maker. Los saludos y las exportaciones nuevas aún requieren prueba en GTA.
