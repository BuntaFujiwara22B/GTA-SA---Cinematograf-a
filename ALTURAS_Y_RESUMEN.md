El aviso de desnivel procede de la comprobación local del mapa de alturas, no de Gemini ni CLIP.
En el puente del ejemplo, los extremos tienen Z=33,6 y una muestra intermedia del mapa devuelve
Z=72,2. Una imagen con una sola altura por píxel no distingue la superficie de paso de otras
estructuras que comparten sus coordenadas X/Y.

La ruta catalogada conserva la altura del puente. Esto solo se aplica si ambos extremos coinciden
con el segmento de referencia y su altura; escribir «puente» no permite saltarse la validación
de otro recorrido. La superficie sigue marcada como incierta hasta comprobarla en GTA. Un
obstáculo comunicado por GTA continúa bloqueando la exportación.

Ya no se exige una diferencia de Z menor de 15 metros. Se comprueba el desnivel respecto a la
distancia horizontal y también los cambios intermedios. Los umbrales preventivos de la aplicación
son 75% para caminar/correr, 115% para escaleras y 25% para un puente. Son heurísticas de
validación, no mediciones de la capacidad física de los personajes. Una bajada de 35 metros
en 100 metros horizontales pasa la comprobación; una pared o un corte brusco no.

Las rutas exportadas desde la interfaz incluyen puntos intermedios con sus alturas. Así, una
loma entre extremos de igual Z no se convierte en un trayecto plano. Las secuencias reparten
ese mismo perfil entre sus pasos. La comprobación de tejados descuenta la pendiente local
para no confundir una ladera uniforme con una superficie flotante.

La selección automática lleva al resumen dibujado en los bocetos: personajes, clima/hora,
ubicación, cámara y duración; el vehículo aparece cuando corresponde. Las tarjetas muestran
un icono de cambio al pasar el cursor. Pulsar la tarjeta o el icono abre su editor, y confirmar
regresa al resumen. La navegación por rueda/flechas no abre los editores sin esa decisión.
La duración se cambia en el resumen. Música y diálogos permanecen como opciones adicionales.

La captura de revisión real de Flet está en `.maintenance/resumen_escena.png`. No se hicieron
consultas a las APIs para estas pruebas ni se modificaron archivos de GTA. La comprobación
visual de la ejecución y las colisiones finales sigue realizándose dentro del juego.
