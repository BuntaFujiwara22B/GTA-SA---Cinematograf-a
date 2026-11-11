# Vehículos y objetos de escena

Se importaron las tablas explícitas del usuario: 66 vehículos y 57 objetos, con 123 fotos presentes. `importar_catalogos_escena.py` vincula número de captura e ID, copia las imágenes a assets/vehicles y assets/objects y genera vehicles_catalogo.json y objects_catalogo.json. Las capturas originales no se modifican. Se usó la tabla pegada en la conversación, no la posición de una captura ni otros JSON antiguos con asociaciones diferentes.

El planificador recibe los dos catálogos y, para peticiones relacionadas, fotografías relevantes junto con sus IDs. Esto es contexto de consulta; no entrenamiento de pesos ni una afirmación de que Gemini haya inspeccionado las 123 imágenes. Se mantiene la caché y el descanso ante 429.

La petición «una persona camina y se sube a un auto» activa la selección visual de vehículo después del personaje. Inicio corresponde al personaje y destino al vehículo estacionado. El modelo elegido se escribe en Vehicle_1.Model. La selección se confirma antes de pasar al mapa.

El compilador usa el vehículo de referencia del usuario, con posición y orientación nuevas, y la tarea nativa de entrada como conductor: ACTION_A_1 Type=2, SPHERE_TYPE=2, SPHERE_VEH2=1, OBJ=0. La fuente local Mission Maker 1.87 (`Source/Mission/Loader/EntityCreate.txt`, bloque USERMISS_ENITY_CREATES_START_CICLE_FOR_VEH) confirma que esa configuración ejecuta enter_car as_driver. Esa tarea se encarga de aproximarse y entrar. No se promete un estilo exacto de marcha durante la aproximación hasta comprobarlo en GTA. No hay acción de ruta peatonal concurrente ni ACTION_V que mueva el coche. No se conduce después de entrar. Esta versión de entrada admite un único actor.

Las sillas, muebles y demás objetos están registrados para que la IA sepa que existen. Aún no se exporta la interacción silla-personaje: necesita calibrar posición, orientación y clip de asiento para cada modelo y comprobarlo en GTA. No debe confundirse catalogar un objeto con tener implementadas sus interacciones.

Validación: pruebas de IDs explícitos (incluidos captura 1477 → 420, 1487 → 411 y 1624 → 1704), flujo de selección de vehículo y exportación sin conducción concurrente. Se completaron 50 pruebas automáticas; el embarque y el espacio de estacionamiento requieren prueba dentro del juego.
