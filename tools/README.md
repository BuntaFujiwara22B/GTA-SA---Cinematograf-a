# Herramientas

Ejecuta los módulos desde la raíz del proyecto. Los comandos que consumen API o
modifican imágenes deben ejecutarse con las opciones y claves de su guía.

| Uso | Comando o módulo |
| --- | --- |
| Comprobar Gemini | `python -m tools.diagnostico_api` |
| Medir tiempos locales | `python -m tools.medir_rendimiento` |
| Revisar copias exactas de imágenes | `python -m tools.limpiar_duplicados` |
| Auditar animaciones | `python -m tools.auditar_catalogo` |
| Buscar una animación | `python -m tools.buscar_animacion --help` |
| Analizar capturas | `tools.analizar_animaciones`, `tools.analizar_noche` |
| Organizar capturas | `tools.organizar_animaciones` |
| Preparar el capturador Lua | `python -m tools.preparar_capturador_completo` |
| Importar catálogos y referencias | `tools.importar_catalogos_escena`, `tools.importar_referencias_mms` |
| Preparar lugares | `tools.preparar_calles`, `tools.preparar_ubicaciones` |
| Preparar fotografías y vistas | `tools.preparar_vistas`, `tools.preparar_vehiculos_transparentes` |
| Procesar actores | `tools.quitar_fondo_actores`, `tools.recortar_actores` |
| Preparar índices visuales | `tools.preparar_clip`, `tools.indexar_climas` |
| Analizar clima | `tools.analizar_fotos_clima` |
| Preparar conocimiento de escenas | `tools.preparar_conocimiento_escena` |
| Preparar recursos del ejecutable | `python -m tools.preparar_distribucion` |

Los scripts de captura están en `tools/moonloader/`. Para ejecutar la aplicación
principal utiliza `python main.py`. Las evaluaciones de modelos mantienen sus
entradas `comparar_llms.py`, `comparar_clasificadores.py` y `evaluar_escenas.py`.
