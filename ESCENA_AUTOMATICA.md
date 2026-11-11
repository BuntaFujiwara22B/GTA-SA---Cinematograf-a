# Propuesta automática de escena

`preparar_calles.py` lee los NODES*.DAT del GTA instalado y guarda 24 segmentos peatonales conectados en assets/rutas_calles.json: ocho por ciudad principal. Excluye nodos apagados, acuáticos o interiores, y limita distancia y desnivel. No inventa coordenadas a partir del aspecto de un mapa. El formato se contrastó con [CPathNode del Plugin SDK](https://github.com/DK22Pac/plugin-sdk/blob/master/plugin_sa/game_sa/CPathNode.h) y [el cargador de rutas de gta-reversed](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/PathFind.cpp).

Gemini recibe el mapa real usado por la interfaz junto con los candidatos y puede seleccionar un ID válido. Si no está disponible, el respaldo local elige un segmento por ciudad mencionada y duración. Las alturas se contrastan con los tiles del mapa; un desacuerdo superior a tres metros impide aplicar la propuesta. La conectividad peatonal no garantiza ausencia de obstáculos, modificaciones del mapa ni espacio para todo el grupo: se conserva la comprobación individual de rutas en GTA y la opción explícita de generar sin ella.

La interfaz rellena automáticamente los dos marcadores para las rutas y permite cambiarlos. Nadar y escaleras siguen necesitando ubicaciones apropiadas marcadas por el usuario.

El exportador de la interfaz activa adaptar_camara. El seguimiento trasero mantiene modo 6 ligado al actor principal, ajustando distancia al reparto; los estilos elevada y costado mantienen modo 3, calculando posición y objetivo para abarcar el grupo y recorrido. La toma inicial se coloca en el encuadre calculado sin enlazar a un actor todavía no creado. Los ejemplos y fotografías son referencias de estilo. Las colisiones de cámara y el resultado visual requieren probarse en GTA.

Si se pide lluvia, atardecer u otro ambiente, se rellenan las barras con las sugerencias del plan. Si no se pide ambiente, el validador descarta sugerencias inventadas y la interfaz reinicia a una vista neutra (12, clima 0) para la elección manual; confirmar sigue siendo obligatorio. No se reutiliza por accidente el ambiente de una escena anterior.

Verificación: 42 pruebas automáticas. Se comprobaron además las alturas reales de propuestas en Los Santos y San Fierro. No se ejecutaron estas nuevas escenas dentro de GTA.
