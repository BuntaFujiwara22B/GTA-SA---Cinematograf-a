# Asociación de capturas de clima

La planificación interpreta lluvia como clima 8 (o 16 en campo), y atardecer como hora 18 con clima despejado de respaldo; Gemini puede proponer 18 o 19 según contexto. No existe un único ID de clima de atardecer. Las sugerencias se muestran en los relojes y se pueden cambiar antes de confirmar. La confirmación conserva la combinación elegida para exportar.

`src/contexto_climas.py` incorpora fotografías reales candidatas a las consultas de Gemini, además de las descripciones visuales guardadas. `python -m tools.analizar_fotos_clima --ejecutar` intenta analizar las 1073 capturas de hora_0..hora_23 por tandas y guarda resultados reutilizables en assets/climas_analisis_visual.json. Reanuda las pendientes al repetir el comando y se detiene ante un fallo de API. En la prueba de conexión del 9 de noviembre Gemini devolvió 429 antes del primer lote: no se obtuvieron descripciones nuevas ni se afirma que haya visto todas las fotos. La selección local de lluvia y hora sigue funcionando sin esa API.

El archivo modelo_clasificador_gta.pkl cargado al iniciar es un LogisticRegression, no contiene un codificador visual CLIP y no se estaba usando para analizar fotografías. El mensaje de arranque se corrigió para reflejarlo.

Corrección contrastada con la captura del juego: hora 21, clima 19 produjo tormenta de arena. La imagen 1294 (rosada) estaba asignada incorrectamente a 19; la tormenta es la 1295. En las tandas completas se excluye ahora la primera captura y se asigna la segunda a clima 0. La foto rosada queda en 18. También se inspeccionó que las capturas 620 (hora 6), 890 (hora 12) y 1160 (hora 18) muestran la tormenta en esa misma posición corregida. Esta evidencia corrige el desplazamiento, sin equivaler a validar individualmente todos los climas y horas.

El registro de captura entregado usa GAME_WEATHER 0..44, no los índices 1..45 sugeridos por la otra guía. El programa mantiene los IDs estándar 0..22 ya admitidos por el exportador. Ahora usa ese ID directamente en el dial, el catálogo y el .mms, sin un índice interno desplazado.

Se revisó el código fuente local de Mission Maker 1.87: `Source/Mission/Loader/GameSet.txt`, etiqueta `USERMISS_WORLDSET_WEATHER`, lee GAME_WEATHER y lo pasa directamente a `set_weather`, sin restar ni sumar uno. El código fuente es evidencia del formato, no una prueba de la apariencia de cada captura ni de que el binario instalado sea idéntico.

Las carpetas 0, 1, 2, 4 y 5 contienen respectivamente 44, 41, 46, 43 y 44 fotos. Por tanto no se puede garantizar una correspondencia por la mera posición del archivo. Se conservan todos los originales.

`indexar_climas.py` genera asociaciones explícitas por hora e ID en assets/climas_catalogo.json. Las tandas completas se indexan según el orden documentado. Las primeras seis horas se comparan mediante cuantiles de color y alineación secuencial con saltos. Se usa la tanda de hora 3 como referencia nocturna, excluyendo su primera captura diurna observada durante la inspección. Eso es una hipótesis de captura previa a aplicar la ambientación, no una lectura del clima real de la foto.

Las asociaciones visuales son estimaciones, no verificaciones. El catálogo conserva la procedencia y el error de comparación. Las imágenes estimadas se muestran con esa advertencia al pasar el cursor. Cuando no hay una asociación, no se elige otra foto arbitrariamente. La alineación permite aprovechar las imágenes existentes, pero no puede demostrar por sí sola cuál era el ID real: las imágenes no contienen un registro del estado del juego.

Las tandas documentadas de hora 0 a 13 usaban minuto igual a la hora. La exportación conserva ese minuto cuando hay una captura asociada (04:04, por ejemplo); para otras horas no documentadas mantiene minuto 0. La verificación definitiva de una asociación exige contrastarla con GTA. El estado `verificado` permanece falso hasta entonces.

Pruebas automáticas: consulta exacta por hora/ID, separación entre estimación y verificación, alineación con capturas extra o ausentes y exportación de hora 0/clima 20 sin desplazamiento y de los minutos documentados. Estas pruebas no verifican visualmente el juego.
