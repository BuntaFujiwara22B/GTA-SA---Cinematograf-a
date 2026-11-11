# Captura completa

`tools/moonloader/animaciones_catalogo.lua` se genera ejecutando `python -m tools.preparar_capturador_completo`. La fuente es `src/todo.txt`: 1263 entradas en 14 categorias, sin cambiar sus indices. `tools/moonloader/animaciones_catalogo_lista.json` conserva ese orden con un campo `orden` global.

## Ejecutar

- Instalar como `moonloader/capturador_skins.lua`, reemplazando la prueba. No dejar otra copia `.lua` del capturador con F8 en MoonLoader.
- Reiniciar GTA, cargar partida y elegir suelo plano e iluminado con espacio libre delante. F8 inicia; F9 cancela. Mantener GTA en primer plano.
- Se solicitan seis imagenes por animacion: hasta 7578 PNG. Reservar unas 6 horas y al menos 10 GB para originales; si se conservan tambien copias organizadas, reservar unos 20 GB en total. Tiempo y espacio dependen del equipo, resolucion y fallos.
- El script no fuerza hora ni clima: cambiaran durante una tanda larga. No guardar la partida mientras captura.

## Continuar

El archivo `moonloader/animaciones_progreso_689e4f3dff34.txt` guarda indices globales que terminaron las seis solicitudes. F8, incluso tras reiniciar GTA, omite esos indices. Una animacion interrumpida se repite completa; las que fallaron se reintentan en otra ejecucion. Esto no certifica que Windows guardara todos los PNG ni que sean validos.

Cada ejecucion genera `moonloader/animaciones_catalogo_FECHA_HORA.csv`. Conservar **un CSV y una carpeta exclusiva de capturas por ejecucion**, incluidas las imagenes azules. No tomar capturas ajenas durante la tanda. No mezclar las dos pruebas anteriores. El script todavia captura mediante Windows y no nombra los PNG directamente.

Si GTA se cierra durante una captura, el PNG puede quedar sin fila en el CSV. El organizador detendra el emparejado si no coincide el numero de imagenes; revisar ese caso antes de continuar.

## Organizar cada tanda

Desde la terminal del proyecto, sustituir las rutas de ejemplo:

```powershell
python -m tools.organizar_animaciones "RUTA_AL_CSV.csv" "CARPETA_EXCLUSIVA_DE_ESTA_TANDA" "assets/animations/tanda_01"
```

El destino debe ser nuevo. Copia los originales, agrupa por categoria e indice y crea `catalogo.json`; los errores quedan en `fallos`. Comprueba cantidad y numeracion consecutiva antes de asignar por orden. El emparejado requiere no haber intercalado capturas ajenas; no es una confirmacion directa de cada guardado de Windows.

## Analisis posterior

Todavia no envia fotos a Gemini. Las fotos azules se conservan para no perder la correspondencia y deberan excluirse del analisis. La marca por tamano del organizador es solo una heuristica. Usar el nombre como pista y las poses como evidencia; si no bastan, dejar la descripcion pendiente. Las poses no representan velocidad, duracion, desplazamiento ni bucle original. Algunas animaciones necesitan parejas u objetos. El resultado sera un catalogo consultable, no un modelo entrenado automaticamente.

Validado: conteos e indices del todo.txt y sintaxis en Lua 5.1. Pendiente: ejecucion de las 1263 animaciones dentro del juego.
